"""Configuration manager for SGX trade matching system."""

import json
from pathlib import Path
from decimal import Decimal
from typing import Optional, Any
from ...unified_recon.types.json_types import NormalizerConfig
from pydantic import BaseModel, Field, ConfigDict


class SGXMatchingConfig(BaseModel):
    """Configuration for SGX trade matching system.

    Contains tolerances, conversion factors, and other configurable parameters
    for the SGX matching engine.
    """

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,  # Immutable configuration
    )

    # Confidence levels for SGX matching rules - ALL 100% for exact matching
    rule_confidence_levels: dict[int, Decimal] = Field(
        default={
            1: Decimal("100"),  # Exact match
            2: Decimal("100"),  # Spread match (changed from 95% to 100%)
            3: Decimal("100"),  # Product spread match (changed from 95% to 100%)
        },
        description="Confidence levels for each rule (0-100%)",
    )

    # Processing order for rules
    processing_order: list[int] = Field(
        default=[
            1,
            2,
            3,
        ],  # Rule 1 (exact), then Rule 2 (spread), then Rule 3 (product spread)
        description="Order in which rules should be processed",
    )

    # Match ID prefix


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
        self.normalizer_config: NormalizerConfig

        # Load configurations
        self._load_normalizer_config()
        self.matching_config = SGXMatchingConfig()

    def _load_normalizer_config(self) -> None:
        """Load normalizer configuration from JSON file."""
        try:
            with open(self.normalizer_config_path, "r", encoding="utf-8") as f:
                # Load as Any first, then validate structure
                raw_config: Any = json.load(f)
                self.normalizer_config = raw_config
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
        # mypy now knows confidence is not None, so it's Decimal
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

        Raises:
            KeyError: If required configuration keys are missing
        """
        try:
            universal = self.normalizer_config["universal_matching_fields"]
            return universal["required_fields"]
        except KeyError as e:
            raise KeyError(
                f"Missing required key in normalizer_config.json: {e}"
            ) from e

    def get_universal_field_mappings(self) -> dict[str, str]:
        """Get mapping from config field names to Trade model attributes.

        Returns:
            Dict mapping config field names to model attribute names

        Raises:
            KeyError: If required configuration keys are missing
        """
        try:
            universal = self.normalizer_config["universal_matching_fields"]
            return universal["field_mappings"]
        except KeyError as e:
            raise KeyError(
                f"Missing required key in normalizer_config.json: {e}"
            ) from e

    def get_product_mappings(self) -> dict[str, str]:
        """Get product name mappings from config.

        Returns:
            Dict mapping raw product names to normalized names

        Raises:
            KeyError: If required configuration keys are missing
        """
        try:
            return self.normalizer_config["product_mappings"]
        except KeyError as e:
            raise KeyError(
                f"Missing required key in normalizer_config.json: {e}"
            ) from e

    def get_month_patterns(self) -> dict[str, str]:
        """Get month pattern mappings from config.

        Returns:
            Dict mapping regex patterns to normalized month formats

        Raises:
            KeyError: If required configuration keys are missing
        """
        try:
            return self.normalizer_config["month_patterns"]
        except KeyError as e:
            raise KeyError(
                f"Missing required key in normalizer_config.json: {e}"
            ) from e

    def get_buy_sell_mappings(self) -> dict[str, str]:
        """Get buy/sell value mappings from config.

        Returns:
            Dict mapping raw buy/sell values to normalized values
            
        Raises:
            KeyError: If required configuration keys are missing
        """
        try:
            buy_sell_config = self.normalizer_config["buy_sell_mappings"]
            # Handle both simple dict and BuySellMappings structure
            if isinstance(buy_sell_config, dict):
                if "mappings" in buy_sell_config:
                    return buy_sell_config["mappings"]  # type: ignore[return-value]
            return buy_sell_config  # type: ignore[return-value]
        except KeyError as e:
            raise KeyError(
                f"Missing required key in normalizer_config.json: {e}"
            ) from e

    def reload_config(self) -> None:
        """Reload configuration from files.

        Useful for development and testing when config files change.
        """
        self._load_normalizer_config()
        # MatchingConfig is immutable, so we create a new instance
        self.matching_config = SGXMatchingConfig()
