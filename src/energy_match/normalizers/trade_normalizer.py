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
    Loads normalization mappings from external configuration files.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the normalizer."""
        self.config_manager = config_manager
        self.BBL_TO_MT_RATIO = config_manager.get_conversion_ratio()
        
        # Load mappings from configuration file
        self._load_normalizer_config()
        
        logger.info(f"Loaded {len(self.product_mappings)} product mappings, "
                   f"{len(self.month_patterns)} month patterns, "
                   f"{len(self.product_variation_map)} product variations")
    
    def _load_normalizer_config(self):
        """Load normalizer configuration from JSON file."""
        config_path = Path(__file__).parent.parent / "config" / "normalizer_config.json"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Load product mappings
            self.product_mappings = config.get("product_mappings", {})
            
            # Load month patterns
            self.month_patterns = config.get("month_patterns", {})
            
            # Load product variation map - convert comma-separated keys back to tuples
            variation_config = config.get("product_variation_map", {})
            self.product_variation_map = {
                tuple(key.split(",")): value 
                for key, value in variation_config.items()
            }
            
            logger.debug(f"Successfully loaded normalizer config from {config_path}")
            
        except FileNotFoundError:
            logger.error(f"Normalizer config file not found: {config_path}")
            # Fallback to empty mappings
            self.product_mappings = {}
            self.month_patterns = {}
            self.product_variation_map = {}
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in normalizer config: {e}")
            # Fallback to empty mappings
            self.product_mappings = {}
            self.month_patterns = {}
            self.product_variation_map = {}
            
        except Exception as e:
            logger.error(f"Error loading normalizer config: {e}")
            # Fallback to empty mappings
            self.product_mappings = {}
            self.month_patterns = {}
            self.product_variation_map = {}
    
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
