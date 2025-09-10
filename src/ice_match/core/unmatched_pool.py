"""Unmatched trade pool manager for ensuring non-duplication."""

from typing import List, Set, Dict, Optional, Tuple, Any
from collections import defaultdict
import logging
from decimal import Decimal

from ..models import Trade, TradeSource, MatchResult

logger = logging.getLogger(__name__)


class UnmatchedPoolManager:
    """Manages pools of unmatched trades to ensure no duplicate matching.

    Critical for the sequential rule processing where once a trade is matched
    by ANY rule, it must be permanently removed from consideration.
    """

    def __init__(self, trader_trades: List[Trade], exchange_trades: List[Trade]):
        """Initialize the pool manager with initial trade lists.

        Args:
            trader_trades: List of all trader trades
            exchange_trades: List of all exchange trades
        """
        # Store original trades for statistics
        self._original_trader_count = len(trader_trades)
        self._original_exchange_count = len(exchange_trades)

        # Active pools - trades still available for matching
        self._trader_pool: Dict[str, Trade] = {
            trade.internal_trade_id: trade for trade in trader_trades
        }
        self._exchange_pool: Dict[str, Trade] = {
            trade.internal_trade_id: trade for trade in exchange_trades
        }

        # Matched trade tracking
        self._matched_trader_ids: Set[str] = set()
        self._matched_exchange_ids: Set[str] = set()

        # Match history for audit trail
        self._match_history: List[
            Tuple[str, str, str]
        ] = []  # (trader_id, exchange_id, rule_type)

        logger.info(
            f"Initialized pool manager with {len(trader_trades)} trader trades "
            f"and {len(exchange_trades)} exchange trades"
        )

    def get_unmatched_trader_trades(self) -> List[Trade]:
        """Get list of all unmatched trader trades.

        Returns:
            List of trader trades still available for matching
        """
        return list(self._trader_pool.values())

    def get_unmatched_exchange_trades(self) -> List[Trade]:
        """Get list of all unmatched exchange trades.

        Returns:
            List of exchange trades still available for matching
        """
        return list(self._exchange_pool.values())

    def get_unmatched_count(self) -> Tuple[int, int]:
        """Get count of unmatched trades.

        Returns:
            Tuple of (trader_count, exchange_count)
        """
        return len(self._trader_pool), len(self._exchange_pool)

    def get_matched_count(self) -> Tuple[int, int]:
        """Get count of matched trades.

        Returns:
            Tuple of (trader_count, exchange_count)
        """
        return len(self._matched_trader_ids), len(self._matched_exchange_ids)

    def get_original_count(self) -> Tuple[int, int]:
        """Get count of original trades.

        Returns:
            Tuple of (trader_count, exchange_count)
        """
        return self._original_trader_count, self._original_exchange_count

    def is_trade_matched(self, trade: Trade) -> bool:
        """Check if a trade has already been matched.

        Args:
            trade: Trade to check

        Returns:
            True if trade has been matched, False otherwise
        """
        if trade.source == TradeSource.TRADER:
            return trade.internal_trade_id in self._matched_trader_ids
        else:
            return trade.internal_trade_id in self._matched_exchange_ids

    def get_trade_by_id(self, trade_id: str) -> Optional[Trade]:
        """Get a trade by ID from either pool.

        Args:
            trade_id: Trade ID to look up

        Returns:
            Trade object if found, None otherwise
        """
        if trade_id in self._trader_pool:
            return self._trader_pool[trade_id]
        elif trade_id in self._exchange_pool:
            return self._exchange_pool[trade_id]
        else:
            return None

    def get_match_history(self) -> List[Tuple[str, str, str]]:
        """Get history of all matches made.

        Returns:
            List of tuples (trader_id, exchange_id, match_type)
        """
        return self._match_history.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the matching progress.

        Returns:
            Dictionary with detailed statistics
        """
        trader_original, exchange_original = self.get_original_count()
        trader_matched, exchange_matched = self.get_matched_count()
        trader_unmatched, exchange_unmatched = self.get_unmatched_count()

        # Calculate percentages
        trader_match_rate = (
            (trader_matched / trader_original * 100) if trader_original > 0 else 0
        )
        exchange_match_rate = (
            (exchange_matched / exchange_original * 100) if exchange_original > 0 else 0
        )

        # Count matches by rule type
        match_by_rule: Dict[str, int] = defaultdict(int)
        for _, _, rule_type in self._match_history:
            match_by_rule[rule_type] += 1

        return {
            "original": {
                "trader": trader_original,
                "exchange": exchange_original,
                "total": trader_original + exchange_original,
            },
            "matched": {
                "trader": trader_matched,
                "exchange": exchange_matched,
                "total": trader_matched + exchange_matched,
                "pairs": len(self._match_history),
            },
            "unmatched": {
                "trader": trader_unmatched,
                "exchange": exchange_unmatched,
                "total": trader_unmatched + exchange_unmatched,
            },
            "match_rates": {
                "trader": f"{trader_match_rate:.1f}%",
                "exchange": f"{exchange_match_rate:.1f}%",
                "overall": f"{(Decimal(str(trader_match_rate)) * Decimal('0.5') + Decimal(str(exchange_match_rate)) * Decimal('0.5')):.1f}%",
            },
            "matches_by_rule": dict(match_by_rule),
        }

    def record_match(self, match_result: MatchResult) -> bool:
        """Record a match and remove all involved trades from the unmatched pools.

        Args:
            match_result: The MatchResult object containing all matched trades.

        Returns:
            True if all trades were successfully removed, False otherwise.
        """
        trades_to_remove: List[Trade] = []
        trades_to_remove.append(match_result.trader_trade)
        if match_result.additional_trader_trades:
            trades_to_remove.extend(match_result.additional_trader_trades)
        trades_to_remove.append(match_result.exchange_trade)
        if match_result.additional_exchange_trades:
            trades_to_remove.extend(match_result.additional_exchange_trades)

        success = True
        for trade in trades_to_remove:
            trade_id = trade.internal_trade_id
            if trade.source == TradeSource.TRADER:
                if trade_id not in self._trader_pool:
                    logger.warning(
                        f"Trader trade {trade_id} not found in unmatched pool for recording match."
                    )
                    success = False
                    continue
                if trade_id in self._matched_trader_ids:
                    logger.error(
                        f"Trader trade {trade_id} was already matched when trying to record match!"
                    )
                    success = False
                    continue
                del self._trader_pool[trade_id]
                self._matched_trader_ids.add(trade_id)
            else:  # TradeSource.EXCHANGE
                if trade_id not in self._exchange_pool:
                    logger.warning(
                        f"Exchange trade {trade_id} not found in unmatched pool for recording match."
                    )
                    success = False
                    continue
                if trade_id in self._matched_exchange_ids:
                    logger.error(
                        f"Exchange trade {trade_id} was already matched when trying to record match!"
                    )
                    success = False
                    continue
                del self._exchange_pool[trade_id]
                self._matched_exchange_ids.add(trade_id)

        # Record in history only if all removals succeeded
        if success:
            self._match_history.append(
                (
                    match_result.trader_trade.internal_trade_id,
                    match_result.exchange_trade.internal_trade_id,
                    match_result.match_type.value,
                )
            )

        logger.debug(
            f"Recorded match {match_result.match_id}. Removed {len(trades_to_remove)} trades from pools."
        )
        logger.debug(
            f"Remaining unmatched: {len(self._trader_pool)} trader, "
            f"{len(self._exchange_pool)} exchange"
        )

        return success

    def reset_to_unmatched(
        self, trader_trades: List[Trade], exchange_trades: List[Trade]
    ):
        """Reset pools with new unmatched trade lists.

        Args:
            trader_trades: New list of trader trades
            exchange_trades: New list of exchange trades
        """
        self._trader_pool = {trade.internal_trade_id: trade for trade in trader_trades}
        self._exchange_pool = {
            trade.internal_trade_id: trade for trade in exchange_trades
        }
        self._original_trader_count = len(trader_trades)
        self._original_exchange_count = len(exchange_trades)
        self._matched_trader_ids.clear()
        self._matched_exchange_ids.clear()
        self._match_history.clear()

        logger.info(
            f"Reset pools with {len(trader_trades)} trader trades "
            f"and {len(exchange_trades)} exchange trades"
        )

    def validate_integrity(self) -> bool:
        """Validate the integrity of the pool state.

        Returns:
            True if pools are in valid state, False otherwise
        """
        # Check for overlapping IDs between matched and unmatched
        trader_overlap = self._matched_trader_ids.intersection(self._trader_pool.keys())
        exchange_overlap = self._matched_exchange_ids.intersection(
            self._exchange_pool.keys()
        )

        if trader_overlap:
            logger.error(
                f"Trader trades in both matched and unmatched pools: {trader_overlap}"
            )
            return False

        if exchange_overlap:
            logger.error(
                f"Exchange trades in both matched and unmatched pools: {exchange_overlap}"
            )
            return False

        # Check match history consistency
        for trader_id, exchange_id, _ in self._match_history:
            if trader_id not in self._matched_trader_ids:
                logger.error(f"Match history contains untracked trader ID: {trader_id}")
                return False

            if exchange_id not in self._matched_exchange_ids:
                logger.error(
                    f"Match history contains untracked exchange ID: {exchange_id}"
                )
                return False

        logger.debug("Pool integrity validation passed")
        return True
