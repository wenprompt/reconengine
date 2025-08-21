"""Product spread mixin with shared utility methods."""

from typing import Optional, Tuple
from decimal import Decimal
from ..models import Trade


class ProductSpreadMixin:
    """Mixin for product spread matchers providing shared utility methods."""
    
    def _parse_hyphenated_product(self, product_name: str) -> Optional[Tuple[str, str]]:
        """Parse hyphenated product into component products.
        
        Args:
            product_name: Hyphenated product name (e.g., "marine 0.5%-380cst")
            
        Returns:
            Tuple of (first_product, second_product) or None if not valid
        """
        if not product_name or "-" not in product_name:
            return None

        parts = product_name.split("-", 1)
        if len(parts) != 2:
            return None

        first_product = parts[0].strip()
        second_product = parts[1].strip()

        if not first_product or not second_product or first_product == second_product:
            return None

        return (first_product, second_product)
    
    def _is_hyphenated_product(self, product_name: str) -> bool:
        """Check if product name is hyphenated.
        
        Args:
            product_name: Product name to check
            
        Returns:
            True if product is hyphenated and valid, False otherwise
        """
        return "-" in product_name and self._parse_hyphenated_product(product_name) is not None
    
    def _is_different_products(self, trade1: Trade, trade2: Trade) -> bool:
        """Check if two trades have different product names.
        
        Args:
            trade1: First trade
            trade2: Second trade
            
        Returns:
            True if products are different, False otherwise
        """
        return trade1.product_name != trade2.product_name
    
    def _is_product_spread_pattern(self, trade1: Trade, trade2: Trade, require_different_products: bool = True) -> bool:
        """Check if two trades form a product spread pattern.
        
        A product spread pattern is identified by:
        - One trade has the actual spread price (positive, negative, or zero)
        - The other trade has price = 0 (reference leg)
        - Opposite B/S directions
        - Optionally different products (configurable)
        
        Args:
            trade1: First trade
            trade2: Second trade
            require_different_products: Whether to require different product names
            
        Returns:
            True if this is a product spread pattern, False otherwise
        """
        # Check product names if required
        if require_different_products and trade1.product_name == trade2.product_name:
            return False

        # Must have opposite B/S directions
        if trade1.buy_sell == trade2.buy_sell:
            return False

        # One must have any price (positive, negative, or zero), other must have price = 0
        prices = [trade1.price, trade2.price]
        zero_count = sum(1 for p in prices if p == Decimal("0"))
        
        return zero_count == 1