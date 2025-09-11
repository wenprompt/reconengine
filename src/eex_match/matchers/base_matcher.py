"""Base matcher providing universal field validation for EEX trades."""

from typing import Any, Union
import uuid
import logging
from abc import ABC, abstractmethod

from ..models import EEXTrade, EEXMatchResult
from ..config import EEXConfigManager
from ..core import EEXUnmatchedPool

logger = logging.getLogger(__name__)


class BaseMatcher(ABC):
    """Base class for all EEX matching rules.

    Provides universal field validation that must apply to ALL matches,
    regardless of the specific matching rule being used.
    """

    def __init__(self, config_manager: EEXConfigManager):
        """Initialize base matcher with configuration.

        Args:
            config_manager: Configuration manager for accessing universal fields
        """
        self.config_manager = config_manager

        # Get universal matching fields from config
        self.universal_fields = config_manager.get_universal_matching_fields()
        self.field_mappings = config_manager.get_universal_field_mappings()

        logger.debug(
            f"Initialized {self.__class__.__name__} with universal fields: {self.universal_fields}"
        )

    def validate_universal_fields(self, trade1: EEXTrade, trade2: EEXTrade) -> bool:
        """Validate that universal fields match between two trades.

        Universal fields (like broker_group_id and exch_clearing_acct_id) must
        match for ANY rule to consider the trades as a match.

        Args:
            trade1: First trade to compare
            trade2: Second trade to compare

        Returns:
            True if all universal fields match, False otherwise
        """
        for config_field in self.universal_fields:
            # Map config field name to Trade model attribute name
            trade_attribute = self.field_mappings.get(config_field)
            if not trade_attribute:
                logger.warning(f"No mapping found for universal field: {config_field}")
                continue

            # Get values from both trades
            value1 = getattr(trade1, trade_attribute, None)
            value2 = getattr(trade2, trade_attribute, None)

            # Universal fields must match (including both being None)
            if value1 != value2:
                logger.debug(
                    f"Universal field mismatch on {trade_attribute}: "
                    f"{value1} != {value2}"
                )
                return False

        return True

    def create_universal_signature(
        self, trade: EEXTrade, rule_specific_fields: list[Any]
    ) -> tuple[Any, ...]:
        """Create a matching signature including universal fields.

        Args:
            trade: Trade to create signature for
            rule_specific_fields: List of field values specific to the matching rule

        Returns:
            Tuple containing all fields that must match (rule-specific + universal)
        """
        signature_parts = list(rule_specific_fields)

        # Add universal fields to signature
        for config_field in self.universal_fields:
            trade_attribute = self.field_mappings.get(config_field)
            if trade_attribute:
                value = getattr(trade, trade_attribute, None)
                if value is not None:  # Only append non-None values
                    signature_parts.append(value)

        return tuple(signature_parts)

    def get_universal_matched_fields(self, rule_fields: list[str]) -> list[str]:
        """Get combined list of matched fields (rule-specific + universal).

        Args:
            rule_fields: List of rule-specific field names that matched

        Returns:
            Combined list of all matched field names
        """
        # Map config field names to model attribute names
        universal_model_fields = [
            self.field_mappings.get(field, field) for field in self.universal_fields
        ]

        return rule_fields + universal_model_fields

    def generate_match_id(self, rule_number: int) -> str:
        """Generate a unique match ID with EEX prefix and rule number.

        Args:
            rule_number: The rule number that created this match

        Returns:
            Match ID in format: EEX_{rule}_{uuid}
        """
        unique_id = str(uuid.uuid4())[:8]
        return f"EEX_{rule_number}_{unique_id}"

    @abstractmethod
    def find_matches(self, pool_manager: EEXUnmatchedPool) -> list[EEXMatchResult]:
        """Find matches using this rule's logic.

        Must be implemented by each specific matcher.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of matches found by this rule
        """
        pass

    @abstractmethod
    def get_rule_info(self) -> dict[str, Union[str, int, float, list[str]]]:
        """Get information about this matching rule.

        Returns:
            Dictionary with rule metadata (name, description, confidence, etc.)
        """
        pass
