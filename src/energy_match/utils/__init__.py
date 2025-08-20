"""Utility modules for energy trade matching system.

This package provides two types of utility functions:

1. **Pure Utilities (trade_helpers)**: Functions that don't depend on configuration
   - extract_base_product: Extract base product from crack products
   - extract_month_year: Parse contract month components
   - get_month_order_tuple: Convert months to sortable tuples

2. **Config-Dependent Utilities (conversion_helpers)**: Functions requiring ConfigManager
   - get_product_conversion_ratio: Get product-specific MT↔BBL ratios
   - convert_mt_to_bbl_with_product_ratio: Convert MT to BBL with product ratios
   - validate_mt_to_bbl_quantity_match: Validate quantity matches with conversion

These utilities are separated from TradeNormalizer to improve code organization,
testability, and reusability across the energy matching system.
"""

from .trade_helpers import (
    extract_base_product,
    extract_month_year,
    get_month_order_tuple,
)

from .conversion_helpers import (
    get_product_conversion_ratio,
    convert_mt_to_bbl_with_product_ratio,
    validate_mt_to_bbl_quantity_match,
)

__all__ = [
    "extract_base_product",
    "extract_month_year",
    "get_month_order_tuple",
    "get_product_conversion_ratio",
    "convert_mt_to_bbl_with_product_ratio", 
    "validate_mt_to_bbl_quantity_match",
]