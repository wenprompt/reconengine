"""Exact matching implementation for SGX Rule 1."""

from typing import List, Optional, Dict
from decimal import Decimal
import logging
import uuid
from collections import defaultdict

from ..models import SGXTrade, SGXTradeSource, SGXMatchResult, SGXMatchType
from ..core import SGXUnmatchedPool
from ..config import SGXConfigManager
from .sgx_base_matcher import SGXBaseMatcher

logger = logging.getLogger(__name__)


class SGXExactMatcher(SGXBaseMatcher):
    """Implements SGX Rule 1: Exact matching on key fields.
    
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
        
        logger.info(f"Initialized SGXExactMatcher with {self.confidence}% confidence")
    
    def find_matches(self, pool_manager: SGXUnmatchedPool) -> List[SGXMatchResult]:
        """Find all exact matches between unmatched trader and exchange trades.
        
        Args:
            pool_manager: Pool manager containing unmatched SGX trades
            
        Returns:
            List of SGXMatchResult objects for exact matches found
        """
        logger.info("Starting SGX exact matching (Rule 1)")
        matches = []
        
        # Get unmatched trades
        trader_trades = pool_manager.get_unmatched_trades(SGXTradeSource.TRADER)
        exchange_trades = pool_manager.get_unmatched_trades(SGXTradeSource.EXCHANGE)
        
        logger.info(f"Processing {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades")
        
        # Create index for exchange trades for efficient lookup
        exchange_index = self._create_exchange_index(exchange_trades)
        
        # Find matches
        for trader_trade in trader_trades:
            matching_exchange_trades = self._find_matching_exchanges(trader_trade, exchange_index)
            
            for exchange_trade in matching_exchange_trades:
                # Verify both trades are still unmatched
                if (pool_manager.is_unmatched(trader_trade.trade_id, SGXTradeSource.TRADER) and
                    pool_manager.is_unmatched(exchange_trade.trade_id, SGXTradeSource.EXCHANGE)):
                    
                    match_result = self._create_match_result(trader_trade, exchange_trade)
                    matches.append(match_result)
                    
                    # Mark trades as matched
                    pool_manager.mark_as_matched(trader_trade.trade_id, SGXTradeSource.TRADER)
                    pool_manager.mark_as_matched(exchange_trade.trade_id, SGXTradeSource.EXCHANGE)
                    
                    logger.debug(f"Created exact match: {trader_trade.display_id} ↔ {exchange_trade.display_id}")
                    
                    # Break after first match to avoid duplicates
                    break
        
        logger.info(f"SGX exact matching completed. Found {len(matches)} matches")
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
            trade.quantity_units,
            trade.price,
            trade.buy_sell
        ]
        
        # Add universal fields using base class method
        return self.create_universal_signature(trade, rule_fields)
    
    def _find_matching_exchanges(self, trader_trade: SGXTrade, 
                               exchange_index: Dict[tuple, List[SGXTrade]]) -> List[SGXTrade]:
        """Find exchange trades that match the given trader trade.
        
        Args:
            trader_trade: Trader trade to find matches for
            exchange_index: Pre-built index of exchange trades
            
        Returns:
            List of matching exchange trades
        """
        signature = self._create_matching_signature(trader_trade)
        return exchange_index.get(signature, [])
    
    def _create_match_result(self, trader_trade: SGXTrade, exchange_trade: SGXTrade) -> SGXMatchResult:
        """Create a match result for two matched trades.
        
        Args:
            trader_trade: The trader trade
            exchange_trade: The exchange trade
            
        Returns:
            SGXMatchResult representing this match
        """
        match_id = f"{self.config_manager.get_match_id_prefix()}_{self.rule_number}_{uuid.uuid4().hex[:8]}"
        
        # Fields that matched exactly (rule-specific + universal)
        rule_fields = ["product_name", "contract_month", "quantity_units", "price", "buy_sell"]
        matched_fields = self.get_universal_matched_fields(rule_fields)
        
        return SGXMatchResult(
            match_id=match_id,
            match_type=SGXMatchType.EXACT,
            rule_order=self.rule_number,
            confidence=self.confidence,
            trader_trade=trader_trade,
            exchange_trade=exchange_trade,
            matched_fields=matched_fields,
            tolerances_applied={}  # No tolerances for exact matching
        )