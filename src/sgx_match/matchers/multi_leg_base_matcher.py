"""Base class for multi-leg matchers providing shared validation capabilities."""

from abc import ABC
from decimal import Decimal
import logging

from ..models import SGXTrade
from .base_matcher import BaseMatcher
from ..config import SGXConfigManager

logger = logging.getLogger(__name__)


class MultiLegBaseMatcher(BaseMatcher, ABC):
    """Base class for multi-leg matchers providing shared validation capabilities.

    This class provides reusable methods for matchers that deal with multiple trades
    forming complex instruments like spreads, cracks, and aggregated positions.

    Inherits universal field validation from SGXBaseMatcher and adds:
    - Shared utility methods for multi-leg instruments
    - SGX-specific quantity handling (quantityunit field)
    """

    def __init__(self, config_manager: SGXConfigManager):
        """Initialize multi-leg base matcher."""
        super().__init__(config_manager)

    def _get_quantity_for_grouping(self, trade: SGXTrade) -> Decimal:
        """Get appropriate quantity for grouping (SGX uses quantityunit directly).

        Args:
            trade: SGXTrade object to get quantity for

        Returns:
            Decimal: Trade quantity in units
        """
        return trade.quantityunit

    def validate_spread_pair_characteristics(
        self, trade1: SGXTrade, trade2: SGXTrade
    ) -> bool:
        """Validate that two trades can form a valid spread pair.

        This method provides shared validation logic for spread characteristics
        that can be used by different matching strategies (dealid-based, time-based, etc.)

        Args:
            trade1: First trade in potential spread pair
            trade2: Second trade in potential spread pair

        Returns:
            bool: True if trades form valid spread pair

        Validation criteria:
            - Same product name
            - Same quantity (quantityunit)
            - Opposite buy/sell directions
            - Different contract months
            - Universal fields match (broker, clearing account, etc.)
        """
        # Must have same product
        if trade1.product_name != trade2.product_name:
            return False

        # Must have same quantity
        if trade1.quantityunit != trade2.quantityunit:
            return False

        # Must have opposite buy/sell directions
        if trade1.buy_sell == trade2.buy_sell:
            return False

        # Must have different contract months
        if trade1.contract_month == trade2.contract_month:
            return False

        # Universal fields must match
        if not self.validate_universal_fields(trade1, trade2):
            return False

        return True
