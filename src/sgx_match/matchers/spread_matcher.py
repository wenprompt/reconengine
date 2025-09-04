"""Spread matching implementation for Rule 2."""

from typing import List, Optional, Dict, Tuple
from decimal import Decimal
import logging
from collections import defaultdict

from ..models import SGXTrade, SGXMatchResult, SGXMatchType, SGXTradeSource
from ..core import SGXUnmatchedPool
from ..config import SGXConfigManager
from ..normalizers import SGXTradeNormalizer
from .multi_leg_base_matcher import MultiLegBaseMatcher
from ..utils.trade_helpers import calculate_spread_price

logger = logging.getLogger(__name__)


class SpreadMatcher(MultiLegBaseMatcher):
    """Implements Rule 2: Spread matching for SGX trades."""

    def __init__(self, config_manager: SGXConfigManager, normalizer: SGXTradeNormalizer):
        """Initialize the spread matcher."""
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 2
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        logger.info(f"Initialized SpreadMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: SGXUnmatchedPool) -> List[SGXMatchResult]:
        """Find all spread matches using 2-tier sequential approach (dealid + time-based)."""
        logger.info("Starting spread matching (Rule 2) - 2-tier sequential approach")
        matches = []
        
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Find spread pairs: trader by 'S' indicator, exchange by 2-tier sequential approach
        trader_spread_pairs = self._find_trader_spread_pairs(trader_trades, pool_manager)
        exchange_spread_pairs = self._find_exchange_spread_pairs(exchange_trades, pool_manager)
        
        logger.debug(f"Found {len(trader_spread_pairs)} trader spread pairs")
        logger.debug(f"Found {len(exchange_spread_pairs)} exchange spread pairs")

        # Match trader spread pairs with exchange spread pairs
        for trader_pair in trader_spread_pairs:
            # Skip if any trader trade is already matched
            if any(not pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.TRADER) for trade in trader_pair):
                continue

            match_result = self._match_spread_pair(trader_pair, exchange_spread_pairs, pool_manager)
            if match_result:
                # Atomically record the match
                if pool_manager.record_match(match_result):
                    matches.append(match_result)
                    logger.debug(f"Created spread match: {match_result.match_id}")
                else:
                    logger.warning(f"Failed to atomically record spread match {match_result.match_id}")

        logger.info(f"Found {len(matches)} spread matches")
        return matches

    def _find_trader_spread_pairs(self, trader_trades: List[SGXTrade], pool_manager: SGXUnmatchedPool) -> List[List[SGXTrade]]:
        """Find trader spread pairs with spread indicators."""
        spread_pairs: List[List[SGXTrade]] = []
        
        # Group trades by product and quantity
        trade_groups: Dict[Tuple, List[SGXTrade]] = defaultdict(list)
        for trade in trader_trades:
            if pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.TRADER):
                key = self.create_universal_signature(trade, [trade.product_name, trade.quantityunit])
                trade_groups[key].append(trade)
        
        # Find pairs within each group
        for trades in trade_groups.values():
            if len(trades) >= 2:
                for i in range(len(trades)):
                    for j in range(i + 1, len(trades)):
                        if self._is_trader_spread_pair(trades[i], trades[j]):
                            spread_pairs.append([trades[i], trades[j]])
        
        return spread_pairs

    def _is_trader_spread_pair(self, trade1: SGXTrade, trade2: SGXTrade) -> bool:
        """Check if two trader trades form a spread pair.
        
        Supports two patterns:
        1. Original: Spread indicator pattern (spread column contains 'S')
        2. New: Identical spread price pattern (both trades have same price)
        """
        # Basic requirements: opposite B/S directions and different contract months
        if (trade1.buy_sell == trade2.buy_sell or 
            trade1.contract_month == trade2.contract_month):
            return False
        
        # Pattern 1: Look for spread indicators in trader data (original pattern)
        # Only match 'S' spread indicator, NOT 'PS' (product spread)
        has_spread_indicator = (
            (trade1.spread and str(trade1.spread).upper().strip() == 'S') or
            (trade2.spread and str(trade2.spread).upper().strip() == 'S')
        )
        
        # Pattern 2: Both trades have identical spread price (including zero spreads)
        has_identical_spread_price = (trade1.price == trade2.price)
        
        return has_spread_indicator or has_identical_spread_price

    def _find_exchange_spread_pairs(self, exchange_trades: List[SGXTrade], pool_manager: SGXUnmatchedPool) -> List[List[SGXTrade]]:
        """Find exchange spread pairs using 2-tier sequential approach.
        
        Tier 1: DealID-based grouping (most accurate)
        Tier 2: Time-based grouping with price calculation matching (enhanced detection)
        """
        logger.info("Starting 2-tier sequential spread grouping for SGX")
        
        # Initialize results
        all_spread_pairs: List[List[SGXTrade]] = []
        remaining_trades = [t for t in exchange_trades if pool_manager.is_unmatched(t.internal_trade_id, SGXTradeSource.EXCHANGE)]
        
        # Track tier statistics
        tier_counts = {"tier1": 0, "tier2": 0}
        
        logger.info(f"Starting with {len(remaining_trades)} unmatched exchange trades")
        
        # ══════════════════════════════════════════════════════════════
        # TIER 1: DealID-based grouping (Most Accurate)
        # ══════════════════════════════════════════════════════════════
        logger.info("🔹 TIER 1: Executing DealID-based spread grouping...")
        
        tier1_pairs = self._find_exchange_spread_pairs_by_dealid(remaining_trades, pool_manager)
        tier_counts["tier1"] = len(tier1_pairs)
        
        if tier1_pairs:
            logger.info(f"✓ TIER 1 Results: Found {tier_counts['tier1']} spread pairs using dealid method")
            all_spread_pairs.extend(tier1_pairs)
            
            # Remove tier 1 matched trades from remaining trades
            tier1_trade_ids = set()
            for pair in tier1_pairs:
                for trade in pair:
                    tier1_trade_ids.add(trade.internal_trade_id)
            
            remaining_trades = [t for t in remaining_trades if t.internal_trade_id not in tier1_trade_ids]
            logger.debug(f"TIER 1 → TIER 2 Transition: {len(remaining_trades)} trades remaining after Tier 1")
        else:
            logger.debug("✗ TIER 1 Results: No spread pairs found using dealid method")
        
        # ══════════════════════════════════════════════════════════════
        # TIER 2: Time-based grouping with price calculation matching
        # ══════════════════════════════════════════════════════════════
        logger.info(f"🔹 TIER 2: Executing time-based spread grouping with {len(remaining_trades)} remaining trades...")
        
        if remaining_trades:
            tier2_pairs = self._find_exchange_spread_pairs_by_time(remaining_trades, pool_manager)
            tier_counts["tier2"] = len(tier2_pairs)
            
            if tier2_pairs:
                logger.info(f"✓ TIER 2 Results: Found {tier_counts['tier2']} spread pairs using time-based method")
                all_spread_pairs.extend(tier2_pairs)
            else:
                logger.debug("✗ TIER 2 Results: No spread pairs found using time-based method")
        else:
            logger.debug("✗ TIER 2 Skipped: No remaining trades after Tier 1")
        
        # ══════════════════════════════════════════════════════════════
        # SEQUENTIAL EXECUTION COMPLETE
        # ══════════════════════════════════════════════════════════════
        total_pairs = tier_counts["tier1"] + tier_counts["tier2"]
        logger.info(f"🏁 2-TIER SEQUENTIAL COMPLETE: {total_pairs} spread pairs identified")
        logger.info(f"   📊 TIER BREAKDOWN: Tier 1: {tier_counts['tier1']}, Tier 2: {tier_counts['tier2']}")
        
        return all_spread_pairs

    def _find_exchange_spread_pairs_by_dealid(self, exchange_trades: List[SGXTrade], pool_manager: SGXUnmatchedPool) -> List[List[SGXTrade]]:
        """Find exchange spread pairs using dealid/tradeid grouping (Tier 1 approach)."""
        spread_pairs: List[List[SGXTrade]] = []
        
        # Group trades by dealid
        dealid_groups: Dict[str, List[SGXTrade]] = defaultdict(list)
        for trade in exchange_trades:
            if not pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.EXCHANGE):
                continue
                
            # SGX trades have deal_id field directly (no raw_data access needed)
            dealid = trade.deal_id
            tradeid = trade.internal_trade_id
            
            # Only include trades that have both dealid and tradeid
            if dealid is not None and tradeid and str(dealid).strip() and str(tradeid).strip():
                dealid_str = str(dealid).strip()
                if dealid_str.lower() not in ['nan', 'none', '']:
                    dealid_groups[dealid_str].append(trade)
        
        # Find valid spread pairs within each dealid group
        for dealid_str, trades_in_group in dealid_groups.items():
            # A spread group must have exactly 2 legs for SGX
            if len(trades_in_group) == 2:
                trade1, trade2 = trades_in_group
                
                # Extract tradeids for comparison - must be different
                tradeid1 = str(trade1.internal_trade_id).strip()
                tradeid2 = str(trade2.internal_trade_id).strip()
                
                if tradeid1 != tradeid2 and tradeid1 and tradeid2:
                    # Validate spread characteristics using existing validation
                    if self.validate_spread_pair_characteristics(trade1, trade2):
                        spread_pairs.append([trade1, trade2])
                        logger.debug(f"Found dealid spread pair: {tradeid1}/{tradeid2} (dealid: {dealid_str})")
            elif len(trades_in_group) > 2:
                # Multiple legs - try to find all valid pairs
                for i in range(len(trades_in_group)):
                    for j in range(i + 1, len(trades_in_group)):
                        trade1, trade2 = trades_in_group[i], trades_in_group[j]
                        
                        # Must have different tradeids
                        tradeid1 = str(trade1.internal_trade_id).strip()
                        tradeid2 = str(trade2.internal_trade_id).strip()
                        
                        if tradeid1 != tradeid2 and tradeid1 and tradeid2:
                            if self.validate_spread_pair_characteristics(trade1, trade2):
                                spread_pairs.append([trade1, trade2])
                                logger.debug(f"Found dealid spread pair: {tradeid1}/{tradeid2} (dealid: {dealid_str})")
        
        return spread_pairs

    def _find_exchange_spread_pairs_by_time(self, exchange_trades: List[SGXTrade], pool_manager: SGXUnmatchedPool) -> List[List[SGXTrade]]:
        """
        TIER 2: Enhanced time-based spread detection with price calculation matching.

        This method identifies spread pairs by:
        1. Grouping exchange trades by exact same trade_time
        2. Finding pairs within datetime groups that form valid spreads
        3. Calculating spread price from exchange pair (earlier month - later month)
        4. Looking for trader spreads with one leg = spread price, other leg = 0

        Args:
            exchange_trades: List of unmatched exchange trades (pre-filtered)
            pool_manager: Pool manager for checking if trades are already matched

        Returns:
            List of validated spread pairs found using time-based approach
        """
        spread_pairs: List[List[SGXTrade]] = []

        # Step 1: Group trades by exact same trade_time
        time_groups = self._group_trades_by_exact_datetime(exchange_trades)

        if not time_groups:
            logger.debug("No time groups found - unable to parse datetime from trades")
            return spread_pairs

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
                    if not pool_manager.is_unmatched(trade1.internal_trade_id, SGXTradeSource.EXCHANGE) or \
                       not pool_manager.is_unmatched(trade2.internal_trade_id, SGXTradeSource.EXCHANGE):
                        continue

                    # Step 3: Validate pair forms a valid spread
                    if self.validate_spread_pair_characteristics(trade1, trade2):
                        # Step 4: Calculate spread price and find matching trader spreads
                        spread_price = self._calculate_exchange_spread_price_sgx(trade1, trade2)
                        if spread_price is not None:
                            # Find trader spreads that match this exchange spread + calculated price
                            if self._find_matching_trader_spreads_with_price(
                                trade1, trade2, spread_price, pool_manager
                            ):
                                spread_pairs.append([trade1, trade2])

                                logger.debug(
                                    f"Added time-based spread pair: {trade1.internal_trade_id}/{trade2.internal_trade_id} "
                                    f"(datetime: {datetime_key}, spread_price: {spread_price})"
                                )

        return spread_pairs

    def _group_trades_by_exact_datetime(self, exchange_trades: List[SGXTrade]) -> Dict[str, List[SGXTrade]]:
        """Group exchange trades by exact same trade_time for spread detection.

        This method groups trades that occur at the exact same trade_time,
        which is critical for identifying exchange spread pairs where both legs
        are executed simultaneously.

        Args:
            exchange_trades: List of exchange trades to group

        Returns:
            Dict mapping datetime strings to lists of trades with that exact datetime
        """
        time_groups: Dict[str, List[SGXTrade]] = defaultdict(list)

        for trade in exchange_trades:
            # Get the trade_time field directly from SGXTrade model
            datetime_str = trade.trade_time
            if datetime_str and str(datetime_str).strip():
                # Use the exact datetime string as the key (no parsing needed for grouping)
                datetime_key = str(datetime_str).strip()
                time_groups[datetime_key].append(trade)

        logger.debug(
            f"Grouped {len(exchange_trades)} exchange trades into {len(time_groups)} exact datetime groups"
        )
        return time_groups

    def _calculate_exchange_spread_price_sgx(self, trade1: SGXTrade, trade2: SGXTrade) -> Optional[Decimal]:
        """Calculate spread price from exchange pair (earlier month - later month)."""
        try:
            # Use SGX's existing calculate_spread_price utility
            spread_price = calculate_spread_price(
                trade1.price, trade1.contract_month,
                trade2.price, trade2.contract_month
            )

            if spread_price is not None:
                logger.debug(
                    f"Calculated spread price: {spread_price} from {trade1.internal_trade_id} (${trade1.price}) - {trade2.internal_trade_id} (${trade2.price})"
                )
            
            return spread_price

        except Exception as e:
            logger.debug(
                f"Failed to calculate spread price for {trade1.internal_trade_id}/{trade2.internal_trade_id}: {e}"
            )
            return None

    def _find_matching_trader_spreads_with_price(
        self,
        exchange_trade1: SGXTrade,
        exchange_trade2: SGXTrade,
        spread_price: Decimal,
        pool_manager: SGXUnmatchedPool,
    ) -> bool:
        """Check if there are trader spreads that match this exchange spread with calculated price."""
        trader_trades = pool_manager.get_unmatched_trader_trades()

        # Look for trader spread pairs where:
        # - One leg has the calculated spread_price
        # - Other leg has price = 0
        # - Contract months match the exchange pair
        # - B/S directions match the exchange pair

        for i in range(len(trader_trades)):
            for j in range(i + 1, len(trader_trades)):
                trader1, trader2 = trader_trades[i], trader_trades[j]

                if not pool_manager.is_unmatched(trader1.internal_trade_id, SGXTradeSource.TRADER) or \
                   not pool_manager.is_unmatched(trader2.internal_trade_id, SGXTradeSource.TRADER):
                    continue

                # Check if this trader pair matches the exchange spread pattern
                if self._validate_trader_spread_matches_exchange(
                    trader1, trader2, exchange_trade1, exchange_trade2, spread_price
                ):
                    logger.debug(
                        f"Found matching trader spread: {trader1.internal_trade_id} (${trader1.price}) + {trader2.internal_trade_id} (${trader2.price}) "
                        f"matches exchange spread price {spread_price}"
                    )
                    return True

        return False

    def _validate_trader_spread_matches_exchange(
        self,
        trader1: SGXTrade,
        trader2: SGXTrade,
        exchange1: SGXTrade,
        exchange2: SGXTrade,
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
        if trader1.quantityunit != exchange1.quantityunit or trader2.quantityunit != exchange1.quantityunit:
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

        # Validate B/S directions match
        trader_month_bs = {
            trader1.contract_month: trader1.buy_sell,
            trader2.contract_month: trader2.buy_sell,
        }
        exchange_month_bs = {
            exchange1.contract_month: exchange1.buy_sell,
            exchange2.contract_month: exchange2.buy_sell,
        }

        if trader_month_bs != exchange_month_bs:
            return False

        # Price validation: Support TWO patterns
        trader_prices = {trader1.price, trader2.price}
        
        # Pattern 1: One leg = spread price, other leg = 0 (original ICE pattern)
        pattern1_match = (spread_price in trader_prices and Decimal("0") in trader_prices)
        
        # Pattern 2: Both legs = spread price (identical spread price pattern)
        pattern2_match = (trader1.price == spread_price and trader2.price == spread_price)
        
        if pattern1_match or pattern2_match:
            logger.debug(
                f"Trader spread price validation passed: trader_prices={trader_prices}, "
                f"spread_price={spread_price}, pattern1={pattern1_match}, pattern2={pattern2_match}"
            )
            return True
        else:
            logger.debug(
                f"Trader spread price validation failed: trader_prices={trader_prices}, "
                f"spread_price={spread_price}, neither pattern matched"
            )
            return False


    def _match_spread_pair(
        self, 
        trader_pair: List[SGXTrade], 
        exchange_spread_pairs: List[List[SGXTrade]], 
        pool_manager: SGXUnmatchedPool
    ) -> Optional[SGXMatchResult]:
        """Match a trader spread pair with exchange spread pairs (Tier 1 approach)."""
        if len(trader_pair) != 2:
            return None
        
        # Try to match with each exchange spread pair
        for exchange_pair in exchange_spread_pairs:
            if len(exchange_pair) != 2:
                continue
                
            # Skip if either exchange trade is already matched
            if any(not pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.EXCHANGE) 
                   for trade in exchange_pair):
                continue
            
            # Validate this is a valid spread match
            if self._validate_spread_match(trader_pair, exchange_pair):
                return self._create_spread_match_result(trader_pair, exchange_pair)
        
        return None

    def _validate_spread_match(
        self, trader_trades: List[SGXTrade], exchange_trades: List[SGXTrade]
    ) -> bool:
        """Validate that trader and exchange trades form a valid spread match."""
        if len(trader_trades) != 2 or len(exchange_trades) != 2:
            return False

        trader_trade1, trader_trade2 = trader_trades
        exchange_trade1, exchange_trade2 = exchange_trades

        # Validate exchange trades form a valid spread pair
        if not self.validate_spread_pair_characteristics(exchange_trade1, exchange_trade2):
            return False

        # Validate all trades have the same product (calendar spread requirement)
        trader_products = {trader_trade1.product_name, trader_trade2.product_name}
        exchange_products = {exchange_trade1.product_name, exchange_trade2.product_name}
        
        # For calendar spreads, all trades must have the same product
        if len(trader_products) != 1 or len(exchange_products) != 1:
            return False
            
        # The single product must match between trader and exchange
        if trader_products != exchange_products:
            return False

        # Validate contract months match between trader and exchange
        trader_months = {trader_trade1.contract_month, trader_trade2.contract_month}
        exchange_months = {exchange_trade1.contract_month, exchange_trade2.contract_month}
        if trader_months != exchange_months:
            return False

        # Validate B/S directions and spread prices
        return (self._validate_spread_directions(trader_trades, exchange_trades) and 
                self._validate_spread_prices(trader_trades, exchange_trades))

    def _validate_spread_directions(
        self, trader_trades: List[SGXTrade], exchange_trades: List[SGXTrade]
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
        self, trader_trades: List[SGXTrade], exchange_trades: List[SGXTrade]
    ) -> bool:
        """Validate spread price calculation between trader and exchange trades."""
        # For SGX trader spreads: both legs should have the same price (the spread price)
        trader_prices = [t.price for t in trader_trades]
        
        # In SGX, both trader legs should have identical prices
        if len(set(trader_prices)) != 1:
            logger.debug(f"SGX trader spread price validation failed: legs have different prices {trader_prices}")
            return False
            
        trader_spread_price = trader_prices[0]  # Both legs have same price

        # Calculate exchange spread price (earlier month - later month)
        exchange_trade1, exchange_trade2 = exchange_trades
        
        exchange_spread_price = calculate_spread_price(
            exchange_trade1.price, exchange_trade1.contract_month,
            exchange_trade2.price, exchange_trade2.contract_month
        )
        
        if exchange_spread_price is None:
            return False

        price_match = trader_spread_price == exchange_spread_price
        logger.debug(
            f"SGX spread price validation: trader={trader_spread_price}, exchange={exchange_spread_price}, match={price_match}"
        )
        
        return price_match

    def _create_spread_match_result(
        self,
        trader_trades: List[SGXTrade],
        exchange_trades: List[SGXTrade],
    ) -> SGXMatchResult:
        """Create SGXMatchResult for spread match."""
        # Rule-specific matched fields
        rule_specific_fields = [
            "product_name",
            "quantityunit", 
            "contract_months",
            "spread_price_calculation",
        ]

        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        return SGXMatchResult(
            match_id=self.generate_match_id(self.rule_number),
            match_type=SGXMatchType.SPREAD,
            confidence=self.confidence,
            trader_trade=trader_trades[0],
            exchange_trade=exchange_trades[0],
            matched_fields=matched_fields,
            rule_order=self.rule_number,
            additional_trader_trades=trader_trades[1:],
            additional_exchange_trades=exchange_trades[1:],
        )


    def get_rule_info(self) -> dict:
        """Get information about this matching rule."""
        return {
            "rule_number": self.rule_number,
            "rule_name": "Spread Match",
            "match_type": SGXMatchType.SPREAD.value,
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