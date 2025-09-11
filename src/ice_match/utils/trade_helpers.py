"""Pure utility functions for trade processing that don't depend on configuration.

This module contains helper functions that operate on trade data without requiring
access to configuration or external dependencies. These are pure functions that
can be easily tested and reused across different parts of the ice matching system.

Functions:
    extract_base_product: Extract base product name from crack product names
    extract_month_year: Parse contract month into month abbreviation and year
    get_month_order_tuple: Convert contract month to comparable (year, month) tuple

Note: These functions are separated from the TradeNormalizer to improve code organization
and enable better testing and reusability.
"""

import re
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def extract_base_product(crack_product: str) -> Optional[str]:
    """Extract base product name from crack product name.

    Used by complex crack matching to identify the underlying base product
    from crack products like "380cst crack" → "380cst".

    Args:
        crack_product: Crack product name (e.g., "380cst crack", "naphtha crack")

    Returns:
        Base product name without "crack" suffix, or None if not a crack product

    Examples:
        >>> extract_base_product("380cst crack")
        "380cst"
        >>> extract_base_product("naphtha crack")
        "naphtha"
        >>> extract_base_product("brent swap")
        None
    """
    crack_lower = crack_product.lower().strip()

    # Remove "crack" from the end
    if crack_lower.endswith(" crack"):
        return crack_lower[:-6].strip()
    elif crack_lower.endswith("crack"):
        return crack_lower[:-5].strip()

    return None


def extract_month_year(contract_month: str) -> Optional[tuple[str, int]]:
    """Extract month name and year from contract month.

    Parses normalized contract month strings into components for further processing.

    Args:
        contract_month: Normalized contract month (e.g., "Mar-25", "Balmo")

    Returns:
        Tuple of (month_name, full_year) or None if parsing fails

    Examples:
        >>> extract_month_year("Mar-25")
        ("Mar", 2025)
        >>> extract_month_year("Dec-24")
        ("Dec", 2024)
        >>> extract_month_year("Balmo")
        None
    """
    if not contract_month or contract_month == "Balmo":
        return None
    # This regex assumes the month is already normalized to MMM-YY
    match = re.match(r"^([A-Za-z]{3})-(\d{2})$", contract_month)
    if match:
        month_name = match.group(1)
        year_short = int(match.group(2))
        year_full = 2000 + year_short
        return month_name, year_full
    return None


def get_month_order_tuple(contract_month: str) -> Optional[tuple[int, int]]:
    """Parse contract month into a comparable (year, month_order) tuple.

    Converts contract months into sortable tuples for chronological ordering.
    Used by complex crack roll matching to determine month precedence.

    Note: This function expects already normalized contract months.
    For full normalization, use TradeNormalizer.normalize_contract_month() first.

    Args:
        contract_month: Normalized contract month (e.g., "Mar-25", "Balmo")

    Returns:
        Tuple of (year, month_number) for sorting, or None if parsing fails
        Special case: "Balmo" returns (0, 0) to sort before all other months

    Examples:
        >>> get_month_order_tuple("Mar-25")
        (2025, 3)
        >>> get_month_order_tuple("Balmo")
        (0, 0)
        >>> get_month_order_tuple("Dec-24")
        (2024, 12)
    """
    # Handle Balance of Month (Balmo) and Balmo Next Day (BalmoNd)
    # These need special handling as they come before regular months
    # We use negative values to ensure they sort before regular months
    # TODO: Currently using year 0 for Balmo/BalmoNd - may need year context
    if contract_month == "Balmo":
        return (-1, 0)  # Balmo comes before everything
    if contract_month == "BalmoNd":
        return (0, 0)  # BalmoNd comes after Balmo but before regular months

    month_year_parts = extract_month_year(contract_month)
    if not month_year_parts:
        return None

    month_abbr, year = month_year_parts
    month_order_map = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }
    month_num = month_order_map.get(month_abbr)

    if year and month_num:
        return (year, month_num)

    return None
