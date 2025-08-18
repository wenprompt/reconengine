"""Spread matching implementation for Rule 2."""

from typing import List, Optional, Dict, Tuple
import logging
import uuid
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..core import UnmatchedPoolManager
from ..config import ConfigManager
from ..normalizers import TradeNormalizer
from .base_matcher import BaseMatcher

logger = logging.getLogger(__name__)


class SpreadMatcher(BaseMatcher):
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
        exchange_spread_groups = self._group_exchange_spreads(exchange_trades, pool_manager)
        
        for trader_group in trader_spread_groups:
            if any(pool_manager.is_trade_matched(trade) for trade in trader_group):
                continue
                
            match_result = self._find_spread_match(trader_group, exchange_spread_groups, pool_manager)
            if match_result:
                matches.append(match_result)
                if not pool_manager.record_match(match_result):
                    logger.error("Failed to record spread match and remove trades from pool")
                else:
                    logger.debug(f"Created spread match: {match_result}")
        
        logger.info(f"Found {len(matches)} spread matches")
        return matches
    

    def _group_trader_spreads(self, trader_trades: List[Trade], pool_manager: UnmatchedPoolManager) -> List[List[Trade]]:
        """Group trader trades into potential spread pairs."""
        spread_groups = []
        trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        for trade in trader_trades:
            if not pool_manager.is_trade_matched(trade):
                # Use product-specific unit defaults for quantity comparison
                default_unit = self.normalizer.get_trader_product_unit_default(trade.product_name)
                quantity_for_grouping = trade.quantity_bbl if default_unit == "bbl" else trade.quantity_mt
                
                # Create grouping key with universal fields using BaseMatcher method
                key = self.create_universal_signature(trade, [trade.product_name, quantity_for_grouping])
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
            trade1.buy_sell != trade2.buy_sell and
            trade1.contract_month != trade2.contract_month and
            ((trade1.spread == "S" or trade2.spread == "S") or (trade1.price == 0 or trade2.price == 0))
        )
    
    def _group_exchange_spreads(self, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager) -> Dict[Tuple, List[Trade]]:
        """Group exchange trades by criteria for spread matching."""
        trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        for trade in exchange_trades:
            if not pool_manager.is_trade_matched(trade):
                # Exchange data uses actual units, so group by the appropriate quantity
                # For consistency with trader grouping, use BBL for brent swap products
                if trade.product_name.lower() in ["brent swap", "brent_swap"]:
                    quantity_for_grouping = trade.quantity_bbl
                else:
                    quantity_for_grouping = trade.quantity_mt
                
                # Create grouping key with universal fields using BaseMatcher method
                key = self.create_universal_signature(trade, [trade.product_name, quantity_for_grouping])
                trade_groups[key].append(trade)
        return trade_groups
    
    def _find_spread_match(self, trader_group: List[Trade], exchange_groups: Dict[Tuple, List[Trade]], pool_manager: UnmatchedPoolManager) -> Optional[MatchResult]:
        """Find spread match for a trader spread group."""
        if len(trader_group) != 2:
            return None
        
        trader_trade1, trader_trade2 = trader_group
        # Use same unit logic as grouping for consistent key generation
        default_unit = self.normalizer.get_trader_product_unit_default(trader_trade1.product_name)
        quantity_for_key = trader_trade1.quantity_bbl if default_unit == "bbl" else trader_trade1.quantity_mt
        
        # Create grouping key with universal fields (same as in grouping methods)
        group_key = self.create_universal_signature(trader_trade1, [trader_trade1.product_name, quantity_for_key])
        
        if group_key not in exchange_groups:
            return None
        
        exchange_candidates = exchange_groups[group_key]
        for i in range(len(exchange_candidates)):
            for j in range(i + 1, len(exchange_candidates)):
                exchange_trade1, exchange_trade2 = exchange_candidates[i], exchange_candidates[j]
                
                if pool_manager.is_trade_matched(exchange_trade1) or pool_manager.is_trade_matched(exchange_trade2):
                    continue
                if any(pool_manager.is_trade_matched(trade) for trade in trader_group):
                    return None
                
                if self._validate_spread_match(trader_group, [exchange_trade1, exchange_trade2]):
                    return self._create_spread_match_result(trader_group, [exchange_trade1, exchange_trade2])
        return None
    
    def _validate_spread_match(self, trader_trades: List[Trade], exchange_trades: List[Trade]) -> bool:
        """Validate that trader and exchange trades form a valid spread match."""
        if len(trader_trades) != 2 or len(exchange_trades) != 2:
            return False
        
        trader_trade1, trader_trade2 = trader_trades
        exchange_trade1, exchange_trade2 = exchange_trades
        
        if exchange_trade1.buy_sell == exchange_trade2.buy_sell or exchange_trade1.contract_month == exchange_trade2.contract_month:
            return False
        
        if {trader_trade1.contract_month, trader_trade2.contract_month} != {exchange_trade1.contract_month, exchange_trade2.contract_month}:
            return False
        
        return self._validate_spread_directions(trader_trades, exchange_trades) and self._validate_spread_prices(trader_trades, exchange_trades)
    
    def _validate_spread_directions(self, trader_trades: List[Trade], exchange_trades: List[Trade]) -> bool:
        """Validate that B/S directions match between trader and exchange spreads."""
        trader_month_bs = {trade.contract_month: trade.buy_sell for trade in trader_trades}
        exchange_month_bs = {trade.contract_month: trade.buy_sell for trade in exchange_trades}
        return all(month in exchange_month_bs and trader_month_bs[month] == exchange_month_bs[month] for month in trader_month_bs)
    
    def _validate_spread_prices(self, trader_trades: List[Trade], exchange_trades: List[Trade]) -> bool:
        """Validate spread price calculation."""
        trader_spread_price = next((t.price for t in trader_trades if t.price != 0), None)
        if trader_spread_price is None:
            return True
        
        exchange_trade1, exchange_trade2 = exchange_trades
        month1_tuple = self.normalizer.get_month_order_tuple(exchange_trade1.contract_month)
        month2_tuple = self.normalizer.get_month_order_tuple(exchange_trade2.contract_month)
        
        if not month1_tuple or not month2_tuple:
            return False

        exchange_spread_price = exchange_trade1.price - exchange_trade2.price if month1_tuple < month2_tuple else exchange_trade2.price - exchange_trade1.price
        return trader_spread_price == exchange_spread_price
    
    def _create_spread_match_result(self, trader_trades: List[Trade], exchange_trades: List[Trade]) -> MatchResult:
        """Create MatchResult for spread match."""
        # Rule-specific matched fields
        rule_specific_fields = ["product_name", "quantity", "contract_months", "spread_price_calculation"]
        
        # Get complete matched fields with universal fields using BaseMatcher method
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)
        
        return MatchResult(
            match_id=f"SPREAD_{uuid.uuid4().hex[:8].upper()}",
            match_type=MatchType.SPREAD,
            confidence=self.confidence,
            trader_trade=trader_trades[0],
            exchange_trade=exchange_trades[0],
            matched_fields=matched_fields,
            differing_fields=[],
            tolerances_applied={},
            rule_order=self.rule_number,
            additional_trader_trades=trader_trades[1:],
            additional_exchange_trades=exchange_trades[1:]
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
                "Price calculation must match (if available)"
            ]
        }