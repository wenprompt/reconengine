"""Aggregation matcher for Rule 6 - Aggregation matching (split/combined trades)."""

import logging
import uuid
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..config import ConfigManager
from ..core import UnmatchedPoolManager

logger = logging.getLogger(__name__)


class AggregationMatcher:
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
        self.config_manager = config_manager
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
        
        # Find aggregation matches in both directions
        # Scenario A: Multiple trader entries → Single exchange entry
        trader_to_exchange_matches = self._find_many_to_one_matches(
            trader_trades, exchange_trades, pool_manager, "trader_to_exchange"
        )
        matches.extend(trader_to_exchange_matches)
        
        # Scenario B: Single trader entry → Multiple exchange entries
        exchange_to_trader_matches = self._find_many_to_one_matches(
            exchange_trades, trader_trades, pool_manager, "exchange_to_trader"
        )
        matches.extend(exchange_to_trader_matches)
        
        logger.info(f"Found {len(matches)} aggregation matches")
        return matches

    def _find_many_to_one_matches(
        self, 
        many_source: List[Trade], 
        one_source: List[Trade], 
        pool_manager: UnmatchedPoolManager,
        direction: str
    ) -> List[MatchResult]:
        """Find matches where multiple trades from one source aggregate to single trade in other source.
        
        Args:
            many_source: Source with potentially multiple smaller trades
            one_source: Source with potentially single aggregated trades
            pool_manager: Pool manager for validation
            direction: Direction string for debugging ("trader_to_exchange" or "exchange_to_trader")
            
        Returns:
            List of aggregation matches found
        """
        matches = []
        
        # Group many_source trades by aggregation key (all fields except quantity)
        many_groups = self._group_trades_by_aggregation_key(many_source)
        
        # Create lookup index for one_source trades
        one_index = self._create_trade_index(one_source)
        
        logger.debug(f"Direction {direction}: {len(many_groups)} groups from many_source, {len(one_index)} entries in one_source")
        
        for group_key, group_trades in many_groups.items():
            # Skip if any trade in group is already matched
            if any(pool_manager.is_trade_matched(trade) for trade in group_trades):
                continue
                
            # Only consider groups with multiple trades (aggregation candidates)
            if len(group_trades) < 2:
                continue
                
            # Calculate total quantity for this group
            total_quantity = sum(trade.quantity_mt for trade in group_trades)
            
            # Look for matching single trade with this total quantity
            match_key = (*group_key, total_quantity)
            if match_key in one_index:
                candidate_trades = one_index[match_key]
                
                # Find first unmatched candidate
                for candidate_trade in candidate_trades:
                    if not pool_manager.is_trade_matched(candidate_trade):
                        # Validate and create match
                        match = self._create_aggregation_match(
                            group_trades, candidate_trade, direction, pool_manager
                        )
                        if match:
                            matches.append(match)
                            pool_manager.record_match(match)
                            logger.debug(f"Created {direction} aggregation match: {match}")
                            break
        
        return matches

    def _group_trades_by_aggregation_key(self, trades: List[Trade]) -> Dict[tuple, List[Trade]]:
        """Group trades by aggregation key (all fields except quantity).
        
        Args:
            trades: List of trades to group
            
        Returns:
            Dictionary mapping aggregation keys to trade lists
        """
        groups: Dict[tuple, List[Trade]] = defaultdict(list)
        
        for trade in trades:
            # Aggregation key: all fundamental trade details except quantity
            key = (
                trade.product_name,
                trade.contract_month,
                trade.price,
                trade.buy_sell,
                trade.broker_group_id
            )
            groups[key].append(trade)
        
        logger.debug(f"Grouped {len(trades)} trades into {len(groups)} aggregation groups")
        return groups

    def _create_trade_index(self, trades: List[Trade]) -> Dict[tuple, List[Trade]]:
        """Create index for single trades by full matching signature.
        
        Args:
            trades: List of trades to index
            
        Returns:
            Dictionary mapping full signatures to trade lists
        """
        index: Dict[tuple, List[Trade]] = defaultdict(list)
        
        for trade in trades:
            # Full signature: all fields including quantity
            signature = (
                trade.product_name,
                trade.contract_month,
                trade.price,
                trade.buy_sell,
                trade.broker_group_id,
                trade.quantity_mt
            )
            index[signature].append(trade)
        
        logger.debug(f"Created trade index with {len(index)} unique signatures")
        return index

    def _create_aggregation_match(
        self, 
        many_trades: List[Trade], 
        one_trade: Trade, 
        direction: str,
        pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
        """Create aggregation match result.
        
        Args:
            many_trades: List of trades that aggregate (multiple smaller trades)
            one_trade: Single trade that represents the aggregation
            direction: Direction of aggregation for proper assignment
            pool_manager: Pool manager for validation
            
        Returns:
            MatchResult if match is valid, None otherwise
        """
        try:
            # Validate the aggregation
            if not self._validate_aggregation_match(many_trades, one_trade):
                return None
            
            # Generate unique match ID
            match_id = f"AGG_{uuid.uuid4().hex[:8].upper()}"
            
            # Fields that match exactly (all except quantity)
            matched_fields = [
                "product_name",
                "contract_month", 
                "price",
                "buy_sell",
                "broker_group_id"
            ]
            
            # Quantity is the aggregated field
            differing_fields = ["quantity_aggregation"]
            
            # Create match result based on direction
            if direction == "trader_to_exchange":
                # Multiple trader trades → Single exchange trade
                return MatchResult(
                    match_id=match_id,
                    match_type=MatchType.AGGREGATION,
                    confidence=self.confidence,
                    trader_trade=many_trades[0],  # Primary trader trade
                    exchange_trade=one_trade,     # Single exchange trade
                    additional_trader_trades=many_trades[1:],  # Additional aggregated trader trades
                    matched_fields=matched_fields,
                    differing_fields=differing_fields,
                    tolerances_applied={
                        "quantity_aggregation": f"{len(many_trades)} trader trades → 1 exchange trade"
                    },
                    rule_order=self.rule_number
                )
            else:  # direction == "exchange_to_trader"
                # Single trader trade → Multiple exchange trades
                return MatchResult(
                    match_id=match_id,
                    match_type=MatchType.AGGREGATION,
                    confidence=self.confidence,
                    trader_trade=one_trade,       # Single trader trade
                    exchange_trade=many_trades[0], # Primary exchange trade
                    additional_exchange_trades=many_trades[1:],  # Additional aggregated exchange trades
                    matched_fields=matched_fields,
                    differing_fields=differing_fields,
                    tolerances_applied={
                        "quantity_aggregation": f"1 trader trade → {len(many_trades)} exchange trades"
                    },
                    rule_order=self.rule_number
                )
                
        except Exception as e:
            logger.error(f"Error creating aggregation match: {e}")
            return None

    def _validate_aggregation_match(self, many_trades: List[Trade], one_trade: Trade) -> bool:
        """Validate that trades form a valid aggregation match.
        
        Args:
            many_trades: List of trades that should aggregate
            one_trade: Single trade that represents the aggregation
            
        Returns:
            True if valid aggregation match, False otherwise
        """
        try:
            # Must have at least 2 trades to aggregate
            if len(many_trades) < 2:
                logger.debug("Aggregation validation failed: less than 2 trades to aggregate")
                return False
            
            # All fundamental fields must match exactly between many_trades and one_trade
            first_trade = many_trades[0]
            
            # Check fundamental fields match
            if (first_trade.product_name != one_trade.product_name or
                first_trade.contract_month != one_trade.contract_month or
                first_trade.price != one_trade.price or
                first_trade.buy_sell != one_trade.buy_sell or
                first_trade.broker_group_id != one_trade.broker_group_id):
                logger.debug("Aggregation validation failed: fundamental fields don't match")
                return False
            
            # All trades in many_trades must have identical fundamental fields
            for trade in many_trades:
                if (trade.product_name != first_trade.product_name or
                    trade.contract_month != first_trade.contract_month or
                    trade.price != first_trade.price or
                    trade.buy_sell != first_trade.buy_sell or
                    trade.broker_group_id != first_trade.broker_group_id):
                    logger.debug("Aggregation validation failed: many_trades have different fundamental fields")
                    return False
            
            # Quantity sum validation: sum of many_trades must equal one_trade quantity
            total_quantity = sum(trade.quantity_mt for trade in many_trades)
            if total_quantity != one_trade.quantity_mt:
                logger.debug(f"Aggregation validation failed: quantity sum {total_quantity} != {one_trade.quantity_mt}")
                return False
            
            logger.debug(f"✅ Aggregation validation passed: {len(many_trades)} trades sum to {total_quantity} MT")
            return True
            
        except Exception as e:
            logger.error(f"Error validating aggregation match: {e}")
            return False

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
            "fields_matched": [
                "product_name",
                "contract_month",
                "price", 
                "buy_sell",
                "broker_group_id"
            ],
            "requirements": [
                "All fundamental trade details must match exactly (product, contract, price, broker, B/S)",
                "Multiple trades in one source must sum to single trade quantity in other source", 
                "Sum validation must be exact (no quantity tolerance)",
                "Handles both many→one and one→many scenarios",
                "No timestamp matching required"
            ],
            "tolerances": {
                "quantity_matching": "exact sum required",
                "field_matching": "exact"
            }
        }