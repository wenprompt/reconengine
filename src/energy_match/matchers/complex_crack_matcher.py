"""Complex crack matcher for 2-leg crack trades (base product + brent swap)."""

import logging
import uuid
from decimal import Decimal
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..normalizers import TradeNormalizer
from ..config import ConfigManager  # Added import
from ..core import UnmatchedPoolManager # Added import
from .base_matcher import BaseMatcher

logger = logging.getLogger(__name__)


class ComplexCrackMatcher(BaseMatcher):
    """Matches complex crack trades (base product + brent swap combinations).

    Handles Rule 4: Complex Crack Match Rules (2-Leg with Brent Swap)
    - Processes trades that remain unmatched after Rules 1-3
    - Matches single crack trades against base product + brent swap pairs
    - Applies unit conversion (MT → BBL) with product-specific ratios
    - Validates price formula: (base_price ÷ product_ratio) - brent_price = crack_price
    """

    def __init__(
        self, normalizer: TradeNormalizer, config_manager: ConfigManager
    ):  # Modified __init__
        """Initialize the complex crack matcher."""
        self.normalizer = normalizer
        super().__init__(config_manager)  # Initialize BaseMatcher
        self.rule_number = 4  # Rule number for complex crack
        self.confidence = config_manager.get_rule_confidence(
            self.rule_number
        )  # Get confidence from config
        # Get unit-specific tolerances (shared with Rule 3)
        self.MT_TOLERANCE = config_manager.get_crack_tolerance_mt()   # ±50 MT
        self.BBL_TOLERANCE = config_manager.get_crack_tolerance_bbl() # ±100 BBL
        self.price_tolerance = (
            config_manager.get_complex_crack_price_tolerance()
        )  # Get price tolerance

        self.matches_found: List[MatchResult] = []  # Added type annotation

    def find_matches(
        self, pool_manager: UnmatchedPoolManager
    ) -> List[MatchResult]:
        """Find complex crack matches between trader and exchange data.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of complex crack matches found
        """
        self.matches_found = []

        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Filter trader trades to only crack products
        crack_trades = [t for t in trader_trades if "crack" in t.product_name.lower()]

        if not crack_trades:
            logger.debug("No crack products found in trader data")
            return []

        logger.info(f"Processing {len(crack_trades)} crack trades for complex matching")

        for crack_trade in crack_trades:
            match = self._find_complex_crack_match(crack_trade, exchange_trades, pool_manager)
            if match:
                self.matches_found.append(match)
                logger.info(
                    f"Found complex crack match: {crack_trade.product_name} "
                    f"{crack_trade.contract_month} {crack_trade.quantity}"
                )

        logger.info(f"Found {len(self.matches_found)} complex crack matches")
        return self.matches_found

    def _find_complex_crack_match(
        self, crack_trade: Trade, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
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
            # CRITICAL: Only consider trades that are still unmatched
            if pool_manager.is_trade_matched(exchange_trade):
                continue

            exchange_key = self._build_exchange_match_key(exchange_trade)

            # Check if this could be the base product component
            if (
                exchange_trade.product_name.lower() == base_product.lower()
                and exchange_key[1:] == crack_key[1:]
            ):  # Skip product name, match other fields
                base_candidates.append(exchange_trade)

            # Check if this could be the brent swap component
            # For brent swap, B/S direction should be opposite to crack (handled in validation)
            # So we only match contract_month and broker_group_id
            elif (
                exchange_trade.product_name.lower() in ["brent swap", "brent_swap"]
                and exchange_key[1] == crack_key[1]  # contract_month matches
                and exchange_key[3] == crack_key[3]
            ):  # broker_group_id matches
                brent_candidates.append(exchange_trade)

        # Try to find valid base + brent combinations
        for base_trade in base_candidates:
            # CRITICAL: Only consider base_trade if it's still unmatched
            if pool_manager.is_trade_matched(base_trade):
                continue

            for brent_trade in brent_candidates:
                # CRITICAL: Only consider brent_trade if it's still unmatched
                if pool_manager.is_trade_matched(brent_trade):
                    continue

                if self._validate_complex_crack_combination(
                    crack_trade, base_trade, brent_trade
                ):
                    return MatchResult(
                        match_id=str(uuid.uuid4()),
                        match_type=MatchType.COMPLEX_CRACK,
                        confidence=self.confidence,  # Get confidence from config
                        trader_trade=crack_trade,
                        exchange_trade=base_trade,  # Primary exchange trade (base product)
                        additional_exchange_trades=[
                            brent_trade
                        ],  # Additional trade (brent swap)
                        matched_fields=self._get_matched_fields(),
                        rule_order=self.rule_number,  # Get rule number from config
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

    def _build_crack_match_key(self, trade: Trade) -> Tuple:
        """Build match key for crack trade with universal fields."""
        # Rule-specific fields
        rule_specific_fields = [
            trade.product_name.lower(),
            trade.contract_month,
            trade.buy_sell
        ]
        
        # Use BaseMatcher method to add universal fields
        return self.create_universal_signature(trade, rule_specific_fields)

    def _build_exchange_match_key(self, trade: Trade) -> Tuple:
        """Build match key for exchange trade with universal fields."""
        # Rule-specific fields
        rule_specific_fields = [
            trade.product_name.lower(),
            trade.contract_month,
            trade.buy_sell
        ]
        
        # Use BaseMatcher method to add universal fields
        return self.create_universal_signature(trade, rule_specific_fields)

    def _get_matched_fields(self) -> List[str]:
        """Get list of fields that matched for complex crack matches."""
        # Rule-specific matched fields
        rule_specific_fields = [
            "product_name",
            "contract_month",
            "quantity",
            "buy_sell",
            "price"
        ]
        
        # Get complete matched fields with universal fields using BaseMatcher method
        return self.get_universal_matched_fields(rule_specific_fields)

    def _validate_complex_crack_combination(
        self, crack_trade: Trade, base_trade: Trade, brent_trade: Trade
    ) -> bool:
        """Validate that base + brent combination matches the crack trade."""

        # 1. Validate B/S direction logic
        if not self._validate_bs_direction_logic(crack_trade, base_trade, brent_trade):
            return False

        # 2. Validate quantity with unit conversion
        if not self._validate_quantity_with_conversion(
            crack_trade, base_trade, brent_trade
        ):
            return False

        # 3. Validate price calculation
        if not self._validate_price_calculation(crack_trade, base_trade, brent_trade):
            return False

        return True

    def _validate_bs_direction_logic(
        self, crack_trade: Trade, base_trade: Trade, brent_trade: Trade
    ) -> bool:
        """Validate B/S direction logic for complex crack.

        Rule: Sell Crack = Sell Base Product + Buy Brent Swap
              Buy Crack = Buy Base Product + Sell Brent Swap
        """
        # Trade.buy_sell is already normalized to "B" or "S"
        crack_bs = crack_trade.buy_sell
        base_bs = base_trade.buy_sell
        brent_bs = brent_trade.buy_sell

        if crack_bs == "S":
            # Sell crack = Sell base + Buy brent
            return base_bs == "S" and brent_bs == "B"
        elif crack_bs == "B":
            # Buy crack = Buy base + Sell brent
            return base_bs == "B" and brent_bs == "S"

        return False

    def _validate_quantity_with_conversion(
        self, crack_trade: Trade, base_trade: Trade, brent_trade: Trade
    ) -> bool:
        """Validate quantities using unit-specific tolerances and shared conversion logic."""

        crack_quantity_mt = crack_trade.quantity_mt
        base_quantity_mt = base_trade.quantity_mt

        # 1. Crack vs Base: Both should be MT (trader=MT, base product from exchange=MT)
        qty_diff_mt = abs(crack_quantity_mt - base_quantity_mt)
        if qty_diff_mt > self.MT_TOLERANCE:
            logger.debug(
                f"Crack-base quantity mismatch: {qty_diff_mt} MT > {self.MT_TOLERANCE} MT tolerance"
            )
            return False

        # 2. Crack vs Brent: Brent swap is always in BBL, use shared MT→BBL conversion validation
        # Use shared conversion method from normalizer (same as Rule 3)
        if not self.normalizer.validate_mt_to_bbl_quantity_match(
            crack_quantity_mt, 
            brent_trade.quantity_bbl, 
            crack_trade.product_name, 
            self.BBL_TOLERANCE
        ):
            logger.debug("Crack-brent quantity mismatch using shared MT→BBL validation")
            return False

        logger.debug("Quantity validation passed using shared conversion logic")
        return True

    def _validate_price_calculation(
        self, crack_trade: Trade, base_trade: Trade, brent_trade: Trade
    ) -> bool:
        """Validate price calculation using shared product-specific conversion ratio: (base_price ÷ ratio) - brent_price = crack_price."""

        try:
            # Get product-specific conversion ratio using shared method
            conversion_factor = self.normalizer.get_product_conversion_ratio(crack_trade.product_name)
            
            # Formula: (Base Product Price ÷ PRODUCT_RATIO) - Brent Swap Price = Crack Price
            calculated_crack_price = (
                base_trade.price / conversion_factor
            ) - brent_trade.price

            # Allow tolerance for calculation precision from config
            price_tolerance = self.price_tolerance
            price_diff = abs(calculated_crack_price - crack_trade.price)

            if price_diff <= price_tolerance:
                logger.debug(
                    f"Price calculation valid (shared ratio): ({base_trade.price} ÷ {conversion_factor}) - {brent_trade.price} "
                    f"= {calculated_crack_price} ≈ {crack_trade.price}"
                )
                return True
            else:
                logger.debug(
                    f"Price calculation invalid: ({base_trade.price} ÷ {conversion_factor}) - {brent_trade.price} "
                    f"= {calculated_crack_price} ≠ {crack_trade.price} (diff: {price_diff})"
                )
                return False

        except (ValueError, TypeError, ArithmeticError) as e:
            logger.warning(f"Price calculation error: {e}")
            return False

    def get_rule_info(
        self,
    ) -> dict[str, str | int | float | list[str] | dict[str, float]]:
        """Get information about this matching rule.

        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Complex Crack Match",
            "match_type": MatchType.COMPLEX_CRACK.value,
            "confidence": float(self.confidence),
            "description": "Matches complex crack trades (base product + brent swap combinations)",
            "requirements": [
                "Trader crack product base name must match exchange base product",
                "All three trades (base product, brent swap, crack) must have identical contract months",
                "Quantities must align after unit conversion",
                "B/S direction logic: Sell Crack = Sell Base + Buy Brent; Buy Crack = Buy Base + Sell Brent",
                "Price calculation: (Base Product Price / Product-Specific Ratio) - Brent Swap Price = Crack Price",
                "All trades must have matching brokergroupid",
            ],
            "tolerances": {
                "quantity_mt": float(self.MT_TOLERANCE),
                "quantity_bbl": float(self.BBL_TOLERANCE), 
                "price": float(self.price_tolerance),
            },
        }
