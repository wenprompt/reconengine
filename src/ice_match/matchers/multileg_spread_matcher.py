"""Multileg spread matching implementation for Rule 9."""

from typing import Optional, Any, TypedDict
from decimal import Decimal
import logging
from collections import defaultdict
from itertools import combinations, permutations
from dataclasses import dataclass

from ...unified_recon.models.recon_status import ReconStatus
from ..models import Trade, MatchResult, MatchType
from ..core import UnmatchedPoolManager
from ..config import ConfigManager
from ..normalizers import TradeNormalizer
from .multi_leg_base_matcher import MultiLegBaseMatcher
from .spread_matcher import SpreadMatcher
from ..utils.trade_helpers import get_month_order_tuple

logger = logging.getLogger(__name__)


class TraderSpreadInfo(TypedDict):
    """Type for trader spread information."""

    earlier_leg: Trade
    later_leg: Trade
    spread_price: Decimal
    quantity: Decimal


@dataclass(frozen=True)
class ExchangeSpread:
    """Represents a validated 2-leg spread from exchange trades for efficient combination matching."""

    leg1: Trade  # Earlier month leg
    leg2: Trade  # Later month leg
    spread_price: Decimal  # leg1.price - leg2.price (earlier - later)
    spread_months: tuple[str, str]  # (earlier_month, later_month)
    dealid: Optional[str]  # DealID if from dealid grouping, None if from other grouping

    @property
    def product_name(self) -> str:
        """Product name (both legs should be same)."""
        return self.leg1.product_name

    @property
    def quantity(self) -> Decimal:
        """Quantity (both legs should be same).

        Note: Multileg spreads are always in MT units (never BBL - no brent swap spreads).
        """
        return self.leg1.quantity_mt

    @property
    def broker_group_id(self) -> Optional[int]:
        """Broker group ID (both legs should be same)."""
        return self.leg1.broker_group_id

    @property
    def exch_clearing_acct_id(self) -> Optional[int]:
        """Exchange clearing account ID (both legs should be same)."""
        return self.leg1.exch_clearing_acct_id

    @property
    def all_trades(self) -> list[Trade]:
        """Get all trades in this spread."""
        return [self.leg1, self.leg2]

    def can_net_with(self, other: "ExchangeSpread") -> bool:
        """Check if this spread can net with another spread (share one month)."""
        return (
            self.spread_months[1] == other.spread_months[0]
            or self.spread_months[0] == other.spread_months[1]
        )

    def calculate_net_spread_with(
        self, other: "ExchangeSpread"
    ) -> Optional[tuple[str, str, Decimal]]:
        """Calculate net spread when combined with another spread.

        Returns:
            Tuple of (net_start_month, net_end_month, net_price) or None if cannot net
        """
        # Case 1: self ends where other begins (A/B + B/C = A/C)
        if self.spread_months[1] == other.spread_months[0]:
            net_months = (self.spread_months[0], other.spread_months[1])
            net_price = self.spread_price + other.spread_price
            return net_months[0], net_months[1], net_price

        # Case 2: other ends where self begins (B/C + A/B = A/C)
        if other.spread_months[1] == self.spread_months[0]:
            net_months = (other.spread_months[0], self.spread_months[1])
            net_price = other.spread_price + self.spread_price
            return net_months[0], net_months[1], net_price

        return None


