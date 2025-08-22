"""Universal trade data normalizer for consistent matching."""

import re
from decimal import Decimal
import logging

from ..config import ConfigManager

logger = logging.getLogger(__name__)


class TradeNormalizer:
    """Normalizes trade data for consistent matching across different sources.
    
    Handles product name normalization, contract month standardization,
    quantity unit conversions, and other data standardization tasks.
    Loads normalization mappings from the central ConfigManager.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the normalizer."""
        self.config_manager = config_manager
        self.BBL_TO_MT_RATIO = config_manager.get_conversion_ratio()
        
        # Load mappings from the central configuration manager
        self.product_mappings = self.config_manager.get_product_mappings()
        self.month_patterns = self.config_manager.get_month_patterns()
        self.product_conversion_ratios = self.config_manager.get_product_conversion_ratios()
        self.traders_product_unit_defaults = self.config_manager.get_traders_product_unit_defaults()
        self.buy_sell_mappings = self.config_manager.get_buy_sell_mappings()

        
        logger.info(f"Loaded {len(self.product_mappings)} product mappings, "
                   f"{len(self.month_patterns)} month patterns, "
                   f"{len(self.traders_product_unit_defaults)} trader unit defaults, "
                   f"{len(self.buy_sell_mappings)} buy/sell mappings from ConfigManager")

    def normalize_product_name(self, product_name: str) -> str:
        """Normalize product name for consistent matching."""
        if not product_name:
            return ""
        product_lower = product_name.strip().lower()
        if product_lower in self.product_mappings:
            return self.product_mappings[product_lower]
        # Return as-is if no mapping found
        logger.debug(f"No mapping found for product '{product_name}', returning as-is")
        return product_lower
    
    
    def normalize_contract_month(self, contract_month: str) -> str:
        """Normalize contract month to standard format."""
        if not contract_month:
            return ""
        month_clean = contract_month.strip().lower()
        for pattern, replacement in self.month_patterns.items():
            if re.match(pattern, month_clean, re.IGNORECASE):
                result = re.sub(pattern, replacement, month_clean, flags=re.IGNORECASE)
                logger.debug(f"Normalized contract month '{contract_month}' -> '{result}'")
                return result
        logger.warning(f"No normalization pattern for contract month: '{contract_month}'")
        return contract_month.strip()
    
    def normalize_buy_sell(self, buy_sell: str) -> str:
        """Normalize buy/sell indicator to B or S using JSON configuration."""
        if not buy_sell:
            return ""
        
        value_clean = buy_sell.strip().lower()
        
        # Check against JSON mappings
        if value_clean in self.buy_sell_mappings:
            result = self.buy_sell_mappings[value_clean]
            logger.debug(f"Normalized buy/sell '{buy_sell}' -> '{result}'")
            return result
        
        # Fallback for unmapped values - return uppercase original
        logger.warning(f"Unknown buy/sell indicator: '{buy_sell}', no mapping found")
        return buy_sell.strip().upper()
    
    def convert_quantity_to_mt(self, quantity: Decimal, unit: str) -> Decimal:
        """Convert quantity to MT if needed."""
        if not quantity:
            return Decimal("0")
        unit_clean = unit.strip().lower()
        if unit_clean == "bbl":
            return quantity / self.BBL_TO_MT_RATIO
        elif unit_clean == "mt":
            return quantity
        else:
            logger.warning(f"Unknown unit '{unit}', treating as MT")
            return quantity
    
    def convert_quantity_to_bbl(self, quantity: Decimal, unit: str) -> Decimal:
        """Convert quantity to BBL if needed."""
        if not quantity:
            return Decimal("0")
        unit_clean = unit.strip().lower()
        if unit_clean == "mt":
            return quantity * self.BBL_TO_MT_RATIO
        elif unit_clean == "bbl":
            return quantity
        else:
            logger.warning(f"Unknown unit '{unit}', treating as BBL")
            return quantity


    def get_trader_product_unit_default(self, product_name: str) -> str:
        """Get default unit for trader product based on configuration.
        
        Args:
            product_name: Normalized product name
            
        Returns:
            Default unit for the product ("mt" or "bbl")
        """
        product_lower = product_name.lower().strip()
        
        # Check for exact match in trader unit defaults
        if product_lower in self.traders_product_unit_defaults:
            unit = self.traders_product_unit_defaults[product_lower]
            logger.debug(f"Found specific unit default for '{product_lower}': {unit}")
            return unit
        
        # Return default unit
        default_unit = self.traders_product_unit_defaults.get("default", "mt")
        return default_unit
