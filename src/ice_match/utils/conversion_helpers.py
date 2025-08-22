"""Conversion utility functions that depend on configuration.

This module contains utility functions for unit conversion and quantity validation
that require access to configuration data. These functions are separated from
pure helpers to maintain clean dependency boundaries.

Functions:
    get_product_conversion_ratio: Get product-specific MT to BBL conversion ratios
    convert_mt_to_bbl_with_product_ratio: Convert MT to BBL using product ratios
    validate_mt_to_bbl_quantity_match: Validate quantity matches with conversion

These functions are used by Rules 3, 4, and 10 for crack and complex crack matching
where product-specific conversion ratios are critical for accurate quantity matching.

Note: These functions require ConfigManager access and are separated from pure
utility functions in trade_helpers.py to maintain clear architectural boundaries.
"""

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import ConfigManager

logger = logging.getLogger(__name__)


def get_product_conversion_ratio(product_name: str, config_manager: 'ConfigManager') -> Decimal:
    """Get product-specific MT to BBL conversion ratio from configuration.
    
    Used by crack matching rules to get accurate conversion ratios for different products.
    Marine 0.5%/380cst crack uses 6.35, naphtha japan/nwe crack uses 8.9, default is 7.0.
    
    Since product names are already normalized, we can use exact matching.
    
    Args:
        product_name: Normalized product name to get conversion ratio for
        config_manager: Configuration manager with product conversion ratios
        
    Returns:
        Product-specific conversion ratio, fallback to default 7.0
        
    Examples:
        >>> get_product_conversion_ratio("marine 0.5% crack", config_manager)
        Decimal('6.35')
        >>> get_product_conversion_ratio("naphtha crack", config_manager)
        Decimal('8.9')
        >>> get_product_conversion_ratio("unknown product", config_manager)
        Decimal('7.0')
    """
    product_conversion_ratios = config_manager.get_product_conversion_ratios()
    product_lower = product_name.lower().strip()
    
    # Direct exact match since product names are already normalized
    if product_lower in product_conversion_ratios:
        return Decimal(str(product_conversion_ratios[product_lower]))
    
    # Fallback to default ratio
    default_ratio = product_conversion_ratios.get("default", 7.0)
    return Decimal(str(default_ratio))


def convert_mt_to_bbl_with_product_ratio(
    quantity_mt: Decimal, product_name: str, config_manager: 'ConfigManager'
) -> Decimal:
    """Convert MT quantity to BBL using product-specific conversion ratio.
    
    This is the shared MT→BBL conversion method used by Rules 3, 4, and 10.
    Essential for accurate quantity matching when trader data is in MT and exchange data is in BBL.
    
    Args:
        quantity_mt: Quantity in metric tons
        product_name: Product name to determine conversion ratio
        config_manager: Configuration manager with product conversion ratios
        
    Returns:
        Converted quantity in barrels (BBL)
        
    Examples:
        >>> convert_mt_to_bbl_with_product_ratio(Decimal('1000'), "marine 0.5% crack", config_manager)
        Decimal('6350.0')  # 1000 * 6.35
        >>> convert_mt_to_bbl_with_product_ratio(Decimal('500'), "naphtha crack", config_manager)
        Decimal('4450.0')  # 500 * 8.9
    """
    product_ratio = get_product_conversion_ratio(product_name, config_manager)
    converted_bbl = quantity_mt * product_ratio
    
    logger.debug(
        f"MT→BBL conversion: {quantity_mt} MT × {product_ratio} = {converted_bbl} BBL for {product_name}"
    )
    return converted_bbl


def validate_mt_to_bbl_quantity_match(
    trader_quantity_mt: Decimal, 
    exchange_quantity_bbl: Decimal, 
    product_name: str, 
    bbl_tolerance: Decimal,
    config_manager: 'ConfigManager'
) -> bool:
    """Validate MT vs BBL quantity match using product-specific conversion.
    
    This is the shared validation method used by Rules 3, 4, and 10.
    Converts trader MT to BBL using product-specific ratios, then compares with exchange BBL data.
    
    Args:
        trader_quantity_mt: Trader quantity in MT
        exchange_quantity_bbl: Exchange quantity in BBL
        product_name: Product name for conversion ratio
        bbl_tolerance: BBL tolerance (dynamically loaded from config)
        config_manager: Configuration manager with product conversion ratios
        
    Returns:
        True if quantities match within BBL tolerance after conversion
        
    Examples:
        >>> validate_mt_to_bbl_quantity_match(
        ...     Decimal('1000'), Decimal('6300'), "marine 0.5% crack", Decimal('500'), config_manager
        ... )
        True  # 1000*6.35=6350, diff=50 < 500 tolerance
        >>> validate_mt_to_bbl_quantity_match(
        ...     Decimal('1000'), Decimal('5000'), "marine 0.5% crack", Decimal('500'), config_manager
        ... )
        False  # 1000*6.35=6350, diff=1350 > 500 tolerance
    """
    # Convert trader MT to BBL using product-specific ratio
    trader_quantity_bbl = convert_mt_to_bbl_with_product_ratio(
        trader_quantity_mt, product_name, config_manager
    )
    
    # Compare BBL vs BBL with tolerance
    qty_diff_bbl = abs(trader_quantity_bbl - exchange_quantity_bbl)
    is_match = qty_diff_bbl <= bbl_tolerance
    
    logger.debug(
        f"MT→BBL quantity validation: {trader_quantity_mt} MT → {trader_quantity_bbl} BBL "
        f"vs {exchange_quantity_bbl} BBL = {qty_diff_bbl} BBL diff "
        f"(tolerance: ±{bbl_tolerance} BBL) → {'MATCH' if is_match else 'NO MATCH'}"
    )
    
    return is_match