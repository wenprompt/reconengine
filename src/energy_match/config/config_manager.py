"""Configuration manager for energy trade matching system."""

import json
from pathlib import Path
from decimal import Decimal
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict


class MatchingConfig(BaseModel):
    """Configuration for trade matching system.

    Contains tolerances, conversion factors, and other configurable parameters
    for the matching engine.
    """

    model_config = ConfigDict(
        frozen=True, validate_assignment=True  # Immutable configuration
    )

    # Unit conversion
    bbl_to_mt_ratio: Decimal = Field(
        default=Decimal("6.35"), description="Default conversion ratio from BBL to MT"
    )

    # Quantity tolerances (for future rules)
    quantity_tolerance_percentage: Decimal = Field(
        default=Decimal("5.0"),
        ge=0,
        le=100,
        description="Quantity tolerance as percentage for Rule 3",
    )

    # Universal tolerances are now loaded from normalizer_config.json
    # This allows for easy customization without code changes

    # Confidence levels for each rule (from rules.md) - implemented rules
    rule_confidence_levels: Dict[int, Decimal] = Field(
        default={
            1: Decimal("100"),  # Exact match
            2: Decimal("95"),  # Spread match
            3: Decimal("90"),  # Crack match
            4: Decimal("80"),  # Complex crack match
            5: Decimal("75"),  # Product spread match
            6: Decimal("72"),  # Aggregation match
            7: Decimal("65"),  # Aggregated complex crack match
            8: Decimal("70"),  # Aggregated spread match
            9: Decimal("68"),  # Aggregated crack match
            10: Decimal("65"),  # Crack roll match
        },
        description="Confidence levels for each matching rule (implemented rules)",
    )

    # Processing order (from rules.md) - implemented rules
    rule_processing_order: list[int] = Field(
        default=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        description="Order in which rules should be processed (implemented rules)",
    )

    # Logging configuration
    log_level: str = Field(
        default="INFO",
        pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level",
    )

    # Performance settings
    max_trades_per_batch: int = Field(
        default=10000, ge=1, description="Maximum trades to process in one batch"
    )

    # Output settings
    output_format: str = Field(
        default="rich",
        pattern=r"^(rich|json|csv)$",
        description="Output format for results",
    )

    show_unmatched: bool = Field(
        default=True, description="Whether to show unmatched trades in output"
    )

    show_statistics: bool = Field(
        default=True, description="Whether to show matching statistics"
    )


