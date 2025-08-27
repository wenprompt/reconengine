"""Configuration manager for SGX trade matching system."""

import json
from pathlib import Path
from decimal import Decimal
from typing import Dict, Optional, List
from pydantic import BaseModel, Field, ConfigDict


class SGXMatchingConfig(BaseModel):
    """Configuration for SGX trade matching system.

    Contains tolerances, conversion factors, and other configurable parameters
    for the SGX matching engine.
    """

    model_config = ConfigDict(
        frozen=True, validate_assignment=True  # Immutable configuration
    )

    # Confidence levels for SGX matching rules - ALL 100% for exact matching
    rule_confidence_levels: Dict[int, Decimal] = Field(
        default={
            1: Decimal("100"),  # Exact match
            2: Decimal("100"),  # Spread match (changed from 95% to 100%)
            3: Decimal("100"),  # Product spread match (changed from 95% to 100%)
        },
        description="Confidence levels for each rule (0-100%) - SGX uses exact matching only"
    )

    # Processing order for rules
    processing_order: List[int] = Field(
        default=[1, 2, 3],  # Rule 1 (exact), then Rule 2 (spread), then Rule 3 (product spread)
        description="Order in which rules should be processed"
    )

    # Match ID prefix
    match_id_prefix: str = Field(
        default="SGX",
        description="Prefix for match IDs"
    )


class SGXConfigManager:
    """Manages configuration for SGX trade matching system.
    
    Loads configuration from JSON files and provides a unified interface
    for accessing system settings, tolerances, and field mappings.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Optional path to config directory. Defaults to this module's dir.
        """
        if config_path is None:
            config_path = Path(__file__).parent
        
        self.config_path = config_path
        self.normalizer_config_path = config_path / "normalizer_config.json"
        
        # Load configurations
        self._load_normalizer_config()
        self.matching_config = SGXMatchingConfig()
    
    def _load_normalizer_config(self) -> None:
        """Load normalizer configuration from JSON file."""
        try:
            with open(self.normalizer_config_path, 'r', encoding='utf-8') as f:
                self.normalizer_config = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Normalizer config not found at {self.normalizer_config_path}"
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in normalizer config: {e}") from e
    
    def get_rule_confidence(self, rule_number: int) -> Decimal:
        """Get confidence level for a specific rule.
        
        Args:
            rule_number: Rule number (1, 2, etc.)
            
        Returns:
            Confidence level as Decimal (0-100)
            
        Raises:
            ValueError: If rule number is not configured
        """
        confidence = self.matching_config.rule_confidence_levels.get(rule_number)
        if confidence is None:
            raise ValueError(f"No confidence level configured for rule {rule_number}")
        return confidence
    
    def get_processing_order(self) -> List[int]:
        """Get the order in which rules should be processed.
        
        Returns:
            List of rule numbers in processing order
        """
        return list(self.matching_config.processing_order)
    
    def get_universal_matching_fields(self) -> List[str]:
        """Get list of universal matching field names from config.
        
        Returns:
            List of field names that must match across all rules
        """
        universal_config = self.normalizer_config.get("universal_matching_fields", {})
        return universal_config.get("required_fields", [])
    
    def get_universal_field_mappings(self) -> Dict[str, str]:
        """Get mapping from config field names to Trade model attributes.
        
        Returns:
            Dict mapping config field names to model attribute names
        """
        universal_config = self.normalizer_config.get("universal_matching_fields", {})
        return universal_config.get("field_mappings", {})
    
    def get_product_mappings(self) -> Dict[str, str]:
        """Get product name mappings from config.
        
        Returns:
            Dict mapping raw product names to normalized names
        """
        return self.normalizer_config.get("product_mappings", {})
    
    def get_month_patterns(self) -> Dict[str, str]:
        """Get month pattern mappings from config.
        
        Returns:
            Dict mapping regex patterns to normalized month formats
        """
        return self.normalizer_config.get("month_patterns", {})
    
    def get_buy_sell_mappings(self) -> Dict[str, str]:
        """Get buy/sell value mappings from config.
        
        Returns:
            Dict mapping raw buy/sell values to normalized values
        """
        return self.normalizer_config.get("buy_sell_mappings", {})
    
    def get_match_id_prefix(self) -> str:
        """Get prefix for match IDs.
        
        Returns:
            String prefix for generating match IDs
        """
        return self.matching_config.match_id_prefix

    
    def get_field_mappings(self) -> Dict[str, Dict[str, str]]:
        """Get field mappings for trader and exchange CSV files.
        
        Returns:
            Dictionary with trader_mappings and exchange_mappings
            
        Raises:
            KeyError: If field mappings not found in config
        """
        try:
            return self.normalizer_config["field_mappings"]
        except KeyError as e:
            raise KeyError(f"Missing field mappings in normalizer config: {e}") from e
    
    def reload_config(self) -> None:
        """Reload configuration from files.
        
        Useful for development and testing when config files change.
        """
        self._load_normalizer_config()
        # MatchingConfig is immutable, so we create a new instance
        self.matching_config = SGXMatchingConfig()