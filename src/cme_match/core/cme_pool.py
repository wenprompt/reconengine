"""Unmatched CME trade pool manager for ensuring non-duplication."""

from typing import List, Set, Dict, Tuple, Any
import logging

from ..models import CMETrade, CMETradeSource

logger = logging.getLogger(__name__)


class CMEUnmatchedPool:
    """Manages pools of unmatched CME trades to ensure no duplicate matching.
    
    Critical for the sequential rule processing where once a trade is matched
    by ANY rule, it must be permanently removed from consideration.
    """
    
    def __init__(self, trader_trades: List[CMETrade], exchange_trades: List[CMETrade]):
        """Initialize the CME pool manager with initial trade lists.
        
        Args:
            trader_trades: List of all CME trader trades
            exchange_trades: List of all CME exchange trades
        """
        # Store original trades for statistics
        self._original_trader_count = len(trader_trades)
        self._original_exchange_count = len(exchange_trades)
        
        # Active pools - trades still available for matching
        self._trader_pool: Dict[str, CMETrade] = {trade.internal_trade_id: trade for trade in trader_trades}
        self._exchange_pool: Dict[str, CMETrade] = {trade.internal_trade_id: trade for trade in exchange_trades}
        
        # Matched trade tracking
        self._matched_trader_ids: Set[str] = set()
        self._matched_exchange_ids: Set[str] = set()
        
        # Match history for audit trail
        self._match_history: List[Tuple[str, str, str]] = []  # (trader_id, exchange_id, rule_type)
        
        logger.info(f"Initialized CME pool with {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades")
    
    def get_unmatched_trades(self, source: CMETradeSource) -> List[CMETrade]:
        """Get list of unmatched trades for a specific source.
        
        Args:
            source: Trade source (TRADER or EXCHANGE)
            
        Returns:
            List of unmatched trades from the specified source
        """
        if source == CMETradeSource.TRADER:
            return list(self._trader_pool.values())
        elif source == CMETradeSource.EXCHANGE:
            return list(self._exchange_pool.values())
        else:
            raise ValueError(f"Unknown trade source: {source}")
    
    def is_unmatched(self, trade_id: str, source: CMETradeSource) -> bool:
        """Check if a trade is still unmatched.
        
        Args:
            trade_id: Trade ID to check
            source: Trade source (TRADER or EXCHANGE)
            
        Returns:
            True if trade is still unmatched, False otherwise
        """
        if source == CMETradeSource.TRADER:
            return trade_id in self._trader_pool
        elif source == CMETradeSource.EXCHANGE:
            return trade_id in self._exchange_pool
        else:
            raise ValueError(f"Unknown trade source: {source}")
    
    def mark_as_matched(self, trade_id: str, source: CMETradeSource, 
                       match_type: str = "unknown") -> bool:
        """Mark a trade as matched and remove from pool.
        
        Args:
            trade_id: Trade ID to mark as matched
            source: Trade source (TRADER or EXCHANGE)
            match_type: Type of match for audit trail
            
        Returns:
            True if trade was successfully marked, False if not found
        """
        if source == CMETradeSource.TRADER:
            if trade_id in self._trader_pool:
                del self._trader_pool[trade_id]
                self._matched_trader_ids.add(trade_id)
                logger.debug(f"Marked trader trade {trade_id} as matched ({match_type})")
                return True
            else:
                logger.warning(f"Attempted to mark non-existent trader trade {trade_id} as matched")
                return False
                
        elif source == CMETradeSource.EXCHANGE:
            if trade_id in self._exchange_pool:
                del self._exchange_pool[trade_id]
                self._matched_exchange_ids.add(trade_id)
                logger.debug(f"Marked exchange trade {trade_id} as matched ({match_type})")
                return True
            else:
                logger.warning(f"Attempted to mark non-existent exchange trade {trade_id} as matched")
                return False
        else:
            raise ValueError(f"Unknown trade source: {source}")
    
    def record_match(self, trader_id: str, exchange_id: str, rule_type: str) -> None:
        """Record a match in the audit trail.
        
        Args:
            trader_id: Trader trade ID
            exchange_id: Exchange trade ID
            rule_type: Type of matching rule used
        """
        self._match_history.append((trader_id, exchange_id, rule_type))
    
    def get_match_statistics(self) -> Dict[str, Any]:
        """Get matching statistics.
        
        Returns:
            Dictionary with matching statistics
        """
        unmatched_trader_count = len(self._trader_pool)
        unmatched_exchange_count = len(self._exchange_pool)
        matched_trader_count = len(self._matched_trader_ids)
        matched_exchange_count = len(self._matched_exchange_ids)
        
        return {
            "original_trader_count": self._original_trader_count,
            "original_exchange_count": self._original_exchange_count,
            "matched_trader_count": matched_trader_count,
            "matched_exchange_count": matched_exchange_count,
            "unmatched_trader_count": unmatched_trader_count,
            "unmatched_exchange_count": unmatched_exchange_count,
            "trader_match_rate": (matched_trader_count / max(self._original_trader_count, 1)) * 100,
            "exchange_match_rate": (matched_exchange_count / max(self._original_exchange_count, 1)) * 100,
            "total_matches": len(self._match_history),
            "match_history": self._match_history.copy()
        }
    
    def get_unmatched_trader_trades(self) -> List[CMETrade]:
        """Get all unmatched trader trades.
        
        Returns:
            List of unmatched trader trades
        """
        return list(self._trader_pool.values())
    
    def get_unmatched_exchange_trades(self) -> List[CMETrade]:
        """Get all unmatched exchange trades.
        
        Returns:
            List of unmatched exchange trades
        """
        return list(self._exchange_pool.values())
    
    def get_matched_trader_ids(self) -> Set[str]:
        """Get set of matched trader trade IDs.
        
        Returns:
            Set of trader trade IDs that have been matched
        """
        return self._matched_trader_ids.copy()
    
    def get_matched_exchange_ids(self) -> Set[str]:
        """Get set of matched exchange trade IDs.
        
        Returns:
            Set of exchange trade IDs that have been matched
        """
        return self._matched_exchange_ids.copy()
    
    def reset(self, trader_trades: List[CMETrade], exchange_trades: List[CMETrade]) -> None:
        """Reset the pool with new trade lists.
        
        Args:
            trader_trades: New list of trader trades
            exchange_trades: New list of exchange trades
        """
        self._original_trader_count = len(trader_trades)
        self._original_exchange_count = len(exchange_trades)
        
        self._trader_pool = {trade.internal_trade_id: trade for trade in trader_trades}
        self._exchange_pool = {trade.internal_trade_id: trade for trade in exchange_trades}
        
        self._matched_trader_ids.clear()
        self._matched_exchange_ids.clear()
        self._match_history.clear()
        
        logger.info(f"Reset CME pool with {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades")