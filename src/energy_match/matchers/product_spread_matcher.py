"""Product spread matcher for Rule 5 - Product spread matching (hyphenated products)."""

import logging
import uuid
from decimal import Decimal
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..normalizers import TradeNormalizer
from ..config import ConfigManager
from ..core import UnmatchedPoolManager

logger = logging.getLogger(__name__)


class ProductSpreadMatcher:
    """Matches product spread trades (hyphenated products vs separate component trades).

    Handles Rule 5: Product Spread Match Rules
    - Exchange data: Shows hyphenated product names (e.g., "marine 0.5%-380cst")
    - Trader data: Shows separate trades for component products
    - Key pattern: Usually one leg has spread price, other has price = 0
    - Validates B/S direction logic and price calculation
    """

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the product spread matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
            normalizer: Trade normalizer for data processing
        """
        self.config_manager = config_manager
        self.normalizer = normalizer
        self.rule_number = 5
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        logger.info(f"Initialized ProductSpreadMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find product spread matches between trader and exchange data.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of product spread matches found
        """
        logger.info("Starting product spread matching (Rule 5)")
        
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()
        
        # Filter exchange trades to only hyphenated products
        hyphenated_trades = [
            t for t in exchange_trades 
            if "-" in t.product_name and self._parse_hyphenated_product(t.product_name) is not None
        ]
        
        if not hyphenated_trades:
            logger.debug("No hyphenated products found in exchange data")
            return []
        
        logger.info(f"Processing {len(hyphenated_trades)} hyphenated products "
                   f"against {len(trader_trades)} trader trades")
        
        # Debug: show hyphenated products found
        for trade in hyphenated_trades:
            logger.debug(f"Found hyphenated product: {trade.trade_id} - {trade.product_name} "
                        f"{trade.contract_month} {trade.quantity_mt} {trade.price} {trade.buy_sell}")
        
        # Create index of trader trades by product, contract, quantity, broker
        trader_index = self._create_trader_index(trader_trades)
        
        for exchange_trade in hyphenated_trades:
            match = self._find_product_spread_match(exchange_trade, trader_index, pool_manager)
            if match:
                matches.append(match)
                # Record the match to remove trades from unmatched pools
                pool_manager.record_match(match)
                logger.debug(f"Found product spread match: {match}")
        
        logger.info(f"Found {len(matches)} product spread matches")
        return matches

    def _parse_hyphenated_product(self, product_name: str) -> Optional[Tuple[str, str]]:
        """Parse hyphenated product into component products.
        
        Args:
            product_name: Hyphenated product name (e.g., "marine 0.5%-380cst")
            
        Returns:
            Tuple of (first_product, second_product) or None if not valid
        """
        if "-" not in product_name:
            return None
        
        parts = product_name.split("-", 1)
        if len(parts) != 2:
            return None
        
        first_product = parts[0].strip()
        second_product = parts[1].strip()
        
        # Ensure both components are non-empty
        if not first_product or not second_product:
            return None
            
        return (first_product, second_product)

    def _create_trader_index(self, trader_trades: List[Trade]) -> Dict[tuple, List[Trade]]:
        """Create index of trader trades by matching signature.
        
        Args:
            trader_trades: List of trader trades to index
            
        Returns:
            Dictionary mapping signatures to trader trades
        """
        index: Dict[tuple, List[Trade]] = defaultdict(list)
        
        for trade in trader_trades:
            # Index by contract month, quantity, and broker group
            signature = (
                trade.contract_month,
                trade.quantity_mt,
                trade.broker_group_id
            )
            index[signature].append(trade)
        
        logger.debug(f"Created trader index with {len(index)} unique signatures")
        return index

    def _find_product_spread_match(
        self, 
        exchange_trade: Trade, 
        trader_index: Dict[tuple, List[Trade]], 
        pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
        """Find product spread match for an exchange trade.
        
        Args:
            exchange_trade: Exchange trade with hyphenated product
            trader_index: Index of trader trades by signature
            pool_manager: Pool manager for validation
            
        Returns:
            MatchResult if match found, None otherwise
        """
        # Parse the hyphenated product
        components = self._parse_hyphenated_product(exchange_trade.product_name)
        if not components:
            return None
            
        first_product, second_product = components
        logger.debug(f"Parsed {exchange_trade.product_name} into: '{first_product}' + '{second_product}'")
        
        # Create signature for finding matching trader trades
        signature = (
            exchange_trade.contract_month,
            exchange_trade.quantity_mt,
            exchange_trade.broker_group_id
        )
        
        if signature not in trader_index:
            logger.debug(f"No trades found for signature: {signature}")
            return None
        
        # Find matching component trades in trader data
        matching_trades = trader_index[signature]
        logger.debug(f"Found {len(matching_trades)} potential trader trades for signature")
        
        # Look for two trades: one for each component product
        first_trade = None
        second_trade = None
        
        for trade in matching_trades:
            if pool_manager.is_trade_matched(trade):
                continue
                
            logger.debug(f"Checking trader trade: {trade.trade_id} - {trade.product_name} {trade.price} {trade.buy_sell}")
            
            if trade.product_name == first_product:
                first_trade = trade
                logger.debug(f"Found first product match: {trade.trade_id}")
            elif trade.product_name == second_product:
                second_trade = trade
                logger.debug(f"Found second product match: {trade.trade_id}")
        
        # Must have both component trades
        if not first_trade or not second_trade:
            logger.debug(f"Missing component trades - first: {first_trade is not None}, second: {second_trade is not None}")
            return None
        
        # Check if this is a product spread pattern (one with price, one with 0)
        if not self._is_product_spread_pattern(first_trade, second_trade):
            logger.debug(f"Not a product spread pattern - first: {first_trade.price} {first_trade.buy_sell}, second: {second_trade.price} {second_trade.buy_sell}")
            return None
        
        logger.debug(f"✅ Product spread pattern detected: {first_trade.price} {first_trade.buy_sell} + {second_trade.price} {second_trade.buy_sell}")
        
        # Validate the match
        if not self._validate_product_spread_match(
            exchange_trade, first_trade, second_trade
        ):
            logger.debug("❌ Product spread validation failed")
            return None
        
        logger.debug("✅ Product spread validation passed")
        
        # Create match result
        return self._create_match_result(exchange_trade, first_trade, second_trade)

    def _is_product_spread_pattern(self, first_trade: Trade, second_trade: Trade) -> bool:
        """Check if two trader trades form a product spread pattern.
        
        A product spread pattern is identified by:
        - One trade has the actual spread price
        - The other trade has price = 0
        - Opposite B/S directions
        
        Args:
            first_trade: First component trader trade
            second_trade: Second component trader trade
            
        Returns:
            True if this is a product spread pattern, False otherwise
        """
        # Check if one has price = 0 and the other has a non-zero price
        has_zero_price = (first_trade.price == 0) or (second_trade.price == 0)
        has_nonzero_price = (first_trade.price != 0) or (second_trade.price != 0)
        
        # Check if they have opposite B/S directions
        opposite_directions = first_trade.buy_sell != second_trade.buy_sell
        
        # Must have one zero price leg, one non-zero price leg, and opposite directions
        return has_zero_price and has_nonzero_price and opposite_directions

    def _validate_product_spread_match(
        self, 
        exchange_trade: Trade, 
        first_trader_trade: Trade, 
        second_trader_trade: Trade
    ) -> bool:
        """Validate that trades can form a product spread match.
        
        Args:
            exchange_trade: Exchange trade with hyphenated product
            first_trader_trade: First component trader trade
            second_trader_trade: Second component trader trade
            
        Returns:
            True if valid product spread match, False otherwise
        """
        try:
            # Validate B/S direction logic
            if not self._validate_direction_logic(
                exchange_trade, first_trader_trade, second_trader_trade
            ):
                logger.debug("❌ Direction logic validation failed")
                return False
            
            logger.debug("✅ Direction logic validation passed")
            
            # Validate price calculation - exact match required (no tolerance)
            if not self._validate_price_calculation(
                exchange_trade.price, 
                first_trader_trade.price, 
                second_trader_trade.price
            ):
                logger.debug("❌ Price calculation validation failed")
                return False
            
            logger.debug("✅ Price calculation validation passed")
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating product spread match: {e}")
            return False

    def _validate_direction_logic(
        self, 
        exchange_trade: Trade, 
        first_trader_trade: Trade, 
        second_trader_trade: Trade
    ) -> bool:
        """Validate product spread B/S direction logic.
        
        Args:
            exchange_trade: Exchange trade with hyphenated product
            first_trader_trade: First component trader trade  
            second_trader_trade: Second component trader trade
            
        Returns:
            True if direction logic is valid, False otherwise
        """
        # Product spread direction logic from rules.md:
        # Sell Product Spread: Exchange Sells "Product1-Product2" = Trader Sells Product1 + Buys Product2
        # Buy Product Spread: Exchange Buys "Product1-Product2" = Trader Buys Product1 + Sells Product2
        
        if exchange_trade.buy_sell == "S":
            # Sell spread = Sell first product (S) + Buy second product (B)
            return (first_trader_trade.buy_sell == "S" and 
                    second_trader_trade.buy_sell == "B")
        else:  # exchange_trade.buy_sell == "B"
            # Buy spread = Buy first product (B) + Sell second product (S)
            return (first_trader_trade.buy_sell == "B" and 
                    second_trader_trade.buy_sell == "S")

    def _validate_price_calculation(
        self, 
        exchange_price: Decimal, 
        first_price: Decimal, 
        second_price: Decimal
    ) -> bool:
        """Validate spread price calculation (exact match required).
        
        Args:
            exchange_price: Exchange spread price
            first_price: First component price
            second_price: Second component price
            
        Returns:
            True if price calculation is valid, False otherwise
        """
        # Price calculation: first_product_price - second_product_price = spread_price
        calculated_spread = first_price - second_price
        
        # Exact match required (no tolerance)
        is_valid = calculated_spread == exchange_price
        
        if not is_valid:
            logger.debug(
                f"Price calculation failed: {first_price} - {second_price} = {calculated_spread}, "
                f"expected {exchange_price} (exact match required)"
            )
        
        return is_valid

    def _create_match_result(
        self, 
        exchange_trade: Trade, 
        first_trader_trade: Trade, 
        second_trader_trade: Trade
    ) -> MatchResult:
        """Create MatchResult for product spread match.
        
        Args:
            exchange_trade: Matched exchange trade
            first_trader_trade: First component trader trade
            second_trader_trade: Second component trader trade
            
        Returns:
            MatchResult representing the product spread match
        """
        # Generate unique match ID
        match_id = f"PROD_SPREAD_{uuid.uuid4().hex[:8].upper()}"
        
        # Fields that match exactly
        matched_fields = [
            "contract_month",
            "quantity_mt", 
            "broker_group_id"
        ]
        
        # Product name and price are calculated/derived
        differing_fields = ["product_name", "price"]
        
        return MatchResult(
            match_id=match_id,
            match_type=MatchType.PRODUCT_SPREAD,
            confidence=self.confidence,
            trader_trade=first_trader_trade,  # Primary trader trade
            exchange_trade=exchange_trade,
            additional_trader_trades=[second_trader_trade],  # Additional component trade
            matched_fields=matched_fields,
            differing_fields=differing_fields,
            rule_order=self.rule_number
        )

    def get_rule_info(self) -> dict:
        """Get information about this matching rule.
        
        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Product Spread Match",
            "match_type": MatchType.PRODUCT_SPREAD.value,
            "confidence": float(self.confidence),
            "description": "Matches hyphenated exchange products with separate component trader trades",
            "fields_matched": [
                "contract_month",
                "quantity_mt",
                "broker_group_id"
            ],
            "requirements": [
                "Exchange product must be hyphenated (e.g., 'marine 0.5%-380cst')",
                "Trader must have separate trades for each component product",
                "B/S direction logic: Sell spread = Sell first + Buy second",
                "Price calculation: first_price - second_price = spread_price",
                "Same contract month, quantity, and broker group"
            ],
            "tolerances": {
                "price_matching": "exact"
            }
        }