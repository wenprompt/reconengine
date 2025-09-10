"""Unmatched EEX trade pool manager for ensuring non-duplication."""

from typing import Any, Set, TYPE_CHECKING
import logging

from ..models import EEXTrade, EEXTradeSource

if TYPE_CHECKING:
    from ..models import EEXMatchResult

logger = logging.getLogger(__name__)


class EEXUnmatchedPool:
    """Manages pools of unmatched EEX trades to ensure no duplicate matching.

    Critical for the sequential rule processing where once a trade is matched
    by ANY rule, it must be permanently removed from consideration.
    """

    def __init__(self, trader_trades: list[EEXTrade], exchange_trades: list[EEXTrade]):
        """Initialize the EEX pool manager with initial trade lists.

        Args:
            trader_trades: List of all EEX trader trades
            exchange_trades: List of all EEX exchange trades
        """
        # Store original trades for statistics
        self._original_trader_count = len(trader_trades)
        self._original_exchange_count = len(exchange_trades)

        # Active pools - trades still available for matching
        self._trader_pool: dict[str, EEXTrade] = {
            trade.internal_trade_id: trade for trade in trader_trades
        }
        self._exchange_pool: dict[str, EEXTrade] = {
            trade.internal_trade_id: trade for trade in exchange_trades
        }

        # Matched trade tracking
        self._matched_trader_ids: Set[str] = set()
        self._matched_exchange_ids: Set[str] = set()

        # Match history for audit trail
        self._match_history: list[
            tuple[str, str, str]
        ] = []  # (trader_id, exchange_id, rule_type)

        logger.info(
            f"Initialized EEX pool with {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades"
        )

    def get_unmatched_trades(self, source: EEXTradeSource) -> list[EEXTrade]:
        """Get list of unmatched trades for a specific source.

        Args:
            source: Trade source (TRADER or EXCHANGE)

        Returns:
            List of unmatched trades from the specified source
        """
        if source == EEXTradeSource.TRADER:
            return list(self._trader_pool.values())
        elif source == EEXTradeSource.EXCHANGE:
            return list(self._exchange_pool.values())
        else:
            raise ValueError(f"Unknown trade source: {source}")

    def is_unmatched(self, trade_id: str, source: EEXTradeSource) -> bool:
        """Check if a trade is still unmatched.

        Args:
            trade_id: Trade ID to check
            source: Trade source (TRADER or EXCHANGE)

        Returns:
            True if trade is still unmatched, False otherwise
        """
        if source == EEXTradeSource.TRADER:
            return trade_id in self._trader_pool
        elif source == EEXTradeSource.EXCHANGE:
            return trade_id in self._exchange_pool
        else:
            raise ValueError(f"Unknown trade source: {source}")

    def record_match(self, match_result: "EEXMatchResult") -> bool:
        """Atomically record a match and remove all involved trades from pools.

        This follows the ICE-style atomic pattern that prevents partial states.

        Args:
            match_result: The match result containing all matched trades

        Returns:
            True if all trades were successfully removed, False otherwise
        """
        # Collect all trades to remove
        trades_to_remove = []
        trades_to_remove.append(
            (match_result.trader_trade.internal_trade_id, EEXTradeSource.TRADER)
        )
        if match_result.additional_trader_trades:
            for trade in match_result.additional_trader_trades:
                trades_to_remove.append(
                    (trade.internal_trade_id, EEXTradeSource.TRADER)
                )

        trades_to_remove.append(
            (match_result.exchange_trade.internal_trade_id, EEXTradeSource.EXCHANGE)
        )
        if match_result.additional_exchange_trades:
            for trade in match_result.additional_exchange_trades:
                trades_to_remove.append(
                    (trade.internal_trade_id, EEXTradeSource.EXCHANGE)
                )

        # First verify all trades are available for matching
        for trade_id, source in trades_to_remove:
            if not self.is_unmatched(trade_id, source):
                logger.warning(
                    f"Trade {trade_id} ({source.value}) not available for atomic match"
                )
                return False

        # All trades verified, now remove them atomically
        for trade_id, source in trades_to_remove:
            if source == EEXTradeSource.TRADER:
                del self._trader_pool[trade_id]
                self._matched_trader_ids.add(trade_id)
            else:  # EXCHANGE
                del self._exchange_pool[trade_id]
                self._matched_exchange_ids.add(trade_id)

        # Record in match history
        self._match_history.append(
            (
                match_result.trader_trade.internal_trade_id,
                match_result.exchange_trade.internal_trade_id,
                match_result.match_type.value,
            )
        )

        logger.debug(
            f"Atomically recorded match {match_result.match_id}, removed {len(trades_to_remove)} trades"
        )
        return True

    def get_match_statistics(self) -> dict[str, Any]:
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
            "trader_match_rate": (
                matched_trader_count / max(self._original_trader_count, 1)
            )
            * 100,
            "exchange_match_rate": (
                matched_exchange_count / max(self._original_exchange_count, 1)
            )
            * 100,
            "total_matches": len(self._match_history),
            "match_history": self._match_history.copy(),
        }

    def get_unmatched_trader_trades(self) -> list[EEXTrade]:
        """Get all unmatched trader trades.

        Returns:
            List of unmatched trader trades
        """
        return list(self._trader_pool.values())

    def get_unmatched_exchange_trades(self) -> list[EEXTrade]:
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

    def reset(
        self, trader_trades: list[EEXTrade], exchange_trades: list[EEXTrade]
    ) -> None:
        """Reset the pool with new trade lists.

        Args:
            trader_trades: New list of trader trades
            exchange_trades: New list of exchange trades
        """
        self._original_trader_count = len(trader_trades)
        self._original_exchange_count = len(exchange_trades)

        self._trader_pool = {trade.internal_trade_id: trade for trade in trader_trades}
        self._exchange_pool = {
            trade.internal_trade_id: trade for trade in exchange_trades
        }

        self._matched_trader_ids.clear()
        self._matched_exchange_ids.clear()
        self._match_history.clear()

        logger.info(
            f"Reset EEX pool with {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades"
        )
