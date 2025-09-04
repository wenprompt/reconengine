"""Crack matching implementation for Rule 3."""

from typing import List, Dict, Tuple
import logging
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..core import UnmatchedPoolManager
from ..config import ConfigManager
from .base_matcher import BaseMatcher
from ..utils.conversion_helpers import (
    get_product_conversion_ratio,
    convert_mt_to_bbl_with_product_ratio,
    validate_mt_to_bbl_quantity_match,
)

logger = logging.getLogger(__name__)


class CrackMatcher(BaseMatcher):
    """Implements Rule 3: Crack matching with unit conversion.

    From rules.md:
    A crack match occurs when a trader executes a crack spread trade (price
    differential between refined products and crude oil) that appears in both
    data sources but may require unit conversion between metric tons (MT) and
    barrels (BBL).

    Confidence: 95%
    """

    def __init__(self, config_manager: ConfigManager, normalizer=None):
        """Initialize the crack matcher.

        Args:
            config_manager: Configuration manager with rule settings
            normalizer: Optional normalizer for product-specific conversion ratios
        """
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 3
        self.confidence = config_manager.get_rule_confidence(self.rule_number)

        # Unit conversion tolerances from config (using universal tolerances for consistency)
        self.BBL_TOLERANCE = (
            config_manager.get_universal_tolerance_bbl()
        )  # Dynamic BBL tolerance from config
        self.MT_TOLERANCE = config_manager.get_universal_tolerance_mt()  # ±145 MT

        logger.info(f"Initialized CrackMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find all crack matches between unmatched trader and exchange trades.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of MatchResult objects for crack matches found
        """
        logger.info("Starting crack matching (Rule 3)")

        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Filter for crack trades only
        crack_trader_trades = self._filter_crack_trades(trader_trades)
        crack_exchange_trades = self._filter_crack_trades(exchange_trades)

        logger.info(
            f"Checking {len(crack_trader_trades)} crack trader trades against "
            f"{len(crack_exchange_trades)} crack exchange trades"
        )

        # Build optimized index from exchange trades for O(1) lookup
        exchange_index = self._build_exchange_index(crack_exchange_trades, pool_manager)

        # Find matches using indexed lookup - O(N) instead of O(N*M)
        for trader_trade in crack_trader_trades:
            # CRITICAL: Verify trade is still unmatched
            if pool_manager.is_trade_matched(trader_trade):
                continue

            # Build lookup key for this trader trade
            match_key = self._build_match_key(trader_trade)

            # Get potential candidates from index - O(1) lookup
            candidates = exchange_index.get(match_key, [])

            # Find first valid match among candidates
            for exchange_trade in candidates:
                # CRITICAL: Verify trade is still unmatched (prevents duplicates)
                if pool_manager.is_trade_matched(exchange_trade):
                    continue

                # Validate quantity with conversion tolerance
                if self._validate_quantity_with_conversion(
                    trader_trade, exchange_trade
                ):
                    match_result = self._create_crack_match_result(
                        trader_trade, exchange_trade
                    )

                    # Record the match in the pool manager to prevent re-matching
                    success = pool_manager.record_match(match_result)

                    if success:
                        matches.append(match_result)
                        logger.debug(
                            f"Created and recorded crack match: {match_result}"
                        )
                    else:
                        logger.error("Failed to record crack match in pool")

                    break  # Move to next trader trade

        logger.info(f"Found {len(matches)} crack matches")
        return matches

    def _filter_crack_trades(self, trades: List[Trade]) -> List[Trade]:
        """Filter trades to only include crack trades.

        Args:
            trades: List of trades to filter

        Returns:
            List of trades that contain "crack" in product name
        """
        crack_trades = []
        for trade in trades:
            if "crack" in trade.product_name.lower():
                crack_trades.append(trade)

        logger.debug(
            f"Filtered {len(crack_trades)} crack trades from {len(trades)} total"
        )
        return crack_trades

    def _build_exchange_index(
        self, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> Dict[Tuple, List[Trade]]:
        """Build optimized index from exchange trades for fast lookup.

        Args:
            exchange_trades: List of exchange crack trades
            pool_manager: Pool manager to check if trades are already matched

        Returns:
            Dictionary mapping match keys to lists of candidate exchange trades
        """
        index: Dict[Tuple, List[Trade]] = defaultdict(list)

        for trade in exchange_trades:
            # CRITICAL: Only index unmatched trades (prevents duplicates)
            if not pool_manager.is_trade_matched(trade):
                match_key = self._build_match_key(trade)
                index[match_key].append(trade)

        logger.debug(f"Built exchange index with {len(index)} unique match keys")
        return index

    def _build_match_key(self, trade: Trade) -> Tuple:
        """Build consistent match key for indexing and lookup.

        For crack matches, trades must match exactly on:
        1. Product name (already filtered for "crack")
        2. Contract month
        3. Price
        4. Buy/Sell indicator
        5. Universal fields (dynamic from config)

        Quantity is handled separately with tolerance validation.

        Args:
            trade: Trade to build key for

        Returns:
            Tuple key for consistent matching
        """
        # Rule-specific fields
        rule_specific_fields = [
            trade.product_name,
            trade.contract_month,
            trade.price,
            trade.buy_sell,
        ]

        # Use BaseMatcher method to add universal fields
        return self.create_universal_signature(trade, rule_specific_fields)

    def _validate_quantity_with_conversion(
        self, trader_trade: Trade, exchange_trade: Trade
    ) -> bool:
        """Validate quantities using one-way MT→BBL conversion with product-specific ratios.

        Rule 3 Logic: Convert trader MT to BBL, compare with exchange BBL using BBL tolerance only.
        Example: 2040 MT × 6.35 = 12,954 BBL vs 13,000 BBL = 46 BBL diff < 1000 BBL tolerance ✅

        Args:
            trader_trade: Trade from trader source (always MT)
            exchange_trade: Trade from exchange source (check unit column)

        Returns:
            True if quantities match within BBL tolerance after MT→BBL conversion
        """
        # Get trader quantity in MT (always MT for trader data)
        trader_qty_mt = trader_trade.quantity_mt

        # Rule 3 is specifically for MT→BBL conversion scenarios
        # If both were MT, it would have been caught by Rule 1 (Exact Match)
        if exchange_trade.unit.lower() == "bbl":
            # Pure MT→BBL conversion scenario (the main Rule 3 case)
            # Use shared conversion method from utils
            return validate_mt_to_bbl_quantity_match(
                trader_qty_mt,
                exchange_trade.quantity_bbl,
                trader_trade.product_name,
                self.BBL_TOLERANCE,
                self.config_manager,
            )
        else:
            # Exchange is not BBL, this shouldn't happen in Rule 3 scenarios
            logger.debug(
                f"Exchange unit is {exchange_trade.unit}, not BBL - no conversion needed, should have been exact match"
            )
            return False

    def _create_crack_match_result(
        self, trader_trade: Trade, exchange_trade: Trade
    ) -> MatchResult:
        """Create MatchResult for crack match.

        Args:
            trader_trade: Matched trader trade
            exchange_trade: Matched exchange trade

        Returns:
            MatchResult representing the crack match
        """
        # Generate unique match ID
        match_id = self.generate_match_id(self.rule_number)

        # Rule-specific fields that matched for cracks
        rule_specific_fields = ["product_name", "contract_month", "price", "buy_sell"]

        # Get complete matched fields with universal fields using BaseMatcher method
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        # Check if unit conversion was applied and calculate tolerances
        tolerances_applied: dict[str, str | float] = {}
        if trader_trade.unit.lower() != exchange_trade.unit.lower():
            matched_fields.append("quantity_with_conversion")

            # Use shared conversion logic from utils
            product_ratio = get_product_conversion_ratio(
                trader_trade.product_name, self.config_manager
            )
            trader_qty_bbl = convert_mt_to_bbl_with_product_ratio(
                trader_trade.quantity_mt, trader_trade.product_name, self.config_manager
            )
            qty_diff_bbl = abs(trader_qty_bbl - exchange_trade.quantity_bbl)

            tolerances_applied["unit_conversion"] = (
                f"{trader_trade.unit} → {exchange_trade.unit} (one-way MT→BBL)"
            )
            tolerances_applied["conversion_ratio"] = float(product_ratio)
            tolerances_applied["product_specific_ratio"] = (
                f"{trader_trade.product_name}: {product_ratio}"
            )
            tolerances_applied["quantity_tolerance_bbl"] = float(qty_diff_bbl)
        else:
            # This shouldn't happen in Rule 3 - both MT would be exact match
            matched_fields.append("quantity")
            logger.warning(
                f"Rule 3 handling same units ({trader_trade.unit} vs {exchange_trade.unit}) - should have been exact match"
            )

        # No differing fields for successful crack matches
        differing_fields: List[str] = []

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.CRACK,
            confidence=self.confidence,
            trader_trade=trader_trade,
            exchange_trade=exchange_trade,
            matched_fields=matched_fields,
            differing_fields=differing_fields,
            tolerances_applied=tolerances_applied,
            rule_order=self.rule_number,
        )

    def get_rule_info(
        self,
    ) -> dict[str, str | int | float | list[str] | dict[str, float]]:
        """Get information about this matching rule.

        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Crack Match",
            "match_type": MatchType.CRACK.value,
            "confidence": float(self.confidence),
            "description": "Matches crack spread trades with unit conversion between MT and BBL",
            "requirements": [
                "Product name must contain 'crack'",
                "Same contract month",
                "Same price",
                "Same broker group",
                "Same buy/sell indicator",
                "Quantity match after MT→BBL conversion (±{} BBL tolerance)".format(
                    self.BBL_TOLERANCE
                ),
            ],
            "tolerances": {
                "quantity_bbl": float(
                    self.config_manager.get_universal_tolerance_bbl()
                ),
                "quantity_mt": float(self.config_manager.get_universal_tolerance_mt()),
            },
        }
