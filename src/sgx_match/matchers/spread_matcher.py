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
from ..utils.trade_helpers import get_month_order_tuple, calculate_spread_price

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
        """Find all spread matches using Tier 1 approach."""
        logger.info("Starting spread matching (Rule 2) - Tier 1")
        matches = []
        
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Tier 1: Simple spread pair matching
        trader_spread_pairs = self._find_trader_spread_pairs(trader_trades, pool_manager)
        exchange_spread_pairs = self._find_exchange_spread_pairs(exchange_trades, pool_manager)
        
        logger.debug(f"Found {len(trader_spread_pairs)} trader spread pairs")
        logger.debug(f"Found {len(exchange_spread_pairs)} exchange spread pairs")

        # Match trader spread pairs with exchange spread pairs
        for trader_pair in trader_spread_pairs:
            # Skip if any trader trade is already matched
            if any(not pool_manager.is_unmatched(trade.trade_id, SGXTradeSource.TRADER) for trade in trader_pair):
                continue

            match_result = self._match_spread_pair(trader_pair, exchange_spread_pairs, pool_manager)
            if match_result:
                matches.append(match_result)
                
                # Mark all trades as matched
                for trade in trader_pair:
                    pool_manager.mark_as_matched(trade.trade_id, SGXTradeSource.TRADER, "spread")
                
                for trade in [match_result.exchange_trade] + match_result.additional_exchange_trades:
                    pool_manager.mark_as_matched(trade.trade_id, SGXTradeSource.EXCHANGE, "spread")
                
                # Record in audit trail
                pool_manager.record_match(
                    match_result.trader_trade.trade_id,
                    match_result.exchange_trade.trade_id,
                    match_result.match_type.value
                )
                
                logger.debug(f"Created spread match: {match_result.match_id}")

        logger.info(f"Found {len(matches)} spread matches")
        return matches

    def _find_trader_spread_pairs(self, trader_trades: List[SGXTrade], pool_manager: SGXUnmatchedPool) -> List[List[SGXTrade]]:
        """Find trader spread pairs with spread indicators."""
        spread_pairs = []
        
        # Group trades by product and quantity
        trade_groups: Dict[Tuple, List[SGXTrade]] = defaultdict(list)
        for trade in trader_trades:
            if pool_manager.is_unmatched(trade.trade_id, SGXTradeSource.TRADER):
                key = self.create_universal_signature(trade, [trade.product_name, trade.quantity_units])
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
        2. New: Identical spread price pattern (both trades have same non-zero price)
        """
        # Basic requirements: opposite B/S directions and different contract months
        if (trade1.buy_sell == trade2.buy_sell or 
            trade1.contract_month == trade2.contract_month):
            return False
        
        # Pattern 1: Look for spread indicators in trader data (original pattern)
        has_spread_indicator = (
            (trade1.spread and 'S' in str(trade1.spread).upper()) or
            (trade2.spread and 'S' in str(trade2.spread).upper())
        )
        
        # Pattern 2: Both trades have identical non-zero spread price (new pattern)
        has_identical_spread_price = (
            trade1.price != 0 and 
            trade2.price != 0 and 
            trade1.price == trade2.price
        )
        
        return has_spread_indicator or has_identical_spread_price

    def _find_exchange_spread_pairs(self, exchange_trades: List[SGXTrade], pool_manager: SGXUnmatchedPool) -> List[List[SGXTrade]]:
        """Find exchange spread pairs."""
        spread_pairs = []
        
        # Group trades by product and quantity
        trade_groups: Dict[Tuple, List[SGXTrade]] = defaultdict(list)
        for trade in exchange_trades:
            if pool_manager.is_unmatched(trade.trade_id, SGXTradeSource.EXCHANGE):
                key = self.create_universal_signature(trade, [trade.product_name, trade.quantity_units])
                trade_groups[key].append(trade)
        
        # Find pairs within each group
        for trades in trade_groups.values():
            if len(trades) >= 2:
                for i in range(len(trades)):
                    for j in range(i + 1, len(trades)):
                        if self.validate_spread_pair_characteristics(trades[i], trades[j]):
                            spread_pairs.append([trades[i], trades[j]])
        
        return spread_pairs

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
            if any(not pool_manager.is_unmatched(trade.trade_id, SGXTradeSource.EXCHANGE) 
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
        # For trader spreads: find the non-zero price (if any) as the spread price
        trader_prices = [t.price for t in trader_trades]
        trader_spread_price = next((p for p in trader_prices if p != 0), Decimal("0"))

        # Calculate exchange spread price (earlier month - later month)
        exchange_trade1, exchange_trade2 = exchange_trades
        
        exchange_spread_price = calculate_spread_price(
            exchange_trade1.price, exchange_trade1.contract_month,
            exchange_trade2.price, exchange_trade2.contract_month
        )
        
        if exchange_spread_price is None:
            return False

        return trader_spread_price == exchange_spread_price

    def _create_spread_match_result(
        self,
        trader_trades: List[SGXTrade],
        exchange_trades: List[SGXTrade],
    ) -> SGXMatchResult:
        """Create SGXMatchResult for spread match."""
        # Rule-specific matched fields
        rule_specific_fields = [
            "product_name",
            "quantity_units", 
            "contract_months",
            "spread_price_calculation",
        ]

        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        return SGXMatchResult(
            match_id=self._generate_match_id(),
            match_type=SGXMatchType.SPREAD,
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

    def _generate_match_id(self) -> str:
        """Generate unique match ID for spread matches."""
        import uuid
        prefix = self.config_manager.get_match_id_prefix()
        uuid_suffix = uuid.uuid4().hex[:6]
        return f"{prefix}_SPREAD_{self.rule_number}_{uuid_suffix}"

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