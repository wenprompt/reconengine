"""Exact matching implementation for Rule 1."""

from typing import Optional, Any
import logging

from ...unified_recon.models.recon_status import ReconStatus
from ..models import Trade, TradeSource, MatchResult, MatchType, SignatureValue
from ..core import UnmatchedPoolManager
from ..config import ConfigManager
from .base_matcher import BaseMatcher

logger = logging.getLogger(__name__)


class ExactMatcher(BaseMatcher):
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
        super().__init__(config_manager)
        self.rule_number = 1
        self.confidence = config_manager.get_rule_confidence(self.rule_number)

        logger.info(f"Initialized ExactMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> list[MatchResult]:
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

        logger.info(
            f"Checking {len(trader_trades)} trader trades against "
            f"{len(exchange_trades)} exchange trades"
        )

        # Create lookup index for exchange trades by matching signature
        exchange_index = self._create_exchange_index(exchange_trades)

        # Find matches for each trader trade
        for trader_trade in trader_trades:
            match_result = self._find_exact_match(
                trader_trade, exchange_index, pool_manager
            )
            if match_result:
                # Record the match in the pool manager to prevent re-matching
                success = pool_manager.record_match(match_result)

                if success:
                    matches.append(match_result)
                    logger.debug(f"Created and recorded exact match: {match_result}")
                else:
                    logger.error("Failed to record exact match in pool")

        logger.info(f"Found {len(matches)} exact matches")
        return matches

    def _create_exchange_index(
        self, exchange_trades: list[Trade]
    ) -> dict[tuple[SignatureValue, ...], list[Trade]]:
        """Create lookup index for exchange trades by matching signature.

        Args:
            exchange_trades: List of exchange trades to index

        Returns:
            Dictionary mapping matching signatures to exchange trades
        """
        index: dict[tuple[SignatureValue, ...], list[Trade]] = {}

        for exchange_trade in exchange_trades:
            # Create matching signature for exact comparison
            signature = self._create_matching_signature(exchange_trade)

            if signature not in index:
                index[signature] = []
            index[signature].append(exchange_trade)

        logger.debug(f"Created exchange index with {len(index)} unique signatures")
        return index

    def _create_matching_signature(self, trade: Trade) -> tuple[SignatureValue, ...]:
        """Create matching signature for exact comparison.

        Args:
            trade: Trade to create signature for

        Returns:
            Tuple representing the matching signature
        """
        # Rule 1 specific matching fields
        # Convert Decimal to float for consistent hashing
        rule_specific_fields: list[SignatureValue] = [
            trade.product_name,
            float(trade.quantity_mt)
            if trade.quantity_mt is not None
            else None,  # Always in MT for comparison
            float(trade.price) if trade.price is not None else None,
            trade.contract_month,
            trade.buy_sell,
        ]

        # Create signature with universal fields automatically included
        return self.create_universal_signature(trade, rule_specific_fields)

    def _find_exact_match(
        self,
        trader_trade: Trade,
        exchange_index: dict[tuple[SignatureValue, ...], list[Trade]],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[MatchResult]:
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

        exchange_trades_list = exchange_index[trader_signature]

        # Check each potential exchange match
        for i in range(
            len(exchange_trades_list) - 1, -1, -1
        ):  # Iterate backwards for safe removal
            exchange_trade = exchange_trades_list[i]

            # Verify trade is still unmatched
            if pool_manager.is_trade_matched(exchange_trade):
                continue

            # Since signature match guarantees field equality, we only need minimal validation
            # Check source types (signature doesn't validate these)
            if (
                trader_trade.source != TradeSource.TRADER
                or exchange_trade.source != TradeSource.EXCHANGE
            ):
                continue

            # Found exact match! Remove from index to prevent re-checking
            del exchange_trades_list[i]
            if not exchange_trades_list:
                del exchange_index[trader_signature]

            return self._create_match_result(trader_trade, exchange_trade)

        return None

    def _create_match_result(
        self, trader_trade: Trade, exchange_trade: Trade
    ) -> MatchResult:
        """Create MatchResult for exact match.

        Args:
            trader_trade: Matched trader trade
            exchange_trade: Matched exchange trade

        Returns:
            MatchResult representing the exact match
        """
        # Generate unique match ID using centralized helper
        match_id = self.generate_match_id(self.rule_number)

        # Rule-specific fields that match exactly
        rule_specific_fields = [
            "product_name",
            "quantity_mt",
            "price",
            "contract_month",
            "buy_sell",  # B/S also matches exactly for exact matches
        ]

        # Get complete matched fields with universal fields automatically included
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        # No differing fields for exact matches
        differing_fields: list[str] = []

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.EXACT,
            confidence=self.confidence,
            status=ReconStatus.MATCHED,  # ICE always returns matched status
            trader_trade=trader_trade,
            exchange_trade=exchange_trade,
            matched_fields=matched_fields,
            differing_fields=differing_fields,
            tolerances_applied={},  # No tolerances for exact match
            rule_order=self.rule_number,
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

            # Rule-specific field validation
            rule_specific_match = (
                trader_trade.product_name == exchange_trade.product_name
                and trader_trade.quantity_mt == exchange_trade.quantity_mt
                and trader_trade.price == exchange_trade.price
                and trader_trade.contract_month == exchange_trade.contract_month
                and trader_trade.buy_sell == exchange_trade.buy_sell  # EXACT B/S match
            )

            # Universal field validation (using base class method)
            return rule_specific_match and self.validate_universal_fields(
                trader_trade, exchange_trade
            )

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error validating exact match: {e}")
            return False

    def get_rule_info(self) -> dict[str, Any]:
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
            "fields_matched": self.get_universal_matched_fields(
                ["product_name", "quantity_mt", "price", "contract_month", "buy_sell"]
            ),
            "requirements": [
                "All 6 fields must match exactly",
                "B/S must be identical (same side)",
                "Quantities compared in MT after unit conversion",
            ],
        }
