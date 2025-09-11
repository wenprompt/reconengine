"""Product spread matcher for Rule 5 - Product spread matching (hyphenated products)."""

import logging
from decimal import Decimal
from typing import Optional, Any
from collections import defaultdict

from ...unified_recon.models.recon_status import ReconStatus
from ..models import Trade, MatchResult, MatchType, SignatureValue
from ..normalizers import TradeNormalizer
from ..config import ConfigManager
from ..core import UnmatchedPoolManager
from .product_spread_base_matcher import ProductSpreadMixin
from .base_matcher import BaseMatcher

logger = logging.getLogger(__name__)


class ProductSpreadMatcher(BaseMatcher, ProductSpreadMixin):
    """Matches product spread trades between trader and exchange data.

    Handles Rule 5: Product Spread Match Rules
    Two matching paths:

    Path 1 (Original):
    - Exchange data: Hyphenated product names (e.g., "marine 0.5%-380cst")
    - Trader data: Separate trades for component products

    Path 2 (Enhanced):
    - Exchange data: Separate 2-leg trades for component products
    - Trader data: Separate 2-leg trades for component products

    Key patterns:
    - Trader: Usually one leg has spread price, other has price = 0
    - Exchange 2-leg: Both legs have actual product prices
    - Validates B/S direction logic and price calculation
    """

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the product spread matcher.

        Args:
            config_manager: Configuration manager with rule settings
            normalizer: Trade normalizer for data processing
        """
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 5
        self.confidence = config_manager.get_rule_confidence(self.rule_number)

        logger.info(
            f"Initialized ProductSpreadMatcher with {self.confidence}% confidence"
        )

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> list[MatchResult]:
        """Find product spread matches between trader and exchange data.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of product spread matches found
        """
        logger.info("Starting product spread matching (Rule 5)")

        matches: list[MatchResult] = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Path 1: Match trader 2-leg against exchange hyphenated products
        matches.extend(
            self._find_hyphenated_exchange_matches(
                trader_trades, exchange_trades, pool_manager
            )
        )

        # Path 2: Match trader 2-leg against exchange 2-leg spreads
        matches.extend(
            self._find_two_leg_exchange_matches(
                trader_trades, exchange_trades, pool_manager
            )
        )

        logger.info(f"Found {len(matches)} total product spread matches")
        return matches

    def _find_hyphenated_exchange_matches(
        self,
        trader_trades: list[Trade],
        exchange_trades: list[Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> list[MatchResult]:
        """Find matches where exchange has hyphenated products and trader has 2-leg trades.

        Args:
            trader_trades: List of trader trades
            exchange_trades: List of exchange trades
            pool_manager: Pool manager for validation

        Returns:
            List of matches found for hyphenated exchange products
        """
        matches: list[MatchResult] = []

        # Filter exchange trades to only hyphenated products
        hyphenated_trades = [
            t
            for t in exchange_trades
            if "-" in t.product_name
            and self._parse_hyphenated_product(t.product_name) is not None
        ]

        if not hyphenated_trades:
            logger.debug("No hyphenated products found in exchange data")
            return matches

        logger.info(
            f"Processing {len(hyphenated_trades)} hyphenated products "
            f"against {len(trader_trades)} trader trades"
        )

        # Debug: show hyphenated products found
        for trade in hyphenated_trades:
            logger.debug(
                f"Found hyphenated product: {trade.internal_trade_id} - {trade.product_name} "
                f"{trade.contract_month} {trade.quantity_mt} {trade.price} {trade.buy_sell}"
            )

        # Create index of trader trades by product, contract, quantity, broker
        trader_index = self._create_trader_index(trader_trades)

        for exchange_trade in hyphenated_trades:
            if pool_manager.is_trade_matched(exchange_trade):
                continue

            match = self._find_product_spread_match(
                exchange_trade, trader_index, pool_manager
            )
            if match:
                # Record the match to remove trades from unmatched pools
                if pool_manager.record_match(match):
                    matches.append(match)
                    logger.debug(f"Found hyphenated product spread match: {match}")
                else:
                    logger.error(
                        f"Failed to record hyphenated product spread match: {match.match_id}"
                    )

        logger.info(f"Found {len(matches)} hyphenated product spread matches")
        return matches

    def _find_two_leg_exchange_matches(
        self,
        trader_trades: list[Trade],
        exchange_trades: list[Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> list[MatchResult]:
        """Find matches where both trader and exchange have 2-leg spread trades.

        Args:
            trader_trades: List of trader trades
            exchange_trades: List of exchange trades
            pool_manager: Pool manager for validation

        Returns:
            List of matches found for 2-leg exchange spreads
        """
        matches: list[MatchResult] = []

        # Group trader trades into 2-leg spread pairs
        trader_spread_pairs = self._group_trader_spreads(trader_trades, pool_manager)

        # Group exchange trades into 2-leg spread pairs
        exchange_spread_pairs = self._group_exchange_spreads(
            exchange_trades, pool_manager
        )

        if not trader_spread_pairs or not exchange_spread_pairs:
            logger.debug(
                f"Limited 2-leg spreads found - trader pairs: {len(trader_spread_pairs)}, "
                f"exchange pairs: {len(exchange_spread_pairs)}"
            )
            return matches

        logger.info(
            f"Processing {len(trader_spread_pairs)} trader spread pairs against "
            f"{len(exchange_spread_pairs)} exchange spread pairs"
        )

        # Try to match trader spread pairs with exchange spread pairs
        for trader_pair in trader_spread_pairs:
            if any(pool_manager.is_trade_matched(trade) for trade in trader_pair):
                continue

            for exchange_pair in exchange_spread_pairs:
                if any(pool_manager.is_trade_matched(trade) for trade in exchange_pair):
                    continue

                match = self._find_two_leg_spread_match(
                    trader_pair, exchange_pair, pool_manager
                )
                if match:
                    if pool_manager.record_match(match):
                        matches.append(match)
                        logger.debug(f"Found 2-leg product spread match: {match}")
                        break  # Move to next trader pair
                    else:
                        logger.error(
                            f"Failed to record 2-leg product spread match: {match.match_id}"
                        )

        logger.info(f"Found {len(matches)} 2-leg product spread matches")
        return matches

    def _create_trader_index(
        self, trader_trades: list[Trade]
    ) -> dict[tuple[Any, ...], list[Trade]]:
        """Create index of trader trades by matching signature.

        Args:
            trader_trades: List of trader trades to index

        Returns:
            Dictionary mapping signatures to trader trades
        """
        index: dict[tuple[Any, ...], list[Trade]] = defaultdict(list)

        for trade in trader_trades:
            # Index by contract month, quantity, and universal fields
            signature = self._create_trader_signature(trade)
            index[signature].append(trade)

        logger.debug(f"Created trader index with {len(index)} unique signatures")
        return index

    def _group_trader_spreads(
        self, trader_trades: list[Trade], pool_manager: UnmatchedPoolManager
    ) -> list[tuple[Trade, Trade]]:
        """Group trader trades into 2-leg spread pairs.

        Args:
            trader_trades: List of trader trades to group
            pool_manager: Pool manager for checking matched status

        Returns:
            List of trader trade pairs that form spreads
        """
        spread_pairs = []

        # Group trades by signature (contract month, quantity, universal fields)
        groups = defaultdict(list)
        for trade in trader_trades:
            if pool_manager.is_trade_matched(trade):
                continue
            signature = self._create_trader_signature(trade)
            groups[signature].append(trade)

        # Find 2-leg spread patterns within each group
        for signature, trades in groups.items():
            if len(trades) < 2:
                continue

            # Look for pairs with spread pattern
            for i in range(len(trades)):
                for j in range(i + 1, len(trades)):
                    trade1, trade2 = trades[i], trades[j]

                    if self._is_product_spread_pattern(
                        trade1, trade2, require_different_products=False
                    ):
                        spread_pairs.append((trade1, trade2))
                        logger.debug(
                            f"Found trader spread pair: {trade1.internal_trade_id} + {trade2.internal_trade_id} "
                            f"({trade1.product_name}/{trade2.product_name})"
                        )

        logger.debug(f"Found {len(spread_pairs)} trader spread pairs")
        return spread_pairs

    def _group_exchange_spreads(
        self, exchange_trades: list[Trade], pool_manager: UnmatchedPoolManager
    ) -> list[tuple[Trade, Trade]]:
        """Group exchange trades into 2-leg spread pairs.

        Args:
            exchange_trades: List of exchange trades to group
            pool_manager: Pool manager for checking matched status

        Returns:
            List of exchange trade pairs that form spreads
        """
        spread_pairs = []

        # Filter out hyphenated products (they're handled separately)
        non_hyphenated_trades = [
            t
            for t in exchange_trades
            if not pool_manager.is_trade_matched(t)
            and (
                ("-" not in t.product_name)
                or self._parse_hyphenated_product(t.product_name) is None
            )
        ]

        # Group trades by signature (contract month, quantity, universal fields)
        groups = defaultdict(list)
        for trade in non_hyphenated_trades:
            signature = self._create_exchange_signature(trade)
            groups[signature].append(trade)

        # Find 2-leg spread patterns within each group
        for signature, trades in groups.items():
            if len(trades) < 2:
                continue

            # Look for pairs with opposite B/S directions (potential spreads)
            for i in range(len(trades)):
                for j in range(i + 1, len(trades)):
                    trade1, trade2 = trades[i], trades[j]

                    # Check if they have opposite B/S directions and different products
                    if (
                        trade1.buy_sell != trade2.buy_sell
                        and trade1.product_name != trade2.product_name
                    ):
                        spread_pairs.append((trade1, trade2))
                        logger.debug(
                            f"Found exchange spread pair: {trade1.internal_trade_id} + {trade2.internal_trade_id} "
                            f"({trade1.product_name}/{trade2.product_name})"
                        )

        logger.debug(f"Found {len(spread_pairs)} exchange spread pairs")
        return spread_pairs

    def _create_trader_signature(self, trade: Trade) -> tuple[Any, ...]:
        """Create signature for trader trade grouping."""
        return self._create_base_signature(trade)

    def _create_exchange_signature(self, trade: Trade) -> tuple[Any, ...]:
        """Create signature for exchange trade grouping."""
        return self._create_base_signature(trade)

    def _create_base_signature(self, trade: Trade) -> tuple[SignatureValue, ...]:
        """Create base signature for trade grouping (shared between trader and exchange)."""
        # Convert Decimal to float for consistent hashing
        rule_fields: list[SignatureValue] = [
            trade.contract_month,
            float(trade.quantity_mt) if trade.quantity_mt is not None else None,
        ]
        return self.create_universal_signature(trade, rule_fields)

    def _find_product_spread_match(
        self,
        exchange_trade: Trade,
        trader_index: dict[tuple[SignatureValue, ...], list[Trade]],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[MatchResult]:
        """Find product spread match for an exchange trade.

        Args:
            exchange_trade: Exchange trade with hyphenated product
            trader_index: Index of trader trades by signature
            pool_manager: Pool manager for validation

        Returns:
            MatchResult if match found, None otherwise
        """
        # Parse the hyphenated product
        components = self._parse_hyphenated_product(exchange_trade.product_name)
        if not components:
            return None

        first_product, second_product = components
        logger.debug(
            f"Parsed {exchange_trade.product_name} into: '{first_product}' + '{second_product}'"
        )

        # Create signature for finding matching trader trades
        signature = self._create_exchange_signature(exchange_trade)

        if signature not in trader_index:
            logger.debug(f"No trades found for signature: {signature}")
            return None

        # Find matching component trades in trader data
        matching_trades = trader_index[signature]
        logger.debug(
            f"Found {len(matching_trades)} potential trader trades for signature"
        )

        # Look for two trades: one for each component product
        first_trade = None
        second_trade = None

        for trade in matching_trades:
            if pool_manager.is_trade_matched(trade):
                continue

            logger.debug(
                f"Checking trader trade: {trade.internal_trade_id} - {trade.product_name} {trade.price} {trade.buy_sell}"
            )

            if trade.product_name == first_product:
                first_trade = trade
                logger.debug(f"Found first product match: {trade.internal_trade_id}")
            elif trade.product_name == second_product:
                second_trade = trade
                logger.debug(f"Found second product match: {trade.internal_trade_id}")

        # Must have both component trades
        if not first_trade or not second_trade:
            logger.debug(
                f"Missing component trades - first: {first_trade is not None}, second: {second_trade is not None}"
            )
            return None

        # Check if this is a product spread pattern (one with price, one with 0)
        if not self._is_product_spread_pattern(
            first_trade, second_trade, require_different_products=False
        ):
            logger.debug(
                f"Not a product spread pattern - first: {first_trade.price} {first_trade.buy_sell}, second: {second_trade.price} {second_trade.buy_sell}"
            )
            return None

        logger.debug(
            f"✅ Product spread pattern detected: {first_trade.price} {first_trade.buy_sell} + {second_trade.price} {second_trade.buy_sell}"
        )

        # Validate the match
        if not self._validate_product_spread_match(
            exchange_trade, first_trade, second_trade
        ):
            logger.debug("❌ Product spread validation failed")
            return None

        logger.debug("✅ Product spread validation passed")

        # Create match result
        return self._create_match_result(exchange_trade, first_trade, second_trade)

    def _find_two_leg_spread_match(
        self,
        trader_pair: tuple[Trade, Trade],
        exchange_pair: tuple[Trade, Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[MatchResult]:
        """Find match between trader 2-leg spread and exchange 2-leg spread.

        Args:
            trader_pair: Tuple of two trader trades forming a spread
            exchange_pair: Tuple of two exchange trades forming a spread
            pool_manager: Pool manager for validation

        Returns:
            MatchResult if valid match found, None otherwise
        """
        trader1, trader2 = trader_pair
        exchange1, exchange2 = exchange_pair

        logger.debug(
            f"Attempting 2-leg match: Trader({trader1.internal_trade_id}+{trader2.internal_trade_id}) "
            f"vs Exchange({exchange1.internal_trade_id}+{exchange2.internal_trade_id})"
        )

        # Try both product orderings since we don't know which exchange trade corresponds to which trader product
        # Option 1: trader1 product -> exchange1, trader2 product -> exchange2
        if self._validate_two_leg_spread_match(
            trader_pair, exchange_pair, (exchange1, exchange2)
        ):
            return self._create_two_leg_match_result(
                trader_pair, exchange_pair, (exchange1, exchange2)
            )

        # Option 2: trader1 product -> exchange2, trader2 product -> exchange1
        if self._validate_two_leg_spread_match(
            trader_pair, exchange_pair, (exchange2, exchange1)
        ):
            return self._create_two_leg_match_result(
                trader_pair, exchange_pair, (exchange2, exchange1)
            )

        logger.debug("❌ No valid 2-leg spread match found")
        return None

    def _validate_two_leg_spread_match(
        self,
        trader_pair: tuple[Trade, Trade],
        exchange_pair: tuple[Trade, Trade],
        exchange_order: tuple[Trade, Trade],
    ) -> bool:
        """Validate that trader and exchange 2-leg spreads can match.

        Args:
            trader_pair: Tuple of two trader trades
            exchange_pair: Tuple of two exchange trades
            exchange_order: Specific ordering of exchange trades to try

        Returns:
            True if valid match, False otherwise
        """
        trader1, trader2 = trader_pair
        exchange1_ordered, exchange2_ordered = exchange_order

        try:
            # Check quantity alignment - CRITICAL CHECK THAT WAS MISSING
            if (
                trader1.quantity_mt != exchange1_ordered.quantity_mt
                or trader2.quantity_mt != exchange2_ordered.quantity_mt
            ):
                logger.debug(
                    f"❌ Quantity mismatch: trader({trader1.quantity_mt}+{trader2.quantity_mt}={trader1.quantity_mt + trader2.quantity_mt}MT) "
                    f"vs exchange({exchange1_ordered.quantity_mt}+{exchange2_ordered.quantity_mt}={exchange1_ordered.quantity_mt + exchange2_ordered.quantity_mt}MT) "
                    f"- should use Aggregated Product Spread Matcher (Rule 13)"
                )
                return False

            # Check product alignment
            if (
                trader1.product_name != exchange1_ordered.product_name
                or trader2.product_name != exchange2_ordered.product_name
            ):
                logger.debug(
                    f"❌ Product alignment failed: trader({trader1.product_name}/{trader2.product_name}) "
                    f"vs exchange({exchange1_ordered.product_name}/{exchange2_ordered.product_name})"
                )
                return False

            # Check B/S direction alignment
            if (
                trader1.buy_sell != exchange1_ordered.buy_sell
                or trader2.buy_sell != exchange2_ordered.buy_sell
            ):
                logger.debug(
                    f"❌ B/S direction mismatch: trader({trader1.buy_sell}/{trader2.buy_sell}) "
                    f"vs exchange({exchange1_ordered.buy_sell}/{exchange2_ordered.buy_sell})"
                )
                return False

            # Calculate and validate spread prices
            # Trader spread: non-zero price from the trader pair
            trader_spread_price = trader1.price if trader1.price != 0 else trader2.price

            # Exchange spread: first_price - second_price
            exchange_spread_price = exchange1_ordered.price - exchange2_ordered.price

            # Prices must match exactly
            if trader_spread_price != exchange_spread_price:
                logger.debug(
                    f"❌ Spread price validation failed: trader_spread={trader_spread_price} "
                    f"vs exchange_spread={exchange_spread_price} ({exchange1_ordered.price}-{exchange2_ordered.price})"
                )
                return False

            logger.debug(
                f"✅ 2-leg spread validation passed: spread_price={trader_spread_price}"
            )
            return True

        except (AttributeError, TypeError, ValueError, ArithmeticError) as e:
            logger.error(f"Error validating 2-leg spread match: {e}")
            return False

    def _create_two_leg_match_result(
        self,
        trader_pair: tuple[Trade, Trade],
        exchange_pair: tuple[Trade, Trade],
        exchange_order: tuple[Trade, Trade],
    ) -> MatchResult:
        """Create MatchResult for 2-leg spread match.

        Args:
            trader_pair: Tuple of matched trader trades
            exchange_pair: Tuple of matched exchange trades
            exchange_order: Specific ordering used for the match

        Returns:
            MatchResult for the 2-leg spread match
        """
        trader1, trader2 = trader_pair
        exchange1_ordered, exchange2_ordered = exchange_order

        # Generate unique match ID
        match_id = self.generate_match_id(self.rule_number)

        # Rule-specific fields that match exactly
        rule_specific_fields = [
            "contract_month",
            "quantity_mt",
            "product_names",
            "buy_sell_directions",
        ]

        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        # Price is calculated/derived
        differing_fields = ["price"]

        # Create a synthetic trade representing the spread for display purposes
        display_trade = trader1.model_copy(
            update={"product_name": f"{trader1.product_name}/{trader2.product_name}"}
        )

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.PRODUCT_SPREAD,
            confidence=self.confidence,
            status=ReconStatus.MATCHED,  # ICE always returns matched status
            trader_trade=display_trade,  # Display trade showing spread format
            exchange_trade=exchange1_ordered,  # Primary exchange trade
            additional_trader_trades=[trader2],  # Additional trader trade
            additional_exchange_trades=[exchange2_ordered],  # Additional exchange trade
            matched_fields=matched_fields,
            differing_fields=differing_fields,
            rule_order=self.rule_number,
        )

    def _validate_product_spread_match(
        self,
        exchange_trade: Trade,
        first_trader_trade: Trade,
        second_trader_trade: Trade,
    ) -> bool:
        """Validate that trades can form a product spread match.

        Args:
            exchange_trade: Exchange trade with hyphenated product
            first_trader_trade: First component trader trade
            second_trader_trade: Second component trader trade

        Returns:
            True if valid product spread match, False otherwise
        """
        try:
            # Validate B/S direction logic
            if not self._validate_direction_logic(
                exchange_trade, first_trader_trade, second_trader_trade
            ):
                logger.debug("❌ Direction logic validation failed")
                return False

            logger.debug("✅ Direction logic validation passed")

            # Validate price calculation - exact match required (no tolerance)
            if not self._validate_price_calculation(
                exchange_trade.price,
                first_trader_trade.price,
                second_trader_trade.price,
            ):
                logger.debug("❌ Price calculation validation failed")
                return False

            logger.debug("✅ Price calculation validation passed")

            return True

        except (AttributeError, TypeError, ValueError, ArithmeticError) as e:
            logger.error(f"Error validating product spread match: {e}")
            return False

    def _validate_direction_logic(
        self,
        exchange_trade: Trade,
        first_trader_trade: Trade,
        second_trader_trade: Trade,
    ) -> bool:
        """Validate product spread B/S direction logic.

        Args:
            exchange_trade: Exchange trade with hyphenated product
            first_trader_trade: First component trader trade
            second_trader_trade: Second component trader trade

        Returns:
            True if direction logic is valid, False otherwise
        """
        # Product spread direction logic from rules.md:
        # Sell Product Spread: Exchange Sells "Product1-Product2" = Trader Sells Product1 + Buys Product2
        # Buy Product Spread: Exchange Buys "Product1-Product2" = Trader Buys Product1 + Sells Product2

        if exchange_trade.buy_sell == "S":
            # Sell spread = Sell first product (S) + Buy second product (B)
            return (
                first_trader_trade.buy_sell == "S"
                and second_trader_trade.buy_sell == "B"
            )
        else:  # exchange_trade.buy_sell == "B"
            # Buy spread = Buy first product (B) + Sell second product (S)
            return (
                first_trader_trade.buy_sell == "B"
                and second_trader_trade.buy_sell == "S"
            )

    def _validate_price_calculation(
        self, exchange_price: Decimal, first_price: Decimal, second_price: Decimal
    ) -> bool:
        """Validate spread price calculation (exact match required).

        Args:
            exchange_price: Exchange spread price
            first_price: First component price
            second_price: Second component price

        Returns:
            True if price calculation is valid, False otherwise
        """
        # Price calculation: first_product_price - second_product_price = spread_price
        calculated_spread = first_price - second_price

        # Exact match required (no tolerance)
        is_valid = calculated_spread == exchange_price

        if not is_valid:
            logger.debug(
                f"Price calculation failed: {first_price} - {second_price} = {calculated_spread}, "
                f"expected {exchange_price} (exact match required)"
            )

        return is_valid

    def _create_match_result(
        self,
        exchange_trade: Trade,
        first_trader_trade: Trade,
        second_trader_trade: Trade,
    ) -> MatchResult:
        """Create MatchResult for product spread match.

        Args:
            exchange_trade: Matched exchange trade
            first_trader_trade: First component trader trade
            second_trader_trade: Second component trader trade

        Returns:
            MatchResult representing the product spread match
        """
        # Generate unique match ID
        match_id = self.generate_match_id(self.rule_number)

        # Rule-specific fields that match exactly
        rule_specific_fields = ["contract_month", "quantity_mt"]

        # Get complete matched fields with universal fields using BaseMatcher method
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        # Product name and price are calculated/derived
        differing_fields = ["product_name", "price"]

        # Create a synthetic trade representing the spread for display purposes
        display_trade = first_trader_trade.model_copy(
            update={
                "product_name": f"{first_trader_trade.product_name}/{second_trader_trade.product_name}"
            }
        )

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.PRODUCT_SPREAD,
            confidence=self.confidence,
            status=ReconStatus.MATCHED,  # ICE always returns matched status
            trader_trade=display_trade,  # Display trade showing spread format
            exchange_trade=exchange_trade,
            additional_trader_trades=[
                second_trader_trade
            ],  # Additional component trade
            matched_fields=matched_fields,
            differing_fields=differing_fields,
            rule_order=self.rule_number,
        )

    def get_rule_info(self) -> dict[str, Any]:
        """Get information about this matching rule.

        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Product Spread Match",
            "match_type": MatchType.PRODUCT_SPREAD.value,
            "confidence": float(self.confidence),
            "description": "Matches product spreads between trader and exchange data (both hyphenated and 2-leg formats)",
            "fields_matched": self.get_universal_matched_fields(
                ["contract_month", "quantity_mt"]
            ),
            "requirements": [
                "Path 1: Exchange hyphenated products (e.g., 'marine 0.5%-380cst') vs trader 2-leg trades",
                "Path 2: Exchange 2-leg trades vs trader 2-leg trades",
                "Trader: separate trades for each component product (one with price, one with 0.0)",
                "B/S direction logic: Sell spread = Sell first + Buy second",
                "Price calculation: first_price - second_price = spread_price",
                "Same contract month, quantity, and broker group",
            ],
            "tolerances": {"price_matching": "exact"},
        }
