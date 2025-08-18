"""Aggregated complex crack matcher for Rule 7 - Aggregated complex crack matching (2-leg with split base products)."""

import logging
import uuid
from decimal import Decimal
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..normalizers import TradeNormalizer
from ..config import ConfigManager
from ..core import UnmatchedPoolManager
from .complex_crack_matcher import ComplexCrackMatcher

logger = logging.getLogger(__name__)


class AggregatedComplexCrackMatcher(ComplexCrackMatcher):
    """Matches aggregated complex crack trades (multiple base products + brent swap combinations).

    Handles Rule 7: Aggregated Complex Crack Match Rules (2-Leg with Split Base Products)
    - Inherits from ComplexCrackMatcher to reuse core validation logic
    - Extends functionality to handle multiple base product aggregation
    - Uses enhanced tolerances for aggregation complexity
    """

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the aggregated complex crack matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
            normalizer: Trade normalizer for data processing and shared conversion methods
        """
        # Initialize parent class with normalizer, config_manager parameter order
        super().__init__(normalizer, config_manager)
        
        # Override rule-specific settings for Rule 7
        self.rule_number = 7
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        # Enhanced tolerances for aggregation complexity - now sourced from ConfigManager
        # Use the same tolerances as ComplexCrackMatcher (Rule 4)
        self.MT_TOLERANCE = config_manager.get_crack_tolerance_mt()
        self.BBL_TOLERANCE = config_manager.get_crack_tolerance_bbl()
        
        logger.info(f"Initialized AggregatedComplexCrackMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find aggregated complex crack matches between trader and exchange data.
        
        Uses the parent class structure but with aggregated matching logic.
        """
        logger.info("Starting aggregated complex crack matching (Rule 7)")
        
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Filter trader trades to only crack products (reuse parent logic)
        crack_trades = [t for t in trader_trades if "crack" in t.product_name.lower()]

        if not crack_trades:
            logger.debug("No crack products found in trader data")
            return []

        logger.info(f"Processing {len(crack_trades)} crack trades for aggregated complex matching")

        for crack_trade in crack_trades:
            # Use our aggregated matching method instead of parent's simple matching
            match = self._find_aggregated_complex_crack_match(crack_trade, exchange_trades, pool_manager)
            if match:
                matches.append(match)
                logger.info(
                    f"Found aggregated complex crack match: {crack_trade.product_name} "
                    f"{crack_trade.contract_month} {crack_trade.quantity}"
                )

        logger.info(f"Found {len(matches)} aggregated complex crack matches")
        return matches

    def _find_aggregated_complex_crack_match(
        self, crack_trade: Trade, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
        """Find matching aggregated base products + brent swap combination for a crack trade.
        
        Extends parent logic to handle multiple base products that need aggregation.
        """
        # Use parent method to extract base product
        base_product = self._extract_base_product(crack_trade.product_name)
        if not base_product:
            return None

        # Find candidates using similar logic to parent but collecting all base products
        base_candidates = []
        brent_candidates = []

        for exchange_trade in exchange_trades:
            if pool_manager.is_trade_matched(exchange_trade):
                continue

            # Check for base product candidates (same as parent)
            if (
                exchange_trade.product_name.lower() == base_product.lower()
                and exchange_trade.contract_month == crack_trade.contract_month
                and exchange_trade.broker_group_id == crack_trade.broker_group_id
            ):
                base_candidates.append(exchange_trade)

            # Check for brent swap candidates (same as parent)
            elif (
                exchange_trade.product_name.lower() in ["brent swap", "brent_swap"]
                and exchange_trade.contract_month == crack_trade.contract_month
                and exchange_trade.broker_group_id == crack_trade.broker_group_id
            ):
                brent_candidates.append(exchange_trade)

        # Try aggregated combinations instead of single base + brent
        for brent_trade in brent_candidates:
            if pool_manager.is_trade_matched(brent_trade):
                continue

            aggregated_match = self._find_aggregated_base_combination(
                crack_trade, base_candidates, brent_trade, pool_manager
            )
            
            if aggregated_match:
                return aggregated_match

        return None

    def _find_aggregated_base_combination(
        self, 
        crack_trade: Trade, 
        base_candidates: List[Trade], 
        brent_trade: Trade,
        pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
        """Find valid aggregated base product combination that matches crack trade."""
        
        # Group base candidates by aggregation characteristics (price, B/S direction)
        aggregation_groups = defaultdict(list)
        
        for base_trade in base_candidates:
            # CRITICAL: Only consider unmatched base trades
            if pool_manager.is_trade_matched(base_trade):
                continue
                
            # Group by price and B/S (must be identical for aggregation)
            group_key = (base_trade.price, base_trade.buy_sell)
            aggregation_groups[group_key].append(base_trade)

        # Try each aggregation group
        for group_key, base_group in aggregation_groups.items():
            if len(base_group) < 2:  # Need at least 2 trades for aggregation
                continue
                
            # Calculate total aggregated quantity
            total_base_quantity = sum((trade.quantity_mt for trade in base_group), Decimal("0"))
            
            # Validate this aggregated combination against crack trade
            if self._validate_aggregated_complex_crack_combination(
                crack_trade, base_group, total_base_quantity, brent_trade
            ):
                return self._create_aggregated_crack_match_result(
                    crack_trade, base_group, brent_trade
                )

        return None

    def _validate_aggregated_complex_crack_combination(
        self, 
        crack_trade: Trade, 
        base_trades: List[Trade], 
        total_base_quantity: Decimal,
        brent_trade: Trade
    ) -> bool:
        """Validate that aggregated base + brent combination matches the crack trade.
        
        Reuses parent validation methods with aggregated quantity logic.
        """
        # 1. Validate B/S direction logic using parent method and first base trade
        if not super()._validate_bs_direction_logic(crack_trade, base_trades[0], brent_trade):
            return False

        # 2. Validate aggregated quantity with enhanced conversion tolerance
        if not self._validate_aggregated_quantity_with_conversion(
            crack_trade, total_base_quantity, brent_trade
        ):
            return False

        # 3. Validate price calculation using parent method and first base trade price
        if not super()._validate_price_calculation(crack_trade, base_trades[0], brent_trade):
            return False

        return True

    def _validate_aggregated_quantity_with_conversion(
        self, crack_trade: Trade, total_base_quantity: Decimal, brent_trade: Trade
    ) -> bool:
        """Validate quantities using enhanced tolerances for aggregation complexity."""

        crack_quantity_mt = crack_trade.quantity_mt

        # 1. Crack vs Aggregated Base: Both should be MT with enhanced tolerance
        qty_diff_mt = abs(crack_quantity_mt - total_base_quantity)
        if qty_diff_mt > self.MT_TOLERANCE:
            logger.debug(
                f"Crack-aggregated base quantity mismatch: {qty_diff_mt} MT > {self.MT_TOLERANCE} MT tolerance"
            )
            return False

        # 2. Crack vs Brent: Use shared MT→BBL conversion validation
        if not self.normalizer.validate_mt_to_bbl_quantity_match(
            crack_quantity_mt, 
            brent_trade.quantity_bbl, 
            crack_trade.product_name, 
            self.BBL_TOLERANCE
        ):
            logger.debug("Crack-brent quantity mismatch using shared MT→BBL validation")
            return False

        logger.debug("Aggregated quantity validation passed using enhanced tolerance")
        return True

    # Note: _extract_base_product and _validate_price_calculation methods 
    # are inherited from parent ComplexCrackMatcher and don't need to be redefined

    def _create_aggregated_crack_match_result(
        self, crack_trade: Trade, base_trades: List[Trade], brent_trade: Trade
    ) -> MatchResult:
        """Create MatchResult for aggregated complex crack match."""
        
        # Generate unique match ID
        match_id = f"AGG_CRACK_{uuid.uuid4().hex[:8].upper()}"

        # Primary exchange trade is the first base trade
        primary_base_trade = base_trades[0]
        
        # Additional exchange trades include remaining base trades + brent swap
        additional_trades = base_trades[1:] + [brent_trade]

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.AGGREGATED_COMPLEX_CRACK,
            confidence=self.confidence,
            trader_trade=crack_trade,
            exchange_trade=primary_base_trade,
            additional_exchange_trades=additional_trades,
            matched_fields=self._get_matched_fields(),
            rule_order=self.rule_number
        )

    def _get_matched_fields(self) -> List[str]:
        """Get list of fields that matched for aggregated complex crack matches."""
        # Rule-specific matched fields
        rule_specific_fields = [
            "product_name",
            "contract_month", 
            "quantity_with_aggregation",
            "buy_sell",
            "price_with_formula"
        ]
        
        # Get complete matched fields with universal fields using BaseMatcher method
        return self.get_universal_matched_fields(rule_specific_fields)

    def get_rule_info(self) -> dict[str, str | int | float | list[str] | dict[str, float]]:
        """Get information about this matching rule.

        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Aggregated Complex Crack Match",
            "match_type": MatchType.AGGREGATED_COMPLEX_CRACK.value,
            "confidence": float(self.confidence),
            "description": "Matches complex crack trades against aggregated base products + brent swap combinations",
            "requirements": [
                "Trader crack product base name must match exchange base products",
                "Multiple base product trades must have identical price, B/S, contract month, and broker",
                "Sum of base product quantities must match crack quantity after unit conversion",
                "B/S direction logic: Sell Crack = Sell Base + Buy Brent; Buy Crack = Buy Base + Sell Brent",
                "Price calculation: (Aggregated Base Product Price / Product-Specific Ratio) - Brent Swap Price = Crack Price",
                "All trades must have matching brokergroupid",
                "Enhanced tolerances applied for aggregation complexity"
            ],
            "tolerances": {
                "quantity_mt": float(self.MT_TOLERANCE),
                "quantity_bbl": float(self.BBL_TOLERANCE)
            },
        }