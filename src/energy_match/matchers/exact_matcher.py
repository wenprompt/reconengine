"""Exact matching implementation for Rule 1."""

from typing import List, Optional, Dict
from decimal import Decimal
import logging
import uuid

from ..models import Trade, TradeSource, MatchResult, MatchType
from ..core import UnmatchedPoolManager
from ..config import ConfigManager

logger = logging.getLogger(__name__)


class ExactMatcher:
    """Implements Rule 1: Exact matching on 6 fields.
    
    From rules.md:
    - ProductName (exact)
    - Quantity (exact, in MT after conversion)
    - Price (exact)
    - ContractMonth (exact)
    - B/S (exact match)
    - BrokerGroupId (exact)
    
    Confidence: 100%
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the exact matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
        """
        self.config_manager = config_manager
        self.rule_number = 1
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        logger.info(f"Initialized ExactMatcher with {self.confidence}% confidence")
    
    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find all exact matches between unmatched trader and exchange trades.
        
        Args:
            pool_manager: Pool manager containing unmatched trades
            
        Returns:
            List of MatchResult objects for exact matches found
        """
        logger.info("Starting exact matching (Rule 1)")
        
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()
        
        logger.info(f"Checking {len(trader_trades)} trader trades against "
                   f"{len(exchange_trades)} exchange trades")
        
        # Create lookup index for exchange trades by matching signature
        exchange_index = self._create_exchange_index(exchange_trades)
        
        # Find matches for each trader trade
        for trader_trade in trader_trades:
            match_result = self._find_exact_match(trader_trade, exchange_index, pool_manager)
            if match_result:
                matches.append(match_result)
                
                # Remove matched trades from pools
                success = pool_manager.remove_matched_trades(
                    trader_trade, 
                    match_result.exchange_trade,
                    match_result.match_type.value
                )
                
                if not success:
                    logger.error(f"Failed to remove matched trades from pool")
                else:
                    logger.debug(f"Created exact match: {match_result}")
        
        logger.info(f"Found {len(matches)} exact matches")
        return matches
    
    def _create_exchange_index(self, exchange_trades: List[Trade]) -> dict:
        """Create lookup index for exchange trades by matching signature.
        
        Args:
            exchange_trades: List of exchange trades to index
            
        Returns:
            Dictionary mapping matching signatures to exchange trades
        """
        index: Dict[tuple, List[Trade]] = {}
        
        for exchange_trade in exchange_trades:
            # Create matching signature for exact comparison
            signature = self._create_matching_signature(exchange_trade)
            
            if signature not in index:
                index[signature] = []
            index[signature].append(exchange_trade)
        
        logger.debug(f"Created exchange index with {len(index)} unique signatures")
        return index
    
    def _create_matching_signature(self, trade: Trade) -> tuple:
        """Create matching signature for exact comparison.
        
        Args:
            trade: Trade to create signature for
            
        Returns:
            Tuple representing the matching signature
        """
        # Rule 1 matching fields (6 fields):
        # 1. ProductName (exact)
        # 2. Quantity in MT (exact after conversion)
        # 3. Price (exact)
        # 4. ContractMonth (exact)
        # 5. B/S (exact match)
        # 6. BrokerGroupId (exact)
        
        return (
            trade.product_name,
            trade.quantity_mt,  # Always in MT for comparison
            trade.price,
            trade.contract_month,
            trade.buy_sell,
            trade.broker_group_id
        )
    
    def _find_exact_match(self, trader_trade: Trade, exchange_index: dict, 
                         pool_manager: UnmatchedPoolManager) -> Optional[MatchResult]:
        """Find exact match for a trader trade.
        
        Args:
            trader_trade: Trader trade to find match for
            exchange_index: Index of exchange trades by signature
            pool_manager: Pool manager for validation
            
        Returns:
            MatchResult if exact match found, None otherwise
        """
        # Create signature for trader trade
        trader_signature = self._create_matching_signature(trader_trade)
        
        # Look for exchange trades with EXACT matching signature (including same B/S)
        if trader_signature not in exchange_index:
            return None
        
        # Check each potential exchange match
        for exchange_trade in exchange_index[trader_signature]:
            # Verify trade is still unmatched
            if pool_manager.is_trade_matched(exchange_trade):
                continue
            
            # Verify exact match validation
            if not self.validate_match(trader_trade, exchange_trade):
                continue
            
            # Found exact match!
            return self._create_match_result(trader_trade, exchange_trade)
        
        return None
    
    
    def _create_match_result(self, trader_trade: Trade, exchange_trade: Trade) -> MatchResult:
        """Create MatchResult for exact match.
        
        Args:
            trader_trade: Matched trader trade
            exchange_trade: Matched exchange trade
            
        Returns:
            MatchResult representing the exact match
        """
        # Generate unique match ID
        match_id = f"EXACT_{uuid.uuid4().hex[:8].upper()}"
        
        # All 6 fields match exactly for exact matches
        matched_fields = [
            "product_name",
            "quantity_mt", 
            "price",
            "contract_month",
            "buy_sell",  # B/S also matches exactly for exact matches
            "broker_group_id"
        ]
        
        # No differing fields for exact matches
        differing_fields: List[str] = []
        
        return MatchResult(
            match_id=match_id,
            match_type=MatchType.EXACT,
            confidence=self.confidence,
            trader_trade=trader_trade,
            exchange_trade=exchange_trade,
            matched_fields=matched_fields,
            differing_fields=differing_fields,
            tolerances_applied={},  # No tolerances for exact match
            rule_order=self.rule_number
        )
    
    def validate_match(self, trader_trade: Trade, exchange_trade: Trade) -> bool:
        """Validate that two trades can form an exact match.
        
        Args:
            trader_trade: Trader trade
            exchange_trade: Exchange trade
            
        Returns:
            True if trades can form exact match, False otherwise
        """
        try:
            # Check source types
            if trader_trade.source != TradeSource.TRADER:
                return False
            if exchange_trade.source != TradeSource.EXCHANGE:
                return False
            
            # Check ALL 6 fields match exactly (including B/S)
            return (
                trader_trade.product_name == exchange_trade.product_name and
                trader_trade.quantity_mt == exchange_trade.quantity_mt and
                trader_trade.price == exchange_trade.price and
                trader_trade.contract_month == exchange_trade.contract_month and
                trader_trade.buy_sell == exchange_trade.buy_sell and  # EXACT B/S match
                trader_trade.broker_group_id == exchange_trade.broker_group_id
            )
            
        except Exception as e:
            logger.error(f"Error validating exact match: {e}")
            return False
    
    def get_rule_info(self) -> dict:
        """Get information about this matching rule.
        
        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Exact Match",
            "match_type": MatchType.EXACT.value,
            "confidence": float(self.confidence),
            "description": "Exact matching on 6 fields: ProductName, Quantity(MT), Price, ContractMonth, B/S, BrokerGroupId",
            "fields_matched": [
                "product_name",
                "quantity_mt",
                "price", 
                "contract_month",
                "buy_sell",
                "broker_group_id"
            ],
            "requirements": [
                "All 6 fields must match exactly",
                "B/S must be identical (same side)",
                "Quantities compared in MT after unit conversion"
            ]
        }