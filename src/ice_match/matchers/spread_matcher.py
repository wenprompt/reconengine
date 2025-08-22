"""Spread matching implementation for Rule 2."""

from typing import List, Optional, Dict, Tuple
from decimal import Decimal
import logging
import uuid
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..core import UnmatchedPoolManager
from ..config import ConfigManager
from ..normalizers import TradeNormalizer
from .multi_leg_base_matcher import MultiLegBaseMatcher
from .base_matcher import UUID_LENGTH
from ..utils.trade_helpers import get_month_order_tuple

logger = logging.getLogger(__name__)


class SpreadMatcher(MultiLegBaseMatcher):
    """Implements Rule 2: Spread matching."""

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the spread matcher."""
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 2
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        logger.info(f"Initialized SpreadMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find all spread matches."""
        logger.info("Starting spread matching (Rule 2)")
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        trader_spread_groups = self._group_trader_spreads(trader_trades, pool_manager)
        exchange_spread_groups, tier_potential_counts, tier_trade_mapping = self._group_exchange_spreads(
            exchange_trades, pool_manager
        )

        # Track actual matches created from each tier
        tier_actual_matches = {"tier1": 0, "tier2": 0, "tier3": 0}

        for trader_group in trader_spread_groups:
            if any(pool_manager.is_trade_matched(trade) for trade in trader_group):
                continue

            match_result, source_tier = self._find_spread_match_with_tier_tracking(
                trader_group, exchange_spread_groups, pool_manager, tier_trade_mapping
            )
            if match_result:
                matches.append(match_result)
                if source_tier:
                    tier_actual_matches[source_tier] += 1
                
                if not pool_manager.record_match(match_result):
                    logger.error(
                        "Failed to record spread match and remove trades from pool"
                    )
                else:
                    logger.debug(f"Created spread match: {match_result} (from {source_tier})")

        # Log accurate tier breakdown based on actual matches created
        logger.info(f"Found {len(matches)} spread matches")
        logger.info(f"   📊 ACTUAL TIER BREAKDOWN: Tier 1: {tier_actual_matches['tier1']}, Tier 2: {tier_actual_matches['tier2']}, Tier 3: {tier_actual_matches['tier3']}")
        return matches

    def _group_trader_spreads(
        self, trader_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> List[List[Trade]]:
        """Group trader trades into potential spread pairs."""
        spread_groups = []
        trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        for trade in trader_trades:
            if not pool_manager.is_trade_matched(trade):
                # Use product-specific unit defaults for quantity comparison
                default_unit = self.normalizer.get_trader_product_unit_default(
                    trade.product_name
                )
                quantity_for_grouping = (
                    trade.quantity_bbl if default_unit == "bbl" else trade.quantity_mt
                )

                # Create grouping key with universal fields using BaseMatcher method
                key = self.create_universal_signature(
                    trade, [trade.product_name, quantity_for_grouping]
                )
                trade_groups[key].append(trade)

        for trades in trade_groups.values():
            if len(trades) >= 2:
                for i in range(len(trades)):
                    for j in range(i + 1, len(trades)):
                        if self._is_potential_trader_spread_pair(trades[i], trades[j]):
                            spread_groups.append([trades[i], trades[j]])
        return spread_groups

    def _is_potential_trader_spread_pair(self, trade1: Trade, trade2: Trade) -> bool:
        """Check if two trader trades could form a spread pair."""
        return (
            trade1.buy_sell != trade2.buy_sell
            and trade1.contract_month != trade2.contract_month
            and (
                (trade1.spread == "S" or trade2.spread == "S")
                or (trade1.price == 0 or trade2.price == 0)
            )
        )

    def _is_dealid_data_usable(self, exchange_trades: List[Trade]) -> bool:
        """
        Check if dealid data quality is sufficient for dealid/tradeid-based grouping.

        This method prevents attempting dealid/tradeid grouping when CSV parsing
        has corrupted the data (e.g., converting large numbers to scientific notation).

        Returns:
            bool: True if dealid data is distinct and usable, False if corrupted/identical

        Quality checks performed:
            - At least some trades have dealid values (not all empty/None)
            - Not all dealid values are identical (indicates parsing failure like 1.9E+13)
            - No scientific notation patterns detected in dealid values
            - Dealid values are reasonable length strings (not just 'nan' or similar)
        """
        # Extract dealid values from raw data, filtering out None/empty
        dealids = []
        for trade in exchange_trades:
            dealid = trade.raw_data.get("dealid")
            if dealid and str(dealid).strip() and str(dealid).lower() != "nan":
                dealids.append(str(dealid).strip())

        # Need at least some dealid values to be useful
        if len(dealids) < 2:
            logger.debug(
                "Insufficient dealid data: less than 2 valid dealid values found"
            )
            return False

        # Check if all dealids are identical (indicates parsing failure)
        unique_dealids = set(dealids)
        if len(unique_dealids) == 1:
            logger.debug(
                f"All dealids are identical ({list(unique_dealids)[0]}), indicating parsing failure"
            )
            return False

        # Check for scientific notation patterns (E+ or e+)
        scientific_notation_count = sum(
            1 for d in dealids if "E+" in d or "e+" in d or "E-" in d or "e-" in d
        )
        if scientific_notation_count > 0:
            logger.debug(
                f"Scientific notation detected in {scientific_notation_count} dealid values"
            )
            return False

        logger.debug(
            f"DealID data quality check passed: {len(unique_dealids)} unique dealids found"
        )
        return True

    def _group_exchange_spreads_by_dealid(
        self, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> Tuple[Dict[Tuple, List[Trade]], int]:
        """
        Group exchange trades using dealid/tradeid for enhanced spread detection.

        This method identifies spread pairs by looking for trades that share the same
        dealid but have different tradeids - a pattern indicating linked spread legs.

        Process:
            1. Group trades by dealid (same dealid = related trades)
            2. Within each dealid group, find pairs with different tradeids
            3. Validate each pair meets spread criteria:
               - Same product name and quantity
               - Opposite buy/sell directions
               - Different contract months
               - Same universal fields (broker, clearing account)
            4. Return validated spread groups using same key structure as fallback method

        Args:
            exchange_trades: List of unmatched exchange trades
            pool_manager: Pool manager for checking if trades are already matched

        Returns:
            Tuple of (Dict mapping group keys to lists of validated spread pairs, count of spread pairs found)

        Note:
            Uses same key structure as _group_exchange_spreads() for compatibility
            with existing _find_spread_match() logic.
        """
        trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        spread_pairs_found = 0

        # Step 1: Group trades by dealid
        dealid_groups: Dict[str, List[Trade]] = defaultdict(list)
        for trade in exchange_trades:
            if pool_manager.is_trade_matched(trade):
                continue

            # Extract dealid from raw data
            dealid = trade.raw_data.get("dealid")
            tradeid = trade.raw_data.get("tradeid")

            # Only include trades that have both dealid and tradeid
            if dealid and tradeid and str(dealid).strip() and str(tradeid).strip():
                dealid_str = str(dealid).strip()
                if dealid_str.lower() != "nan":
                    dealid_groups[dealid_str].append(trade)

        # Step 2: Within each dealid group, find valid spread pairs
        for dealid, trades_in_group in dealid_groups.items():
            if len(trades_in_group) < 2:
                continue

            # Check all pairs within this dealid group
            for i in range(len(trades_in_group)):
                for j in range(i + 1, len(trades_in_group)):
                    trade1, trade2 = trades_in_group[i], trades_in_group[j]

                    # Extract tradeids for comparison
                    tradeid1 = str(trade1.raw_data.get("tradeid", "")).strip()
                    tradeid2 = str(trade2.raw_data.get("tradeid", "")).strip()

                    # Must have different tradeids (same dealid + different tradeid = spread pair)
                    if tradeid1 == tradeid2 or not tradeid1 or not tradeid2:
                        continue

                    # Step 3: Validate spread characteristics
                    if self.validate_spread_pair_characteristics(
                        trade1, trade2, self.normalizer
                    ):
                        # Step 4: Add to results using same key structure as fallback method
                        # This ensures compatibility with existing _find_spread_match() logic
                        quantity_for_key = self._get_quantity_for_grouping(
                            trade1, self.normalizer
                        )

                        group_key = self.create_universal_signature(
                            trade1, [trade1.product_name, quantity_for_key]
                        )
                        trade_groups[group_key].extend([trade1, trade2])
                        spread_pairs_found += 1

                        logger.debug(
                            f"Found valid dealid spread pair: {trade1.trade_id}/{trade2.trade_id} "
                            f"(dealid: {dealid}, tradeids: {tradeid1}/{tradeid2})"
                        )

        return trade_groups, spread_pairs_found

    # Note: Dealid spread pair validation is now handled by MultiLegBaseMatcher.validate_spread_pair_characteristics

    def _group_exchange_spreads(
        self, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> Tuple[Dict[Tuple, List[Trade]], Dict[str, int], Dict[str, str]]:
        """
        Group exchange trades using 3-tier sequential approach for comprehensive spread detection.

        ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        3-TIER SEQUENTIAL EXECUTION APPROACH (All tiers run in sequence, not fallback)
        ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

        🔹 TIER 1: DealID/TradeID-based grouping
            - Uses dealid/tradeid fields from exchange's native grouping system
            - Same dealid + different tradeid = spread pair indicator
            - Most accurate method when data quality is sufficient
            - Matched trades are removed from pool before Tier 2

        🔹 TIER 2: Time-based grouping with price calculation matching
            - Groups remaining trades by exact same tradedatetime
            - Calculates spread price from exchange pairs (earlier month - later month)
            - Matches with trader spreads having one leg = spread price, other = 0
            - Matched trades are removed from pool before Tier 3

        🔹 TIER 3: Product/quantity-based grouping (traditional fallback)
            - Uses existing product/quantity matching logic on remaining trades
            - Ensures all possible spreads are detected
            - Maintains compatibility with existing functionality

        ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        SEQUENTIAL EXECUTION: Each tier processes remaining unmatched trades and accumulates results
        ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        """

        # Initialize cumulative results from all tiers
        all_trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        tier_trade_mapping: Dict[str, str] = {}  # Maps trade_id to tier
        remaining_trades = [
            t for t in exchange_trades if not pool_manager.is_trade_matched(t)
        ]

        logger.info(
            f"Starting 3-tier sequential spread grouping with {len(remaining_trades)} exchange trades"
        )

        # Track matches found by each tier
        tier_match_counts = {"tier1": 0, "tier2": 0, "tier3": 0}

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        # 🔹 TIER 1: DealID/TradeID-based grouping (Most Accurate)
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        logger.info("🔹 TIER 1: Executing DealID/TradeID-based spread grouping...")

        if self._is_dealid_data_usable(remaining_trades):
            logger.debug(
                "DealID data quality sufficient - proceeding with dealid/tradeid grouping"
            )
            tier1_groups, tier1_spread_count = self._group_exchange_spreads_by_dealid(
                remaining_trades, pool_manager
            )
            tier_match_counts["tier1"] = tier1_spread_count

            if tier1_groups:
                logger.info(
                    f"✓ TIER 1 Results: Found {tier1_spread_count} spread pairs using dealid/tradeid method"
                )

                # Add Tier 1 results to cumulative results and track tier mapping
                for key, trades in tier1_groups.items():
                    all_trade_groups[key].extend(trades)
                    # Mark these trades as coming from Tier 1
                    for trade in trades:
                        tier_trade_mapping[trade.trade_id] = "tier1"

                # Remove Tier 1 matched trades from remaining trades for Tier 2
                tier1_matched_trades = []
                for trades in tier1_groups.values():
                    tier1_matched_trades.extend(trades)
                remaining_trades = [
                    t for t in remaining_trades if t not in tier1_matched_trades
                ]

                logger.debug(
                    f"TIER 1 → TIER 2 Transition: {len(remaining_trades)} trades remaining after Tier 1"
                )
            else:
                logger.debug(
                    "✗ TIER 1 Results: No spread pairs found using dealid/tradeid method"
                )
        else:
            logger.debug("✗ TIER 1 Skipped: DealID data quality insufficient")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        # 🔹 TIER 2: Time-based grouping with zero-price detection (Enhanced Detection)
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        logger.info(
            f"🔹 TIER 2: Executing time-based spread grouping with {len(remaining_trades)} remaining trades..."
        )

        if remaining_trades:
            tier2_groups, tier2_spread_count = self._group_exchange_spreads_by_time(
                remaining_trades, pool_manager
            )
            tier_match_counts["tier2"] = tier2_spread_count

            if tier2_groups:
                logger.info(
                    f"✓ TIER 2 Results: Found {tier2_spread_count} spread pairs using time-based method"
                )

                # Add Tier 2 results to cumulative results and track tier mapping
                for key, trades in tier2_groups.items():
                    all_trade_groups[key].extend(trades)
                    # Mark these trades as coming from Tier 2
                    for trade in trades:
                        tier_trade_mapping[trade.trade_id] = "tier2"

                # Remove Tier 2 matched trades from remaining trades for Tier 3
                tier2_matched_trades = []
                for trades in tier2_groups.values():
                    tier2_matched_trades.extend(trades)
                remaining_trades = [
                    t for t in remaining_trades if t not in tier2_matched_trades
                ]

                logger.debug(
                    f"TIER 2 → TIER 3 Transition: {len(remaining_trades)} trades remaining after Tier 2"
                )
            else:
                logger.debug(
                    "✗ TIER 2 Results: No spread pairs found using time-based method"
                )
        else:
            logger.debug("✗ TIER 2 Skipped: No remaining trades after Tier 1")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        # 🔹 TIER 3: Product/quantity-based grouping (Traditional Fallback)
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        logger.info(
            f"🔹 TIER 3: Executing product/quantity-based spread grouping with {len(remaining_trades)} remaining trades..."
        )

        if remaining_trades:
            tier3_groups, tier3_spread_count = self._group_exchange_spreads_by_product_quantity(
                remaining_trades, pool_manager
            )
            tier_match_counts["tier3"] = tier3_spread_count

            if tier3_groups:
                logger.info(
                    f"✓ TIER 3 Results: Found {tier3_spread_count} spread pairs using product/quantity method"
                )

                # Add Tier 3 results to cumulative results and track tier mapping
                for key, trades in tier3_groups.items():
                    all_trade_groups[key].extend(trades)
                    # Mark these trades as coming from Tier 3
                    for trade in trades:
                        tier_trade_mapping[trade.trade_id] = "tier3"
            else:
                logger.debug(
                    "✗ TIER 3 Results: No spread pairs found using product/quantity method"
                )
        else:
            logger.debug("✗ TIER 3 Skipped: No remaining trades after Tier 1 + Tier 2")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        # 🏁 SEQUENTIAL EXECUTION COMPLETE: Return cumulative results from all tiers
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
        total_groups = len(all_trade_groups)
        total_trades = sum(len(trades) for trades in all_trade_groups.values())
        total_spread_pairs = sum(tier_match_counts.values())

        logger.info(
            f"🏁 3-TIER SEQUENTIAL COMPLETE: {total_spread_pairs} potential spread pairs identified"
        )
        logger.info(
            f"   📊 POTENTIAL PAIRS BY TIER: Tier 1: {tier_match_counts['tier1']}, Tier 2: {tier_match_counts['tier2']}, Tier 3: {tier_match_counts['tier3']}"
        )

        return dict(all_trade_groups), tier_match_counts, tier_trade_mapping

    def _group_exchange_spreads_by_time(
        self, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> Tuple[Dict[Tuple, List[Trade]], int]:
        """
        TIER 2: Enhanced time-based spread detection with price calculation matching.

        This method identifies spread pairs by:
        1. Grouping exchange trades by exact same tradedatetime
        2. Finding pairs within datetime groups that form valid spreads
        3. Calculating spread price from exchange pair (earlier month - later month)
        4. Looking for trader spreads with one leg = spread price, other leg = 0

        Args:
            exchange_trades: List of unmatched exchange trades
            pool_manager: Pool manager for checking if trades are already matched

        Returns:
            Tuple of (Dict mapping group keys to lists of validated spread pairs, count of spread pairs found)
        """
        trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        spread_pairs_found = 0

        # Step 1: Group trades by exact same tradedatetime (not time windows)
        time_groups = self._group_trades_by_exact_datetime(exchange_trades)

        if not time_groups:
            logger.debug("No time groups found - unable to parse datetime from trades")
            return trade_groups, 0

        logger.debug(
            f"Grouped trades into {len(time_groups)} exact datetime groups for enhanced spread detection"
        )

        # Step 2: Find valid spread pairs within each datetime group
        for datetime_key, trades in time_groups.items():
            if len(trades) < 2:
                continue

            # Check all pairs within this exact datetime group
            for i in range(len(trades)):
                for j in range(i + 1, len(trades)):
                    trade1, trade2 = trades[i], trades[j]

                    # Skip if either trade is already matched
                    if pool_manager.is_trade_matched(
                        trade1
                    ) or pool_manager.is_trade_matched(trade2):
                        continue

                    # Step 3: Validate pair forms a valid spread
                    if self.validate_spread_pair_characteristics(
                        trade1, trade2, self.normalizer
                    ):
                        # Step 4: Calculate spread price and find matching trader spreads
                        spread_price = self._calculate_exchange_spread_price(
                            trade1, trade2
                        )
                        if spread_price is not None:
                            # Find trader spreads that match this exchange spread + calculated price
                            if self._find_matching_trader_spreads_with_price(
                                trade1, trade2, spread_price, pool_manager
                            ):
                                # Add to results using same key structure for compatibility
                                quantity_for_key = self._get_quantity_for_grouping(
                                    trade1, self.normalizer
                                )
                                group_key = self.create_universal_signature(
                                    trade1, [trade1.product_name, quantity_for_key]
                                )
                                trade_groups[group_key].extend([trade1, trade2])
                                spread_pairs_found += 1

                                logger.debug(
                                    f"Added time-based spread pair: {trade1.trade_id}/{trade2.trade_id} "
                                    f"(datetime: {datetime_key}, spread_price: {spread_price})"
                                )

        return trade_groups, spread_pairs_found

    def _group_trades_by_exact_datetime(
        self, exchange_trades: List[Trade]
    ) -> Dict[str, List[Trade]]:
        """Group exchange trades by exact same tradedatetime for spread detection.

        This method groups trades that occur at the exact same tradedatetime,
        which is critical for identifying exchange spread pairs where both legs
        are executed simultaneously.

        Args:
            exchange_trades: List of exchange trades to group

        Returns:
            Dict mapping datetime strings to lists of trades with that exact datetime
        """
        time_groups: Dict[str, List[Trade]] = defaultdict(list)

        for trade in exchange_trades:
            # Get the raw tradedatetime field directly from raw_data
            datetime_str = trade.raw_data.get("tradedatetime")
            if datetime_str and str(datetime_str).strip():
                # Use the exact datetime string as the key (no parsing needed for grouping)
                datetime_key = str(datetime_str).strip()
                time_groups[datetime_key].append(trade)

        logger.debug(
            f"Grouped {len(exchange_trades)} exchange trades into {len(time_groups)} exact datetime groups"
        )
        return time_groups

    # Note: Time-based spread pair validation is now handled by MultiLegBaseMatcher.validate_spread_pair_characteristics

    def _calculate_exchange_spread_price(
        self, trade1: Trade, trade2: Trade
    ) -> Optional[Decimal]:
        """Calculate spread price from exchange pair (earlier month - later month)."""
        try:
            month1_tuple = get_month_order_tuple(self.normalizer.normalize_contract_month(trade1.contract_month))
            month2_tuple = get_month_order_tuple(self.normalizer.normalize_contract_month(trade2.contract_month))

            if not month1_tuple or not month2_tuple:
                return None

            # Earlier month price - later month price
            if month1_tuple < month2_tuple:
                spread_price = trade1.price - trade2.price
            else:
                spread_price = trade2.price - trade1.price

            logger.debug(
                f"Calculated spread price: {spread_price} from {trade1.trade_id} (${trade1.price}) - {trade2.trade_id} (${trade2.price})"
            )
            return spread_price

        except Exception as e:
            logger.debug(
                f"Failed to calculate spread price for {trade1.trade_id}/{trade2.trade_id}: {e}"
            )
            return None

    def _find_matching_trader_spreads_with_price(
        self,
        exchange_trade1: Trade,
        exchange_trade2: Trade,
        spread_price: Decimal,
        pool_manager: UnmatchedPoolManager,
    ) -> bool:
        """Check if there are trader spreads that match this exchange spread with calculated price."""
        trader_trades = pool_manager.get_unmatched_trader_trades()

        # Create expected contract months set from exchange trades
        exchange_months = {
            exchange_trade1.contract_month,
            exchange_trade2.contract_month,
        }

        # Look for trader spread pairs where:
        # - One leg has the calculated spread_price
        # - Other leg has price = 0
        # - Contract months match the exchange pair
        # - B/S directions match the exchange pair

        for i in range(len(trader_trades)):
            for j in range(i + 1, len(trader_trades)):
                trader1, trader2 = trader_trades[i], trader_trades[j]

                if pool_manager.is_trade_matched(
                    trader1
                ) or pool_manager.is_trade_matched(trader2):
                    continue

                # Check if this trader pair matches the exchange spread pattern
                if self._validate_trader_spread_matches_exchange(
                    trader1, trader2, exchange_trade1, exchange_trade2, spread_price
                ):
                    logger.debug(
                        f"Found matching trader spread: {trader1.trade_id} (${trader1.price}) + {trader2.trade_id} (${trader2.price}) "
                        f"matches exchange spread price {spread_price}"
                    )
                    return True

        return False

    def _validate_trader_spread_matches_exchange(
        self,
        trader1: Trade,
        trader2: Trade,
        exchange1: Trade,
        exchange2: Trade,
        spread_price: Decimal,
    ) -> bool:
        """Validate that trader spread pair matches the exchange spread pattern."""
        # Must be same product
        if (
            trader1.product_name != exchange1.product_name
            or trader2.product_name != exchange1.product_name
        ):
            return False

        # Must have same quantity
        trader_qty1 = self._get_quantity_for_grouping(trader1, self.normalizer)
        trader_qty2 = self._get_quantity_for_grouping(trader2, self.normalizer)
        exchange_qty = self._get_quantity_for_grouping(exchange1, self.normalizer)

        if trader_qty1 != exchange_qty or trader_qty2 != exchange_qty:
            return False

        # Universal fields must match
        if not (
            self.validate_universal_fields(trader1, exchange1)
            and self.validate_universal_fields(trader2, exchange1)
        ):
            return False

        # Contract months must match
        trader_months = {trader1.contract_month, trader2.contract_month}
        exchange_months = {exchange1.contract_month, exchange2.contract_month}
        if trader_months != exchange_months:
            return False

        # One trader leg must have spread_price, other must have price = 0
        trader_prices = {trader1.price, trader2.price}
        if not (spread_price in trader_prices and Decimal("0") in trader_prices):
            return False

        # Validate B/S directions match
        trader_month_bs = {
            trader1.contract_month: trader1.buy_sell,
            trader2.contract_month: trader2.buy_sell,
        }
        exchange_month_bs = {
            exchange1.contract_month: exchange1.buy_sell,
            exchange2.contract_month: exchange2.buy_sell,
        }

        return trader_month_bs == exchange_month_bs

    def _group_exchange_spreads_by_product_quantity(
        self, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> Tuple[Dict[Tuple, List[Trade]], int]:
        """
        TIER 3: Group exchange trades by product/quantity (traditional fallback method).

        This is the original spread grouping method that groups trades by:
        - Same product name
        - Same quantity (in appropriate units)
        - Universal fields (broker, clearing account)

        Args:
            exchange_trades: List of remaining unmatched exchange trades (pre-filtered)
            pool_manager: Pool manager for checking if trades are already matched (unused in Tier 3)

        Returns:
            Tuple of (Dict mapping group keys to lists of trades, count of potential spread pairs)
        """
        trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        spread_pairs_found = 0

        # Process only the remaining trades passed in (already filtered by previous tiers)
        for trade in exchange_trades:
            # Exchange data uses actual units, so group by the appropriate quantity
            # Use config-based unit determination for consistency with trader grouping
            quantity_for_grouping = self._get_quantity_for_grouping(
                trade, self.normalizer
            )

            # Create grouping key with universal fields using BaseMatcher method
            key = self.create_universal_signature(
                trade, [trade.product_name, quantity_for_grouping]
            )
            trade_groups[key].append(trade)

        # Count potential spread pairs in grouped trades
        for trades in trade_groups.values():
            if len(trades) >= 2:
                # Count actual spread pairs that could form from this group
                for i in range(len(trades)):
                    for j in range(i + 1, len(trades)):
                        if self.validate_spread_pair_characteristics(
                            trades[i], trades[j], self.normalizer
                        ):
                            spread_pairs_found += 1

        return trade_groups, spread_pairs_found

    def _find_spread_match(
        self,
        trader_group: List[Trade],
        exchange_groups: Dict[Tuple, List[Trade]],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[MatchResult]:
        """Find spread match for a trader spread group."""
        if len(trader_group) != 2:
            return None

        trader_trade1, trader_trade2 = trader_group
        # Use same unit logic as grouping for consistent key generation
        default_unit = self.normalizer.get_trader_product_unit_default(
            trader_trade1.product_name
        )
        quantity_for_key = (
            trader_trade1.quantity_bbl
            if default_unit == "bbl"
            else trader_trade1.quantity_mt
        )

        # Create grouping key with universal fields (same as in grouping methods)
        group_key = self.create_universal_signature(
            trader_trade1, [trader_trade1.product_name, quantity_for_key]
        )

        if group_key not in exchange_groups:
            return None

        exchange_candidates = exchange_groups[group_key]
        for i in range(len(exchange_candidates)):
            for j in range(i + 1, len(exchange_candidates)):
                exchange_trade1, exchange_trade2 = (
                    exchange_candidates[i],
                    exchange_candidates[j],
                )

                if pool_manager.is_trade_matched(
                    exchange_trade1
                ) or pool_manager.is_trade_matched(exchange_trade2):
                    continue
                if any(pool_manager.is_trade_matched(trade) for trade in trader_group):
                    return None

                if self._validate_spread_match(
                    trader_group, [exchange_trade1, exchange_trade2]
                ):
                    return self._create_spread_match_result(
                        trader_group, [exchange_trade1, exchange_trade2]
                    )
        return None

    def _find_spread_match_with_tier_tracking(
        self,
        trader_group: List[Trade],
        exchange_groups: Dict[Tuple, List[Trade]],
        pool_manager: UnmatchedPoolManager,
        tier_trade_mapping: Dict[str, str],
    ) -> Tuple[Optional[MatchResult], Optional[str]]:
        """Find spread match for a trader spread group and track which tier it came from."""
        if len(trader_group) != 2:
            return None, None

        trader_trade1, trader_trade2 = trader_group
        # Use same unit logic as grouping for consistent key generation
        default_unit = self.normalizer.get_trader_product_unit_default(
            trader_trade1.product_name
        )
        quantity_for_key = (
            trader_trade1.quantity_bbl
            if default_unit == "bbl"
            else trader_trade1.quantity_mt
        )

        # Create grouping key with universal fields (same as in grouping methods)
        group_key = self.create_universal_signature(
            trader_trade1, [trader_trade1.product_name, quantity_for_key]
        )

        if group_key not in exchange_groups:
            return None, None

        exchange_candidates = exchange_groups[group_key]
        for i in range(len(exchange_candidates)):
            for j in range(i + 1, len(exchange_candidates)):
                exchange_trade1, exchange_trade2 = (
                    exchange_candidates[i],
                    exchange_candidates[j],
                )

                if pool_manager.is_trade_matched(
                    exchange_trade1
                ) or pool_manager.is_trade_matched(exchange_trade2):
                    continue
                if any(pool_manager.is_trade_matched(trade) for trade in trader_group):
                    return None, None

                if self._validate_spread_match(
                    trader_group, [exchange_trade1, exchange_trade2]
                ):
                    # Determine which tier this match came from
                    source_tier = tier_trade_mapping.get(exchange_trade1.trade_id, "unknown")
                    
                    match_result = self._create_spread_match_result(
                        trader_group, [exchange_trade1, exchange_trade2]
                    )
                    return match_result, source_tier
        return None, None

    def _validate_spread_match(
        self, trader_trades: List[Trade], exchange_trades: List[Trade]
    ) -> bool:
        """Validate that trader and exchange trades form a valid spread match."""
        if len(trader_trades) != 2 or len(exchange_trades) != 2:
            return False

        trader_trade1, trader_trade2 = trader_trades
        exchange_trade1, exchange_trade2 = exchange_trades

        # Use MultiLegBaseMatcher validation for both exchange trades
        if not self.validate_spread_pair_characteristics(
            exchange_trade1, exchange_trade2, self.normalizer
        ):
            return False

        # Validate contract months match between trader and exchange
        if {trader_trade1.contract_month, trader_trade2.contract_month} != {
            exchange_trade1.contract_month,
            exchange_trade2.contract_month,
        }:
            return False

        return self._validate_spread_directions(
            trader_trades, exchange_trades
        ) and self._validate_spread_prices(trader_trades, exchange_trades)

    def _validate_spread_directions(
        self, trader_trades: List[Trade], exchange_trades: List[Trade]
    ) -> bool:
        """Validate that B/S directions match between trader and exchange spreads."""
        trader_month_bs = {
            trade.contract_month: trade.buy_sell for trade in trader_trades
        }
        exchange_month_bs = {
            trade.contract_month: trade.buy_sell for trade in exchange_trades
        }
        return all(
            month in exchange_month_bs
            and trader_month_bs[month] == exchange_month_bs[month]
            for month in trader_month_bs
        )

    def _validate_spread_prices(
        self, trader_trades: List[Trade], exchange_trades: List[Trade]
    ) -> bool:
        """Validate spread price calculation between trader and exchange trades."""
        # For trader spreads: find the non-zero price (if any) as the spread price
        # If both legs are 0, then spread price is 0 (which is now allowed)
        trader_prices = [t.price for t in trader_trades]
        trader_spread_price = next((p for p in trader_prices if p != 0), Decimal("0"))

        # Calculate exchange spread price (earlier month - later month)
        exchange_trade1, exchange_trade2 = exchange_trades
        month1_tuple = get_month_order_tuple(
            self.normalizer.normalize_contract_month(exchange_trade1.contract_month)
        )
        month2_tuple = get_month_order_tuple(
            self.normalizer.normalize_contract_month(exchange_trade2.contract_month)
        )

        if not month1_tuple or not month2_tuple:
            return False

        exchange_spread_price = (
            exchange_trade1.price - exchange_trade2.price
            if month1_tuple < month2_tuple
            else exchange_trade2.price - exchange_trade1.price
        )
        
        return trader_spread_price == exchange_spread_price

    def _create_spread_match_result(
        self, trader_trades: List[Trade], exchange_trades: List[Trade]
    ) -> MatchResult:
        """Create MatchResult for spread match."""
        # Rule-specific matched fields
        rule_specific_fields = [
            "product_name",
            "quantity",
            "contract_months",
            "spread_price_calculation",
        ]

        # Get complete matched fields with universal fields using BaseMatcher method
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        return MatchResult(
            match_id=f"SPREAD_{uuid.uuid4().hex[:UUID_LENGTH].upper()}",
            match_type=MatchType.SPREAD,
            confidence=self.confidence,
            trader_trade=trader_trades[0],
            exchange_trade=exchange_trades[0],
            matched_fields=matched_fields,
            differing_fields=[],
            tolerances_applied={},
            rule_order=self.rule_number,
            additional_trader_trades=trader_trades[1:],
            additional_exchange_trades=exchange_trades[1:],
        )

    def get_rule_info(self) -> dict:
        """Get information about this matching rule."""
        return {
            "rule_number": self.rule_number,
            "rule_name": "Spread Match",
            "match_type": MatchType.SPREAD.value,
            "confidence": float(self.confidence),
            "description": "Matches spread trades where trader shows calculated spread but exchange shows individual legs",
            "requirements": [
                "Both sources must have 2 trades each (spread legs)",
                "Same product, quantity, and broker group",
                "Opposite B/S directions for each leg",
                "Different contract months for legs",
                "Price calculation must match (if available)",
            ],
        }
