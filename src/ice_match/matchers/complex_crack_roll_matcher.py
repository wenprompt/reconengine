"""Complex crack roll matcher for Rule 12: Calendar spreads of crack positions."""

import logging
from decimal import Decimal
from typing import List, Tuple, Dict, Optional

from ..models import Trade, MatchResult, MatchType
from ..normalizers import TradeNormalizer
from ..config import ConfigManager
from ..core import UnmatchedPoolManager
from .multi_leg_base_matcher import MultiLegBaseMatcher
from ..utils.trade_helpers import extract_base_product, get_month_order_tuple
from ..utils.conversion_helpers import (
    get_product_conversion_ratio,
    validate_mt_to_bbl_quantity_match,
    convert_mt_to_bbl_with_product_ratio,
)

logger = logging.getLogger(__name__)


class ComplexCrackRollMatcher(MultiLegBaseMatcher):
    """Matches complex crack roll trades (calendar spreads of crack positions).

    Handles Rule 12: Complex Crack Roll Match Rules (Calendar Spread of Crack Positions)
    - Processes trades that remain unmatched after Rules 1-9
    - Matches 2 consecutive trader crack trades against 4 exchange trades (2 complete crack positions)
    - Applies enhanced unit conversion tolerance (±145 MT, dynamic BBL from config)
    - Validates crack roll spread calculation and price pattern (one price, one 0.0)

    Pattern: 2 consecutive trader crack trades ↔ 4 exchange trades (2 complete crack positions)
    """

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the complex crack roll matcher."""
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 12
        self.confidence = config_manager.get_rule_confidence(self.rule_number)  # 65%

        # Use universal tolerances (enhanced tolerance for crack roll matching)
        self.MT_TOLERANCE = config_manager.get_universal_tolerance_mt()  # ±145 MT
        self.BBL_TOLERANCE = (
            config_manager.get_universal_tolerance_bbl()
        )  # Dynamic BBL tolerance from config

        logger.info(
            f"Initialized ComplexCrackRollMatcher with {self.confidence}% confidence"
        )

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find complex crack roll matches between consecutive trader crack trades and complete exchange crack positions.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of complex crack roll match results
        """
        logger.info("Starting complex crack roll matching (Rule 12)")
        matches: List[MatchResult] = []

        # Get unmatched trades
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Find consecutive crack pairs in trader data
        trader_crack_pairs = self._find_consecutive_crack_pairs(trader_trades)

        if not trader_crack_pairs:
            logger.debug("No consecutive crack pairs found in trader data")
            return matches

        logger.debug(
            f"Found {len(trader_crack_pairs)} potential trader crack roll pairs"
        )

        # For each trader crack pair, try to find matching exchange crack positions
        for trader_pair in trader_crack_pairs:
            if any(pool_manager.is_trade_matched(trade) for trade in trader_pair):
                continue

            match_result = self._find_crack_roll_match(
                trader_pair, exchange_trades, pool_manager
            )
            if match_result:
                # Record the match to remove trades from pool
                if pool_manager.record_match(match_result):
                    matches.append(match_result)
                    logger.debug(f"Created complex crack roll match: {match_result}")
                else:
                    logger.error(
                        "Failed to record complex crack roll match and remove trades from pool"
                    )

        logger.info(f"Found {len(matches)} complex crack roll matches")
        return matches

    def _find_consecutive_crack_pairs(
        self, trader_trades: List[Trade]
    ) -> List[Tuple[Trade, Trade]]:
        """Find consecutive crack trades that could form crack roll pairs.

        Args:
            trader_trades: List of trader trades to search

        Returns:
            List of consecutive crack trade pairs
        """
        crack_pairs: List[Tuple[Trade, Trade]] = []

        # Filter to crack trades only
        crack_trades = [t for t in trader_trades if "crack" in t.product_name.lower()]

        if len(crack_trades) < 2:
            return crack_pairs

        # Sort by trade_id to find consecutive trades (assuming trade_id reflects order)
        crack_trades.sort(key=lambda t: t.internal_trade_id)

        # Look for consecutive pairs with index proximity (±2 tolerance)
        for i in range(len(crack_trades)):
            for j in range(i + 1, min(i + 3, len(crack_trades))):  # Check next 2 trades
                trade1, trade2 = crack_trades[i], crack_trades[j]

                if self._validate_crack_roll_pattern(trade1, trade2):
                    crack_pairs.append((trade1, trade2))
                    logger.debug(
                        f"Found potential crack roll pair: {trade1.internal_trade_id} + {trade2.internal_trade_id}"
                    )

        return crack_pairs

    def _validate_crack_roll_pattern(self, trade1: Trade, trade2: Trade) -> bool:
        """Validate that two trades form a valid crack roll pattern.

        Args:
            trade1: First crack trade
            trade2: Second crack trade

        Returns:
            True if trades form valid crack roll pattern

        Validation criteria:
            - Both products contain "crack"
            - Same base product (e.g., both "380cst crack")
            - Different contract months
            - Opposite buy/sell directions
            - Price pattern: one with price, one with 0.0
            - Same quantity (with tolerance)
            - Universal fields match
        """
        # Must both be crack products
        if (
            "crack" not in trade1.product_name.lower()
            or "crack" not in trade2.product_name.lower()
        ):
            return False

        # Must be same crack product
        if trade1.product_name != trade2.product_name:
            return False

        # Must have different contract months
        if trade1.contract_month == trade2.contract_month:
            return False

        # Must have opposite buy/sell directions
        if trade1.buy_sell == trade2.buy_sell:
            return False

        # Price pattern: one trade has price, other has 0.0
        prices = [trade1.price, trade2.price]
        if not (Decimal("0") in prices and any(p != 0 for p in prices)):
            return False

        # Must have same quantity (with tolerance)
        # NOTE: Crack trades are always in MT units, so compare directly in MT
        qty1 = trade1.quantity_mt
        qty2 = trade2.quantity_mt
        if abs(qty1 - qty2) > self.MT_TOLERANCE:
            return False

        # Universal fields must match
        if not self.validate_universal_fields(trade1, trade2):
            return False

        return True

    def _find_crack_roll_match(
        self,
        trader_pair: Tuple[Trade, Trade],
        exchange_trades: List[Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[MatchResult]:
        """Find complex crack roll match for a trader crack pair.

        Args:
            trader_pair: Tuple of two trader crack trades
            exchange_trades: List of exchange trades to search
            pool_manager: Pool manager for checking matched status

        Returns:
            MatchResult if valid complex crack roll match found, None otherwise
        """
        trader1, trader2 = trader_pair

        # Extract base product name from crack product (e.g., "380cst crack" → "380cst")
        base_product = extract_base_product(trader1.product_name)
        if not base_product:
            return None

        # Find complete crack positions for each contract month
        contract_months = [trader1.contract_month, trader2.contract_month]
        exchange_positions = {}

        for month in contract_months:
            position = self._find_exchange_crack_position(
                exchange_trades, month, base_product, trader1, pool_manager
            )
            if position:
                exchange_positions[month] = position

        # Need both crack positions to form a roll
        if len(exchange_positions) != 2:
            return None

        # Validate the complete crack roll match
        if self._validate_crack_roll_match(trader_pair, exchange_positions):
            return self._create_crack_roll_match_result(trader_pair, exchange_positions)

        return None

    def _find_exchange_crack_position(
        self,
        exchange_trades: List[Trade],
        contract_month: str,
        base_product: str,
        reference_trade: Trade,
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[Tuple[Trade, Trade]]:
        """Find complete crack position (base product + brent swap) for a contract month.

        Args:
            exchange_trades: List of exchange trades to search
            contract_month: Contract month to match
            base_product: Base product name (e.g., "380cst")
            reference_trade: Reference trader trade for universal field matching
            pool_manager: Pool manager for checking matched status

        Returns:
            Tuple of (base_product_trade, brent_swap_trade) if found, None otherwise
        """
        base_trade = None
        brent_trade = None

        # Find base product and brent swap trades for this contract month
        for trade in exchange_trades:
            if pool_manager.is_trade_matched(trade):
                continue

            if (
                trade.contract_month == contract_month
                and self.validate_universal_fields(trade, reference_trade)
            ):
                # Check for base product trade
                if trade.product_name.lower() == base_product.lower():
                    if not base_trade:
                        base_trade = trade

                # Check for brent swap trade
                elif trade.product_name.lower() in ["brent swap", "brent_swap"]:
                    if not brent_trade:
                        brent_trade = trade

        # Return complete position if both components found
        if base_trade and brent_trade:
            # Validate quantities align (with unit conversion tolerance)
            if self._validate_crack_position_quantities(
                base_trade, brent_trade, reference_trade
            ):
                return (base_trade, brent_trade)

        return None

    def _validate_crack_position_quantities(
        self, base_trade: Trade, brent_trade: Trade, reference_trade: Trade
    ) -> bool:
        """Validate that crack position quantities align with reference trade.

        Since crack spreads involve unit conversions, we validate everything in BBL
        for consistency. Both base product and brent swap comparisons use BBL tolerance.

        Args:
            base_trade: Base product trade (in MT)
            brent_trade: Brent swap trade (in BBL)
            reference_trade: Reference trader crack trade for quantity comparison

        Returns:
            True if quantities align within BBL tolerance
        """
        # Get reference quantity in MT (crack trades are always in MT)
        ref_qty_mt = reference_trade.quantity_mt

        # Convert reference MT to BBL for comparisons
        ref_qty_bbl = convert_mt_to_bbl_with_product_ratio(
            ref_qty_mt, reference_trade.product_name, self.config_manager
        )

        # For base product: validate MT to BBL conversion
        # Convert base MT to BBL and compare with reference BBL
        if not validate_mt_to_bbl_quantity_match(
            base_trade.quantity_mt,
            ref_qty_bbl,
            reference_trade.product_name,
            self.BBL_TOLERANCE,
            self.config_manager,
        ):
            return False

        # For brent swap: validate reference MT to exchange BBL
        # Convert reference MT to BBL and compare with brent BBL
        if not validate_mt_to_bbl_quantity_match(
            ref_qty_mt,
            brent_trade.quantity_bbl,
            reference_trade.product_name,
            self.BBL_TOLERANCE,
            self.config_manager,
        ):
            return False

        return True

    def _validate_crack_roll_match(
        self,
        trader_pair: Tuple[Trade, Trade],
        exchange_positions: Dict[str, Tuple[Trade, Trade]],
    ) -> bool:
        """Validate complete complex crack roll match between trader and exchange data.

        Args:
            trader_pair: Tuple of two trader crack trades
            exchange_positions: Dict mapping contract months to (base, brent) trade tuples

        Returns:
            True if valid complex crack roll match
        """
        trader1, trader2 = trader_pair

        # Calculate crack prices for each exchange position
        crack_prices = {}
        for month, (base_trade, brent_trade) in exchange_positions.items():
            # Find the trader crack trade for this month to get the correct product name for conversion ratio
            trader_for_month = trader1 if trader1.contract_month == month else trader2
            crack_price = self._calculate_crack_price(
                base_trade, brent_trade, trader_for_month
            )
            if crack_price is None:
                return False
            crack_prices[month] = crack_price

        # Validate B/S direction logic for each position
        for trade in [trader1, trader2]:
            month = trade.contract_month
            base_trade, brent_trade = exchange_positions[month]

            if not self._validate_crack_direction_logic(trade, base_trade, brent_trade):
                return False

        # Calculate roll spread and validate against trader pattern
        return self._validate_roll_spread_calculation(trader_pair, crack_prices)

    def _calculate_crack_price(
        self, base_trade: Trade, brent_trade: Trade, trader_crack_trade: Trade
    ) -> Optional[Decimal]:
        """Calculate crack price from base product and brent swap trades.

        Args:
            base_trade: Base product trade
            brent_trade: Brent swap trade
            trader_crack_trade: Trader crack trade, used to get the correct product name for conversion ratio

        Returns:
            Calculated crack price or None if calculation fails
        """
        try:
            # Get product-specific conversion ratio using the crack product name
            product_ratio = get_product_conversion_ratio(
                trader_crack_trade.product_name, self.config_manager
            )

            # Formula: (base_product_price ÷ conversion_ratio) - brent_swap_price
            # Round the intermediate calculation to 2 decimal places for proper financial precision
            base_price_per_bbl = round(base_trade.price / product_ratio, 2)
            crack_price = base_price_per_bbl - brent_trade.price

            logger.debug(
                f"Calculated crack price (with rounding): ({base_trade.price} ÷ {product_ratio}) = {base_price_per_bbl}, "
                f"{base_price_per_bbl} - {brent_trade.price} = {crack_price}"
            )
            return crack_price

        except (ArithmeticError, ValueError, TypeError, ZeroDivisionError) as e:
            logger.debug(f"Failed to calculate crack price: {e}")
            return None

    def _validate_crack_direction_logic(
        self, trader_crack: Trade, base_trade: Trade, brent_trade: Trade
    ) -> bool:
        """Validate B/S direction logic for crack position.

        Args:
            trader_crack: Trader crack trade
            base_trade: Exchange base product trade
            brent_trade: Exchange brent swap trade

        Returns:
            True if direction logic is correct

        Direction logic:
            - Sell Crack = Sell Base + Buy Brent
            - Buy Crack = Buy Base + Sell Brent
        """
        if trader_crack.buy_sell == "S":
            return base_trade.buy_sell == "S" and brent_trade.buy_sell == "B"
        elif trader_crack.buy_sell == "B":
            return base_trade.buy_sell == "B" and brent_trade.buy_sell == "S"
        else:
            return False

    def _validate_roll_spread_calculation(
        self, trader_pair: Tuple[Trade, Trade], crack_prices: Dict[str, Decimal]
    ) -> bool:
        """Validate roll spread calculation matches trader price pattern.

        Args:
            trader_pair: Tuple of two trader crack trades
            crack_prices: Dict mapping contract months to calculated crack prices

        Returns:
            True if roll spread calculation matches trader pattern
        """
        trader1, trader2 = trader_pair

        # Get calculated crack prices for each month
        crack_price1 = crack_prices[trader1.contract_month]
        crack_price2 = crack_prices[trader2.contract_month]

        # Calculate roll spread (earlier month - later month)
        month1_tuple = get_month_order_tuple(
            self.normalizer.normalize_contract_month(trader1.contract_month)
        )
        month2_tuple = get_month_order_tuple(
            self.normalizer.normalize_contract_month(trader2.contract_month)
        )

        if not month1_tuple or not month2_tuple:
            return False

        if month1_tuple < month2_tuple:
            # trader1 is earlier month
            roll_spread = crack_price1 - crack_price2
            trader_spread_price = trader1.price if trader1.price != 0 else trader2.price
        else:
            # trader2 is earlier month
            roll_spread = crack_price2 - crack_price1
            trader_spread_price = trader2.price if trader2.price != 0 else trader1.price

        # Validate roll spread matches trader non-zero price
        if roll_spread != trader_spread_price:
            return False

        logger.debug(
            f"Roll spread validation: calculated={roll_spread}, trader={trader_spread_price}"
        )
        return True

    def _create_crack_roll_match_result(
        self,
        trader_pair: Tuple[Trade, Trade],
        exchange_positions: Dict[str, Tuple[Trade, Trade]],
    ) -> MatchResult:
        """Create MatchResult for complex crack roll match.

        Args:
            trader_pair: Tuple of two trader crack trades
            exchange_positions: Dict mapping contract months to exchange trade pairs

        Returns:
            MatchResult for the complex crack roll match
        """
        trader1, trader2 = trader_pair

        # Flatten exchange trades
        exchange_trades = []
        for base_trade, brent_trade in exchange_positions.values():
            exchange_trades.extend([base_trade, brent_trade])

        # Rule-specific matched fields
        rule_specific_fields = [
            "crack_products",
            "contract_months",
            "crack_roll_spread_calculation",
            "quantity_with_unit_conversion",
            "crack_position_direction_logic",
        ]

        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        # Create tolerances applied info
        tolerances_applied = {
            "quantity_tolerance_mt": float(self.MT_TOLERANCE),
            "quantity_tolerance_bbl": float(self.BBL_TOLERANCE),
            "unit_conversion": "MT ↔ BBL with product-specific ratios",
        }

        return MatchResult(
            match_id=self.generate_match_id(self.rule_number),
            match_type=MatchType.COMPLEX_CRACK_ROLL,
            confidence=self.confidence,
            trader_trade=trader1,
            exchange_trade=exchange_trades[0],
            matched_fields=matched_fields,
            differing_fields=[],
            tolerances_applied=tolerances_applied,
            rule_order=self.rule_number,
            additional_trader_trades=[trader2],
            additional_exchange_trades=exchange_trades[1:],
        )

    def get_rule_info(self) -> dict:
        """Get information about this matching rule."""
        return {
            "rule_number": self.rule_number,
            "rule_name": "Complex Crack Roll Match",
            "match_type": MatchType.COMPLEX_CRACK_ROLL.value,
            "confidence": float(self.confidence),
            "description": "Matches consecutive complex crack trades (calendar spread) against complete exchange crack positions",
            "requirements": [
                "Two consecutive trader crack trades (same base product)",
                "Price pattern: one with spread price, one with 0.0",
                "Opposite B/S directions between crack trades",
                "Four exchange trades: base product + brent swap for each contract month",
                "Crack price calculation validation using product-specific ratios",
                "Roll spread calculation matches trader price pattern",
            ],
            "tolerances": {
                "quantity_mt": float(self.MT_TOLERANCE),
                "quantity_bbl": float(self.BBL_TOLERANCE),
            },
        }
