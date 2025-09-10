"""Base matcher with universal field handling for SGX trades."""

from abc import ABC, abstractmethod
from typing import List, Tuple, Any
import uuid
import logging
from ..models import SGXTrade
from ..config import SGXConfigManager

# Constants
UUID_LENGTH = 8  # Length of UUID suffix for match IDs (must be 1-32)

# Module logger
logger = logging.getLogger(__name__)


class BaseMatcher(ABC):
    """Base class for all SGX matchers providing universal field handling."""

    def __init__(self, config_manager: SGXConfigManager):
        """Initialize base SGX matcher with config manager."""
        self.config_manager = config_manager

    def create_universal_signature(
        self, trade: SGXTrade, rule_specific_fields: List[Any]
    ) -> Tuple:
        """Create matching signature by combining rule-specific fields with universal fields.

        Args:
            trade: SGXTrade to create signature for
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

    def get_universal_matched_fields(
        self, rule_specific_fields: List[str]
    ) -> List[str]:
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

    def validate_universal_fields(self, trade1: SGXTrade, trade2: SGXTrade) -> bool:
        """Validate that universal fields match between two trades.

        Args:
            trade1: First SGX trade
            trade2: Second SGX trade

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

    def validate_options_compatibility(self, *trades: SGXTrade) -> bool:
        """Check if all trades have compatible option characteristics.

        All trades must be either:
        - All futures (strike=None, put_call=None)
        - All options with identical strike and put_call values

        This prevents incorrect matching between options and futures trades.

        Args:
            *trades: Variable number of SGXTrade objects to validate

        Returns:
            True if all trades have compatible option characteristics, False otherwise
        """
        if not trades:
            return True

        # Use first trade as reference
        first_trade = trades[0]

        # Check all other trades match the first trade's option characteristics
        for trade in trades[1:]:
            if (
                trade.strike != first_trade.strike
                or trade.put_call != first_trade.put_call
            ):
                return False

        return True

    def _get_trade_field_value(self, trade: SGXTrade, config_field_name: str) -> Any:
        """Get trade field value by config field name.

        Args:
            trade: SGXTrade object
            config_field_name: Field name from config (e.g., 'brokergroupid')

        Returns:
            Field value from trade object
        """
        # Get field mappings from config to convert config field name to SGXTrade attribute
        field_mappings = self.config_manager.get_universal_field_mappings()

        # Get the actual SGXTrade model attribute name
        trade_attribute = field_mappings.get(config_field_name, config_field_name)

        # Use getattr to dynamically access the field
        return getattr(trade, trade_attribute, None)

    def _convert_config_field_to_trade_attribute(self, config_field_name: str) -> str:
        """Convert config field name to SGXTrade model attribute name.

        Args:
            config_field_name: Field name from config (e.g., 'brokergroupid')

        Returns:
            Trade model attribute name (e.g., 'broker_group_id')
        """
        field_mappings = self.config_manager.get_universal_field_mappings()
        return field_mappings.get(config_field_name, config_field_name)

    def generate_match_id(self, rule_number: int) -> str:
        """Generate a unique match ID with standardized format.

        Args:
            rule_number: Rule number for the match

        Returns:
            Unique match ID string in format: MODULE_RULE_UUID

        Raises:
            ValueError: If UUID_LENGTH is invalid or UUID generation fails

        Examples:
            >>> matcher.generate_match_id(1)
            'SGX_1_a1b2c3d4'
            >>> matcher.generate_match_id(2)
            'SGX_2_e5f6g7h8'
        """
        # Validate UUID_LENGTH to prevent silent failures
        if not (1 <= UUID_LENGTH <= 32):
            raise ValueError(f"UUID_LENGTH must be between 1 and 32, got {UUID_LENGTH}")

        # Generate UUID suffix with validated length
        try:
            uuid_suffix = uuid.uuid4().hex[:UUID_LENGTH]
        except (OSError, SystemError, ValueError) as e:
            logger.error(f"Failed to generate UUID: {e}")
            raise ValueError(f"UUID generation failed: {e}") from e

        # Build match ID with standardized format: MODULE_RULE_UUID
        match_id = f"SGX_{rule_number}_{uuid_suffix}"

        logger.debug(f"Generated match ID: {match_id}")
        return match_id

    @abstractmethod
    def find_matches(self, pool_manager) -> List:
        """Find matches using this matcher's rule. Must be implemented by subclasses.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of match results
        """
        pass
