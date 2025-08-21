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
from .aggregation_base_matcher import AggregationBaseMatcher
from ..utils.conversion_helpers import validate_mt_to_bbl_quantity_match

logger = logging.getLogger(__name__)


class AggregatedCrackMatcher(AggregationBaseMatcher):
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
        
        # Use universal tolerances for consistency across all rules
        self.BBL_TOLERANCE = config_manager.get_universal_tolerance_bbl() # ±500 BBL
        self.MT_TOLERANCE = config_manager.get_universal_tolerance_mt()   # ±145 MT
        
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

        # Define aggregation fields for crack trades (product, contract, price, B/S)
        aggregation_fields = ["product_name", "contract_month", "price", "buy_sell"]

        for crack_trade in crack_trades:
            # Skip if already matched
            if pool_manager.is_trade_matched(crack_trade):
                continue
                
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
                continue

            # Use base class aggregation logic to find many-to-one matches
            # Exchange trades (many) → Trader trade (one) with unit conversion
            aggregations = self._find_crack_aggregations_with_conversion(
                crack_candidates, [crack_trade], pool_manager, aggregation_fields, crack_trade
            )
            
            for aggregated_trades, single_trade in aggregations:
                match = self._create_crack_match_result(aggregated_trades, single_trade)
                if match:
                    matches.append(match)
                    pool_manager.record_match(match)
                    logger.info(f"Found aggregated crack match: {crack_trade.product_name} {crack_trade.contract_month} {crack_trade.quantity}")

        logger.info(f"Found {len(matches)} aggregated crack matches")
        return matches

    def _find_crack_aggregations_with_conversion(
        self,
        many_source: List[Trade],
        one_source: List[Trade],
        pool_manager: UnmatchedPoolManager,
        aggregation_fields: List[str],
        reference_trade: Trade
    ) -> List[Tuple[List[Trade], Trade]]:
        """Find crack aggregations with unit conversion validation.
        
        Modified version of base class method that uses unit conversion instead of exact quantity matching.
        """
        aggregations = []
        
        # Group many_source trades by aggregation signature
        many_groups = self.group_trades_by_aggregation_signature(many_source, aggregation_fields)
        
        logger.debug(f"Crack aggregation: {len(many_groups)} groups from many_source, {len(one_source)} single trades")
        
        for group_signature, group_trades in many_groups.items():
            # Skip if any trade in group is already matched
            if any(pool_manager.is_trade_matched(trade) for trade in group_trades):
                continue
                
            # Only consider groups with sufficient trades for aggregation
            if len(group_trades) < 2:
                continue
                
            logger.debug(f"Processing crack group with {len(group_trades)} trades: {[t.trade_id for t in group_trades]}")
            
            # Calculate total quantity in BBL (exchange trades are in BBL)
            total_quantity_bbl = Decimal(sum(trade.quantity_bbl for trade in group_trades))
            logger.debug(f"  Total BBL quantity: {total_quantity_bbl}")
            
            # Find matching single trade using unit conversion validation
            for candidate_trade in one_source:
                if pool_manager.is_trade_matched(candidate_trade):
                    continue
                    
                # Validate using MT→BBL conversion instead of exact quantity match
                if self._validate_crack_aggregation_with_conversion(
                    group_trades, candidate_trade, total_quantity_bbl
                ):
                    aggregations.append((group_trades, candidate_trade))
                    logger.debug(f"✅ Found crack aggregation with conversion: {len(group_trades)} trades → 1 trade ({candidate_trade.trade_id})")
                    break
        
        return aggregations

    def _validate_crack_aggregation_with_conversion(
        self, 
        aggregated_trades: List[Trade], 
        single_trade: Trade,
        total_quantity_bbl: Decimal
    ) -> bool:
        """Validate crack aggregation using unit conversion instead of exact quantity matching."""
        
        # 1. All aggregated trades must have identical characteristics (except quantity)
        first_trade = aggregated_trades[0]
        for trade in aggregated_trades[1:]:
            if not self._trades_have_matching_characteristics(first_trade, trade, ignore_quantity=True):
                logger.debug("Crack aggregation validation failed: aggregated trades have different characteristics")
                return False
        
        # 2. Aggregated trades must match single trade characteristics (except quantity)
        if not self._trades_have_matching_characteristics(first_trade, single_trade, ignore_quantity=True):
            logger.debug("Crack aggregation validation failed: aggregated and single trade characteristics don't match")
            return False
        
        # 3. Validate quantity using MT→BBL conversion from utils
        if not validate_mt_to_bbl_quantity_match(
            single_trade.quantity_mt, 
            total_quantity_bbl, 
            single_trade.product_name,
            self.BBL_TOLERANCE,
            self.config_manager
        ):
            logger.debug("Crack aggregation validation failed: MT→BBL quantity mismatch")
            return False
        
        logger.debug(f"✅ Crack aggregation validation passed: {len(aggregated_trades)} trades convert to {single_trade.quantity_mt} MT")
        return True

    def _create_crack_match_result(
        self, 
        aggregated_trades: List[Trade], 
        single_trade: Trade
    ) -> MatchResult:
        """Create MatchResult for aggregated crack match using base class method."""
        
        # Generate unique match ID
        import uuid
        match_id = f"AGG_CRACK_{uuid.uuid4().hex[:8].upper()}"
        
        # Rule-specific fields that match
        rule_specific_fields = [
            "product_name",
            "contract_month", 
            "quantity_with_conversion",
            "buy_sell",
            "price"
        ]
        
        # Create match result - exchange trades (many) → trader trade (one)
        return self.create_aggregation_match_result(
            match_id=match_id,
            match_type=MatchType.AGGREGATED_CRACK,
            confidence=self.confidence,
            aggregated_trades=aggregated_trades,
            single_trade=single_trade,
            direction="exchange_to_trader",
            rule_specific_fields=rule_specific_fields,
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