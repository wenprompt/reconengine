"""Exact matching rule for EEX trades (Rule 1)."""

from typing import List, Dict, Tuple
from collections import defaultdict
import logging

from ..models import EEXTrade, EEXMatchResult, EEXMatchType, EEXTradeSource
from ..config import EEXConfigManager
from ..core import EEXUnmatchedPool
from .base_matcher import BaseMatcher

logger = logging.getLogger(__name__)


class ExactMatcher(BaseMatcher):
    """Rule 1: Exact matching for EEX trades.
    
    Matches trades where all key fields match exactly:
    - product_name
    - contract_month
    - quantityunit
    - price
    - buy_sell (opposite)
    - strike (for options - ensures options match only with options)
    - put_call (for options - ensures correct option type matching)
    - broker_group_id (universal)
    - exch_clearing_acct_id (universal)
    
    This is the only matching rule for EEX trades.
    Options trades match only with other options having the same strike/put_call.
    Futures trades (strike=None, put_call=None) match only with other futures.
    """
    
    def __init__(self, config_manager: EEXConfigManager):
        """Initialize exact matcher.
        
        Args:
            config_manager: Configuration manager
        """
        super().__init__(config_manager)
        self.rule_number = 1
        self.confidence = config_manager.get_rule_confidence(1)
        logger.info(f"Initialized EEX ExactMatcher with {self.confidence}% confidence")
    
    def find_matches(self, pool_manager: EEXUnmatchedPool) -> List[EEXMatchResult]:
        """Find exact matches in the unmatched pool.
        
        Args:
            pool_manager: Pool manager containing unmatched trades
            
        Returns:
            List of exact matches found
        """
        matches = []
        
        # Get unmatched trades
        trader_trades = pool_manager.get_unmatched_trades(EEXTradeSource.TRADER)
        exchange_trades = pool_manager.get_unmatched_trades(EEXTradeSource.EXCHANGE)
        
        logger.info(
            f"Searching for exact matches among {len(trader_trades)} trader "
            f"and {len(exchange_trades)} exchange trades"
        )
        
        # Create signature lookup for exchange trades
        exchange_lookup = self._build_exchange_lookup(exchange_trades)
        
        # Find matches
        for trader_trade in trader_trades:
            # Create matching signature for this trader trade
            signature = self._create_matching_signature(trader_trade)
            
            # Look for matching exchange trades
            if signature in exchange_lookup and exchange_lookup[signature]:
                # Get list of potential exchange trades
                exchange_trades_list = exchange_lookup[signature]
                
                # Find first available exchange trade from the list
                for exchange_trade in exchange_trades_list:
                    # Double-check the match is still available in the pool
                    if not pool_manager.is_unmatched(
                        exchange_trade.internal_trade_id, EEXTradeSource.EXCHANGE
                    ):
                        continue
                    
                    # Create match result
                    match = self._create_match_result(trader_trade, exchange_trade)
                    
                    # Atomically record the match (ICE pattern)
                    if pool_manager.record_match(match):
                        matches.append(match)
                        logger.debug(f"Created exact match: {trader_trade.display_id} ↔ {exchange_trade.display_id}")
                        
                        # Remove this specific trade from the list (already safe since we're breaking)
                        exchange_trades_list.remove(exchange_trade)
                        
                        # If list is now empty, remove the signature key
                        if not exchange_trades_list:
                            del exchange_lookup[signature]
                        
                        # Break after finding first match for this trader trade
                        break
                    else:
                        logger.warning(f"Failed to atomically record match for {trader_trade.display_id} ↔ {exchange_trade.display_id}")
                        # Don't break - try next exchange trade
        
        logger.info(f"Found {len(matches)} exact matches")
        return matches
    
    def _build_exchange_lookup(self, exchange_trades: List[EEXTrade]) -> Dict[Tuple, List[EEXTrade]]:
        """Build a lookup dictionary for exchange trades based on matching signature.
        
        Args:
            exchange_trades: List of unmatched exchange trades
            
        Returns:
            Dictionary mapping signatures to lists of trades
        """
        lookup = defaultdict(list)
        for trade in exchange_trades:
            signature = self._create_matching_signature(trade)
            lookup[signature].append(trade)
        return dict(lookup)
    
    def _create_matching_signature(self, trade: EEXTrade) -> Tuple:
        """Create a signature for exact matching.
        
        Args:
            trade: Trade to create signature for
            
        Returns:
            Tuple of fields that must match exactly
        """
        # Flip buy/sell for matching (trader Buy matches exchange Sell)
        opposite_buy_sell = "S" if trade.buy_sell == "B" else "B"
        
        # Create signature with rule-specific fields
        rule_fields = [
            trade.product_name,
            trade.contract_month,
            trade.quantityunit,
            trade.price,
            opposite_buy_sell,  # Use opposite for matching
            # Include options fields to ensure options match only with options
            trade.strike,  # Will be None for futures
            trade.put_call  # Will be None for futures
        ]
        
        # Add universal fields using base class method
        return self.create_universal_signature(trade, rule_fields)
    
    def _create_match_result(self, trader_trade: EEXTrade, 
                           exchange_trade: EEXTrade) -> EEXMatchResult:
        """Create a match result for an exact match.
        
        Args:
            trader_trade: Matched trader trade
            exchange_trade: Matched exchange trade
            
        Returns:
            EEXMatchResult object
        """
        # Generate match ID using the base class method
        match_id = self.generate_match_id(self.rule_number)
        
        # Get list of matched fields
        rule_fields = [
            "product_name",
            "contract_month", 
            "quantityunit",
            "price",
            "buy_sell"
        ]
        
        matched_fields = self.get_universal_matched_fields(rule_fields)
        
        return EEXMatchResult(
            match_id=match_id,
            match_type=EEXMatchType.EXACT,
            rule_order=1,
            confidence=self.confidence,
            trader_trade=trader_trade,
            exchange_trade=exchange_trade,
            matched_fields=matched_fields
        )
    
    def get_rule_info(self) -> Dict:
        """Get information about the exact matching rule.
        
        Returns:
            Dictionary with rule metadata
        """
        return {
            "rule_number": 1,
            "name": "Exact Match",
            "description": "Matches trades where all key fields match exactly",
            "confidence": float(self.confidence),
            "matched_fields": [
                "product_name",
                "contract_month",
                "quantityunit", 
                "price",
                "buy_sell (opposite)",
                "strike (for options)",
                "put_call (for options)",
                "broker_group_id",
                "exch_clearing_acct_id"
            ],
            "notes": "Options match only with options, futures only with futures"
        }