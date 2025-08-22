"""Multi-leg base matcher with shared validation capabilities."""

from abc import ABC
from decimal import Decimal
import logging

from ..models import Trade
from ..config import ConfigManager
from .base_matcher import BaseMatcher
from ..normalizers import TradeNormalizer

logger = logging.getLogger(__name__)


class MultiLegBaseMatcher(BaseMatcher, ABC):
    """Base class for multi-leg matchers providing shared validation capabilities.
    
    This class provides reusable methods for matchers that deal with multiple trades
    forming complex instruments like spreads, cracks, and aggregated positions.
    
    Inherits universal field validation from BaseMatcher and adds:
    - Config-based quantity unit determination
    - Shared utility methods for multi-leg instruments
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize multi-leg base matcher."""
        super().__init__(config_manager)
    
    def _get_quantity_for_grouping(self, trade: Trade, normalizer: TradeNormalizer) -> Decimal:
        """Get appropriate quantity for grouping based on product type from config.
        
        Uses traders_product_unit_defaults from normalizer_config.json to determine
        whether to use BBL or MT units for quantity comparison.
        
        Args:
            trade: Trade object to get quantity for
            normalizer: TradeNormalizer instance for accessing config
            
        Returns:
            Decimal: Appropriate quantity (BBL or MT based on product config)
        """
        default_unit = normalizer.get_trader_product_unit_default(trade.product_name)
        return trade.quantity_bbl if default_unit == "bbl" else trade.quantity_mt
    
    def validate_spread_pair_characteristics(self, trade1: Trade, trade2: Trade, normalizer: TradeNormalizer) -> bool:
        """Validate that two trades can form a valid spread pair.
        
        This method provides shared validation logic for spread characteristics
        that can be used by different matching strategies (dealid-based, time-based, etc.)
        
        Args:
            trade1: First trade in potential spread pair
            trade2: Second trade in potential spread pair
            normalizer: TradeNormalizer instance for unit determination
            
        Returns:
            bool: True if trades form valid spread pair
            
        Validation criteria:
            - Same product name
            - Same quantity (in appropriate units)
            - Opposite buy/sell directions
            - Different contract months
            - Universal fields match (broker, clearing account, etc.)
        """
        # Must have same product
        if trade1.product_name != trade2.product_name:
            return False
            
        # Must have same quantity (use appropriate unit for comparison)
        quantity1 = self._get_quantity_for_grouping(trade1, normalizer)
        quantity2 = self._get_quantity_for_grouping(trade2, normalizer)
        if quantity1 != quantity2:
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