"""Configuration manager for energy trade matching system."""

from decimal import Decimal
from typing import Dict, Any, Optional
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
        default=Decimal("6.35"), description="Conversion ratio from BBL to MT"
    )

    # Price tolerances (for future rules)
    price_tolerance_percentage: Decimal = Field(
        default=Decimal("2.0"),
        ge=0,
        le=100,
        description="Price tolerance as percentage for Rule 2",
    )

    # Quantity tolerances (for future rules)
    quantity_tolerance_percentage: Decimal = Field(
        default=Decimal("5.0"),
        ge=0,
        le=100,
        description="Quantity tolerance as percentage for Rule 3",
    )

    # Crack matching tolerances (Rule 3)
    crack_tolerance_bbl: Decimal = Field(
        default=Decimal("100"),
        ge=0,
        description="Crack matching tolerance in BBL (±100 BBL)",
    )

    crack_tolerance_mt: Decimal = Field(
        default=Decimal("50"),
        ge=0,
        description="Crack matching tolerance in MT (±50 MT)",
    )

    # Confidence levels for each rule (from rules.md)
    rule_confidence_levels: Dict[int, Decimal] = Field(
        default={
            1: Decimal("100"),  # Exact match
            2: Decimal("95"),  # Price tolerance
            3: Decimal("90"),  # Quantity tolerance
            4: Decimal("85"),  # Both tolerances
            5: Decimal("80"),  # Product similar
            6: Decimal("75"),  # Contract adjacent
            7: Decimal("70"),  # Product + contract + tolerances
            8: Decimal("65"),  # Broker different
            9: Decimal("62"),  # Exchange different
            10: Decimal("60"),  # Clearing different
        },
        description="Confidence levels for each matching rule",
    )

    # Processing order (from rules.md)
    rule_processing_order: list[int] = Field(
        default=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        description="Order in which rules should be processed",
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

    @property
    def config(self) -> MatchingConfig:
        """Get current configuration."""
        return self._config

    def get_rule_confidence(self, rule_number: int) -> Decimal:
        """Get confidence level for a specific rule.

        Args:
            rule_number: Rule number (1-10)

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

    def get_price_tolerance(self) -> Decimal:
        """Get price tolerance percentage.

        Returns:
            Price tolerance as percentage (e.g., 2.0 for 2%)
        """
        return self._config.price_tolerance_percentage

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

    def get_crack_tolerance_bbl(self) -> Decimal:
        """Get crack matching tolerance in BBL.

        Returns:
            Tolerance in BBL (default ±100 BBL)
        """
        return self._config.crack_tolerance_bbl

    def get_crack_tolerance_mt(self) -> Decimal:
        """Get crack matching tolerance in MT.

        Returns:
            Tolerance in MT (default ±50 MT)
        """
        return self._config.crack_tolerance_mt

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
            "price_tolerance": f"{self._config.price_tolerance_percentage}%",
            "quantity_tolerance": f"{self._config.quantity_tolerance_percentage}%",
            "rule_count": len(self._config.rule_confidence_levels),
            "processing_order": self._config.rule_processing_order,
            "log_level": self._config.log_level,
            "output_format": self._config.output_format,
            "show_unmatched": self._config.show_unmatched,
            "show_statistics": self._config.show_statistics,
        }