class MultilegSpreadMatcher(MultiLegBaseMatcher):
    """Implements Rule 9: Multileg spread matching.

    Handles scenarios where 2 trader spread trades correspond to 4+ exchange trades
    that form multiple interconnected spreads with internal netting legs.
    """

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the multileg spread matcher."""
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 10
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        logger.info(
            f"Initialized MultilegSpreadMatcher with {self.confidence}% confidence"
        )

    def get_rule_info(self) -> dict[str, Any]:
        """Get rule information for display purposes."""
        return {
            "rule_number": self.rule_number,
            "rule_name": "Multileg Spread Match",
            "match_type": MatchType.MULTILEG_SPREAD.value,
            "confidence": float(self.confidence),
            "description": "Matches 2 trader spreads against 4+ exchange trades with netting",
            "fields_matched": self.get_universal_matched_fields(["product_name"]),
            "requirements": [
                "Trader: Exactly 2 spread trades with different contract months and opposite B/S",
                "Tier 1: 4 exchange trades (3 months) with perfect internal netting",
                "Tier 2: 6 exchange trades (4 months) with flexible netting",
                "Perfect quantity matching across all trades",
                "Combined exchange spread prices must EXACTLY equal trader spread prices",
                "Same base product and broker details across all trades",
            ],
            "tiers": {
                "tier_1": {
                    "description": "4 exchange trades (3 months) with perfect internal netting",
                    "example": "Sep/Oct + Oct/Nov = Sep/Nov (Oct legs @ same price)",
                    "pattern": "A-sell, B-buy, B-sell, C-buy where B-buy price = B-sell price",
                },
                "tier_2": {
                    "description": "6 exchange trades (4 months) forming 3 consecutive spreads",
                    "example": "Aug/Sep + Sep/Oct + Oct/Nov = Aug/Nov (-2.75 + 2.25 + 4.00 = 3.50)",
                    "pattern": "A-sell, B-buy, B-sell, C-buy, C-sell, D-buy (flexible pricing)",
                },
            },
        }

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> list[MatchResult]:
        """Find all multileg spread matches."""
        logger.info("Starting multileg spread matching (Rule 9)")
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Group trader trades into potential spread pairs
        trader_spread_pairs = self._group_trader_spread_pairs(
            trader_trades, pool_manager
        )
        logger.debug(f"Found {len(trader_spread_pairs)} trader spread pairs")

        # Get available exchange trades for combination analysis
        available_exchange_trades = [
            trade
            for trade in exchange_trades
            if not pool_manager.is_trade_matched(trade)
        ]
        logger.debug(
            f"Found {len(available_exchange_trades)} available exchange trades"
        )

        for trader_pair in trader_spread_pairs:
            if any(pool_manager.is_trade_matched(trade) for trade in trader_pair):
                continue

            match_result = self._find_multileg_match(
                trader_pair, available_exchange_trades, pool_manager
            )
            if match_result:
                # Record the match to remove all involved trades from unmatched pools
                if pool_manager.record_match(match_result):
                    matches.append(match_result)
                    logger.info(f"Found multileg spread match: {match_result.match_id}")
                else:
                    logger.error(
                        f"Failed to record multileg spread match: {match_result.match_id}"
                    )

        logger.info(
            f"Completed multileg spread matching - found {len(matches)} matches"
        )
        return matches

    def _group_trader_spread_pairs(
        self, trader_trades: list[Trade], pool_manager: UnmatchedPoolManager
    ) -> list[list[Trade]]:
        """Group trader trades into spread pairs for multileg matching.

        Looks for trader spread pattern: one leg with price, one leg with price 0.00
        """
        available_trades = [
            trade for trade in trader_trades if not pool_manager.is_trade_matched(trade)
        ]

        pairs = []

        # Group by universal signature + product and quantity
        grouped_trades = defaultdict(list)
        for trade in available_trades:
            quantity_for_grouping = self._get_quantity_for_grouping(
                trade, self.normalizer
            )
            # Convert Decimal to float for consistent hashing
            key = self.create_universal_signature(
                trade,
                [
                    trade.product_name,
                    float(quantity_for_grouping)
                    if quantity_for_grouping is not None
                    else None,
                ],
            )
            grouped_trades[key].append(trade)

        # Find spread pairs within each group
        for trades_list in grouped_trades.values():
            for i, trade1 in enumerate(trades_list):
                for trade2 in trades_list[i + 1 :]:
                    if self._is_trader_spread_pair(trade1, trade2):
                        pairs.append([trade1, trade2])

        return pairs

    def _is_trader_spread_pair(self, trade1: Trade, trade2: Trade) -> bool:
        """Check if two trader trades form a valid spread pair (price + 0.00 pattern)."""
        # Must have different contract months
        if trade1.contract_month == trade2.contract_month:
            return False

        # Must have opposite B/S directions
        if trade1.buy_sell == trade2.buy_sell:
            return False

        # One must have price, other must have price 0.00
        prices = [trade1.price, trade2.price]
        if not (0 in prices and any(p != 0 for p in prices)):
            return False

        return True

    def _get_trader_spread_info(
        self, trader_pair: list[Trade]
    ) -> Optional[TraderSpreadInfo]:
        """Extract spread info from trader pair, organizing legs chronologically."""
        if len(trader_pair) != 2:
            return None

        price_trade = next((t for t in trader_pair if t.price != 0), None)
        zero_trade = next((t for t in trader_pair if t.price == 0), None)

        if not price_trade or not zero_trade:
            return None

        # Determine chronological order of trader legs
        try:
            price_month_tuple = get_month_order_tuple(
                self.normalizer.normalize_contract_month(price_trade.contract_month)
            )
            zero_month_tuple = get_month_order_tuple(
                self.normalizer.normalize_contract_month(zero_trade.contract_month)
            )
        except (ValueError, KeyError) as e:
            logger.warning(
                f"Could not determine month order for trader pair {price_trade.internal_trade_id}/{zero_trade.internal_trade_id}: {e}"
            )
            return None

        # Handle cases where a month cannot be ordered (e.g., 'Balmo')
        if not price_month_tuple or not zero_month_tuple:
            return None

        if price_month_tuple < zero_month_tuple:
            earlier_leg = price_trade
            later_leg = zero_trade
        else:
            earlier_leg = zero_trade
            later_leg = price_trade

        return {
            "earlier_leg": earlier_leg,
            "later_leg": later_leg,
            "spread_price": price_trade.price,  # Preserve sign for direction
            "quantity": self._get_quantity_for_grouping(price_trade, self.normalizer),
        }

    def _pre_identify_exchange_spreads(
        self, exchange_trades: list[Trade], pool_manager: UnmatchedPoolManager
    ) -> list[ExchangeSpread]:
        """Pre-identify valid 2-leg spreads using complete SpreadMatcher 3-tier infrastructure."""
        logger.debug(
            f"Pre-identifying exchange spreads from {len(exchange_trades)} trades"
        )

        # Create temporary SpreadMatcher to leverage complete 3-tier infrastructure
        temp_spread_matcher = SpreadMatcher(self.config_manager, self.normalizer)

        # Use the complete 3-tier sequential execution
        trade_groups, tier_counts, tier_mapping = (
            temp_spread_matcher._group_exchange_spreads(exchange_trades, pool_manager)
        )

        logger.debug(f"SpreadMatcher found spread groups across tiers: {tier_counts}")

        # Convert grouped trades to ExchangeSpread objects
        spreads = []

        for _, group_trades in trade_groups.items():
            # Each group contains validated spread pairs (should be in pairs of 2)
            for i in range(0, len(group_trades), 2):
                if i + 1 < len(group_trades):
                    trade1, trade2 = group_trades[i], group_trades[i + 1]

                    # Guard against mixed-tier pairs to avoid cross-tier contamination
                    tier1 = tier_mapping.get(trade1.internal_trade_id)
                    tier2 = tier_mapping.get(trade2.internal_trade_id)

                    if tier1 != tier2:
                        logger.debug(
                            f"Skipping mixed-tier pair: {trade1.internal_trade_id} ({tier1}) + {trade2.internal_trade_id} ({tier2})"
                        )
                        continue

                    # Verify spread pair validity using inherited validation
                    if temp_spread_matcher.validate_spread_pair_characteristics(
                        trade1, trade2, self.normalizer
                    ):
                        # Determine dealid if this spread came from Tier 1 (dealid-based)
                        dealid = None
                        if tier1 == "tier1":
                            dealid = (
                                str(trade1.raw_data.get("dealid", "")).strip() or None
                            )

                        spread = self._create_exchange_spread(trade1, trade2, dealid)
                        if spread:
                            spreads.append(spread)
                            logger.debug(
                                f"Created {tier1} ExchangeSpread: {spread.spread_months[0]}/{spread.spread_months[1]} @ {spread.spread_price}"
                            )
                    else:
                        logger.debug(
                            f"Spread validation failed for {trade1.internal_trade_id}/{trade2.internal_trade_id}"
                        )

        logger.info(
            f"Pre-identified {len(spreads)} exchange spreads for multileg matching"
        )
        return spreads

    def _create_exchange_spread(
        self, trade1: Trade, trade2: Trade, dealid: Optional[str]
    ) -> Optional[ExchangeSpread]:
        """Create ExchangeSpread object from two validated trades."""
        try:
            # Determine chronological order of months
            month1_tuple = get_month_order_tuple(
                self.normalizer.normalize_contract_month(trade1.contract_month)
            )
            month2_tuple = get_month_order_tuple(
                self.normalizer.normalize_contract_month(trade2.contract_month)
            )

            if not month1_tuple or not month2_tuple:
                return None

            # Order trades by month (earlier month first)
            if month1_tuple < month2_tuple:
                earlier_trade, later_trade = trade1, trade2
                spread_months = (trade1.contract_month, trade2.contract_month)
            else:
                earlier_trade, later_trade = trade2, trade1
                spread_months = (trade2.contract_month, trade1.contract_month)

            # Calculate spread price (earlier month price - later month price)
            spread_price = earlier_trade.price - later_trade.price

            return ExchangeSpread(
                leg1=earlier_trade,
                leg2=later_trade,
                spread_price=spread_price,
                spread_months=spread_months,
                dealid=dealid,
            )

        except (AttributeError, TypeError, ValueError, ArithmeticError) as e:
            logger.debug(
                f"Failed to create ExchangeSpread from {trade1.internal_trade_id}/{trade2.internal_trade_id}: {e}"
            )
            return None

    def _find_multileg_match(
        self,
        trader_pair: list[Trade],
        exchange_trades: list[Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[MatchResult]:
        """Find multileg spread match using optimized spread-based approach."""
        # Get trader spread info
        trader_spread_info = self._get_trader_spread_info(trader_pair)
        if not trader_spread_info:
            return None

        # Pre-identify all valid 2-leg spreads using SpreadMatcher infrastructure
        logger.debug(
            f"Pre-identifying exchange spreads from {len(exchange_trades)} trades"
        )
        exchange_spreads = self._pre_identify_exchange_spreads(
            exchange_trades, pool_manager
        )

        if len(exchange_spreads) < 2:  # Need at least 2 spreads
            logger.debug(f"Only {len(exchange_spreads)} spreads found, need at least 2")
            return None

        logger.debug(f"Found {len(exchange_spreads)} pre-identified spreads")

        # Tier 1: Try combinations of 2 spreads (A/B + B/C = A/C)
        match_result = self._find_tier1_netting_combination(
            trader_pair, trader_spread_info, exchange_spreads
        )
        if match_result:
            logger.debug("Found Tier 1 multileg spread match")
            return match_result

        # Tier 2: Try combinations of 3 spreads (A/B + B/C + C/D = A/D)
        if len(exchange_spreads) >= 3:
            match_result = self._find_tier2_netting_combination(
                trader_pair, trader_spread_info, exchange_spreads
            )
            if match_result:
                logger.debug("Found Tier 2 multileg spread match")
                return match_result

        return None

    def _find_tier1_netting_combination(
        self,
        trader_pair: list[Trade],
        trader_spread_info: TraderSpreadInfo,
        exchange_spreads: list[ExchangeSpread],
    ) -> Optional[MatchResult]:
        """Tier 1: Find 2 exchange spreads that net to match the trader spread."""
        trader_earlier_leg = trader_spread_info["earlier_leg"]
        trader_later_leg = trader_spread_info["later_leg"]
        target_price = trader_spread_info["spread_price"]
        target_quantity = trader_spread_info["quantity"]
        target_product = trader_pair[0].product_name

        # Filter spreads once for efficiency based on product and quantity
        matching_spreads = [
            spread
            for spread in exchange_spreads
            if (
                spread.product_name == target_product
                and self._get_quantity_for_grouping(spread.leg1, self.normalizer)
                == target_quantity
                and self.validate_universal_fields(spread.leg1, trader_pair[0])
            )
        ]

        logger.debug(
            f"Tier 1: Found {len(matching_spreads)} spreads with matching product/quantity/universal fields"
        )

        # Try combinations of 2 spreads (O(s^2) instead of O(n^4))
        for spread1, spread2 in combinations(matching_spreads, 2):
            # Ensure the two spreads also share universal fields between them
            if not self.validate_universal_fields(spread1.leg1, spread2.leg1):
                continue

            net_result = spread1.calculate_net_spread_with(spread2)
            if not net_result:
                continue

            _, _, net_price = net_result

            # Identify outer legs and netting legs
            outer_leg_earlier, outer_leg_later = None, None
            netting_leg1, netting_leg2 = None, None

            if spread1.spread_months[1] == spread2.spread_months[0]:  # A/B + B/C
                outer_leg_earlier, outer_leg_later = spread1.leg1, spread2.leg2
                netting_leg1, netting_leg2 = spread1.leg2, spread2.leg1
            elif spread2.spread_months[1] == spread1.spread_months[0]:  # B/C + A/B
                outer_leg_earlier, outer_leg_later = spread2.leg1, spread1.leg2
                netting_leg1, netting_leg2 = spread2.leg2, spread1.leg1
            else:
                continue  # Should not happen due to net_result check

            # --- Tier 1 Specific Validations ---
            # 1. Perfect Netting: Internal legs must have opposite B/S (prices don't need to match)
            if netting_leg1.buy_sell == netting_leg2.buy_sell:
                continue

            # 2. Outer Leg Match: Chronological legs must match month and B/S direction
            if not (
                outer_leg_earlier.contract_month == trader_earlier_leg.contract_month
                and outer_leg_earlier.buy_sell == trader_earlier_leg.buy_sell
                and outer_leg_later.contract_month == trader_later_leg.contract_month
                and outer_leg_later.buy_sell == trader_later_leg.buy_sell
            ):
                continue

            # 3. Price Match: Combined price must match trader's spread price exactly
            if net_price != target_price:
                continue

            # --- Match Found ---
            logger.debug(
                f"Found Tier 1 netting: {spread1.spread_months} + {spread2.spread_months}"
            )
            return self._create_match_result_from_spreads(
                trader_pair, [spread1, spread2]
            )

        return None

    def _find_tier2_netting_combination(
        self,
        trader_pair: list[Trade],
        trader_spread_info: TraderSpreadInfo,
        exchange_spreads: list[ExchangeSpread],
    ) -> Optional[MatchResult]:
        """Tier 2: Find 3 exchange spreads forming consecutive chain to match trader spread."""
        trader_earlier_leg = trader_spread_info["earlier_leg"]
        trader_later_leg = trader_spread_info["later_leg"]
        target_price = trader_spread_info["spread_price"]
        target_quantity = trader_spread_info["quantity"]
        target_product = trader_pair[0].product_name

        # Filter spreads once for efficiency
        matching_spreads = [
            spread
            for spread in exchange_spreads
            if (
                spread.product_name == target_product
                and self._get_quantity_for_grouping(spread.leg1, self.normalizer)
                == target_quantity
                and self.validate_universal_fields(spread.leg1, trader_pair[0])
            )
        ]

        if len(matching_spreads) < 3:
            return None

        logger.debug(
            f"Tier 2: Found {len(matching_spreads)} spreads for potential combination"
        )

        # Try combinations of 3 spreads (O(s^3) instead of O(n^6))
        for spread_combination in combinations(matching_spreads, 3):
            # Ensure all three spreads share universal fields
            if not (
                self.validate_universal_fields(
                    spread_combination[0].leg1, spread_combination[1].leg1
                )
                and self.validate_universal_fields(
                    spread_combination[0].leg1, spread_combination[2].leg1
                )
            ):
                continue

            # Validate if this combination can form the target trader spread
            if self._validate_tier2_spread_netting(
                spreads=list(spread_combination),
                trader_earlier_leg=trader_earlier_leg,
                trader_later_leg=trader_later_leg,
                target_price=target_price,
            ):
                logger.debug(
                    f"Found Tier 2 chain: {[s.spread_months for s in spread_combination]}"
                )
                return self._create_match_result_from_spreads(
                    trader_pair, list(spread_combination)
                )

        return None

    def _validate_tier2_spread_netting(
        self,
        spreads: list[ExchangeSpread],
        trader_earlier_leg: Trade,
        trader_later_leg: Trade,
        target_price: Decimal,
    ) -> bool:
        """Validate that 3 spreads form a consecutive chain that matches the target trader spread."""
        # Try all 6 possible orderings of the 3 spreads to find a valid chain
        for p in permutations(spreads):
            first, second, third = p[0], p[1], p[2]

            # Chain the first two spreads (e.g., A/B + B/C = A/C)
            intermediate_result = first.calculate_net_spread_with(second)
            if not intermediate_result:
                continue

            # Determine the outer legs of the intermediate spread
            inter_outer_earlier, inter_outer_later = None, None
            if first.spread_months[1] == second.spread_months[0]:  # A/B + B/C
                # Netting validation: B/S must be opposite for flexible netting
                if first.leg2.buy_sell == second.leg1.buy_sell:
                    continue
                inter_outer_earlier, inter_outer_later = first.leg1, second.leg2
            elif second.spread_months[1] == first.spread_months[0]:  # B/C + A/B
                # Netting validation: B/S must be opposite for flexible netting
                if second.leg2.buy_sell == first.leg1.buy_sell:
                    continue
                inter_outer_earlier, inter_outer_later = second.leg1, first.leg2
            else:
                continue

            # Chain the intermediate result with the third spread
            final_result = self._calculate_final_net_spread(
                inter_outer_earlier, inter_outer_later, intermediate_result[2], third
            )
            if not final_result:
                continue

            final_outer_earlier, final_outer_later, final_price = final_result

            # Final validation: check if the final outer legs and price match the trader spread
            if (
                final_outer_earlier.contract_month == trader_earlier_leg.contract_month
                and final_outer_earlier.buy_sell == trader_earlier_leg.buy_sell
                and final_outer_later.contract_month == trader_later_leg.contract_month
                and final_outer_later.buy_sell == trader_later_leg.buy_sell
                and final_price == target_price
            ):
                return True

        return False

    def _calculate_final_net_spread(
        self,
        inter_earlier: Trade,
        inter_later: Trade,
        inter_price: Decimal,
        third_spread: ExchangeSpread,
    ) -> Optional[tuple[Trade, Trade, Decimal]]:
        """Helper to chain an intermediate spread with a third spread."""
        # Case 1: Third spread starts where intermediate ends (A/C + C/D = A/D)
        if inter_later.contract_month == third_spread.leg1.contract_month:
            # Netting validation: B/S must be opposite
            if inter_later.buy_sell != third_spread.leg1.buy_sell:
                final_price = inter_price + third_spread.spread_price
                return inter_earlier, third_spread.leg2, final_price

        # Case 2: Third spread ends where intermediate starts (D/A + A/C = D/C)
        if inter_earlier.contract_month == third_spread.leg2.contract_month:
            # Netting validation: B/S must be opposite
            if inter_earlier.buy_sell != third_spread.leg2.buy_sell:
                final_price = third_spread.spread_price + inter_price
                return third_spread.leg1, inter_later, final_price

        return None

    def _create_match_result_from_spreads(
        self, trader_pair: list[Trade], exchange_spreads: list[ExchangeSpread]
    ) -> MatchResult:
        """Create match result from trader pair and exchange spreads."""
        # Collect all exchange trades from the spreads
        all_exchange_trades = []
        for spread in exchange_spreads:
            all_exchange_trades.extend(spread.all_trades)

        # Use first trader and first exchange trade as primary
        primary_trader = trader_pair[0]
        primary_exchange = all_exchange_trades[0]

        # Remaining trades as additional
        additional_trader = trader_pair[1:] if len(trader_pair) > 1 else []
        additional_exchange = (
            all_exchange_trades[1:] if len(all_exchange_trades) > 1 else []
        )

        match_id = self.generate_match_id(self.rule_number)

        # Only pass rule-specific fields - universal fields added automatically
        matched_fields = self.get_universal_matched_fields(["product_name", "quantity"])

        # Add spread-specific metadata - NO price tolerance
        tolerances_applied = {
            "price_matching": "EXACT - no tolerance",
            "spread_count": str(len(exchange_spreads)),
            "netting_type": f"Tier {len(exchange_spreads) - 1}"
            if len(exchange_spreads) <= 3
            else "Complex",
        }

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.MULTILEG_SPREAD,
            confidence=self.confidence,
            status=ReconStatus.MATCHED,  # ICE always returns matched status
            trader_trade=primary_trader,
            exchange_trade=primary_exchange,
            additional_trader_trades=additional_trader,
            additional_exchange_trades=additional_exchange,
            matched_fields=matched_fields,
            tolerances_applied=tolerances_applied,
            rule_order=self.rule_number,
        )
