"""Exact matching implementation for CME Rule 1."""

from typing import List, Dict
import logging
import uuid
from collections import defaultdict

from ..models import CMETrade, CMETradeSource, CMEMatchResult, CMEMatchType
from ..core import CMEUnmatchedPool
from ..config import CMEConfigManager
from .base_matcher import BaseMatcher

logger = logging.getLogger(__name__)

# Constants
UUID_LENGTH = 8  # Length of UUID suffix for match IDs


class ExactMatcher(BaseMatcher):
    """Implements Rule 1: Exact matching on key fields.
    
    Matches CME trades based on:
    - ProductName (exact match)
    - ContractMonth (exact match)
    - QuantityLots (exact match)
    - Price (exact match)
    - B/S (exact match)
    - BrokerGroupId (universal field - exact match)
    - ExchClearingAcctId (universal field - exact match)
    
    Confidence: 100%
    """
    
    def __init__(self, config_manager: CMEConfigManager):
        """Initialize the CME exact matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
        """
        super().__init__(config_manager)
        self.rule_number = 1
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        logger.info(f"Initialized ExactMatcher with {self.confidence}% confidence")
    
    def find_matches(self, pool_manager: CMEUnmatchedPool) -> List[CMEMatchResult]:
        """Find all exact matches between unmatched trader and exchange trades.
        
        Args:
            pool_manager: Pool manager containing unmatched CME trades
            
        Returns:
            List of CMEMatchResult objects for exact matches found
        """
        logger.info("Starting exact matching (Rule 1)")
        matches = []
        
        # Get unmatched trades
        trader_trades = pool_manager.get_unmatched_trades(CMETradeSource.TRADER)
        exchange_trades = pool_manager.get_unmatched_trades(CMETradeSource.EXCHANGE)
        
        logger.info(f"Processing {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades")
        
        # Create index for exchange trades for efficient lookup
        exchange_index = self._create_exchange_index(exchange_trades)
        
        # Find matches
        for trader_trade in trader_trades:
            matching_exchange_trades = self._find_matching_exchanges(trader_trade, exchange_index)
            
            for exchange_trade in matching_exchange_trades:
                # Verify both trades are still unmatched
                if (pool_manager.is_unmatched(trader_trade.trade_id, CMETradeSource.TRADER) and
                    pool_manager.is_unmatched(exchange_trade.trade_id, CMETradeSource.EXCHANGE)):
                    
                    match_result = self._create_match_result(trader_trade, exchange_trade)
                    matches.append(match_result)
                    
                    # Mark trades as matched
                    pool_manager.mark_as_matched(trader_trade.trade_id, CMETradeSource.TRADER)
                    pool_manager.mark_as_matched(exchange_trade.trade_id, CMETradeSource.EXCHANGE)
                    
                    logger.debug(f"Created exact match: {trader_trade.display_id} ↔ {exchange_trade.display_id}")
                    
                    # Break after first match to avoid duplicates
                    break
        
        logger.info(f"Exact matching completed. Found {len(matches)} matches")
        return matches
    
    def _create_exchange_index(self, exchange_trades: List[CMETrade]) -> Dict[tuple, List[CMETrade]]:
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
    
    def _create_matching_signature(self, trade: CMETrade) -> tuple:
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
            trade.quantity_lots,
            trade.price,
            trade.buy_sell
        ]
        
        # Add universal fields using base class method
        return self.create_universal_signature(trade, rule_fields)
    
    def _find_matching_exchanges(self, trader_trade: CMETrade, 
                               exchange_index: Dict[tuple, List[CMETrade]]) -> List[CMETrade]:
        """Find exchange trades that match the given trader trade.
        
        Args:
            trader_trade: Trader trade to find matches for
            exchange_index: Pre-built index of exchange trades
            
        Returns:
            List of matching exchange trades
        """
        signature = self._create_matching_signature(trader_trade)
        return exchange_index.get(signature, [])
    
    def _create_match_result(self, trader_trade: CMETrade, exchange_trade: CMETrade) -> CMEMatchResult:
        """Create a match result for two matched trades.
        
        Args:
            trader_trade: The trader trade
            exchange_trade: The exchange trade
            
        Returns:
            CMEMatchResult representing this match
        """
        match_id = f"{self.config_manager.get_match_id_prefix()}_{self.rule_number}_{uuid.uuid4().hex[:UUID_LENGTH]}"
        
        # Fields that matched exactly (rule-specific + universal)
        rule_fields = ["product_name", "contract_month", "quantity_lots", "price", "buy_sell"]
        matched_fields = self.get_universal_matched_fields(rule_fields)
        
        return CMEMatchResult(
            match_id=match_id,
            match_type=CMEMatchType.EXACT,
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
            "match_type": CMEMatchType.EXACT.value,
            "confidence": float(self.confidence),
            "description": "Exact matching on all key fields for CME trades",
            "requirements": [
                "Product name must match exactly",
                "Contract month must match exactly",
                "Quantity lots must match exactly",
                "Price must match exactly", 
                "Buy/Sell direction must match exactly ('B' or 'S')",
                "Universal fields must match (broker group, clearing account)"
            ]
        }