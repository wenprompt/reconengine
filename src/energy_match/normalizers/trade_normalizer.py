"""Universal trade data normalizer for consistent matching."""

import re
from decimal import Decimal
from typing import Dict, Any, Optional
import logging

from ..config import ConfigManager

logger = logging.getLogger(__name__)


class TradeNormalizer:
    """Normalizes trade data for consistent matching across different sources.
    
    Handles product name normalization, contract month standardization,
    quantity unit conversions, and other data standardization tasks.
    """
    
    PRODUCT_MAPPINGS = {
        "marine 0.5%": "marine 0.5%",
        "marine 0.5% crack": "marine 0.5% crack", 
        "380cst": "380cst",
        "380cst crack": "380cst crack",
        "brent swap": "brent swap"
    }
    
    MONTH_PATTERNS = {
        r'^jan\-?(\d{2})$': r'Jan-\1',
        r'^feb\-?(\d{2})$': r'Feb-\1', 
        r'^mar\-?(\d{2})$': r'Mar-\1',
        r'^apr\-?(\d{2})$': r'Apr-\1',
        r'^may\-?(\d{2})$': r'May-\1',
        r'^jun\-?(\d{2})$': r'Jun-\1',
        r'^jul\-?(\d{2})$': r'Jul-\1',
        r'^aug\-?(\d{2})$': r'Aug-\1',
        r'^sep\-?(\d{2})$': r'Sep-\1',
        r'^sept\-?(\d{2})$': r'Sep-\1',
        r'^oct\-?(\d{2})$': r'Oct-\1',
        r'^nov\-?(\d{2})$': r'Nov-\1',
        r'^dec\-?(\d{2})$': r'Dec-\1',
        r'^balmo$': 'Balmo'
    }
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the normalizer.
        
        Args:
            config_manager: Configuration manager for conversion ratios
        """
        self.config_manager = config_manager
        self.BBL_TO_MT_RATIO = config_manager.get_conversion_ratio()
    
    def normalize_product_name(self, product_name: str) -> str:
        """Normalize product name for consistent matching."""
        if not product_name:
            return ""
        product_lower = product_name.strip().lower()
        if product_lower in self.PRODUCT_MAPPINGS:
            return self.PRODUCT_MAPPINGS[product_lower]
        normalized = self._handle_product_variations(product_lower)
        logger.debug(f"Normalized product '{product_name}' -> '{normalized}'")
        return normalized
    
    def _handle_product_variations(self, product_lower: str) -> str:
        """Handle product name variations not in direct mapping."""
        if "marine" in product_lower and "0.5" in product_lower:
            return "marine 0.5% crack" if "crack" in product_lower else "marine 0.5%"
        if "380" in product_lower and "cst" in product_lower:
            return "380cst crack" if "crack" in product_lower else "380cst"
        if "brent" in product_lower and "swap" in product_lower:
            return "brent swap"
        return product_lower
    
    def normalize_contract_month(self, contract_month: str) -> str:
        """Normalize contract month to standard format."""
        if not contract_month:
            return ""
        month_clean = contract_month.strip().lower()
        for pattern, replacement in self.MONTH_PATTERNS.items():
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
            result = quantity / self.BBL_TO_MT_RATIO
            logger.debug(f"Converted {quantity} BBL -> {result} MT")
            return result
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
            result = quantity * self.BBL_TO_MT_RATIO
            logger.debug(f"Converted {quantity} MT -> {result} BBL")
            return result
        elif unit_clean == "bbl":
            return quantity
        else:
            logger.warning(f"Unknown unit '{unit}', treating as BBL")
            return quantity
    
    def normalize_all_fields(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all normalizations to trade data dictionary."""
        normalized = trade_data.copy()
        if "product_name" in normalized:
            normalized["product_name"] = self.normalize_product_name(normalized["product_name"])
        if "contract_month" in normalized:
            normalized["contract_month"] = self.normalize_contract_month(normalized["contract_month"])
        if "buy_sell" in normalized:
            normalized["buy_sell"] = self.normalize_buy_sell(normalized["buy_sell"])
        return normalized
    
    def get_similar_products(self, product_name: str) -> list[str]:
        """Get list of similar product names for fuzzy matching."""
        normalized = self.normalize_product_name(product_name)
        similar = []
        if "marine" in normalized:
            similar.extend(["marine 0.5%", "marine 0.5% crack"])
        if "380cst" in normalized:
            similar.extend(["380cst", "380cst crack"])
        if normalized in similar:
            similar.remove(normalized)
        return similar
    
    def are_adjacent_months(self, month1: str, month2: str) -> bool:
        """Check if two contract months are adjacent."""
        month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month1_parts = self._extract_month_year(month1)
        month2_parts = self._extract_month_year(month2)
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
    
    def _extract_month_year(self, contract_month: str) -> Optional[tuple[str, int]]:
        """Extract month name and year from contract month."""
        if not contract_month or contract_month == "Balmo":
            return None
        match = re.match(r'^([A-Za-z]{3})-(\d{2})$', contract_month)
        if match:
            month_name = match.group(1)
            year_short = int(match.group(2))
            year_full = 2000 + year_short
            return month_name, year_full
        return None
