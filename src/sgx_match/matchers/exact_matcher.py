"""Exact matching implementation for SGX Rule 1."""

from typing import List, Dict
import logging
from collections import defaultdict

from ..models import SGXTrade, SGXTradeSource, SGXMatchResult, SGXMatchType
from ..core import SGXUnmatchedPool
from ..config import SGXConfigManager
from .base_matcher import BaseMatcher

logger = logging.getLogger(__name__)


class ExactMatcher(BaseMatcher):
    """Implements Rule 1: Exact matching on key fields.
    
    From SGX rules.md:
    - ProductName (exact match, e.g., "FE")
    - ContractMonth (exact match, e.g., "Oct25")
    - QuantityUnits (exact match, e.g., 15000.0)
    - Price (exact match, e.g., 101.65)
    - B/S (exact match, "B" or "S")
    - BrokerGroupId (universal field - exact match)
    - ExchClearingAcctId (universal field - exact match)
    
    Confidence: 100%
    """
    
    def __init__(self, config_manager: SGXConfigManager):
        """Initialize the SGX exact matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
        """
        super().__init__(config_manager)
        self.rule_number = 1
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        logger.info(f"Initialized ExactMatcher with {self.confidence}% confidence")
    
    def find_matches(self, pool_manager: SGXUnmatchedPool) -> List[SGXMatchResult]:
        """Find all exact matches between unmatched trader and exchange trades.
        
        Args:
            pool_manager: Pool manager containing unmatched SGX trades
            
        Returns:
            List of SGXMatchResult objects for exact matches found
        """
        logger.info("Starting exact matching (Rule 1)")
        matches = []
        
        # Get unmatched trades
        trader_trades = pool_manager.get_unmatched_trades(SGXTradeSource.TRADER)
        exchange_trades = pool_manager.get_unmatched_trades(SGXTradeSource.EXCHANGE)
        
        logger.info(f"Processing {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades")
        
        # Create index for exchange trades for efficient lookup
        exchange_index = self._create_exchange_index(exchange_trades)
        
        # Find matches
        for trader_trade in trader_trades:
            signature = self._create_matching_signature(trader_trade)
            
            # Skip if no matching signature exists
            if signature not in exchange_index:
                continue
                
            exchange_trades_list = exchange_index[signature]
            
            # Iterate backwards for safe removal
            for i in range(len(exchange_trades_list) - 1, -1, -1):
                exchange_trade = exchange_trades_list[i]
                
                # Verify exchange trade is still unmatched
                if not pool_manager.is_unmatched(exchange_trade.internal_trade_id, SGXTradeSource.EXCHANGE):
                    continue
                    
                match_result = self._create_match_result(trader_trade, exchange_trade)
                
                # Atomically record the match
                if pool_manager.record_match(match_result):
                    matches.append(match_result)
                    logger.debug(f"Created exact match: {trader_trade.display_id} ↔ {exchange_trade.display_id}")
                    
                    # Remove matched trade from index to prevent re-checking
                    del exchange_trades_list[i]
                    if not exchange_trades_list:
                        del exchange_index[signature]
                    
                    # Break after successful match
                    break
                else:
                    logger.warning(f"Failed to atomically record match for {trader_trade.display_id} ↔ {exchange_trade.display_id}")
                    # Don't break - try next exchange trade
        
        logger.info(f"Exact matching completed. Found {len(matches)} matches")
        return matches
    
    def _create_exchange_index(self, exchange_trades: List[SGXTrade]) -> Dict[tuple, List[SGXTrade]]:
        """Create index of exchange trades by matching signature for efficient lookup.
        
        Args:
            exchange_trades: List of exchange trades to index
            
        Returns:
            Dict mapping signatures to lists of matching exchange trades
        """
        index = defaultdict(list)
        
        for trade in exchange_trades:
            signature = self._create_matching_signature(trade)
            index[signature].append(trade)
            
        logger.debug(f"Created exchange index with {len(index)} unique signatures")
        return dict(index)
    
    def _create_matching_signature(self, trade: SGXTrade) -> tuple:
        """Create a signature for exact matching.
        
        Args:
            trade: Trade to create signature for
            
        Returns:
            Tuple representing the exact match signature
        """
        # Rule-specific fields for exact matching
        rule_fields = [
            trade.product_name,
            trade.contract_month,
            trade.quantityunit,
            trade.price,
            trade.buy_sell
        ]
        
        # Add universal fields using base class method
        return self.create_universal_signature(trade, rule_fields)
    
    
    def _create_match_result(self, trader_trade: SGXTrade, exchange_trade: SGXTrade) -> SGXMatchResult:
        """Create a match result for two matched trades.
        
        Args:
            trader_trade: The trader trade
            exchange_trade: The exchange trade
            
        Returns:
            SGXMatchResult representing this match
        """
        match_id = self.generate_match_id(self.rule_number)
        
        # Fields that matched exactly (rule-specific + universal)
        rule_fields = ["product_name", "contract_month", "quantityunit", "price", "buy_sell"]
        matched_fields = self.get_universal_matched_fields(rule_fields)
        
        return SGXMatchResult(
            match_id=match_id,
            match_type=SGXMatchType.EXACT,
            rule_order=self.rule_number,
            confidence=self.confidence,
            trader_trade=trader_trade,
            exchange_trade=exchange_trade,
            matched_fields=matched_fields
        )
    
    def get_rule_info(self) -> dict:
        """Get information about this matching rule.
        
        Returns:
            Dict containing rule metadata and requirements
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Exact Match",
            "match_type": SGXMatchType.EXACT.value,
            "confidence": float(self.confidence),
            "description": "Exact matching on all key fields for SGX trades",
            "requirements": [
                "Product name must match exactly (e.g., 'FE')",
                "Contract month must match exactly (e.g., 'Oct25')",
                "Quantity units must match exactly (e.g., 15000.0)",
                "Price must match exactly (e.g., 101.65)",
                "Buy/Sell direction must match exactly ('B' or 'S')",
                "Universal fields must match (broker group, clearing account)"
            ]
        }