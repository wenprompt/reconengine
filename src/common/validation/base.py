"""Base classes for input validation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import pandas as pd


@dataclass
class ValidatedData:
    """
    Container for validated data that can be passed between modules.
    
    This intermediate format sits between raw input and Trade objects,
    allowing format-agnostic data handling across all matching modules.
    
    Attributes:
        trader_data: Validated trader records as list of dicts
        exchange_data: Validated exchange records as list of dicts
        metadata: Optional metadata about the validation process
    """
    
    trader_data: List[Dict[str, Any]]
    exchange_data: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dataframe(self, data_type: str = "trader") -> pd.DataFrame:
        """
        Convert validated data to pandas DataFrame.
        
        Args:
            data_type: Either "trader" or "exchange"
            
        Returns:
            DataFrame with validated data
            
        Raises:
            ValueError: If data_type is invalid
        """
        if data_type == "trader":
            return pd.DataFrame(self.trader_data)
        elif data_type == "exchange":
            return pd.DataFrame(self.exchange_data)
        else:
            raise ValueError(f"Invalid data_type: {data_type}. Must be 'trader' or 'exchange'")
    
    @property
    def trader_count(self) -> int:
        """Get count of trader records."""
        return len(self.trader_data)
    
    @property
    def exchange_count(self) -> int:
        """Get count of exchange records."""
        return len(self.exchange_data)


class BaseInputValidator(ABC):
    """
    Abstract base class for input validators.
    
    Provides a common interface for validating different input formats
    (CSV, JSON, API) and converting them to ValidatedData objects.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize validator with optional configuration.
        
        Args:
            config: Optional configuration dictionary for field mappings,
                   validation rules, etc.
        """
        self.config = config or {}
        self.field_mappings = self.config.get("field_mappings", {})
        self.required_fields = self.config.get("required_fields", {})
    
    @abstractmethod
    def validate(self, trader_input: Any, exchange_input: Any) -> ValidatedData:
        """
        Validate input data and return ValidatedData object.
        
        Args:
            trader_input: Raw trader data in format-specific type
            exchange_input: Raw exchange data in format-specific type
            
        Returns:
            ValidatedData object with validated and normalized data
            
        Raises:
            ValidationError: If validation fails
        """
        pass
    
    @abstractmethod
    def _validate_trader_data(self, data: Any) -> List[Dict[str, Any]]:
        """
        Validate trader-specific data.
        
        Args:
            data: Raw trader data
            
        Returns:
            List of validated trader records as dictionaries
            
        Raises:
            ValidationError: If validation fails
        """
        pass
    
    @abstractmethod
    def _validate_exchange_data(self, data: Any) -> List[Dict[str, Any]]:
        """
        Validate exchange-specific data.
        
        Args:
            data: Raw exchange data
            
        Returns:
            List of validated exchange records as dictionaries
            
        Raises:
            ValidationError: If validation fails
        """
        pass
    
    def apply_field_mappings(self, record: Dict[str, Any], data_type: str) -> Dict[str, Any]:
        """
        Apply field mappings to standardize column names.
        
        Args:
            record: Input record with original field names
            data_type: Either "trader" or "exchange"
            
        Returns:
            Record with standardized field names
        """
        mappings = self.field_mappings.get(data_type, {})
        if not mappings:
            return record
            
        mapped_record = {}
        for original_name, standard_name in mappings.items():
            if original_name in record:
                mapped_record[standard_name] = record[original_name]
        
        # Keep any unmapped fields as-is
        for key, value in record.items():
            if key not in mappings and key not in mapped_record:
                mapped_record[key] = value
                
        return mapped_record