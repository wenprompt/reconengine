"""Aggregated crack matcher for Rule 9 - Aggregated crack matching (crack to aggregated exchange trades)."""

import logging
import uuid
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..config import ConfigManager
from ..normalizers import TradeNormalizer
from ..core import UnmatchedPoolManager
from .base_matcher import BaseMatcher

logger = logging.getLogger(__name__)


class AggregatedCrackMatcher(BaseMatcher):
    """Matches crack trades against aggregated exchange trades with unit conversion.

    Handles Rule 9: Aggregated Crack Match Rules
    - Trader shows single crack trade (MT units)
    - Exchange shows multiple trades requiring aggregation (BBL units)  
    - Uses product-specific MT→BBL conversion ratios
    - Unidirectional: trader crack → exchange aggregated trades
    """

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the aggregated crack matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
            normalizer: Trade normalizer for data processing and unit conversion
        """
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 9
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        # Use tolerances from ConfigManager
        self.BBL_TOLERANCE = config_manager.get_crack_tolerance_bbl()
        
        logger.info(f"Initialized AggregatedCrackMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find aggregated crack matches between trader and exchange data.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of aggregated crack matches found
        """
        logger.info("Starting aggregated crack matching (Rule 9)")
        
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()
        
        # Filter trader trades to only crack products
        crack_trades = [t for t in trader_trades if "crack" in t.product_name.lower()]
        
        if not crack_trades:
            logger.debug("No crack products found in trader data")
            return []

        logger.info(f"Processing {len(crack_trades)} crack trades for aggregated matching")

        for crack_trade in crack_trades:
            # Skip if already matched
            if pool_manager.is_trade_matched(crack_trade):
                continue
                
            match = self._find_aggregated_crack_match(crack_trade, exchange_trades, pool_manager)
            if match:
                matches.append(match)
                # Record the match to remove trades from pool
                pool_manager.record_match(match)
                logger.info(f"Found aggregated crack match: {crack_trade.product_name} {crack_trade.contract_month} {crack_trade.quantity}")

        logger.info(f"Found {len(matches)} aggregated crack matches")
        return matches

    def _find_aggregated_crack_match(
        self, crack_trade: Trade, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
        """Find matching aggregated exchange crack trades for a crack trade.
        
        Args:
            crack_trade: Single crack trade from trader data
            exchange_trades: List of exchange trades to search
            pool_manager: Pool manager to check trade availability
            
        Returns:
            MatchResult if valid aggregated crack match found
        """
        # Find candidate exchange crack trades with the same product name
        crack_candidates = []
        
        for exchange_trade in exchange_trades:
            if pool_manager.is_trade_matched(exchange_trade):
                continue

            # Check for crack product candidates using universal field validation
            if (exchange_trade.product_name.lower() == crack_trade.product_name.lower() and
                exchange_trade.contract_month == crack_trade.contract_month and
                self.validate_universal_fields(crack_trade, exchange_trade)):
                crack_candidates.append(exchange_trade)

        if not crack_candidates:
            logger.debug(f"No crack product candidates found for {crack_trade.product_name}")
            return None

        # Try to find valid aggregated combination
        return self._find_aggregated_crack_combination(crack_trade, crack_candidates, pool_manager)


    def _find_aggregated_crack_combination(
        self, crack_trade: Trade, crack_candidates: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
        """Find valid aggregated crack product combination that matches crack trade.
        
        Args:
            crack_trade: Single crack trade to match
            crack_candidates: List of potential crack product trades
            pool_manager: Pool manager for validation
            
        Returns:
            MatchResult if valid aggregated combination found
        """
        # Group crack candidates by aggregation characteristics (price, B/S direction)
        aggregation_groups = defaultdict(list)
        
        for candidate_trade in crack_candidates:
            # Only consider unmatched crack trades
            if pool_manager.is_trade_matched(candidate_trade):
                continue
                
            # Group by price and B/S (must be identical for aggregation)
            group_key = (candidate_trade.price, candidate_trade.buy_sell)
            aggregation_groups[group_key].append(candidate_trade)

        # Try each aggregation group
        for group_key, crack_group in aggregation_groups.items():
            if len(crack_group) < 2:  # Need at least 2 trades for aggregation
                continue
                
            # Calculate total aggregated quantity in BBL
            total_crack_quantity_bbl = sum((trade.quantity_bbl for trade in crack_group), Decimal("0"))
            
            # Validate this aggregated combination against crack trade
            if self._validate_aggregated_crack_combination(crack_trade, crack_group, total_crack_quantity_bbl):
                return self._create_aggregated_crack_match_result(crack_trade, crack_group)

        return None

    def _validate_aggregated_crack_combination(
        self, crack_trade: Trade, crack_trades: List[Trade], total_crack_quantity_bbl: Decimal
    ) -> bool:
        """Validate that aggregated crack trades match the single crack trade.
        
        Args:
            crack_trade: Single crack trade to validate against
            crack_trades: List of crack trades that would be aggregated
            total_crack_quantity_bbl: Total aggregated quantity in BBL
            
        Returns:
            True if valid aggregated crack match
        """
        # 1. Validate B/S direction logic: directions should match
        first_crack_trade = crack_trades[0]
        if crack_trade.buy_sell != first_crack_trade.buy_sell:
            logger.debug("B/S direction mismatch in aggregated crack validation")
            return False

        # 2. Validate aggregated quantity with MT→BBL conversion
        if not self.normalizer.validate_mt_to_bbl_quantity_match(
            crack_trade.quantity_mt, 
            total_crack_quantity_bbl, 
            crack_trade.product_name,
            self.BBL_TOLERANCE
        ):
            logger.debug("Aggregated quantity mismatch using MT→BBL conversion")
            return False

        # 3. Validate all crack trades have consistent fundamental fields
        for exchange_crack_trade in crack_trades:
            if (exchange_crack_trade.price != first_crack_trade.price or
                exchange_crack_trade.buy_sell != first_crack_trade.buy_sell or
                exchange_crack_trade.contract_month != first_crack_trade.contract_month):
                logger.debug("Exchange crack trades have inconsistent fundamental fields")
                return False
                
            # Validate universal fields against trader crack trade
            if not self.validate_universal_fields(crack_trade, exchange_crack_trade):
                logger.debug("Universal fields validation failed for exchange crack trade")
                return False

        logger.debug("Aggregated crack validation passed")
        return True

    def _create_aggregated_crack_match_result(
        self, crack_trade: Trade, crack_trades: List[Trade]
    ) -> MatchResult:
        """Create MatchResult for aggregated crack match.
        
        Args:
            crack_trade: Single crack trade from trader data
            crack_trades: List of aggregated crack trades from exchange data
            
        Returns:
            MatchResult for the aggregated crack match
        """
        # Generate unique match ID
        match_id = f"AGG_CRACK_{uuid.uuid4().hex[:8].upper()}"

        # Primary exchange trade is the first crack trade
        primary_crack_trade = crack_trades[0]
        
        # Additional exchange trades include remaining crack trades
        additional_trades = crack_trades[1:]

        # Rule-specific fields that match
        rule_specific_fields = [
            "product_name",
            "contract_month", 
            "quantity_with_conversion",
            "buy_sell",
            "price"
        ]
        
        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.AGGREGATED_CRACK,
            confidence=self.confidence,
            trader_trade=crack_trade,
            exchange_trade=primary_crack_trade,
            additional_exchange_trades=additional_trades,
            matched_fields=matched_fields,
            tolerances_applied={
                "quantity_conversion": f"MT→BBL with ±{self.BBL_TOLERANCE} BBL tolerance",
                "aggregation": f"{len(crack_trades)} exchange crack trades aggregated"
            },
            rule_order=self.rule_number
        )

    def get_rule_info(self) -> dict:
        """Get information about this matching rule.

        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Aggregated Crack Match",
            "match_type": MatchType.AGGREGATED_CRACK.value,
            "confidence": float(self.confidence),
            "description": "Matches single crack trades against aggregated crack trades with unit conversion",
            "requirements": [
                "Trader crack product name must match exchange crack products exactly",
                "Multiple exchange crack trades must have identical price, B/S, and contract month",
                "Sum of exchange crack trade quantities (BBL) must match trader crack quantity after MT→BBL conversion",
                "B/S directions must match between trader and exchange crack trades",
                "All trades must have matching universal fields",
                "Product-specific conversion ratios applied (6.35, 8.9, 7.0 default)"
            ],
            "tolerances": {
                "quantity_bbl": float(self.BBL_TOLERANCE)
            }
        }