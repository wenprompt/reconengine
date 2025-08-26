"""Base class for multi-leg matchers providing shared validation capabilities."""

from abc import ABC
from decimal import Decimal
from typing import List
import logging

from ..models import SGXTrade
from ..normalizers import SGXTradeNormalizer
from .base_matcher import BaseMatcher
from ..config import SGXConfigManager

logger = logging.getLogger(__name__)


class MultiLegBaseMatcher(BaseMatcher, ABC):
    """Base class for multi-leg matchers providing shared validation capabilities.
    
    This class provides reusable methods for matchers that deal with multiple trades
    forming complex instruments like spreads, cracks, and aggregated positions.
    
    Inherits universal field validation from SGXBaseMatcher and adds:
    - Shared utility methods for multi-leg instruments
    - SGX-specific quantity handling (quantity_units field)
    """
    
    def __init__(self, config_manager: SGXConfigManager):
        """Initialize multi-leg base matcher."""
        super().__init__(config_manager)
    
    def _get_quantity_for_grouping(self, trade: SGXTrade) -> Decimal:
        """Get appropriate quantity for grouping (SGX uses quantity_units directly).
        
        Args:
            trade: SGXTrade object to get quantity for
            
        Returns:
            Decimal: Trade quantity in units
        """
        return trade.quantity_units
    
    def validate_spread_pair_characteristics(self, trade1: SGXTrade, trade2: SGXTrade) -> bool:
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
            - Same quantity (quantity_units)
            - Opposite buy/sell directions
            - Different contract months
            - Universal fields match (broker, clearing account, etc.)
        """
        # Must have same product
        if trade1.product_name != trade2.product_name:
            return False
            
        # Must have same quantity
        if trade1.quantity_units != trade2.quantity_units:
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

    def validate_spread_group_characteristics(self, trades: List[SGXTrade]) -> bool:
        """Validate that a group of trades can form a valid spread.
        
        Args:
            trades: List of SGXTrade objects to validate as spread group
            
        Returns:
            bool: True if trades form valid spread group
        """
        if len(trades) < 2:
            return False
            
        # All trades must have same product and quantity
        first_trade = trades[0]
        for trade in trades[1:]:
            if not self.validate_spread_pair_characteristics(first_trade, trade):
                # For spread groups, we only check product, quantity, and universal fields
                # Contract months and B/S can vary within the group
                if (trade.product_name != first_trade.product_name or
                    trade.quantity_units != first_trade.quantity_units or
                    not self.validate_universal_fields(first_trade, trade)):
                    return False
        
        # Check that we have different contract months
        contract_months = {trade.contract_month for trade in trades}
        if len(contract_months) < 2:
            return False
            
        # Check that we have opposite B/S directions
        buy_sell_values = {trade.buy_sell for trade in trades}
        if len(buy_sell_values) < 2 or buy_sell_values != {'B', 'S'}:
            return False
            
        return True