class ConfigManager:
    """Manages configuration for the energy trade matching system.

    Provides default configuration and methods to load/save configuration
    from files or environment variables.
    """

    def __init__(self, config: Optional[MatchingConfig] = None):
        """Initialize configuration manager.

        Args:
            config: Optional custom configuration, uses defaults if None
        """
        self._config = config or MatchingConfig()
        self._normalizer_config: Dict[str, Any] = {}
        self._load_normalizer_config()

    def _load_normalizer_config(self):
        """Load normalizer configuration from JSON file."""
        config_dir = Path(__file__).parent
        normalizer_config_path = config_dir / "normalizer_config.json"
        try:
            with open(normalizer_config_path, 'r') as f:
                self._normalizer_config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Normalizer config file not found: {normalizer_config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in normalizer_config.json: {e}")

    @property
    def config(self) -> MatchingConfig:
        """Get current configuration."""
        return self._config

    def get_rule_confidence(self, rule_number: int) -> Decimal:
        """Get confidence level for a specific rule.

        Args:
            rule_number: Rule number (1-9)

        Returns:
            Confidence level as percentage

        Raises:
            ValueError: If rule number is invalid
        """
        if rule_number not in self._config.rule_confidence_levels:
            raise ValueError(f"Invalid rule number: {rule_number}")

        return self._config.rule_confidence_levels[rule_number]

    def get_processing_order(self) -> list[int]:
        """Get the order in which rules should be processed.

        Returns:
            List of rule numbers in processing order
        """
        return self._config.rule_processing_order.copy()

    def get_quantity_tolerance(self) -> Decimal:
        """Get quantity tolerance percentage.

        Returns:
            Quantity tolerance as percentage (e.g., 5.0 for 5%)
        """
        return self._config.quantity_tolerance_percentage

    def get_conversion_ratio(self) -> Decimal:
        """Get BBL to MT conversion ratio.

        Returns:
            Conversion ratio (default 6.35)
        """
        return self._config.bbl_to_mt_ratio

    def get_universal_tolerance_bbl(self) -> Decimal:
        """Get universal BBL tolerance used by all matching rules.

        Returns:
            Universal tolerance in BBL from normalizer_config.json (default ±500 BBL)
        """
        universal_tolerances = self._normalizer_config.get("universal_tolerances", {})
        tolerance_bbl = universal_tolerances.get("tolerance_bbl", 500)
        return Decimal(str(tolerance_bbl))

    def get_universal_tolerance_mt(self) -> Decimal:
        """Get universal MT tolerance used by all matching rules.

        Returns:
            Universal tolerance in MT from normalizer_config.json (default ±145 MT)
        """
        universal_tolerances = self._normalizer_config.get("universal_tolerances", {})
        tolerance_mt = universal_tolerances.get("tolerance_mt", 145)
        return Decimal(str(tolerance_mt))

    # Legacy methods for backwards compatibility (deprecated)
    def get_crack_tolerance_bbl(self) -> Decimal:
        """Get crack matching tolerance in BBL (deprecated - use get_universal_tolerance_bbl)."""
        return self.get_universal_tolerance_bbl()

    def get_crack_tolerance_mt(self) -> Decimal:
        """Get crack matching tolerance in MT (deprecated - use get_universal_tolerance_mt)."""
        return self.get_universal_tolerance_mt()

    def get_complex_crack_quantity_tolerance(self) -> Decimal:
        """Get complex crack matching quantity tolerance in MT (deprecated - use get_universal_tolerance_mt)."""
        return self.get_universal_tolerance_mt()

    def get_universal_matching_fields(self) -> List[str]:
        """Get universal matching fields that must match across ALL rules.
        
        Loads from normalizer_config.json under universal_matching_fields.required_fields
        
        Returns:
            List of field names that must match in all matching rules
            
        Raises:
            KeyError: If required configuration keys are missing
        """
        try:
            universal_config = self._normalizer_config["universal_matching_fields"]
            return universal_config["required_fields"]
        except KeyError as e:
            raise KeyError(f"Missing required key in normalizer_config.json: {e}")
    
    def get_universal_field_mappings(self) -> Dict[str, str]:
        """Get universal field mappings from config (config field name -> Trade attribute name).
        
        Returns:
            Dictionary mapping config field names to Trade model attribute names
            
        Raises:
            KeyError: If required configuration keys are missing
        """
        try:
            universal_config = self._normalizer_config["universal_matching_fields"]
            return universal_config["field_mappings"]
        except KeyError as e:
            raise KeyError(f"Missing required key in normalizer_config.json: {e}")

    def get_product_mappings(self) -> Dict[str, str]:
        """Get product name normalization mappings."""
        return self._normalizer_config.get("product_mappings", {})

    def get_month_patterns(self) -> Dict[str, str]:
        """Get contract month normalization regex patterns."""
        return self._normalizer_config.get("month_patterns", {})


    def get_product_conversion_ratios(self) -> Dict[str, float]:
        """Get product-specific MT to BBL conversion ratios."""
        return self._normalizer_config.get("product_conversion_ratios", {})

    def get_traders_product_unit_defaults(self) -> Dict[str, str]:
        """Get default units for trader products."""
        return self._normalizer_config.get("traders_product_unit_defaults", {})


    def update_config(self, **kwargs) -> "ConfigManager":
        """Create new ConfigManager with updated values.

        Args:
            **kwargs: Configuration values to update

        Returns:
            New ConfigManager instance with updated configuration
        """
        current_dict = self._config.model_dump()
        current_dict.update(kwargs)

        new_config = MatchingConfig(**current_dict)
        return ConfigManager(new_config)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Configuration as dictionary
        """
        return self._config.model_dump()

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ConfigManager":
        """Create ConfigManager from dictionary.

        Args:
            config_dict: Configuration dictionary

        Returns:
            New ConfigManager instance
        """
        config = MatchingConfig(**config_dict)
        return cls(config)

    @classmethod
    def default(cls) -> "ConfigManager":
        """Create ConfigManager with default configuration.

        Returns:
            ConfigManager with default settings
        """
        return cls()

    def get_summary(self) -> Dict[str, Any]:
        """Get configuration summary for display.

        Returns:
            Dictionary with key configuration values
        """
        return {
            "conversion_ratio": float(self._config.bbl_to_mt_ratio),
            "quantity_tolerance": f"{self._config.quantity_tolerance_percentage}%",
            "rule_count": len(self._config.rule_confidence_levels),
            "processing_order": self._config.rule_processing_order,
            "log_level": self._config.log_level,
            "output_format": self._config.output_format,
            "show_unmatched": self._config.show_unmatched,
            "show_statistics": self._config.show_statistics,
        }
