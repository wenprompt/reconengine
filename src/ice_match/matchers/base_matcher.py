"""Base matcher with universal field handling."""

from abc import ABC, abstractmethod
from typing import List, Tuple, Any
from ..models import Trade
from ..config import ConfigManager


class BaseMatcher(ABC):
    """Base class for all matchers providing universal field handling."""
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize base matcher with config manager."""
        self.config_manager = config_manager
    
    def create_universal_signature(self, trade: Trade, rule_specific_fields: List[Any]) -> Tuple:
        """Create matching signature by combining rule-specific fields with universal fields.
        
        Args:
            trade: Trade to create signature for
            rule_specific_fields: Rule-specific field values (in order)
            
        Returns:
            Tuple containing rule-specific fields + universal field values
        """
        # Start with rule-specific fields
        signature_parts = list(rule_specific_fields)
        
        # Add universal fields dynamically
        universal_fields = self.config_manager.get_universal_matching_fields()
        for field_name in universal_fields:
            value = self._get_trade_field_value(trade, field_name)
            signature_parts.append(value)
        
        return tuple(signature_parts)
    
    def get_universal_matched_fields(self, rule_specific_fields: List[str]) -> List[str]:
        """Get complete matched fields list with universal fields added.
        
        Args:
            rule_specific_fields: List of rule-specific field names
            
        Returns:
            Complete list including universal fields
        """
        matched_fields = list(rule_specific_fields)
        
        # Add universal fields dynamically
        universal_fields = self.config_manager.get_universal_matching_fields()
        for field_name in universal_fields:
            trade_field_name = self._convert_config_field_to_trade_attribute(field_name)
            matched_fields.append(trade_field_name)
        
        return matched_fields
    
    def validate_universal_fields(self, trade1: Trade, trade2: Trade) -> bool:
        """Validate that universal fields match between two trades.
        
        Args:
            trade1: First trade
            trade2: Second trade
            
        Returns:
            True if all universal fields match, False otherwise
        """
        universal_fields = self.config_manager.get_universal_matching_fields()
        for field_name in universal_fields:
            value1 = self._get_trade_field_value(trade1, field_name)
            value2 = self._get_trade_field_value(trade2, field_name)
            if value1 != value2:
                return False
        return True
    
    def _get_trade_field_value(self, trade: Trade, config_field_name: str) -> Any:
        """Get trade field value by config field name.
        
        Args:
            trade: Trade object
            config_field_name: Field name from config (e.g., 'brokergroupid')
            
        Returns:
            Field value from trade object
        """
        # Get field mappings from config to convert config field name to Trade attribute
        field_mappings = self.config_manager.get_universal_field_mappings()
        
        # Get the actual Trade model attribute name
        trade_attribute = field_mappings.get(config_field_name, config_field_name)
        
        # Use getattr to dynamically access the field
        return getattr(trade, trade_attribute, None)
    
    def _convert_config_field_to_trade_attribute(self, config_field_name: str) -> str:
        """Convert config field name to Trade model attribute name.
        
        Args:
            config_field_name: Field name from config (e.g., 'brokergroupid')
            
        Returns:
            Trade model attribute name (e.g., 'broker_group_id')
        """
        # Get field mappings from config to convert config field name to Trade attribute
        field_mappings = self.config_manager.get_universal_field_mappings()
        
        # Return the mapped attribute name or the original if not found
        return field_mappings.get(config_field_name, config_field_name)