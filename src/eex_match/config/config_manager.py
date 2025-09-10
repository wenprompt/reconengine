"""Configuration manager for EEX trade matching system."""

import json
from pathlib import Path
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from ...unified_recon.types.json_types import NormalizerConfig


class EEXMatchingConfig(BaseModel):
    """Configuration for EEX trade matching system.

    Contains tolerances, conversion factors, and other configurable parameters
    for the EEX matching engine.
    """

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,  # Immutable configuration
    )

    # Confidence levels for EEX matching rules - only exact matching
    rule_confidence_levels: dict[int, Decimal] = Field(
        default={
            1: Decimal("100"),  # Exact match only
        },
        description="Confidence levels for each rule (0-100%)",
    )

    # Processing order for rules
    processing_order: list[int] = Field(
        default=[1],  # Only Rule 1 (exact) for EEX
        description="Order in which rules should be processed",
    )

    # Match ID prefix


class EEXConfigManager:
    """Manages configuration for EEX trade matching system.

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
        self.matching_config = EEXMatchingConfig()

    def _load_normalizer_config(self) -> None:
        """Load normalizer configuration from JSON file."""
        try:
            with open(self.normalizer_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Validate the structure matches NormalizerConfig
                if not isinstance(data, dict):
                    raise ValueError("Normalizer config must be a dictionary")
                self.normalizer_config: NormalizerConfig = data  # type: ignore[assignment]
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Normalizer config not found at {self.normalizer_config_path}"
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in normalizer config: {e}") from e

    def get_rule_confidence(self, rule_number: int) -> Decimal:
        """Get confidence level for a specific rule.

        Args:
            rule_number: Rule number (1 only for EEX)

        Returns:
            Confidence level as Decimal (0-100)

        Raises:
            ValueError: If rule number is not configured
        """
        confidence = self.matching_config.rule_confidence_levels.get(rule_number)
        if confidence is None:
            raise ValueError(f"No confidence level configured for rule {rule_number}")
        return confidence

    def get_processing_order(self) -> list[int]:
        """Get the order in which rules should be processed.

        Returns:
            List of rule numbers in processing order
        """
        return list(self.matching_config.processing_order)

    def get_universal_matching_fields(self) -> list[str]:
        """Get list of universal matching field names from config.

        Returns:
            List of field names that must match across all rules
        """
        return self.normalizer_config["universal_matching_fields"]["required_fields"]

    def get_universal_field_mappings(self) -> dict[str, str]:
        """Get mapping from config field names to Trade model attributes.

        Returns:
            dict mapping config field names to model attribute names
        """
        return self.normalizer_config["universal_matching_fields"]["field_mappings"]

    def get_product_mappings(self) -> dict[str, str]:
        """Get product name mappings from config.

        Returns:
            dict mapping raw product names to normalized names
        """
        return self.normalizer_config["product_mappings"]

    def get_month_patterns(self) -> dict[str, str]:
        """Get month pattern mappings from config.

        Returns:
            dict mapping regex patterns to normalized month formats
        """
        return self.normalizer_config["month_patterns"]

    def get_buy_sell_mappings(self) -> dict[str, str]:
        """Get buy/sell value mappings from config.

        Returns:
            dict mapping raw buy/sell values to normalized values
        """
        buy_sell_config = self.normalizer_config["buy_sell_mappings"]
        # Handle both simple dict and BuySellMappings structure
        if isinstance(buy_sell_config, dict):
            if "mappings" in buy_sell_config:
                return buy_sell_config["mappings"]  # type: ignore[return-value]
        return buy_sell_config  # type: ignore[return-value]

    def reload_config(self) -> None:
        """Reload configuration from files.

        Useful for development and testing when config files change.
        """
        self._load_normalizer_config()
        # MatchingConfig is immutable, so we create a new instance
        self.matching_config = EEXMatchingConfig()
