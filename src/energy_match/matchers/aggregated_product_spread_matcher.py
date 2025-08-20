"""Aggregated product spread matcher for Rule 11 - Product spread matching with aggregation logic."""

import logging
import uuid
from decimal import Decimal
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..normalizers import TradeNormalizer
from ..config import ConfigManager
from ..core import UnmatchedPoolManager
from .aggregation_base_matcher import AggregationBaseMatcher

logger = logging.getLogger(__name__)


class AggregatedProductSpreadMatcher(AggregationBaseMatcher):
    """Matches product spread trades with aggregation logic between trader and exchange data.

    Handles Rule 11: Aggregated Product Spread Match Rules
    Combines aggregation patterns (1-to-many, many-to-1) with product spread logic:
    
    Scenarios:
    - Many exchange product spread trades → One trader spread pair
    - One exchange spread → Many trader trades per product leg
    - Handles both hyphenated exchange products and 2-leg formats with aggregation
    """

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the aggregated product spread matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
            normalizer: Trade normalizer for data processing
        """
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 11
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        logger.info(f"Initialized AggregatedProductSpreadMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find aggregated product spread matches between trader and exchange data.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of aggregated product spread matches found
        """
        logger.info("Starting aggregated product spread matching (Rule 11)")
        
        matches: List[MatchResult] = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()
        
        # Scenario A: Many exchange trades → One trader spread pair
        exchange_to_trader_matches = self._find_aggregated_exchange_to_trader_matches(
            trader_trades, exchange_trades, pool_manager
        )
        matches.extend(exchange_to_trader_matches)
        
        # Scenario B: One exchange spread → Many trader trades per leg
        trader_to_exchange_matches = self._find_aggregated_trader_to_exchange_matches(
            trader_trades, exchange_trades, pool_manager
        )
        matches.extend(trader_to_exchange_matches)
        
        logger.info(f"Found {len(matches)} aggregated product spread matches")
        return matches

    def _find_aggregated_exchange_to_trader_matches(
        self, 
        trader_trades: List[Trade], 
        exchange_trades: List[Trade], 
        pool_manager: UnmatchedPoolManager
    ) -> List[MatchResult]:
        """Find matches where multiple exchange trades aggregate to trader spread pairs.
        
        Args:
            trader_trades: List of trader trades
            exchange_trades: List of exchange trades
            pool_manager: Pool manager for validation
            
        Returns:
            List of matches found for aggregated exchange → trader spreads
        """
        matches: List[MatchResult] = []
        
        # Find trader spread pairs (price/0.00 pattern)
        trader_spread_pairs = self._find_trader_spread_pairs(trader_trades, pool_manager)
        
        if not trader_spread_pairs:
            logger.debug("No trader spread pairs found for aggregated matching")
            return matches
        
        logger.info(f"Processing {len(trader_spread_pairs)} trader spread pairs for exchange aggregation")
        
        # For each trader spread pair, find aggregated exchange trades
        for spread_pair in trader_spread_pairs:
            if any(pool_manager.is_trade_matched(trade) for trade in spread_pair):
                continue
                
            match = self._find_exchange_aggregation_for_trader_spread(
                spread_pair, exchange_trades, pool_manager
            )
            if match:
                matches.append(match)
                pool_manager.record_match(match)
                logger.info(f"Found aggregated exchange→trader match: {match.match_id}")
        
        logger.info(f"Found {len(matches)} aggregated exchange→trader matches")
        return matches

    def _find_aggregated_trader_to_exchange_matches(
        self, 
        trader_trades: List[Trade], 
        exchange_trades: List[Trade], 
        pool_manager: UnmatchedPoolManager
    ) -> List[MatchResult]:
        """Find matches where multiple trader trades per leg aggregate to exchange spreads.
        
        Args:
            trader_trades: List of trader trades
            exchange_trades: List of exchange trades
            pool_manager: Pool manager for validation
            
        Returns:
            List of matches found for aggregated trader → exchange spreads
        """
        matches: List[MatchResult] = []
        
        # Find exchange spread trades (both hyphenated and 2-leg)
        exchange_spreads = self._find_exchange_spread_trades(exchange_trades, pool_manager)
        
        if not exchange_spreads:
            logger.debug("No exchange spread trades found for aggregated matching")
            return matches
        
        logger.info(f"Processing {len(exchange_spreads)} exchange spreads for trader aggregation")
        
        # For each exchange spread, find aggregated trader trades
        for exchange_spread in exchange_spreads:
            if pool_manager.is_trade_matched(exchange_spread):
                continue
                
            match = self._find_trader_aggregation_for_exchange_spread(
                exchange_spread, trader_trades, pool_manager
            )
            if match:
                matches.append(match)
                pool_manager.record_match(match)
                logger.info(f"Found aggregated trader→exchange match: {match.match_id}")
        
        logger.info(f"Found {len(matches)} aggregated trader→exchange matches")
        return matches

    def _find_trader_spread_pairs(
        self, 
        trader_trades: List[Trade], 
        pool_manager: UnmatchedPoolManager
    ) -> List[Tuple[Trade, Trade]]:
        """Find trader spread pairs (price/0.00 pattern with opposite B/S)."""
        spread_pairs = []
        
        # Group trades by aggregation signature (contract month, quantity, universal fields)
        aggregation_fields = ["contract_month", "quantity_mt"]
        trade_groups = self.group_trades_by_aggregation_signature(trader_trades, aggregation_fields)
        
        for group_signature, group_trades in trade_groups.items():
            if len(group_trades) < 2:
                continue
                
            # Find spread patterns within each group
            for i in range(len(group_trades)):
                for j in range(i + 1, len(group_trades)):
                    trade1, trade2 = group_trades[i], group_trades[j]
                    
                    if (pool_manager.is_trade_matched(trade1) or 
                        pool_manager.is_trade_matched(trade2)):
                        continue
                    
                    if self._is_product_spread_pattern(trade1, trade2):
                        # Order so price trade comes first
                        if trade1.price != Decimal("0"):
                            spread_pairs.append((trade1, trade2))
                        else:
                            spread_pairs.append((trade2, trade1))
                        
                        logger.debug(f"Found trader spread pair: {trade1.trade_id} + {trade2.trade_id}")
                        break  # Only one pair per trade
        
        return spread_pairs

    def _find_exchange_spread_trades(
        self, 
        exchange_trades: List[Trade], 
        pool_manager: UnmatchedPoolManager
    ) -> List[Trade]:
        """Find exchange spread trades (hyphenated products and 2-leg spreads)."""
        spread_trades = []
        
        # Find hyphenated products
        for trade in exchange_trades:
            if pool_manager.is_trade_matched(trade):
                continue
                
            if self._is_hyphenated_product(trade.product_name):
                spread_trades.append(trade)
                logger.debug(f"Found hyphenated exchange spread: {trade.trade_id} - {trade.product_name}")
        
        # TODO: Could also add 2-leg exchange spread detection here if needed
        
        return spread_trades

    def _find_exchange_aggregation_for_trader_spread(
        self, 
        trader_spread_pair: Tuple[Trade, Trade], 
        exchange_trades: List[Trade], 
        pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
        """Find aggregated exchange trades that match trader spread pair."""
        price_trade, zero_trade = trader_spread_pair
        
        # Parse trader product components 
        if not self._is_different_products(price_trade, zero_trade):
            logger.debug("Trader spread pair doesn't have different products")
            return None
        
        # Find exchange trades for each product component
        price_product_candidates = []
        zero_product_candidates = []
        
        for exchange_trade in exchange_trades:
            if pool_manager.is_trade_matched(exchange_trade):
                continue
                
            # Check universal fields first
            if not self.validate_universal_fields(price_trade, exchange_trade):
                continue
                
            # Must match contract month and quantity
            if (exchange_trade.contract_month != price_trade.contract_month or 
                exchange_trade.quantity_mt != price_trade.quantity_mt):
                continue
            
            # Group by product
            if exchange_trade.product_name == price_trade.product_name:
                price_product_candidates.append(exchange_trade)
            elif exchange_trade.product_name == zero_trade.product_name:
                zero_product_candidates.append(exchange_trade)
        
        if not price_product_candidates or not zero_product_candidates:
            logger.debug("Insufficient exchange candidates for trader spread components")
            return None
        
        # Try to find aggregation matches for each component
        price_aggregation = self._find_component_aggregation(
            price_product_candidates, price_trade, pool_manager
        )
        zero_aggregation = self._find_component_aggregation(
            zero_product_candidates, zero_trade, pool_manager
        )
        
        if not price_aggregation or not zero_aggregation:
            return None
        
        # Validate the complete aggregated spread match
        if self._validate_aggregated_spread_match(
            trader_spread_pair, price_aggregation, zero_aggregation
        ):
            return self._create_aggregated_spread_match_result(
                trader_spread_pair, price_aggregation, zero_aggregation
            )
        
        return None

    def _find_trader_aggregation_for_exchange_spread(
        self, 
        exchange_spread: Trade, 
        trader_trades: List[Trade], 
        pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
        """Find aggregated trader trades that match exchange spread."""
        
        # Parse hyphenated product
        components = self._parse_hyphenated_product(exchange_spread.product_name)
        if not components:
            return None
            
        first_product, second_product = components
        
        # Find trader trades for each component
        first_candidates = []
        second_candidates = []
        
        for trader_trade in trader_trades:
            if pool_manager.is_trade_matched(trader_trade):
                continue
                
            # Check universal fields and basic matching criteria
            if (not self.validate_universal_fields(exchange_spread, trader_trade) or
                trader_trade.contract_month != exchange_spread.contract_month or
                trader_trade.quantity_mt != exchange_spread.quantity_mt):
                continue
            
            if trader_trade.product_name == first_product:
                first_candidates.append(trader_trade)
            elif trader_trade.product_name == second_product:
                second_candidates.append(trader_trade)
        
        if not first_candidates or not second_candidates:
            return None
        
        # Try to find aggregated trader combinations
        first_aggregation = self._find_trader_component_aggregation(
            first_candidates, exchange_spread, pool_manager
        )
        second_aggregation = self._find_trader_component_aggregation(
            second_candidates, exchange_spread, pool_manager
        )
        
        if not first_aggregation or not second_aggregation:
            return None
        
        # Validate and create match result
        if self._validate_trader_aggregated_spread_match(
            exchange_spread, first_aggregation, second_aggregation
        ):
            return self._create_trader_aggregated_spread_match_result(
                exchange_spread, first_aggregation, second_aggregation
            )
        
        return None

    def _find_component_aggregation(
        self, 
        candidates: List[Trade], 
        target_trade: Trade, 
        pool_manager: UnmatchedPoolManager
    ) -> Optional[List[Trade]]:
        """Find aggregation of exchange trades that matches target trader trade."""
        
        # Define aggregation fields for product spread components
        aggregation_fields = ["product_name", "contract_month", "price", "buy_sell"]
        
        # Use base class aggregation logic
        aggregations = self.find_many_to_one_aggregations(
            candidates, [target_trade], pool_manager, aggregation_fields, min_aggregation_size=1
        )
        
        # Return first valid aggregation
        for aggregated_trades, single_trade in aggregations:
            if single_trade == target_trade:
                return aggregated_trades
        
        return None

    def _find_trader_component_aggregation(
        self, 
        candidates: List[Trade], 
        target_exchange: Trade, 
        pool_manager: UnmatchedPoolManager
    ) -> Optional[List[Trade]]:
        """Find aggregation of trader trades for exchange component."""
        
        # Group candidates by aggregation characteristics
        aggregation_groups = defaultdict(list)
        
        for trade in candidates:
            if pool_manager.is_trade_matched(trade):
                continue
                
            # Group by characteristics that must match for aggregation
            group_key = (trade.product_name, trade.contract_month, trade.buy_sell, trade.price)
            aggregation_groups[group_key].append(trade)
        
        # Look for groups that can aggregate to match exchange quantity
        for group_trades in aggregation_groups.values():
            if len(group_trades) < 2:  # Need aggregation
                continue
                
            total_quantity = sum(trade.quantity_mt for trade in group_trades)
            if total_quantity == target_exchange.quantity_mt:
                # Validate aggregation consistency
                if self.validate_aggregation_consistency(group_trades, target_exchange):
                    return group_trades
        
        return None

    def _is_product_spread_pattern(self, trade1: Trade, trade2: Trade) -> bool:
        """Check if two trades form a product spread pattern (price/0.00, opposite B/S, different products)."""
        # Must have different products
        if trade1.product_name == trade2.product_name:
            return False
            
        # Must have opposite B/S directions
        if trade1.buy_sell == trade2.buy_sell:
            return False
            
        # One must have price > 0, other must have price = 0
        prices = [trade1.price, trade2.price]
        return Decimal("0") in prices and any(p > Decimal("0") for p in prices)

    def _is_different_products(self, trade1: Trade, trade2: Trade) -> bool:
        """Check if two trades have different product names."""
        return trade1.product_name != trade2.product_name

    def _is_hyphenated_product(self, product_name: str) -> bool:
        """Check if product name is hyphenated."""
        return "-" in product_name and self._parse_hyphenated_product(product_name) is not None

    def _parse_hyphenated_product(self, product_name: str) -> Optional[Tuple[str, str]]:
        """Parse hyphenated product into component products."""
        if "-" not in product_name:
            return None
        
        parts = product_name.split("-", 1)
        if len(parts) != 2:
            return None
        
        first_product = parts[0].strip()
        second_product = parts[1].strip()
        
        if not first_product or not second_product:
            return None
            
        return (first_product, second_product)

    def _validate_aggregated_spread_match(
        self,
        trader_spread_pair: Tuple[Trade, Trade],
        price_aggregation: List[Trade],
        zero_aggregation: List[Trade]
    ) -> bool:
        """Validate aggregated exchange trades match trader spread pair."""
        price_trade, zero_trade = trader_spread_pair
        
        # Validate quantities (should already be validated by aggregation logic)
        price_total = sum(trade.quantity_mt for trade in price_aggregation)
        zero_total = sum(trade.quantity_mt for trade in zero_aggregation)
        
        if (price_total != price_trade.quantity_mt or 
            zero_total != zero_trade.quantity_mt):
            return False
        
        # Validate B/S directions match
        price_direction = price_aggregation[0].buy_sell
        zero_direction = zero_aggregation[0].buy_sell
        
        if (price_direction != price_trade.buy_sell or 
            zero_direction != zero_trade.buy_sell):
            return False
        
        # Validate price calculation
        price_component_price = price_aggregation[0].price
        zero_component_price = zero_aggregation[0].price
        
        calculated_spread = price_component_price - zero_component_price
        if calculated_spread != price_trade.price:
            return False
        
        return True

    def _validate_trader_aggregated_spread_match(
        self,
        exchange_spread: Trade,
        first_aggregation: List[Trade],
        second_aggregation: List[Trade]
    ) -> bool:
        """Validate aggregated trader trades match exchange spread."""
        
        # Validate total quantities
        first_total = sum(trade.quantity_mt for trade in first_aggregation)
        second_total = sum(trade.quantity_mt for trade in second_aggregation)
        
        if (first_total != exchange_spread.quantity_mt or 
            second_total != exchange_spread.quantity_mt):
            return False
        
        # Validate B/S directions form proper spread pattern
        first_direction = first_aggregation[0].buy_sell
        second_direction = second_aggregation[0].buy_sell
        
        # Must have opposite directions
        if first_direction == second_direction:
            return False
        
        # Validate direction logic matches exchange spread
        components = self._parse_hyphenated_product(exchange_spread.product_name)
        if not components:
            return False
        
        first_product, second_product = components
        
        # Check direction logic based on exchange spread direction
        if exchange_spread.buy_sell == "B":
            # Buy spread = Buy first + Sell second
            expected_first_direction = "B"
            expected_second_direction = "S"
        else:
            # Sell spread = Sell first + Buy second  
            expected_first_direction = "S"
            expected_second_direction = "B"
        
        if (first_direction != expected_first_direction or 
            second_direction != expected_second_direction):
            return False
        
        # Validate price calculation
        first_price = first_aggregation[0].price
        second_price = second_aggregation[0].price
        calculated_spread = first_price - second_price
        
        return calculated_spread == exchange_spread.price

    def _create_aggregated_spread_match_result(
        self,
        trader_spread_pair: Tuple[Trade, Trade],
        price_aggregation: List[Trade],
        zero_aggregation: List[Trade]
    ) -> MatchResult:
        """Create match result for aggregated exchange → trader spread."""
        
        price_trade, zero_trade = trader_spread_pair
        all_exchange_trades = price_aggregation + zero_aggregation
        
        # Generate unique match ID
        match_id = f"AGG_PROD_SPREAD_{uuid.uuid4().hex[:8].upper()}"
        
        # Rule-specific fields
        rule_specific_fields = [
            "product_components",
            "contract_month", 
            "quantity_aggregation",
            "buy_sell_spread",
            "price_differential"
        ]
        
        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)
        
        return MatchResult(
            match_id=match_id,
            match_type=MatchType.AGGREGATED_PRODUCT_SPREAD,
            confidence=self.confidence,
            trader_trade=price_trade,  # Primary trader trade
            exchange_trade=all_exchange_trades[0],  # Primary exchange trade
            additional_trader_trades=[zero_trade],  # Zero price trader trade
            additional_exchange_trades=all_exchange_trades[1:],  # Remaining exchange trades
            matched_fields=matched_fields,
            tolerances_applied={
                "aggregation": f"{len(price_aggregation)} + {len(zero_aggregation)} exchange trades aggregated",
                "price_differential": "exact"
            },
            rule_order=self.rule_number
        )

    def _create_trader_aggregated_spread_match_result(
        self,
        exchange_spread: Trade,
        first_aggregation: List[Trade],
        second_aggregation: List[Trade]
    ) -> MatchResult:
        """Create match result for aggregated trader → exchange spread."""
        
        all_trader_trades = first_aggregation + second_aggregation
        
        # Generate unique match ID  
        match_id = f"AGG_PROD_SPREAD_{uuid.uuid4().hex[:8].upper()}"
        
        # Rule-specific fields
        rule_specific_fields = [
            "product_spread",
            "contract_month",
            "quantity_aggregation", 
            "buy_sell_components",
            "price_calculation"
        ]
        
        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)
        
        return MatchResult(
            match_id=match_id,
            match_type=MatchType.AGGREGATED_PRODUCT_SPREAD,
            confidence=self.confidence,
            trader_trade=all_trader_trades[0],  # Primary trader trade
            exchange_trade=exchange_spread,
            additional_trader_trades=all_trader_trades[1:],  # Remaining trader trades
            matched_fields=matched_fields,
            tolerances_applied={
                "aggregation": f"{len(first_aggregation)} + {len(second_aggregation)} trader trades aggregated",
                "price_calculation": "exact"
            },
            rule_order=self.rule_number
        )

    def get_rule_info(self) -> dict:
        """Get information about this matching rule."""
        return {
            "rule_number": self.rule_number,
            "rule_name": "Aggregated Product Spread Match",
            "match_type": MatchType.AGGREGATED_PRODUCT_SPREAD.value,
            "confidence": float(self.confidence),
            "description": "Matches product spreads with aggregation logic (1-to-many, many-to-1)",
            "requirements": [
                "Scenario A: Multiple exchange product trades → Single trader spread pair",
                "Scenario B: Single exchange spread → Multiple trader trades per component", 
                "Aggregated quantities must sum to match target quantities exactly",
                "B/S direction logic must follow product spread rules",
                "Price differential must match exactly after aggregation",
                "All trades must have matching universal fields",
                "Handles both hyphenated exchange products and 2-leg formats"
            ],
            "scenarios": [
                "Many exchange component trades → One trader spread pair", 
                "One exchange hyphenated spread → Many trader component trades"
            ]
        }