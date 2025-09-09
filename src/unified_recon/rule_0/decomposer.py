"""Generic product decomposer for unified Rule 0."""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Dict, Any


@dataclass
class DecomposedProduct:
    """Represents a decomposed product component."""

    base_product: str
    quantity: Decimal
    is_synthetic: bool = False  # True if derived from decomposition


class UnifiedDecomposer:
    """Generic decomposer that uses exchange-specific patterns from config."""

    def __init__(self, decomposition_patterns: Optional[Dict[str, Any]] = None):
        """Initialize with exchange-specific decomposition patterns.

        Args:
            decomposition_patterns: Dict with "crack" and/or "spread" patterns
        """
        self.patterns = decomposition_patterns or {}
        self.crack_pattern: Optional[str] = self.patterns.get(
            "crack"
        )  # e.g., "brent swap" for ICE
        self.spread_pattern: Optional[str] = self.patterns.get(
            "spread"
        )  # e.g., "-" for spreads

    def decompose(
        self, product_name: str, quantity: Decimal, buy_sell: str
    ) -> List[DecomposedProduct]:
        """Decompose a product based on configured patterns.

        Args:
            product_name: Product name to decompose
            quantity: Trade quantity
            buy_sell: Buy/Sell indicator

        Returns:
            List of decomposed components
        """
        product_lower = product_name.lower()

        # Check for crack pattern (ICE only)
        if self.crack_pattern and "crack" in product_lower:
            return self._decompose_crack(product_name, quantity)

        # Check for spread pattern (ICE and SGX)
        if self.spread_pattern and self.spread_pattern in product_name:
            return self._decompose_spread(product_name, quantity)

        # No decomposition - return as-is
        return [
            DecomposedProduct(
                base_product=product_name,
                quantity=quantity,
                is_synthetic=False,
            ),
        ]

    def _decompose_crack(
        self, product_name: str, quantity: Decimal
    ) -> List[DecomposedProduct]:
        """Decompose a crack product into base and synthetic components.

        Args:
            product_name: Product name containing "crack"
            quantity: Trade quantity

        Returns:
            List with base product and synthetic brent swap
        """
        # Extract base product (remove standalone "crack" anywhere, case-insensitive)
        base_product = re.sub(r"\bcrack\b", "", product_name, flags=re.IGNORECASE)
        base_product = re.sub(r"\s{2,}", " ", base_product).strip()

        return [
            DecomposedProduct(
                base_product=base_product,
                quantity=quantity,
                is_synthetic=False,  # Base product of crack
            ),
            DecomposedProduct(
                base_product=self.crack_pattern
                or "",  # e.g., "brent swap", shouldn't be None here
                quantity=quantity,
                is_synthetic=True,  # Synthetic component
            ),
        ]

    def _decompose_spread(
        self, product_name: str, quantity: Decimal
    ) -> List[DecomposedProduct]:
        """Decompose a spread product into two components.

        Args:
            product_name: Product name containing spread pattern
            quantity: Trade quantity

        Returns:
            List with first and second spread components, or original if invalid
        """
        # Split on the spread pattern
        parts = product_name.split(self.spread_pattern, 1)
        if len(parts) == 2:
            first_product = parts[0].strip()
            second_product = parts[1].strip()

            # Validate that both parts exist and are different
            if (
                not first_product
                or not second_product
                or first_product == second_product
            ):
                # Invalid spread - return as-is without decomposition
                return [
                    DecomposedProduct(
                        base_product=product_name,
                        quantity=quantity,
                        is_synthetic=False,
                    ),
                ]

            return [
                DecomposedProduct(
                    base_product=first_product,
                    quantity=quantity,
                    is_synthetic=False,
                ),
                DecomposedProduct(
                    base_product=second_product,
                    quantity=quantity,
                    is_synthetic=True,
                ),
            ]

        # Invalid spread format - return as-is
        return [
            DecomposedProduct(
                base_product=product_name,
                quantity=quantity,
                is_synthetic=False,
            ),
        ]
