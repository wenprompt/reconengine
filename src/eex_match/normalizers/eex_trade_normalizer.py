"""Trade data normalizer for EEX trades."""

import re
from typing import Any, Optional
from decimal import Decimal, InvalidOperation
import logging
import pandas as pd

from ..config import EEXConfigManager

logger = logging.getLogger(__name__)


class EEXTradeNormalizer:
    """Normalizes EEX trade data from various CSV sources to standardized format."""
    
    def __init__(self, config_manager: EEXConfigManager):
        """Initialize normalizer with configuration.
        
        Args:
            config_manager: Configuration manager with normalization rules
        """
        self.config_manager = config_manager
        self._product_mappings = config_manager.get_product_mappings()
        self._month_patterns = config_manager.get_month_patterns()
        self._buy_sell_mappings = config_manager.get_buy_sell_mappings()
        
        logger.info("Initialized EEX trade normalizer")
    
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
        """Normalize buy/sell indicator to standard format using case-insensitive mapping.
        
        Args:
            buy_sell: Raw buy/sell value from CSV
            
        Returns:
            Normalized buy/sell ("B" or "S")
        """
        if not buy_sell:
            return ""
        
        value_clean = buy_sell.strip().lower()
        
        # Check against JSON mappings (case-insensitive)
        if value_clean in self._buy_sell_mappings:
            normalized = self._buy_sell_mappings[value_clean]
            logger.debug(f"Normalized buy/sell: '{buy_sell}' -> '{normalized}'")
            return normalized
        
        # Fallback: try first character for B/S detection
        first_char = value_clean[0].upper() if value_clean else ""
        if first_char in ["B", "S"]:
            logger.debug(f"Normalized buy/sell via first character: '{buy_sell}' -> '{first_char}'")
            return first_char
        
        # Final fallback for invalid values
        logger.error(f"Unable to normalize buy/sell value: '{buy_sell}' - invalid value")
        return ""  # Return empty string for invalid values
    
    def normalize_quantity(self, quantity: Any) -> Optional[Decimal]:
        """Normalize quantity to Decimal.
        
        Args:
            quantity: Raw quantity value (could be string, int, float, or NaN)
            
        Returns:
            Normalized quantity as Decimal, or None if invalid or NaN
        """
        # Check for NaN, None, or empty string
        if pd.isna(quantity) or quantity is None or quantity == "":
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
            
        except (ValueError, TypeError, InvalidOperation) as e:
            logger.error(f"Unable to process quantity value '{quantity}': {e}. Check data format and try again.")
            return None
    
    def normalize_price(self, price: Any) -> Optional[Decimal]:
        """Normalize price to Decimal.
        
        Args:
            price: Raw price value (could be string, int, float, or NaN)
            
        Returns:
            Normalized price as Decimal, or None if invalid or NaN
        """
        # Check for NaN, None, or empty string
        if pd.isna(price) or price is None or price == "":
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
            
        except (ValueError, TypeError, InvalidOperation) as e:
            logger.error(f"Unable to process price value '{price}': {e}. Check data format and try again.")
            return None
    
    def normalize_integer_field(self, value: Any) -> Optional[int]:
        """Normalize integer fields like broker_group_id.
        
        Args:
            value: Raw value to normalize to integer
            
        Returns:
            Normalized integer value, or None if invalid or NaN
        """
        # Check for NaN, None, or empty string
        if pd.isna(value) or value is None or value == "":
            return None
        
        try:
            # Convert to string first, then to int
            value_str = str(value).strip()
            normalized = int(float(value_str))  # Handle decimal strings
            
            logger.debug(f"Normalized integer: '{value}' -> '{normalized}'")
            return normalized
            
        except (ValueError, TypeError) as e:
            logger.error(f"Unable to process numeric value '{value}': {e}. Check data format and try again.")
            return None
    
    def normalize_string_field(self, value: Any) -> str:
        """Normalize string fields by cleaning whitespace.
        
        Args:
            value: Raw value to normalize
            
        Returns:
            Normalized string value
        """
        # Check for NaN or None
        if pd.isna(value) or value is None:
            return ""
        
        normalized = str(value).strip()
        logger.debug(f"Normalized string: '{value}' -> '{normalized}'")
        return normalized