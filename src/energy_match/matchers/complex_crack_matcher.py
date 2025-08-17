"""Complex crack matcher for 2-leg crack trades (base product + brent swap)."""

import logging
import uuid
from decimal import Decimal
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..normalizers import TradeNormalizer
from ..config import ConfigManager # Added import

logger = logging.getLogger(__name__)


class ComplexCrackMatcher:
    """Matches complex crack trades (base product + brent swap combinations).

    Handles Rule 4: Complex Crack Match Rules (2-Leg with Brent Swap)
    - Processes trades that remain unmatched after Rules 1-3
    - Matches single crack trades against base product + brent swap pairs
    - Applies unit conversion (BBL ↔ MT) with 6.35 ratio
    - Validates price formula: (base_price ÷ 6.35) - brent_price = crack_price
    """

    def __init__(self, normalizer: TradeNormalizer, config_manager: ConfigManager): # Modified __init__
        """Initialize the complex crack matcher."""
        self.normalizer = normalizer
        self.config_manager = config_manager # Stored config_manager
        self.rule_number = 4 # Rule number for complex crack
        self.confidence = config_manager.get_rule_confidence(self.rule_number) # Get confidence from config
        self.quantity_tolerance = config_manager.get_complex_crack_quantity_tolerance() # Get quantity tolerance
        self.price_tolerance = config_manager.get_complex_crack_price_tolerance() # Get price tolerance
        self.bbl_to_mt_ratio = config_manager.get_conversion_ratio() # Get conversion ratio

        self.matches_found = []
        
    def find_matches(self, trader_trades: List[Trade], exchange_trades: List[Trade]) -> List[MatchResult]:
        """Find complex crack matches between trader and exchange data.
        
        Args:
            trader_trades: List of unmatched trader trades
            exchange_trades: List of unmatched exchange trades
            
        Returns:
            List of complex crack matches found
        """
        self.matches_found = []
        
        # Filter trader trades to only crack products
        crack_trades = [t for t in trader_trades if "crack" in t.product_name.lower()]
        
        if not crack_trades:
            logger.debug("No crack products found in trader data")
            return []
            
        logger.info(f"Processing {len(crack_trades)} crack trades for complex matching")
        
        for crack_trade in crack_trades:
            match = self._find_complex_crack_match(crack_trade, exchange_trades)
            if match:
                self.matches_found.append(match)
                logger.info(f"Found complex crack match: {crack_trade.product_name} "
                           f"{crack_trade.contract_month} {crack_trade.quantity}")
                
        logger.info(f"Found {len(self.matches_found)} complex crack matches")
        return self.matches_found
    
    def _find_complex_crack_match(self, crack_trade: Trade, exchange_trades: List[Trade]) -> Optional[MatchResult]:
        """Find matching base product + brent swap pair for a crack trade."""
        
        # Extract base product from crack name (e.g., "marine 0.5% crack" -> "marine 0.5%")
        base_product = self._extract_base_product(crack_trade.product_name)
        if not base_product:
            return None
            
        # Build match key for grouping potential matches
        crack_key = self._build_crack_match_key(crack_trade)
        
        # Find potential base product and brent swap matches
        base_candidates = []
        brent_candidates = []
        
        for exchange_trade in exchange_trades:
            exchange_key = self._build_exchange_match_key(exchange_trade)
            
            # Check if this could be the base product component
            if (exchange_trade.product_name.lower() == base_product.lower() and
                exchange_key[1:] == crack_key[1:]):  # Skip product name, match other fields
                base_candidates.append(exchange_trade)
                
            # Check if this could be the brent swap component
            # For brent swap, B/S direction should be opposite to crack (handled in validation)
            # So we only match contract_month and broker_group_id
            elif (exchange_trade.product_name.lower() in ["brent swap", "brent_swap"] and
                  exchange_key[1] == crack_key[1] and  # contract_month matches
                  exchange_key[3] == crack_key[3]):    # broker_group_id matches
                brent_candidates.append(exchange_trade)
        
        # Try to find valid base + brent combinations
        for base_trade in base_candidates:
            for brent_trade in brent_candidates:
                if self._validate_complex_crack_combination(crack_trade, base_trade, brent_trade):
                    return MatchResult(
                        match_id=str(uuid.uuid4()),
                        match_type=MatchType.COMPLEX_CRACK,
                        confidence=self.confidence, # Get confidence from config
                        trader_trade=crack_trade,
                        exchange_trade=base_trade,  # Primary exchange trade (base product)
                        additional_exchange_trades=[brent_trade],  # Additional trade (brent swap)
                        matched_fields=["product_name", "contract_month", "quantity", "buy_sell", "broker_group_id", "price"],
                        rule_order=self.rule_number # Get rule number from config
                    )
        
        return None
    
    def _extract_base_product(self, crack_product: str) -> Optional[str]:
        """Extract base product name from crack product name."""
        crack_lower = crack_product.lower().strip()
        
        # Remove "crack" from the end
        if crack_lower.endswith(" crack"):
            return crack_lower[:-6].strip()
        elif crack_lower.endswith("crack"):
            return crack_lower[:-5].strip()
            
        return None
    
    def _build_crack_match_key(self, trade: Trade) -> Tuple[str, str, str, Optional[int]]:
        """Build match key for crack trade."""
        return (
            trade.product_name.lower(),
            trade.contract_month,
            trade.buy_sell,
            trade.broker_group_id
        )
    
    def _build_exchange_match_key(self, trade: Trade) -> Tuple[str, str, str, Optional[int]]:
        """Build match key for exchange trade."""
        return (
            trade.product_name.lower(), 
            trade.contract_month,
            trade.buy_sell,
            trade.broker_group_id
        )
    
    def _validate_complex_crack_combination(self, crack_trade: Trade, base_trade: Trade, brent_trade: Trade) -> bool:
        """Validate that base + brent combination matches the crack trade."""
        
        # 1. Validate B/S direction logic
        if not self._validate_bs_direction_logic(crack_trade, base_trade, brent_trade):
            return False
            
        # 2. Validate quantity with unit conversion
        if not self._validate_quantity_with_conversion(crack_trade, base_trade, brent_trade):
            return False
            
        # 3. Validate price calculation
        if not self._validate_price_calculation(crack_trade, base_trade, brent_trade):
            return False
            
        return True
    
    def _validate_bs_direction_logic(self, crack_trade: Trade, base_trade: Trade, brent_trade: Trade) -> bool:
        """Validate B/S direction logic for complex crack.
        
        Rule: Sell Crack = Sell Base Product + Buy Brent Swap
              Buy Crack = Buy Base Product + Sell Brent Swap
        """
        crack_bs = crack_trade.buy_sell.lower()
        base_bs = base_trade.buy_sell.lower() 
        brent_bs = brent_trade.buy_sell.lower()
        
        if crack_bs in ["s", "sell", "sold"]:
            # Sell crack = Sell base + Buy brent
            return (base_bs in ["s", "sell", "sold"] and 
                   brent_bs in ["b", "buy", "bought"])
        elif crack_bs in ["b", "buy", "bought"]:
            # Buy crack = Buy base + Sell brent
            return (base_bs in ["b", "buy", "bought"] and
                   brent_bs in ["s", "sell", "sold"])
        
        return False
    
    def _validate_quantity_with_conversion(self, crack_trade: Trade, base_trade: Trade, brent_trade: Trade) -> bool:
        """Validate quantities match after unit conversion."""
        
        # Convert all quantities to MT for comparison
        crack_quantity_mt = self.normalizer.convert_quantity_to_mt(
            crack_trade.quantity, crack_trade.unit or "mt"
        )
        
        base_quantity_mt = self.normalizer.convert_quantity_to_mt(
            base_trade.quantity, base_trade.unit or "mt" 
        )
        
        brent_quantity_mt = self.normalizer.convert_quantity_to_mt(
            brent_trade.quantity, brent_trade.unit or "bbl"
        )
        
        # Allow tolerance for conversion rounding from config
        tolerance = self.quantity_tolerance
        
        # Check crack quantity matches base quantity
        if abs(crack_quantity_mt - base_quantity_mt) > tolerance:
            logger.debug(f"Crack-base quantity mismatch: {crack_quantity_mt} vs {base_quantity_mt}")
            return False
            
        # Check crack quantity matches brent quantity (after conversion)
        if abs(crack_quantity_mt - brent_quantity_mt) > tolerance:
            logger.debug(f"Crack-brent quantity mismatch: {crack_quantity_mt} vs {brent_quantity_mt}")
            return False
            
        return True
    
    def _validate_price_calculation(self, crack_trade: Trade, base_trade: Trade, brent_trade: Trade) -> bool:
        """Validate price calculation: (base_price ÷ 6.35) - brent_price = crack_price."""
        
        try:
            # Formula: (Base Product Price ÷ BBL_TO_MT_RATIO) - Brent Swap Price = Crack Price
            conversion_factor = self.bbl_to_mt_ratio
            calculated_crack_price = (base_trade.price / conversion_factor) - brent_trade.price
            
            # Allow tolerance for calculation precision from config
            price_tolerance = self.price_tolerance
            price_diff = abs(calculated_crack_price - crack_trade.price)
            
            if price_diff <= price_tolerance:
                logger.debug(f"Price calculation valid: ({base_trade.price} ÷ 6.35) - {brent_trade.price} "
                           f"= {calculated_crack_price} ≈ {crack_trade.price}")
                return True
            else:
                logger.debug(f"Price calculation invalid: ({base_trade.price} ÷ 6.35) - {brent_trade.price} "
                           f"= {calculated_crack_price} ≠ {crack_trade.price} (diff: {price_diff})")
                return False
                
        except (ValueError, TypeError, ArithmeticError) as e:
            logger.warning(f"Price calculation error: {e}")
            return False