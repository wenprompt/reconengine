"""Fly matching implementation for Rule 6."""

from typing import List, Optional, Dict, Tuple, TypeAlias
from decimal import Decimal
import logging
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..core import UnmatchedPoolManager
from ..config import ConfigManager
from ..normalizers import TradeNormalizer
from .base_matcher import BaseMatcher
from ..utils.trade_helpers import get_month_order_tuple

logger = logging.getLogger(__name__)

# Type alias for month order tuple (year, month_number)
MonthKey: TypeAlias = Tuple[int, int]


class FlyMatcher(BaseMatcher):
    """Implements Rule 6: Fly (butterfly spread) matching."""

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the fly matcher."""
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 6
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        # Initialize per-instance cache to avoid memory leaks from @lru_cache
        self._month_cache: Dict[str, MonthKey] = {}
        logger.info(f"Initialized FlyMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find all fly matches using dealid-based grouping."""
        logger.info("Starting fly matching (Rule 6) - Dealid-based grouping")
        matches = []

        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Find fly groups: trader by 'S' indicator, exchange by dealid only
        trader_fly_groups = self._find_trader_fly_groups(trader_trades, pool_manager)
        exchange_fly_groups = self._find_exchange_fly_groups(
            exchange_trades, pool_manager
        )

        logger.debug(f"Found {len(trader_fly_groups)} trader fly groups")
        logger.debug(f"Found {len(exchange_fly_groups)} exchange fly groups")

        # Match trader fly groups with exchange fly groups
        for trader_group in trader_fly_groups:
            # Skip if any trader trade is already matched
            if any(pool_manager.is_trade_matched(trade) for trade in trader_group):
                continue

            match_result = self._match_fly_group(
                trader_group, exchange_fly_groups, pool_manager
            )
            if match_result:
                matches.append(match_result)

                # Record the match in the pool manager
                if not pool_manager.record_match(match_result):
                    logger.error(
                        "Failed to record fly match and remove trades from pool"
                    )
                else:
                    logger.debug(f"Created fly match: {match_result.match_id}")

        logger.info(f"Found {len(matches)} fly matches")
        return matches

    def _find_trader_fly_groups(
        self, trader_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> List[List[Trade]]:
        """Find trader fly groups with spread indicators using optimized contract month-based grouping."""
        fly_groups = []

        # Group trades by product and universal fields
        trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        for trade in trader_trades:
            if not pool_manager.is_trade_matched(trade):
                # Check for spread indicator 'S' (fly trades usually have this)
                if trade.spread and str(trade.spread).upper().strip() == "S":
                    key = self.create_universal_signature(trade, [trade.product_name])
                    trade_groups[key].append(trade)

        # Find fly patterns using optimized month-based grouping
        for trades in trade_groups.values():
            if len(trades) >= 3:
                fly_groups.extend(self._find_fly_patterns_by_month_grouping(trades))

        return fly_groups

    def _find_fly_patterns_by_month_grouping(
        self, trades: List[Trade]
    ) -> List[List[Trade]]:
        """Find fly patterns using 3-SUM variant approach - O(m³ + n²) complexity.

        This optimized implementation:
        1. Pre-builds quantity indexes for O(1) middle leg lookups
        2. Iterates through month triplets (O(m³), m is typically small)
        3. Uses hash maps for efficient quantity-based trade lookups
        4. Applies expensive validations last (fail-fast principle)

        Much more efficient than the previous 6-nested-loop O(n × m³) approach.
        """
        fly_patterns: List[List[Trade]] = []

        # Group trades by contract month - O(n)
        month_groups: Dict[str, List[Trade]] = defaultdict(list)
        for trade in trades:
            month_groups[trade.contract_month].append(trade)

        # Get sorted months - O(m log m) where m = unique months
        months = list(month_groups.keys())
        if len(months) < 3:
            return fly_patterns

        sorted_months = self._sort_months_chronologically(months)

        # Pre-build quantity lookups for each month for O(1) access - O(n)
        month_qty_lookups: Dict[str, Dict[Decimal, List[Trade]]] = {
            month: defaultdict(list) for month in sorted_months
        }
        for month, month_trades in month_groups.items():
            for trade in month_trades:
                month_qty_lookups[month][trade.quantity_mt].append(trade)

        # Iterate through all combinations of three distinct months (i < j < k) - O(m³)
        for i in range(len(sorted_months)):
            for j in range(i + 1, len(sorted_months)):
                for k in range(j + 1, len(sorted_months)):
                    month1, month2, month3 = (
                        sorted_months[i],
                        sorted_months[j],
                        sorted_months[k],
                    )

                    # Iterate through trades of the outer legs to find middle leg match - O(n²/m²)
                    for outer1_trade in month_groups[month1]:
                        for outer2_trade in month_groups[month3]:
                            required_middle_qty = (
                                outer1_trade.quantity_mt + outer2_trade.quantity_mt
                            )

                            # Find middle leg trades with required quantity - O(1) lookup
                            if required_middle_qty in month_qty_lookups[month2]:
                                for middle_trade in month_qty_lookups[month2][
                                    required_middle_qty
                                ]:
                                    candidate = [
                                        outer1_trade,
                                        middle_trade,
                                        outer2_trade,
                                    ]

                                    # Apply expensive validation last (fail-fast principle)
                                    if self._is_valid_fly_group(candidate):
                                        fly_patterns.append(candidate)

        return fly_patterns

    def _is_valid_fly_group(self, trades: List[Trade]) -> bool:
        """Unified fly group validation for both trader and exchange trades.

        Requirements:
        - Exactly 3 trades with same product
        - 3 different contract months
        - Quantity relationship: X + Z = Y (outer legs sum = middle leg)
        - Direction pattern: X and Z same direction, Y opposite
        - Universal fields match
        """
        if len(trades) != 3:
            return False

        # Sort trades by contract month to get X (earliest), Y (middle), Z (latest)
        sorted_trades = self._sort_trades_by_contract_month(trades)
        if not sorted_trades:
            return False

        trade_x, trade_y, trade_z = sorted_trades

        # FAST VALIDATIONS FIRST (fail fast principle)

        # 1. Quantity relationship: X + Z = Y (fastest check)
        if trade_x.quantity_mt + trade_z.quantity_mt != trade_y.quantity_mt:
            return False

        # 2. Contract month uniqueness (fast set operation)
        months = {
            trade_x.contract_month,
            trade_y.contract_month,
            trade_z.contract_month,
        }
        if len(months) != 3:
            return False

        # 3. Product matching (string comparison)
        if not (trade_x.product_name == trade_y.product_name == trade_z.product_name):
            return False

        # 4. Direction pattern (string comparison)
        if trade_x.buy_sell != trade_z.buy_sell or trade_x.buy_sell == trade_y.buy_sell:
            return False

        # 5. Universal fields (slowest - do last)
        if not (
            self.validate_universal_fields(trade_x, trade_y)
            and self.validate_universal_fields(trade_x, trade_z)
        ):
            return False

        return True

    def _is_trader_fly_group(self, trades: List[Trade]) -> bool:
        """Check if three trader trades form a fly group."""
        return self._is_valid_fly_group(trades)

    def _find_exchange_fly_groups(
        self, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> List[List[Trade]]:
        """Find exchange fly groups using dealid-based grouping."""
        fly_groups = []

        # Group trades by dealid
        dealid_groups: Dict[str, List[Trade]] = defaultdict(list)
        for trade in exchange_trades:
            if pool_manager.is_trade_matched(trade):
                continue

            # Extract dealid from raw data
            dealid = trade.raw_data.get("dealid")

            if dealid and str(dealid).strip():
                dealid_str = str(dealid).strip()
                if dealid_str.lower() not in ["nan", "none", ""]:
                    dealid_groups[dealid_str].append(trade)

        # Find valid fly groups within each dealid group
        for dealid_str, trades_in_group in dealid_groups.items():
            # A fly group must have exactly 3 legs
            if len(trades_in_group) == 3:
                if self._is_exchange_fly_group(trades_in_group):
                    fly_groups.append(trades_in_group)
                    logger.debug(
                        f"Found dealid fly group: {[t.trade_id for t in trades_in_group]} (dealid: {dealid_str})"
                    )
            elif len(trades_in_group) > 3:
                # Multiple legs - try to find valid 3-trade combinations
                for i in range(len(trades_in_group)):
                    for j in range(i + 1, len(trades_in_group)):
                        for k in range(j + 1, len(trades_in_group)):
                            potential_group = [
                                trades_in_group[i],
                                trades_in_group[j],
                                trades_in_group[k],
                            ]
                            if self._is_exchange_fly_group(potential_group):
                                fly_groups.append(potential_group)
                                logger.debug(
                                    f"Found dealid fly group: {[t.trade_id for t in potential_group]} (dealid: {dealid_str})"
                                )

        return fly_groups

    def _is_exchange_fly_group(self, trades: List[Trade]) -> bool:
        """Check if three exchange trades form a valid fly group."""
        return self._is_valid_fly_group(trades)

    def _get_month_order_tuple_cached(self, contract_month: str) -> Optional[MonthKey]:
        """Cache month parsing for better performance (per-instance cache)."""
        # Check if already cached
        cached = self._month_cache.get(contract_month)
        if cached is not None:
            return cached
        
        # Not cached, compute it
        normalized = self.normalizer.normalize_contract_month(contract_month)
        month_key = get_month_order_tuple(normalized)
        
        # Store in cache if valid
        if month_key is not None:
            self._month_cache[contract_month] = month_key
        
        return month_key

    def _sort_months_chronologically(self, months: List[str]) -> List[str]:
        """Sort months using cached month tuple conversion."""
        month_tuples = [
            (month, self._get_month_order_tuple_cached(month)) for month in months
        ]
        # Filter out invalid months and sort
        valid_month_tuples = [
            (month, tuple_val)
            for month, tuple_val in month_tuples
            if tuple_val is not None
        ]
        valid_month_tuples.sort(key=lambda x: x[1])
        return [month for month, _ in valid_month_tuples]

    def _sort_trades_by_contract_month(
        self, trades: List[Trade]
    ) -> Optional[List[Trade]]:
        """Sort 3 trades by contract month (earliest to latest)."""
        if len(trades) != 3:
            return None

        # Get month tuples for sorting using cached method
        trade_months = []
        for trade in trades:
            month_tuple = self._get_month_order_tuple_cached(trade.contract_month)
            if not month_tuple:
                return None
            trade_months.append((trade, month_tuple))

        # Sort by month tuple
        trade_months.sort(key=lambda x: x[1])

        return [trade for trade, _ in trade_months]

    def _match_fly_group(
        self,
        trader_group: List[Trade],
        exchange_fly_groups: List[List[Trade]],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[MatchResult]:
        """Match a trader fly group with exchange fly groups."""
        if len(trader_group) != 3:
            return None

        # Try to match with each exchange fly group
        for exchange_group in exchange_fly_groups:
            if len(exchange_group) != 3:
                continue

            # Skip if any exchange trade is already matched
            if any(pool_manager.is_trade_matched(trade) for trade in exchange_group):
                continue

            # Validate this is a valid fly match
            if self._validate_fly_match(trader_group, exchange_group):
                return self._create_fly_match_result(trader_group, exchange_group)

        return None

    def _validate_fly_match(
        self, trader_trades: List[Trade], exchange_trades: List[Trade]
    ) -> bool:
        """Validate that trader and exchange trades form a valid fly match."""
        if len(trader_trades) != 3 or len(exchange_trades) != 3:
            return False

        # Sort both groups by contract month for comparison
        sorted_trader = self._sort_trades_by_contract_month(trader_trades)
        sorted_exchange = self._sort_trades_by_contract_month(exchange_trades)

        if not sorted_trader or not sorted_exchange:
            return False

        # Validate all trades have the same product
        trader_products = {t.product_name for t in trader_trades}
        exchange_products = {t.product_name for t in exchange_trades}

        if (
            len(trader_products) != 1
            or len(exchange_products) != 1
            or trader_products != exchange_products
        ):
            return False

        # Validate contract months match between trader and exchange
        trader_months = {t.contract_month for t in trader_trades}
        exchange_months = {t.contract_month for t in exchange_trades}
        if trader_months != exchange_months:
            return False

        # Validate B/S directions and fly price calculation
        return self._validate_fly_directions(
            sorted_trader, sorted_exchange
        ) and self._validate_fly_price_calculation(sorted_trader, sorted_exchange)

    def _validate_fly_directions(
        self, trader_trades: List[Trade], exchange_trades: List[Trade]
    ) -> bool:
        """Validate that B/S directions match between trader and exchange fly patterns."""
        if len(trader_trades) != 3 or len(exchange_trades) != 3:
            return False

        # Create month-to-direction mappings
        trader_month_bs = {
            trade.contract_month: trade.buy_sell for trade in trader_trades
        }
        exchange_month_bs = {
            trade.contract_month: trade.buy_sell for trade in exchange_trades
        }

        # Check that directions match for each contract month
        return all(
            month in exchange_month_bs
            and trader_month_bs[month] == exchange_month_bs[month]
            for month in trader_month_bs
        )

    def _validate_fly_price_calculation(
        self, trader_trades: List[Trade], exchange_trades: List[Trade]
    ) -> bool:
        """Validate fly price calculation between trader and exchange trades."""
        # For trader fly: find the non-zero price (usually on earliest month)
        trader_prices = [t.price for t in trader_trades]
        trader_fly_price = next((p for p in trader_prices if p != 0), Decimal("0"))

        # Calculate exchange fly price: (X_price - Y_price) + (Z_price - Y_price)
        # where X is earliest, Y is middle, Z is latest
        exchange_x, exchange_y, exchange_z = (
            exchange_trades  # Already sorted by contract month
        )

        # Fly price calculation: (X - Y) + (Z - Y) = X + Z - 2*Y
        exchange_fly_price = (exchange_x.price - exchange_y.price) + (
            exchange_z.price - exchange_y.price
        )

        logger.debug(
            f"Fly price validation: trader={trader_fly_price}, "
            f"exchange=({exchange_x.price} - {exchange_y.price}) + ({exchange_z.price} - {exchange_y.price}) = {exchange_fly_price}"
        )

        return trader_fly_price == exchange_fly_price

    def _create_fly_match_result(
        self,
        trader_trades: List[Trade],
        exchange_trades: List[Trade],
    ) -> MatchResult:
        """Create MatchResult for fly match."""
        # Rule-specific matched fields
        rule_specific_fields = [
            "product_name",
            "quantity_relationship",
            "direction_pattern",
            "contract_months",
            "fly_price_calculation",
        ]

        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        return MatchResult(
            match_id=self.generate_match_id(self.rule_number, "FLY"),
            match_type=MatchType.FLY,
            confidence=self.confidence,
            trader_trade=trader_trades[0],  # Primary trade (earliest month)
            exchange_trade=exchange_trades[0],  # Primary trade (earliest month)
            matched_fields=matched_fields,
            rule_order=self.rule_number,
            additional_trader_trades=trader_trades[1:],  # Middle and latest months
            additional_exchange_trades=exchange_trades[1:],  # Middle and latest months
        )

    def get_rule_info(self) -> dict:
        """Get information about this matching rule."""
        return {
            "rule_number": self.rule_number,
            "rule_name": "Fly Match",
            "match_type": MatchType.FLY.value,
            "confidence": float(self.confidence),
            "description": "Matches butterfly spread trades (3-leg buy-sell-buy pattern)",
            "requirements": [
                "Both sources must have 3 trades each (fly legs)",
                "Same product and universal fields",
                "3 different contract months in chronological order",
                "Quantity relationship: outer legs sum = middle leg (X + Z = Y)",
                "Direction pattern: outer legs same direction, middle leg opposite",
                "Fly price calculation must match",
                "Exchange trades must share same dealid",
            ],
        }
