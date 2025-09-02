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

3. **Fly Pattern Utilities (fly_helpers)**: Optimized helpers for butterfly spread matching
   - group_trades_by_month: Group trades by contract month
   - build_month_quantity_lookups: Build O(1) quantity lookup indexes
   - generate_month_triplets: Generate chronological month triplets
   - find_fly_candidates_for_triplet: Find fly candidates using optimized lookups

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

from .fly_helpers import (
    group_trades_by_month,
    build_month_quantity_lookups,
    generate_month_triplets,
    find_fly_candidates_for_triplet,
)

__all__ = [
    "extract_base_product",
    "extract_month_year",
    "get_month_order_tuple",
    "get_product_conversion_ratio",
    "convert_mt_to_bbl_with_product_ratio",
    "validate_mt_to_bbl_quantity_match",
    "group_trades_by_month",
    "build_month_quantity_lookups",
    "generate_month_triplets",
    "find_fly_candidates_for_triplet",
]
