"""Universal trade data normalizer for consistent matching."""

import re
import json
from pathlib import Path
from decimal import Decimal
from typing import Dict, Any, Optional
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

        # Convert comma-separated keys in variation map to tuples for internal use
        variation_config = self.config_manager.get_product_variation_map()
        self.product_variation_map = {
            tuple(key.split(",")): value 
            for key, value in variation_config.items()
        }
        
        logger.info(f"Loaded {len(self.product_mappings)} product mappings, "
                   f"{len(self.month_patterns)} month patterns, "
                   f"{len(self.product_variation_map)} product variations, "
                   f"{len(self.traders_product_unit_defaults)} trader unit defaults from ConfigManager")

    def normalize_product_name(self, product_name: str) -> str:
        """Normalize product name for consistent matching."""
        if not product_name:
            return ""
        product_lower = product_name.strip().lower()
        if product_lower in self.product_mappings:
            return self.product_mappings[product_lower]
        normalized = self._handle_product_variations(product_lower)
        logger.debug(f"Normalized product '{product_name}' -> '{normalized}'")
        return normalized
    
    def _handle_product_variations(self, product_lower: str) -> str:
        """Handle product name variations using a data-driven map."""
        for keywords, normalized_name in self.product_variation_map.items():
            if all(keyword in product_lower for keyword in keywords):
                return normalized_name
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
        """Normalize buy/sell indicator to B or S."""
        if not buy_sell:
            return ""
        value_clean = buy_sell.strip().upper()
        if value_clean in ["B", "BUY", "BOUGHT"]:
            return "B"
        elif value_clean in ["S", "SELL", "SOLD"]:
            return "S"
        else:
            logger.warning(f"Unknown buy/sell indicator: '{buy_sell}'")
            return value_clean
    
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

    def are_adjacent_months(self, month1: str, month2: str) -> bool:
        """Check if two contract months are adjacent."""
        month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month1_parts = self.extract_month_year(month1)
        month2_parts = self.extract_month_year(month2)
        if not month1_parts or not month2_parts:
            return False
        month1_name, year1 = month1_parts
        month2_name, year2 = month2_parts
        if year1 == year2:
            try:
                idx1 = month_order.index(month1_name)
                idx2 = month_order.index(month2_name)
                return abs(idx1 - idx2) == 1
            except ValueError:
                return False
        if abs(year1 - year2) == 1:
            if year1 < year2:
                return month1_name == "Dec" and month2_name == "Jan"
            else:
                return month2_name == "Dec" and month1_name == "Jan"
        return False
    
    def extract_month_year(self, contract_month: str) -> Optional[tuple[str, int]]:
        """Extract month name and year from contract month."""
        if not contract_month or contract_month == "Balmo":
            return None
        # This regex assumes the month is already normalized to MMM-YY
        match = re.match(r'^([A-Za-z]{3})-(\d{2})$', contract_month)
        if match:
            month_name = match.group(1)
            year_short = int(match.group(2))
            year_full = 2000 + year_short
            return month_name, year_full
        return None

    def get_month_order_tuple(self, contract_month: str) -> Optional[tuple[int, int]]:
        """Parse contract month into a comparable (year, month_order) tuple."""
        normalized_month = self.normalize_contract_month(contract_month)
        month_year_parts = self.extract_month_year(normalized_month)
        if not month_year_parts:
            return None
            
        month_abbr, year = month_year_parts
        month_order_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        month_num = month_order_map.get(month_abbr)
        
        if year and month_num:
            return (year, month_num)
        
        return None
    
    def get_product_conversion_ratio(self, product_name: str) -> Decimal:
        """Get product-specific MT to BBL conversion ratio from configuration.
        
        Since product names are already normalized, we can use exact matching.
        
        Args:
            product_name: Normalized product name to get conversion ratio for
            
        Returns:
            Product-specific conversion ratio, fallback to default 7.0
        """
        product_lower = product_name.lower().strip()
        
        # Direct exact match since product names are already normalized
        if product_lower in self.product_conversion_ratios:
            return Decimal(str(self.product_conversion_ratios[product_lower]))
        
        # Fallback to default ratio
        default_ratio = self.product_conversion_ratios.get("default", 7.0)
        return Decimal(str(default_ratio))
    
    def convert_mt_to_bbl_with_product_ratio(self, quantity_mt: Decimal, product_name: str) -> Decimal:
        """Convert MT quantity to BBL using product-specific conversion ratio.
        
        This is the shared MT→BBL conversion method used by Rules 3 and 4.
        
        Args:
            quantity_mt: Quantity in metric tons
            product_name: Product name to determine conversion ratio
            
        Returns:
            Converted quantity in barrels (BBL)
        """
        product_ratio = self.get_product_conversion_ratio(product_name)
        converted_bbl = quantity_mt * product_ratio
        
        logger.debug(f"MT→BBL conversion: {quantity_mt} MT × {product_ratio} = {converted_bbl} BBL for {product_name}")
        return converted_bbl
    
    def validate_mt_to_bbl_quantity_match(
        self, 
        trader_quantity_mt: Decimal, 
        exchange_quantity_bbl: Decimal, 
        product_name: str, 
        bbl_tolerance: Decimal
    ) -> bool:
        """Validate MT vs BBL quantity match using product-specific conversion.
        
        This is the shared validation method used by Rules 3 and 4.
        
        Args:
            trader_quantity_mt: Trader quantity in MT
            exchange_quantity_bbl: Exchange quantity in BBL
            product_name: Product name for conversion ratio
            bbl_tolerance: BBL tolerance (e.g., ±100 BBL)
            
        Returns:
            True if quantities match within BBL tolerance after conversion
        """
        # Convert trader MT to BBL using product-specific ratio
        trader_quantity_bbl = self.convert_mt_to_bbl_with_product_ratio(trader_quantity_mt, product_name)
        
        # Compare BBL vs BBL with tolerance
        qty_diff_bbl = abs(trader_quantity_bbl - exchange_quantity_bbl)
        is_match = qty_diff_bbl <= bbl_tolerance
        
        logger.debug(
            f"MT→BBL quantity validation: {trader_quantity_mt} MT → {trader_quantity_bbl} BBL "
            f"vs {exchange_quantity_bbl} BBL = {qty_diff_bbl} BBL diff "
            f"(tolerance: ±{bbl_tolerance} BBL) → {'MATCH' if is_match else 'NO MATCH'}"
        )
        
        return is_match

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
