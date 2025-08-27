"""Aggregated spread matcher for Rule 8 - Aggregated spread matching (spread with exchange trade aggregation)."""

import logging
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..config import ConfigManager
from ..normalizers import TradeNormalizer
from ..core import UnmatchedPoolManager
from .multi_leg_base_matcher import MultiLegBaseMatcher

logger = logging.getLogger(__name__)


class AggregatedSpreadMatcher(MultiLegBaseMatcher):
    """Matches aggregated spread trades where trader spreads correspond to multiple exchange trades per contract month.

    Handles Rule 8: Aggregated Spread Match Rules
    - Two-phase process: aggregation then spread matching
    - Trader shows spread pattern (price, 0.00) with opposite B/S directions
    - Exchange shows multiple trades per contract month requiring aggregation
    - After aggregation, standard spread matching logic applies
    """

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the aggregated spread matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
            normalizer: Trade normalizer for data processing
        """
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 9
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        logger.info(f"Initialized AggregatedSpreadMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find aggregated spread matches between trader and exchange data.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of aggregated spread matches found
        """
        logger.info("Starting aggregated spread matching (Rule 8)")
        
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()
        
        logger.info(f"Processing {len(trader_trades)} trader trades against {len(exchange_trades)} exchange trades")
        
        # Find trader spread patterns (price/0.00 pairs with opposite B/S)
        trader_spread_pairs = self._find_trader_spread_pairs(trader_trades, pool_manager)
        
        if not trader_spread_pairs:
            logger.debug("No trader spread pairs found")
            return []
        
        logger.info(f"Found {len(trader_spread_pairs)} trader spread pairs to process")
        
        # For each trader spread pair, try to find matching aggregated exchange trades
        for spread_pair in trader_spread_pairs:
            match = self._find_aggregated_spread_match(spread_pair, exchange_trades, pool_manager)
            if match:
                matches.append(match)
                # Record the match to remove trades from pool
                pool_manager.record_match(match)
                logger.info(f"Found aggregated spread match: {match.match_id}")
        
        logger.info(f"Found {len(matches)} aggregated spread matches")
        return matches

    def _find_trader_spread_pairs(self, trader_trades: List[Trade], pool_manager: UnmatchedPoolManager) -> List[Tuple[Trade, Trade]]:
        """Find trader spread patterns using enhanced Tier 3 logic.
        
        Args:
            trader_trades: List of trader trades to analyze
            pool_manager: Pool manager to check if trades are matched
            
        Returns:
            List of trader spread pairs (trade_with_price, trade_with_zero_price)
        """
        spread_pairs = []
        
        # Use enhanced grouping logic similar to SpreadMatcher Tier 3
        trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        
        for trade in trader_trades:
            if pool_manager.is_trade_matched(trade):
                continue
            
            # Use consistent quantity grouping logic from MultiLegBaseMatcher
            quantity_for_grouping = self._get_quantity_for_grouping(trade, self.normalizer)
            
            # Create grouping key with universal fields using MultiLegBaseMatcher method
            group_key = self.create_universal_signature(
                trade, [trade.product_name, quantity_for_grouping]
            )
            trade_groups[group_key].append(trade)
        
        # Look for spread patterns within each group using enhanced validation
        for group_key, group_trades in trade_groups.items():
            if len(group_trades) < 2:
                continue
            
            # Find spread pairs using shared validation logic
            for i in range(len(group_trades)):
                for j in range(i + 1, len(group_trades)):
                    trade1, trade2 = group_trades[i], group_trades[j]
                    
                    # Use MultiLegBaseMatcher validation for consistency
                    if self.validate_spread_pair_characteristics(trade1, trade2, self.normalizer):
                        # Additional check for aggregated spread pattern (exactly one price = 0)
                        if self._is_aggregated_spread_pattern(trade1, trade2):
                            # Order so that trade with non-zero price comes first
                            if trade1.price != Decimal("0"):
                                spread_pairs.append((trade1, trade2))
                            else:
                                spread_pairs.append((trade2, trade1))
                            
                            logger.debug(f"Found trader spread pair: {trade1.trade_id} + {trade2.trade_id}")
                            break  # Only take one pair per trade
        
        return spread_pairs

    def _is_aggregated_spread_pattern(self, trade1: Trade, trade2: Trade) -> bool:
        """Check if two trades form an aggregated spread pattern.
        
        An aggregated spread pattern requires:
        - Opposite B/S directions (spread requirement)
        - Different contract months (spread requirement) 
        - Exactly one trade with price = 0 (the reference leg)
        - One trade with any price (positive, negative, or zero - the spread price)
        
        Args:
            trade1: First trade
            trade2: Second trade
            
        Returns:
            True if trades form aggregated spread pattern
        """
        # Must have opposite B/S directions (spread requirement)
        if trade1.buy_sell == trade2.buy_sell:
            return False
        
        # Must have different contract months (spread requirement)
        if trade1.contract_month == trade2.contract_month:
            return False
        
        # Aggregated spread pattern: exactly one trade must have price = 0 (the reference leg)
        # The other trade has the spread price (can be positive, negative, or even zero)
        prices = [trade1.price, trade2.price]
        zero_count = sum(1 for p in prices if p == Decimal("0"))
        
        return zero_count == 1

    def _is_valid_spread_pair(self, trade1: Trade, trade2: Trade) -> bool:
        """Check if two trades form a valid spread pair (deprecated - use MultiLegBaseMatcher validation).
        
        This method is kept for compatibility but the enhanced validation logic
        is now handled by validate_spread_pair_characteristics() from MultiLegBaseMatcher.
        
        Args:
            trade1: First trade
            trade2: Second trade
            
        Returns:
            True if trades form valid spread pattern
        """
        # Use the enhanced validation from MultiLegBaseMatcher
        return self.validate_spread_pair_characteristics(trade1, trade2, self.normalizer)

    def _find_aggregated_spread_match(
        self, 
        trader_spread_pair: Tuple[Trade, Trade], 
        exchange_trades: List[Trade],
        pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
        """Find aggregated exchange trades that match the trader spread pair.
        
        Args:
            trader_spread_pair: Tuple of (price_trade, zero_price_trade)
            exchange_trades: List of exchange trades to search
            pool_manager: Pool manager to check trade availability
            
        Returns:
            MatchResult if valid aggregated spread match found
        """
        price_trade, zero_price_trade = trader_spread_pair
        
        # Phase 1: Aggregate exchange trades by contract month using universal field validation
        aggregated_positions = self._aggregate_exchange_trades_by_contract(
            exchange_trades, pool_manager, price_trade.product_name, price_trade
        )
        
        if not aggregated_positions:
            return None
        
        # Phase 2: Find matching aggregated positions for both contract months
        price_contract_matches = aggregated_positions.get(price_trade.contract_month, [])
        zero_contract_matches = aggregated_positions.get(zero_price_trade.contract_month, [])
        
        # Try all combinations of aggregated positions
        for price_agg in price_contract_matches:
            for zero_agg in zero_contract_matches:
                if self._validate_aggregated_spread_match(
                    trader_spread_pair, price_agg, zero_agg
                ):
                    return self._create_aggregated_spread_match_result(
                        trader_spread_pair, price_agg, zero_agg
                    )
        
        return None

    def _aggregate_exchange_trades_by_contract(
        self, 
        exchange_trades: List[Trade], 
        pool_manager: UnmatchedPoolManager,
        target_product: str,
        reference_trader_trade: Trade
    ) -> Dict[str, List[Tuple[List[Trade], Decimal, Decimal]]]:
        """Aggregate exchange trades by contract month and characteristics.
        
        Args:
            exchange_trades: Exchange trades to aggregate
            pool_manager: Pool manager to check availability
            target_product: Product name to filter by
            reference_trader_trade: Reference trader trade for universal field validation
            
        Returns:
            Dict mapping contract_month -> list of (trades_list, total_quantity, price)
        """
        # Group trades by aggregation characteristics
        aggregation_groups = defaultdict(list)
        
        for trade in exchange_trades:
            if pool_manager.is_trade_matched(trade):
                continue
            
            # Only consider trades for the target product with matching universal fields
            if (trade.product_name != target_product or 
                not self.validate_universal_fields(reference_trader_trade, trade)):
                continue
            
            # Group by aggregation characteristics (contract, price, B/S)
            # Note: universal fields are already validated above
            group_key = (
                trade.contract_month,
                trade.price,
                trade.buy_sell
            )
            aggregation_groups[group_key].append(trade)
        
        # Create aggregated positions per contract month
        aggregated_by_contract: Dict[str, List[Tuple[List[Trade], Decimal, Decimal]]] = defaultdict(list)
        
        for (contract_month, price, buy_sell), trades_group in aggregation_groups.items():
            # Calculate total quantity for this aggregation
            total_quantity = Decimal(sum(trade.quantity_mt for trade in trades_group))
            
            # Store as (trades_list, total_quantity, price)
            aggregated_position = (trades_group, total_quantity, price)
            aggregated_by_contract[contract_month].append(aggregated_position)
        
        return dict(aggregated_by_contract)

    def _validate_aggregated_spread_match(
        self,
        trader_spread_pair: Tuple[Trade, Trade],
        price_aggregation: Tuple[List[Trade], Decimal, Decimal],
        zero_aggregation: Tuple[List[Trade], Decimal, Decimal]
    ) -> bool:
        """Validate that aggregated exchange positions match trader spread pair.
        
        Args:
            trader_spread_pair: Tuple of trader spread trades
            price_aggregation: Aggregated exchange position for price leg
            zero_aggregation: Aggregated exchange position for zero price leg
            
        Returns:
            True if valid aggregated spread match
        """
        price_trade, zero_price_trade = trader_spread_pair
        price_ex_trades, price_ex_qty, price_ex_price = price_aggregation
        zero_ex_trades, zero_ex_qty, zero_ex_price = zero_aggregation
        
        # Validate quantities match
        if (price_ex_qty != price_trade.quantity_mt or 
            zero_ex_qty != zero_price_trade.quantity_mt):
            logger.debug("Quantity mismatch in aggregated spread validation")
            return False
        
        # Validate B/S directions match
        if (price_ex_trades[0].buy_sell != price_trade.buy_sell or
            zero_ex_trades[0].buy_sell != zero_price_trade.buy_sell):
            logger.debug("B/S direction mismatch in aggregated spread validation")
            return False
        
        # Validate universal fields using BaseMatcher
        if not self.validate_universal_fields(price_trade, price_ex_trades[0]):
            logger.debug("Universal fields validation failed for price leg")
            return False
        
        if not self.validate_universal_fields(zero_price_trade, zero_ex_trades[0]):
            logger.debug("Universal fields validation failed for zero price leg")
            return False
        
        # Validate price differential calculation
        expected_spread_price = price_ex_price - zero_ex_price
        if price_trade.price != expected_spread_price:
            logger.debug(
                f"Price differential mismatch: expected {expected_spread_price}, "
                f"got {price_trade.price}"
            )
            return False
        
        logger.debug("Aggregated spread validation passed")
        return True

    def _create_aggregated_spread_match_result(
        self,
        trader_spread_pair: Tuple[Trade, Trade],
        price_aggregation: Tuple[List[Trade], Decimal, Decimal],
        zero_aggregation: Tuple[List[Trade], Decimal, Decimal]
    ) -> MatchResult:
        """Create match result for aggregated spread match.
        
        Args:
            trader_spread_pair: Tuple of trader spread trades
            price_aggregation: Aggregated exchange position for price leg
            zero_aggregation: Aggregated exchange position for zero price leg
            
        Returns:
            MatchResult for the aggregated spread match
        """
        price_trade, zero_price_trade = trader_spread_pair
        price_ex_trades, _, _ = price_aggregation
        zero_ex_trades, _, _ = zero_aggregation
        
        # Generate unique match ID
        match_id = self.generate_match_id(self.rule_number, "AGG_SPREAD")
        
        # Rule-specific fields that match
        rule_specific_fields = [
            "product_name",
            "contract_month_spread",
            "quantity", 
            "buy_sell_spread",
            "price_differential"
        ]
        
        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)
        
        # All exchange trades involved
        all_exchange_trades = price_ex_trades + zero_ex_trades
        
        return MatchResult(
            match_id=match_id,
            match_type=MatchType.AGGREGATED_SPREAD,
            confidence=self.confidence,
            trader_trade=price_trade,  # Primary trader trade (with non-zero price)
            exchange_trade=all_exchange_trades[0],  # Primary exchange trade
            additional_trader_trades=[zero_price_trade],  # Zero price trader trade
            additional_exchange_trades=all_exchange_trades[1:],  # Remaining exchange trades
            matched_fields=matched_fields,
            tolerances_applied={
                "aggregation": f"{len(price_ex_trades)} + {len(zero_ex_trades)} exchange trades aggregated",
                "price_differential": "exact"
            },
            rule_order=self.rule_number
        )

    def get_rule_info(self) -> dict:
        """Get information about this matching rule.

        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Aggregated Spread Match",
            "match_type": MatchType.AGGREGATED_SPREAD.value,
            "confidence": float(self.confidence),
            "description": "Two-phase matching: aggregates exchange trades then applies spread matching logic",
            "requirements": [
                "Trader must show spread pattern: one leg with price, other with price=0.00",
                "Trader spread legs must have opposite B/S directions and different contract months",
                "Exchange must have multiple trades per contract month requiring aggregation",
                "Aggregated exchange quantities must match trader spread quantities exactly",
                "Price differential must match exactly after aggregation",
                "All trades must have matching universal fields"
            ]
        }