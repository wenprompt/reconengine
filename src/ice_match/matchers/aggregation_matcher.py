"""Aggregation matcher for Rule 6 - Aggregation matching (split/combined trades)."""

import logging
import uuid
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..config import ConfigManager
from ..core import UnmatchedPoolManager
from .aggregation_base_matcher import AggregationBaseMatcher

logger = logging.getLogger(__name__)


class AggregationMatcher(AggregationBaseMatcher):
    """Matches aggregated trades where one source has multiple entries that sum to a single entry in the other.

    Handles Rule 6: Aggregation Match Rules
    - Same fundamental trade details (product, contract, price, broker, B/S) must match
    - Only quantities differ - smaller trades sum to larger trade quantity
    - Handles both scenarios: many→one and one→many
    - No timestamp requirements
    """

    def __init__(self, config_manager: ConfigManager):
        """Initialize the aggregation matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
        """
        super().__init__(config_manager)
        self.rule_number = 6
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        logger.info(f"Initialized AggregationMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find aggregation matches between trader and exchange data.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of aggregation matches found
        """
        logger.info("Starting aggregation matching (Rule 6)")
        
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()
        
        logger.info(f"Processing {len(trader_trades)} trader trades against {len(exchange_trades)} exchange trades")
        
        # Define aggregation fields (all fields except quantity)
        aggregation_fields = ["product_name", "contract_month", "price", "buy_sell"]
        
        # Find aggregation matches in both directions using base class methods
        # Scenario A: Multiple trader entries → Single exchange entry
        trader_to_exchange_aggregations = self.find_many_to_one_aggregations(
            trader_trades, exchange_trades, pool_manager, aggregation_fields
        )
        
        for aggregated_trades, single_trade in trader_to_exchange_aggregations:
            match = self._create_aggregation_match_result(
                aggregated_trades, single_trade, "trader_to_exchange"
            )
            if match:
                matches.append(match)
                pool_manager.record_match(match)
                logger.debug(f"Created trader_to_exchange aggregation match: {match.match_id}")
        
        # Scenario B: Single trader entry → Multiple exchange entries
        exchange_to_trader_aggregations = self.find_many_to_one_aggregations(
            exchange_trades, trader_trades, pool_manager, aggregation_fields
        )
        
        for aggregated_trades, single_trade in exchange_to_trader_aggregations:
            match = self._create_aggregation_match_result(
                aggregated_trades, single_trade, "exchange_to_trader"
            )
            if match:
                matches.append(match)
                pool_manager.record_match(match)
                logger.debug(f"Created exchange_to_trader aggregation match: {match.match_id}")
        
        logger.info(f"Found {len(matches)} aggregation matches")
        return matches

    def _create_aggregation_match_result(
        self, 
        aggregated_trades: List[Trade], 
        single_trade: Trade, 
        direction: str
    ) -> Optional[MatchResult]:
        """Create aggregation match result using base class method.
        
        Args:
            aggregated_trades: List of trades that aggregate
            single_trade: Single trade that represents the aggregation
            direction: Direction of aggregation
            
        Returns:
            MatchResult if match is valid, None otherwise
        """
        try:
            # Generate unique match ID
            import uuid
            match_id = f"AGG_{uuid.uuid4().hex[:8].upper()}"
            
            # Rule-specific fields that match exactly (all except quantity)
            rule_specific_fields = [
                "product_name",
                "contract_month", 
                "price",
                "buy_sell"
            ]
            
            # Use base class method to create match result
            return self.create_aggregation_match_result(
                match_id=match_id,
                match_type=MatchType.AGGREGATION,
                confidence=self.confidence,
                aggregated_trades=aggregated_trades,
                single_trade=single_trade,
                direction=direction,
                rule_specific_fields=rule_specific_fields,
                rule_order=self.rule_number
            )
                
        except Exception as e:
            logger.error(f"Error creating aggregation match: {e}")
            return None

    def get_rule_info(self) -> dict:
        """Get information about this matching rule.

        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Aggregation Match",
            "match_type": MatchType.AGGREGATION.value,
            "confidence": float(self.confidence),
            "description": "Matches trades where one source has multiple smaller entries that sum to a single larger entry in the other source",
            "fields_matched": self.get_universal_matched_fields([
                "product_name",
                "contract_month",
                "price", 
                "buy_sell"
            ]),
            "requirements": [
                "All fundamental trade details must match exactly (product, contract, price, broker, B/S)",
                "Multiple trades in one source must sum to single trade quantity in other source", 
                "Sum validation must be exact (no quantity tolerance)",
                "Handles both many→one and one→many scenarios",
                "No timestamp matching required"
            ]
        }