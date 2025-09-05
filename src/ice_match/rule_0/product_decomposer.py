"""Product decomposition logic for breaking down complex products into base components."""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DecomposedProduct:
    """Represents a decomposed product component."""
    
    base_product: str
    quantity: Decimal
    unit: str
    is_synthetic: bool = False  # True for derived components like in cracks/spreads


class ProductDecomposer:
    """Decomposes complex products into their base components."""
    
    def __init__(self) -> None:
        """Initialize the product decomposer."""
        # No need for specific patterns - we'll handle generically
        pass
    
    def decompose(
        self, 
        product_name: str, 
        quantity: Decimal, 
        unit: str,
        buy_sell: str
    ) -> List[DecomposedProduct]:
        """Decompose a product into its base components.
        
        Args:
            product_name: The product name to decompose
            quantity: The quantity of the product
            unit: The unit (mt or bbl)
            buy_sell: Buy (B) or Sell (S) indicator
            
        Returns:
            List of decomposed products. If not decomposable, returns the original.
        """
        product_lower = product_name.lower().strip()
        
        # Check for crack products
        if "crack" in product_lower:
            return self._decompose_crack(product_lower, quantity, unit, buy_sell)
        
        # Check for spread products (hyphenated)
        if "-" in product_lower and "crack" not in product_lower:
            return self._decompose_spread(product_lower, quantity, unit, buy_sell)
        
        # Return original product if no decomposition needed
        return [DecomposedProduct(
            base_product=product_name,
            quantity=quantity,
            unit=unit,
            is_synthetic=False
        )]
    
    def _decompose_crack(
        self, 
        product_name: str, 
        quantity: Decimal, 
        unit: str,
        buy_sell: str
    ) -> List[DecomposedProduct]:
        """Decompose a crack product into base product and brent swap.
        
        For a crack trade:
        - If buying crack: buying base product, selling brent swap
        - If selling crack: selling base product, buying brent swap
        """
        # Simply extract base product by removing "crack" from the name
        base_product = self._extract_base_from_crack(product_name)
        
        if not base_product:
            # If we can't extract, return as-is
            return [DecomposedProduct(
                base_product=product_name,
                quantity=quantity,
                unit=unit,
                is_synthetic=False
            )]
        
        # Create components
        components = [
            # Base product follows the crack direction
            DecomposedProduct(
                base_product=base_product,
                quantity=quantity,
                unit=unit,
                is_synthetic=True
            ),
            # Brent swap has opposite direction (handled in matrix builder)
            DecomposedProduct(
                base_product="brent swap",
                quantity=quantity,
                unit=unit,
                is_synthetic=True
            )
        ]
        
        logger.debug(
            f"Decomposed '{product_name}' into {base_product} and brent swap"
        )
        
        return components
    
    def _decompose_spread(
        self, 
        product_name: str, 
        quantity: Decimal, 
        unit: str,
        buy_sell: str
    ) -> List[DecomposedProduct]:
        """Decompose a spread product into its components.
        
        For a spread trade (e.g., 0.5% marine-380cst):
        - If buying spread: buying first product, selling second product
        - If selling spread: selling first product, buying second product
        """
        # Generic hyphenated pattern - just split on the hyphen
        parts = product_name.split("-", 1)
        if len(parts) != 2:
            # Can't decompose if not properly hyphenated
            return [DecomposedProduct(
                base_product=product_name,
                quantity=quantity,
                unit=unit,
                is_synthetic=False
            )]
        
        first_product = parts[0].strip()
        second_product = parts[1].strip()
        
        components = [
            # First product follows spread direction
            DecomposedProduct(
                base_product=first_product,
                quantity=quantity,
                unit=unit,
                is_synthetic=True
            ),
            # Second product has opposite direction (handled in matrix builder)
            DecomposedProduct(
                base_product=second_product,
                quantity=quantity,
                unit=unit,
                is_synthetic=True
            )
        ]
        
        logger.debug(
            f"Decomposed '{product_name}' into {first_product} and {second_product}"
        )
        
        return components
    
    def _extract_base_from_crack(self, crack_name: str) -> Optional[str]:
        """Extract base product name from crack product name.
        
        Examples:
            "380cst crack" -> "380cst"
            "marine 0.5% crack" -> "marine 0.5%"
        """
        # Remove "crack" and clean up
        base = crack_name.replace("crack", "").strip()
        if base and base != crack_name:
            return base
        return None
    
    def get_decomposition_summary(self, product_name: str) -> str:
        """Get a summary of how a product would be decomposed.
        
        Args:
            product_name: The product to analyze
            
        Returns:
            String description of the decomposition with direction indicators
        """
        product_lower = product_name.lower().strip()
        
        if "crack" in product_lower:
            # For cracks: base product same direction, brent swap opposite
            base = self._extract_base_from_crack(product_lower)
            if base:
                return f"{product_name} → {base} (same direction) - brent swap (opposite direction)"
        
        if "-" in product_lower and "crack" not in product_lower:
            # For spreads: first product same direction, second opposite
            parts = product_lower.split("-", 1)
            if len(parts) == 2:
                return f"{product_name} → {parts[0].strip()} (same direction) - {parts[1].strip()} (opposite direction)"
        
        return f"{product_name} → No decomposition"