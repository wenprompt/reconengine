"""Trade data normalizer for SGX trades."""

import re
from typing import Dict, Any, Optional
from decimal import Decimal
import logging

from ..config import SGXConfigManager

logger = logging.getLogger(__name__)


class SGXTradeNormalizer:
    """Normalizes SGX trade data from various CSV sources to standardized format."""
    
    def __init__(self, config_manager: SGXConfigManager):
        """Initialize normalizer with configuration.
        
        Args:
            config_manager: Configuration manager with normalization rules
        """
        self.config_manager = config_manager
        self._product_mappings = config_manager.get_product_mappings()
        self._month_patterns = config_manager.get_month_patterns()
        self._buy_sell_mappings = config_manager.get_buy_sell_mappings()
        
        logger.info("Initialized SGX trade normalizer")
    
    def normalize_product_name(self, product_name: str) -> str:
        """Normalize product name to standard format.
        
        Args:
            product_name: Raw product name from CSV
            
        Returns:
            Normalized product name
        """
        if not product_name:
            return ""
        
        # Clean and standardize
        cleaned = product_name.strip()
        
        # Apply mappings from config
        normalized = self._product_mappings.get(cleaned.lower(), cleaned)
        
        logger.debug(f"Normalized product name: '{product_name}' -> '{normalized}'")
        return normalized
    
    def normalize_contract_month(self, contract_month: str) -> str:
        """Normalize contract month to standard format.
        
        Args:
            contract_month: Raw contract month from CSV (e.g., "Oct25", "Oct-25")
            
        Returns:
            Normalized contract month (e.g., "Oct25")
        """
        if not contract_month:
            return ""
        
        cleaned = contract_month.strip()
        
        # Try pattern matching from config
        for pattern, replacement in self._month_patterns.items():
            match = re.match(pattern, cleaned)
            if match:
                normalized = re.sub(pattern, replacement, cleaned)
                logger.debug(f"Normalized contract month: '{contract_month}' -> '{normalized}'")
                return normalized
        
        # If no pattern matches, return cleaned version
        logger.debug(f"No pattern match for contract month: '{contract_month}', returning cleaned")
        return cleaned
    
    def normalize_buy_sell(self, buy_sell: str) -> str:
        """Normalize buy/sell indicator to standard format.
        
        Args:
            buy_sell: Raw buy/sell value from CSV
            
        Returns:
            Normalized buy/sell ("B" or "S")
        """
        if not buy_sell:
            return ""
        
        cleaned = buy_sell.strip()
        
        # Apply mappings from config  
        normalized = self._buy_sell_mappings.get(cleaned, cleaned.upper())
        
        # Ensure only B or S
        if normalized not in ["B", "S"]:
            # Try first character if mapping didn't work
            first_char = cleaned.upper()[0] if cleaned else ""
            if first_char in ["B", "S"]:
                normalized = first_char
            else:
                logger.warning(f"Unable to normalize buy/sell value: '{buy_sell}', defaulting to 'B'")
                normalized = "B"
        
        logger.debug(f"Normalized buy/sell: '{buy_sell}' -> '{normalized}'")
        return normalized
    
    def normalize_quantity(self, quantity: Any) -> Optional[Decimal]:
        """Normalize quantity to Decimal.
        
        Args:
            quantity: Raw quantity value (could be string, int, float)
            
        Returns:
            Normalized quantity as Decimal, or None if invalid
        """
        if quantity is None or quantity == "":
            return None
        
        try:
            # Convert to string first, then clean
            quantity_str = str(quantity).strip()
            
            # Remove commas and quotes
            cleaned = quantity_str.replace(",", "").replace('"', "").replace("'", "")
            
            # Convert to Decimal
            normalized = Decimal(cleaned)
            
            logger.debug(f"Normalized quantity: '{quantity}' -> '{normalized}'")
            return normalized
            
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to normalize quantity '{quantity}': {e}")
            return None
    
    def normalize_price(self, price: Any) -> Optional[Decimal]:
        """Normalize price to Decimal.
        
        Args:
            price: Raw price value (could be string, int, float)
            
        Returns:
            Normalized price as Decimal, or None if invalid
        """
        if price is None or price == "":
            return None
        
        try:
            # Convert to string first, then clean
            price_str = str(price).strip()
            
            # Remove commas
            cleaned = price_str.replace(",", "")
            
            # Convert to Decimal
            normalized = Decimal(cleaned)
            
            logger.debug(f"Normalized price: '{price}' -> '{normalized}'")
            return normalized
            
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to normalize price '{price}': {e}")
            return None
    
    def normalize_integer_field(self, value: Any) -> Optional[int]:
        """Normalize integer fields like broker_group_id.
        
        Args:
            value: Raw value to normalize to integer
            
        Returns:
            Normalized integer value, or None if invalid
        """
        if value is None or value == "":
            return None
        
        try:
            # Convert to string first, then to int
            value_str = str(value).strip()
            normalized = int(float(value_str))  # Handle decimal strings
            
            logger.debug(f"Normalized integer: '{value}' -> '{normalized}'")
            return normalized
            
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to normalize integer '{value}': {e}")
            return None
    
    def normalize_string_field(self, value: Any) -> str:
        """Normalize string fields by cleaning whitespace.
        
        Args:
            value: Raw value to normalize
            
        Returns:
            Normalized string value
        """
        if value is None:
            return ""
        
        normalized = str(value).strip()
        logger.debug(f"Normalized string: '{value}' -> '{normalized}'")
        return normalized