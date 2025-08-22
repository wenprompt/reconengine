"""Aggregated product spread matcher for Rule 11 - Product spread matching with aggregation logic."""

import logging
from decimal import Decimal
from typing import List, Tuple, Dict, Optional, Any
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..normalizers import TradeNormalizer
from ..config import ConfigManager
from ..core import UnmatchedPoolManager
from .aggregation_base_matcher import AggregationBaseMatcher
from .product_spread_base_matcher import ProductSpreadMixin

logger = logging.getLogger(__name__)


class AggregatedProductSpreadMatcher(AggregationBaseMatcher, ProductSpreadMixin):
    """Matches product spread trades with aggregation logic between trader and exchange data.

    Handles Rule 11: Aggregated Product Spread Match Rules
    Combines aggregation patterns (1-to-many, many-to-1) with product spread logic:

    Scenarios:
    - Many exchange product spread trades → One trader spread pair
    - One exchange spread → Many trader trades per product leg
    - Handles both hyphenated exchange products and 2-leg formats with aggregation
    """

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the aggregated product spread matcher.

        Args:
            config_manager: Configuration manager with rule settings
            normalizer: Trade normalizer for data processing
        """
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 11
        self.confidence = config_manager.get_rule_confidence(self.rule_number)

        logger.info(
            f"Initialized AggregatedProductSpreadMatcher with {self.confidence}% confidence"
        )

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find aggregated product spread matches between trader and exchange data.

        Args:
            pool_manager: Pool manager containing unmatched trades

        Returns:
            List of aggregated product spread matches found
        """
        logger.info("Starting aggregated product spread matching (Rule 11)")

        matches: List[MatchResult] = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Scenario A: Many exchange trades → One trader spread pair
        exchange_to_trader_matches = self._find_aggregated_exchange_to_trader_matches(
            trader_trades, exchange_trades, pool_manager
        )
        matches.extend(exchange_to_trader_matches)

        # Scenario B: One exchange spread → Many trader trades per leg
        trader_to_exchange_matches = self._find_aggregated_trader_to_exchange_matches(
            trader_trades, exchange_trades, pool_manager
        )
        matches.extend(trader_to_exchange_matches)

        logger.info(f"Found {len(matches)} aggregated product spread matches")
        return matches

    def _find_aggregated_exchange_to_trader_matches(
        self,
        trader_trades: List[Trade],
        exchange_trades: List[Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> List[MatchResult]:
        """Find matches where multiple exchange trades aggregate to trader spread pairs.

        Args:
            trader_trades: List of trader trades
            exchange_trades: List of exchange trades
            pool_manager: Pool manager for validation

        Returns:
            List of matches found for aggregated exchange → trader spreads
        """
        matches: List[MatchResult] = []

        # Find trader spread pairs (price/0.00 pattern)
        trader_spread_pairs = self._find_trader_spread_pairs(
            trader_trades, pool_manager
        )

        if not trader_spread_pairs:
            logger.debug("No trader spread pairs found for aggregated matching")
            return matches

        logger.info(
            f"Processing {len(trader_spread_pairs)} trader spread pairs for exchange aggregation"
        )

        # For each trader spread pair, try to find aggregated exchange trades (Scenario A)
        for trader_spread_pair in trader_spread_pairs:
            if any(
                pool_manager.is_trade_matched(trade) for trade in trader_spread_pair
            ):
                continue

            match = self._find_exchange_aggregation_for_trader_spread(
                trader_spread_pair, exchange_trades, pool_manager
            )
            if match:
                matches.append(match)
                pool_manager.record_match(match)
                logger.info(f"Found aggregated exchange→trader match: {match.match_id}")

        # Also try cross-spread aggregation (Scenario C)
        cross_match = self._find_cross_spread_aggregation_match(
            trader_spread_pairs, exchange_trades, pool_manager
        )
        if cross_match:
            matches.append(cross_match)
            pool_manager.record_match(cross_match)
            logger.info(f"Found cross-spread aggregation match: {cross_match.match_id}")

        logger.info(f"Found {len(matches)} aggregated exchange→trader matches")
        return matches

    def _find_aggregated_trader_to_exchange_matches(
        self,
        trader_trades: List[Trade],
        exchange_trades: List[Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> List[MatchResult]:
        """Find matches where multiple trader trades per leg aggregate to exchange spreads.

        Args:
            trader_trades: List of trader trades
            exchange_trades: List of exchange trades
            pool_manager: Pool manager for validation

        Returns:
            List of matches found for aggregated trader → exchange spreads
        """
        matches: List[MatchResult] = []

        # Find exchange spread trades (both hyphenated and 2-leg)
        exchange_spreads = self._find_exchange_spread_trades(
            exchange_trades, pool_manager
        )

        if not exchange_spreads:
            logger.debug("No exchange spread trades found for aggregated matching")
            return matches

        logger.info(
            f"Processing {len(exchange_spreads)} exchange spreads for trader aggregation"
        )

        # For each exchange spread, find aggregated trader trades
        for exchange_spread in exchange_spreads:
            if pool_manager.is_trade_matched(exchange_spread):
                continue

            match = self._find_trader_aggregation_for_exchange_spread(
                exchange_spread, trader_trades, pool_manager
            )
            if match:
                matches.append(match)
                pool_manager.record_match(match)
                logger.info(f"Found aggregated trader→exchange match: {match.match_id}")

        logger.info(f"Found {len(matches)} aggregated trader→exchange matches")
        return matches

    def _find_trader_spread_pairs(
        self, trader_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> List[Tuple[Trade, Trade]]:
        """Find trader spread pairs (price/0.00 pattern with opposite B/S)."""
        spread_pairs = []

        # Group trades by aggregation signature (contract month, quantity, universal fields)
        aggregation_fields = ["contract_month", "quantity_mt"]
        trade_groups = self.group_trades_by_aggregation_signature(
            trader_trades, aggregation_fields
        )

        for group_signature, group_trades in trade_groups.items():
            if len(group_trades) < 2:
                continue

            # Find spread patterns within each group
            for i in range(len(group_trades)):
                for j in range(i + 1, len(group_trades)):
                    trade1, trade2 = group_trades[i], group_trades[j]

                    if pool_manager.is_trade_matched(
                        trade1
                    ) or pool_manager.is_trade_matched(trade2):
                        continue

                    if self._is_product_spread_pattern(trade1, trade2, require_different_products=True):
                        # Order so price trade comes first
                        if trade1.price != Decimal("0"):
                            spread_pairs.append((trade1, trade2))
                        else:
                            spread_pairs.append((trade2, trade1))

                        logger.debug(
                            f"Found trader spread pair: {trade1.trade_id} + {trade2.trade_id}"
                        )
                        break  # Only one pair per trade

        return spread_pairs

    def _find_exchange_spread_trades(
        self, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager
    ) -> List[Trade]:
        """Find exchange spread trades (hyphenated products and 2-leg spreads)."""
        spread_trades = []

        # Find hyphenated products
        for trade in exchange_trades:
            if pool_manager.is_trade_matched(trade):
                continue

            if self._is_hyphenated_product(trade.product_name):
                spread_trades.append(trade)
                logger.debug(
                    f"Found hyphenated exchange spread: {trade.trade_id} - {trade.product_name}"
                )

        # TODO: Could also add 2-leg exchange spread detection here if needed

        return spread_trades

    def _find_cross_spread_aggregation_match(
        self,
        trader_spread_pairs: List[Tuple[Trade, Trade]],
        exchange_trades: List[Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[MatchResult]:
        """Find match by aggregating trader spread components across multiple spread pairs.

        This handles the scenario where multiple trader spread pairs need to be aggregated
        by product component to match individual exchange trades.

        Example:
        - Trader spread pair 1: marine 1000 B + 380cst 1000 S (Jul-25)
        - Trader spread pair 2: marine 2000 B + 380cst 2000 S (Jul-25)
        - Aggregated: marine 3000 B + 380cst 3000 S (Jul-25)
        - Matches: E_0062 (marine 3000 B Jul-25) + E_0061 (380cst 3000 S Jul-25)
        """
        if not trader_spread_pairs:
            return None

        # Group spread pairs by contract month to ensure consistency
        month_groups = defaultdict(list)
        for spread_pair in trader_spread_pairs:
            price_trade, zero_trade = spread_pair
            # Both trades in a spread pair should have same contract month
            if price_trade.contract_month == zero_trade.contract_month:
                month_groups[price_trade.contract_month].append(spread_pair)

        # Try each month group separately for cross-spread aggregation
        for contract_month, month_spread_pairs in month_groups.items():
            if (
                len(month_spread_pairs) < 2
            ):  # Need at least 2 spread pairs for aggregation
                continue

            logger.debug(
                f"Attempting cross-spread aggregation for {len(month_spread_pairs)} spread pairs in {contract_month}"
            )

            # Check if any trades in this month group are already matched
            month_trades: List[Trade] = []
            for spread_pair in month_spread_pairs:
                month_trades.extend(spread_pair)

            if any(pool_manager.is_trade_matched(trade) for trade in month_trades):
                logger.debug(
                    f"Some trader spread trades already matched in {contract_month}, skipping"
                )
                continue

            # Try cross-spread aggregation for this month group
            result = self._attempt_cross_spread_aggregation(
                month_spread_pairs, exchange_trades, pool_manager, contract_month
            )
            if result:
                return result

        return None

    def _attempt_cross_spread_aggregation(
        self,
        trader_spread_pairs: List[Tuple[Trade, Trade]],
        exchange_trades: List[Trade],
        pool_manager: UnmatchedPoolManager,
        contract_month: str,
    ) -> Optional[MatchResult]:
        """Attempt cross-spread aggregation for spread pairs within the same contract month."""

        # Group trader trades by product across all spread pairs
        product_groups = defaultdict(list)

        for price_trade, zero_trade in trader_spread_pairs:
            product_groups[price_trade.product_name].append(price_trade)
            product_groups[zero_trade.product_name].append(zero_trade)

        # Validate we have exactly 2 products
        if len(product_groups) != 2:
            logger.debug(
                f"Expected 2 products for spread aggregation, found {len(product_groups)}"
            )
            return None

        product_names = list(product_groups.keys())
        product1_trades = product_groups[product_names[0]]
        product2_trades = product_groups[product_names[1]]

        logger.debug(
            f"Aggregating {product_names[0]} ({len(product1_trades)} trades) and {product_names[1]} ({len(product2_trades)} trades) in {contract_month}"
        )

        # Calculate aggregated quantities and validate consistency
        product1_total = sum(trade.quantity_mt for trade in product1_trades)
        product2_total = sum(trade.quantity_mt for trade in product2_trades)

        # Must have same aggregated quantity for both products in a spread
        if product1_total != product2_total:
            logger.debug(
                f"❌ Cross-spread aggregation failed: Aggregated quantities don't match for {contract_month} - "
                f"{product_names[0]}={product1_total}MT vs {product_names[1]}={product2_total}MT"
            )
            return None

        # Validate all trades have consistent characteristics within each product (allowing price differences)
        if not self._validate_product_group_consistency(
            product1_trades
        ) or not self._validate_product_group_consistency(product2_trades):
            return None

        # Find matching exchange trades for each product (must also match contract month)
        product1_exchange = self._find_matching_exchange_trade_for_month(
            product1_trades[0],
            Decimal(str(product1_total)),
            exchange_trades,
            pool_manager,
            contract_month,
        )
        product2_exchange = self._find_matching_exchange_trade_for_month(
            product2_trades[0],
            Decimal(str(product2_total)),
            exchange_trades,
            pool_manager,
            contract_month,
        )

        if not product1_exchange or not product2_exchange:
            logger.debug(
                f"❌ Cross-spread aggregation failed for {contract_month}: Could not find matching exchange trades "
                f"for both products ({product_names[0]}: {product1_exchange is not None}, "
                f"{product_names[1]}: {product2_exchange is not None})"
            )
            return None

        # Validate the spread direction logic
        if not self._validate_cross_spread_direction_logic(
            product1_trades, product2_trades, product1_exchange, product2_exchange
        ):
            return None

        # Create match result
        return self._create_cross_spread_match_result(
            trader_spread_pairs, product1_exchange, product2_exchange
        )

    def _find_matching_exchange_trade_for_month(
        self,
        reference_trade: Trade,
        target_quantity: Decimal,
        exchange_trades: List[Trade],
        pool_manager: UnmatchedPoolManager,
        contract_month: str,
    ) -> Optional[Trade]:
        """Find exchange trade that matches the aggregated trader component and contract month."""
        for exchange_trade in exchange_trades:
            if pool_manager.is_trade_matched(exchange_trade):
                continue

            if (
                exchange_trade.product_name == reference_trade.product_name
                and exchange_trade.contract_month == contract_month
                and exchange_trade.quantity_mt == Decimal(str(target_quantity))
                and exchange_trade.buy_sell == reference_trade.buy_sell
                and self.validate_universal_fields(reference_trade, exchange_trade)
            ):

                logger.debug(
                    f"Found matching exchange trade {exchange_trade.trade_id} for {reference_trade.product_name} quantity {target_quantity} in {contract_month}"
                )
                return exchange_trade

        logger.debug(
            f"No matching exchange trade found for {reference_trade.product_name} quantity {target_quantity} in {contract_month}"
        )
        return None

    def _validate_product_group_consistency(self, trades: List[Trade]) -> bool:
        """Validate that all trades in a product group have consistent characteristics.

        For cross-spread aggregation, we only require matching product, contract month,
        and buy_sell direction. Price differences are allowed as they represent different
        spread pairs being aggregated.
        """
        if not trades:
            logger.debug(
                "❌ Empty trades list provided for product group consistency validation"
            )
            return False

        if len(trades) == 1:
            return True  # Single trade is always consistent

        first_trade = trades[0]
        for trade in trades[1:]:
            if (
                trade.product_name != first_trade.product_name
                or trade.contract_month != first_trade.contract_month
                or trade.buy_sell != first_trade.buy_sell
            ):
                logger.debug(
                    f"Inconsistent product group: {trade.trade_id} vs {first_trade.trade_id} "
                    f"(product: {trade.product_name}/{first_trade.product_name}, "
                    f"month: {trade.contract_month}/{first_trade.contract_month}, "
                    f"direction: {trade.buy_sell}/{first_trade.buy_sell})"
                )
                return False

        # Log price differences for debugging but don't fail validation
        prices = [trade.price for trade in trades]
        if len(set(prices)) > 1:
            logger.debug(
                f"Price variation in product group {first_trade.product_name}: {prices} - allowed for cross-spread aggregation"
            )

        return True

    def _find_matching_exchange_trade(
        self,
        reference_trade: Trade,
        target_quantity: Decimal,
        exchange_trades: List[Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[Trade]:
        """Find exchange trade that matches the aggregated trader component."""
        for exchange_trade in exchange_trades:
            if pool_manager.is_trade_matched(exchange_trade):
                continue

            if (
                exchange_trade.product_name == reference_trade.product_name
                and exchange_trade.contract_month == reference_trade.contract_month
                and exchange_trade.quantity_mt == Decimal(str(target_quantity))
                and exchange_trade.buy_sell == reference_trade.buy_sell
                and self.validate_universal_fields(reference_trade, exchange_trade)
            ):

                logger.debug(
                    f"Found matching exchange trade {exchange_trade.trade_id} for {reference_trade.product_name} quantity {target_quantity}"
                )
                return exchange_trade

        logger.debug(
            f"No matching exchange trade found for {reference_trade.product_name} quantity {target_quantity}"
        )
        return None

    def _validate_cross_spread_direction_logic(
        self,
        product1_trades: List[Trade],
        product2_trades: List[Trade],
        product1_exchange: Trade,
        product2_exchange: Trade,
    ) -> bool:
        """Validate that the spread direction logic is correct."""
        # Ensure opposite directions between products (spread pattern)
        product1_direction = product1_trades[0].buy_sell
        product2_direction = product2_trades[0].buy_sell

        if product1_direction == product2_direction:
            logger.debug("Trader products have same direction, not a valid spread")
            return False

        # Exchange trades must match trader directions
        if (
            product1_exchange.buy_sell != product1_direction
            or product2_exchange.buy_sell != product2_direction
        ):
            logger.debug("Exchange directions don't match trader directions")
            return False

        return True

    def _create_cross_spread_match_result(
        self,
        trader_spread_pairs: List[Tuple[Trade, Trade]],
        product1_exchange: Trade,
        product2_exchange: Trade,
    ) -> MatchResult:
        """Create match result for cross-spread aggregation."""

        # Flatten all trader trades
        all_trader_trades: List[Trade] = []
        for spread_pair in trader_spread_pairs:
            all_trader_trades.extend(spread_pair)

        # Generate unique match ID
        match_id = self.generate_match_id(self.rule_number, "AGG_PROD_SPREAD")

        # Create synthetic spread trade for display
        product1_name = product1_exchange.product_name
        product2_name = product2_exchange.product_name

        # Use the aggregated quantity, not individual trade quantity
        aggregated_quantity = product1_exchange.quantity_mt  # Should be 3000

        display_trade = all_trader_trades[0].model_copy(
            update={
                "product_name": f"{product1_name}/{product2_name}",
                "quantity": aggregated_quantity,  # Update base quantity field, not the property
            }
        )

        # Rule-specific fields
        rule_specific_fields = [
            "aggregated_product_spread",
            "contract_month",
            "quantity_aggregation",
            "buy_sell_spread_pattern",
            "cross_spread_aggregation",
        ]

        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.AGGREGATED_PRODUCT_SPREAD,
            confidence=self.confidence,
            trader_trade=display_trade,
            exchange_trade=product1_exchange,
            additional_trader_trades=all_trader_trades[1:],
            additional_exchange_trades=[product2_exchange],
            matched_fields=matched_fields,
            tolerances_applied={
                "aggregation": f"{len(trader_spread_pairs)} trader spread pairs aggregated",
                "quantity_match": "exact",
            },
            rule_order=self.rule_number,
        )

    def _find_exchange_aggregation_for_trader_spread(
        self,
        trader_spread_pair: Tuple[Trade, Trade],
        exchange_trades: List[Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[MatchResult]:
        """Find aggregated exchange trades that match trader spread pair.

        Scenario A: Multiple exchange trades → Single trader spread pair
        This is the reverse of cross-spread aggregation (Scenario C).
        """
        price_trade, zero_trade = trader_spread_pair

        # Skip if trades are already matched
        if pool_manager.is_trade_matched(price_trade) or pool_manager.is_trade_matched(
            zero_trade
        ):
            return None

        # Parse trader product components
        if not self._is_different_products(price_trade, zero_trade):
            logger.debug("Trader spread pair doesn't have different products")
            return None

        logger.debug(
            f"Finding exchange aggregation for trader spread: {price_trade.product_name}({price_trade.quantity_mt}) + {zero_trade.product_name}({zero_trade.quantity_mt})"
        )

        # Group exchange trades by product that match trader spread components
        product1_exchanges = []  # Matches price_trade product
        product2_exchanges = []  # Matches zero_trade product

        for exchange_trade in exchange_trades:
            if pool_manager.is_trade_matched(exchange_trade):
                continue

            # Check universal fields first
            if not self.validate_universal_fields(price_trade, exchange_trade):
                continue

            # Must match contract month
            if exchange_trade.contract_month != price_trade.contract_month:
                continue

            # Group by product component
            if exchange_trade.product_name == price_trade.product_name:
                # Must match buy/sell direction (price will be validated at spread level)
                if exchange_trade.buy_sell == price_trade.buy_sell:
                    product1_exchanges.append(exchange_trade)
            elif exchange_trade.product_name == zero_trade.product_name:
                # Must match buy/sell direction (price will be validated at spread level)
                if exchange_trade.buy_sell == zero_trade.buy_sell:
                    product2_exchanges.append(exchange_trade)

        if not product1_exchanges or not product2_exchanges:
            logger.debug(
                f"Insufficient exchange trades: {len(product1_exchanges)} for {price_trade.product_name}, {len(product2_exchanges)} for {zero_trade.product_name}"
            )
            return None

        # Find aggregation combinations that sum to trader quantities
        product1_aggregation = self._find_exchange_quantity_aggregation(
            product1_exchanges, price_trade.quantity_mt
        )
        product2_aggregation = self._find_exchange_quantity_aggregation(
            product2_exchanges, zero_trade.quantity_mt
        )

        if not product1_aggregation or not product2_aggregation:
            logger.debug("Could not find quantity aggregations for both products")
            return None

        # Validate spread price consistency
        if not self._validate_exchange_aggregated_spread_price(
            trader_spread_pair, product1_aggregation, product2_aggregation
        ):
            logger.debug("Exchange aggregated spread price validation failed")
            return None

        # Validate and create match result
        logger.info(
            f"Found exchange aggregation match: {len(product1_aggregation)}+{len(product2_aggregation)} exchange trades → trader spread pair"
        )
        return self._create_exchange_aggregated_spread_match_result(
            trader_spread_pair, product1_aggregation, product2_aggregation
        )

    def _find_exchange_quantity_aggregation(
        self, candidates: List[Trade], target_quantity: Decimal
    ) -> Optional[List[Trade]]:
        """Find combination of exchange trades that sum to target quantity.

        Uses a greedy approach to find trades that aggregate to the exact target quantity.
        """
        if not candidates:
            logger.debug(
                f"❌ No candidate trades provided for quantity aggregation (target: {target_quantity}MT)"
            )
            return None

        if target_quantity <= 0:
            logger.debug(
                f"❌ Invalid target quantity for aggregation: {target_quantity}MT"
            )
            return None

        # Try to find exact combinations that sum to target quantity
        from itertools import combinations

        # Start with individual trades that match exactly
        for trade in candidates:
            if trade.quantity_mt == target_quantity:
                return [trade]

        # Try combinations of 2, 3, etc. trades (up to reasonable limit)
        for combo_size in range(
            2, min(len(candidates) + 1, 6)
        ):  # Limit to 5 trades max
            for combo in combinations(candidates, combo_size):
                total_quantity = sum(trade.quantity_mt for trade in combo)
                if total_quantity == target_quantity:
                    logger.debug(
                        f"Found {combo_size}-trade aggregation for quantity {target_quantity}"
                    )
                    return list(combo)

        available_quantities = [str(trade.quantity_mt) for trade in candidates]
        logger.debug(
            f"❌ No valid aggregation combination found for target {target_quantity}MT from {len(candidates)} candidates "
            f"with quantities: [{', '.join(available_quantities)}]MT"
        )
        return None

    def _validate_exchange_aggregated_spread_price(
        self,
        trader_spread_pair: Tuple[Trade, Trade],
        product1_aggregation: List[Trade],
        product2_aggregation: List[Trade],
    ) -> bool:
        """Validate that aggregated exchange trades maintain the correct spread price relationship."""
        if not product1_aggregation or not product2_aggregation:
            logger.debug(
                "❌ Empty aggregation lists provided for spread price validation"
            )
            return False

        price_trade, zero_trade = trader_spread_pair

        # Calculate trader spread price
        trader_spread_price = price_trade.price - zero_trade.price

        # For aggregated exchange trades, all should have the same price within each product group
        # (since they're matching individual legs of the spread)
        product1_prices = [trade.price for trade in product1_aggregation]
        product2_prices = [trade.price for trade in product2_aggregation]

        # Validate price consistency within each aggregation group
        if len(set(product1_prices)) > 1:
            logger.debug(
                f"Inconsistent prices in product1 aggregation: {product1_prices}"
            )
            return False

        if len(set(product2_prices)) > 1:
            logger.debug(
                f"Inconsistent prices in product2 aggregation: {product2_prices}"
            )
            return False

        # Calculate exchange spread price
        exchange_product1_price = product1_prices[0]
        exchange_product2_price = product2_prices[0]
        exchange_spread_price = exchange_product1_price - exchange_product2_price

        # Validate spread price matches
        if trader_spread_price != exchange_spread_price:
            logger.debug(
                f"Spread price mismatch: trader {trader_spread_price} vs exchange {exchange_spread_price}"
            )
            return False

        logger.debug(
            f"Spread price validation passed: {trader_spread_price} = {exchange_spread_price}"
        )
        return True

    def _create_exchange_aggregated_spread_match_result(
        self,
        trader_spread_pair: Tuple[Trade, Trade],
        product1_aggregation: List[Trade],
        product2_aggregation: List[Trade],
    ) -> MatchResult:
        """Create match result for aggregated exchange → trader spread (Scenario A)."""

        price_trade, zero_trade = trader_spread_pair
        all_exchange_trades = product1_aggregation + product2_aggregation

        # Generate unique match ID
        match_id = self.generate_match_id(self.rule_number, "AGG_PROD_SPREAD")

        # Rule-specific fields
        rule_specific_fields = [
            "exchange_aggregation",
            "product_components",
            "contract_month",
            "quantity_aggregation",
            "buy_sell_spread",
            "price_differential",
        ]

        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        # Create synthetic spread trade for display purposes
        display_trade = price_trade.model_copy(
            update={
                "product_name": f"{price_trade.product_name}/{zero_trade.product_name}"
            }
        )

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.AGGREGATED_PRODUCT_SPREAD,
            confidence=self.confidence,
            trader_trade=display_trade,  # Display trade showing spread format
            exchange_trade=all_exchange_trades[0],  # Primary exchange trade
            additional_trader_trades=[zero_trade],  # Zero price trader trade
            additional_exchange_trades=all_exchange_trades[
                1:
            ],  # Remaining exchange trades
            matched_fields=matched_fields,
            tolerances_applied={
                "aggregation": f"{len(product1_aggregation)} + {len(product2_aggregation)} exchange trades aggregated",
                "scenario": "A - Many exchange trades → One trader spread pair",
            },
            rule_order=self.rule_number,
        )

    def _find_trader_aggregation_for_exchange_spread(
        self,
        exchange_spread: Trade,
        trader_trades: List[Trade],
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[MatchResult]:
        """Find aggregated trader trades that match exchange spread."""

        # Parse hyphenated product
        components = self._parse_hyphenated_product(exchange_spread.product_name)
        if not components:
            return None

        first_product, second_product = components

        # Find trader trades for each component
        first_candidates = []
        second_candidates = []

        for trader_trade in trader_trades:
            if pool_manager.is_trade_matched(trader_trade):
                continue

            # Check universal fields and basic matching criteria
            if (
                not self.validate_universal_fields(exchange_spread, trader_trade)
                or trader_trade.contract_month != exchange_spread.contract_month
                or trader_trade.quantity_mt != exchange_spread.quantity_mt
            ):
                continue

            if trader_trade.product_name == first_product:
                first_candidates.append(trader_trade)
            elif trader_trade.product_name == second_product:
                second_candidates.append(trader_trade)

        if not first_candidates or not second_candidates:
            return None

        # Try to find aggregated trader combinations
        first_aggregation = self._find_trader_component_aggregation(
            first_candidates, exchange_spread, pool_manager
        )
        second_aggregation = self._find_trader_component_aggregation(
            second_candidates, exchange_spread, pool_manager
        )

        if not first_aggregation or not second_aggregation:
            return None

        # Validate and create match result
        if self._validate_trader_aggregated_spread_match(
            exchange_spread, first_aggregation, second_aggregation
        ):
            return self._create_trader_aggregated_spread_match_result(
                exchange_spread, first_aggregation, second_aggregation
            )

        return None

    def _find_component_aggregation(
        self,
        candidates: List[Trade],
        target_trade: Trade,
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[List[Trade]]:
        """Find aggregation of exchange trades that matches target trader trade."""

        # Define aggregation fields for product spread components
        aggregation_fields = ["product_name", "contract_month", "price", "buy_sell"]

        # Use base class aggregation logic
        aggregations = self.find_many_to_one_aggregations(
            candidates,
            [target_trade],
            pool_manager,
            aggregation_fields,
            min_aggregation_size=1,
        )

        # Return first valid aggregation
        for aggregated_trades, single_trade in aggregations:
            if single_trade == target_trade:
                return aggregated_trades

        return None

    def _find_trader_component_aggregation(
        self,
        candidates: List[Trade],
        target_exchange: Trade,
        pool_manager: UnmatchedPoolManager,
    ) -> Optional[List[Trade]]:
        """Find aggregation of trader trades for exchange component."""

        # Group candidates by aggregation characteristics
        aggregation_groups = defaultdict(list)

        for trade in candidates:
            if pool_manager.is_trade_matched(trade):
                continue

            # Group by characteristics that must match for aggregation
            group_key = (
                trade.product_name,
                trade.contract_month,
                trade.buy_sell,
                trade.price,
            )
            aggregation_groups[group_key].append(trade)

        # Look for groups that can aggregate to match exchange quantity
        for group_trades in aggregation_groups.values():
            if len(group_trades) < 2:  # Need aggregation
                continue

            total_quantity = sum(trade.quantity_mt for trade in group_trades)
            if total_quantity == target_exchange.quantity_mt:
                # Validate aggregation consistency
                if self.validate_aggregation_consistency(group_trades, target_exchange):
                    return group_trades

        return None


    def _validate_aggregated_spread_match(
        self,
        trader_spread_pair: Tuple[Trade, Trade],
        price_aggregation: List[Trade],
        zero_aggregation: List[Trade],
    ) -> bool:
        """Validate aggregated exchange trades match trader spread pair."""
        price_trade, zero_trade = trader_spread_pair

        # Validate quantities (should already be validated by aggregation logic)
        price_total = sum(trade.quantity_mt for trade in price_aggregation)
        zero_total = sum(trade.quantity_mt for trade in zero_aggregation)

        if (
            price_total != price_trade.quantity_mt
            or zero_total != zero_trade.quantity_mt
        ):
            return False

        # Validate B/S directions match
        price_direction = price_aggregation[0].buy_sell
        zero_direction = zero_aggregation[0].buy_sell

        if (
            price_direction != price_trade.buy_sell
            or zero_direction != zero_trade.buy_sell
        ):
            return False

        # Validate price calculation
        price_component_price = price_aggregation[0].price
        zero_component_price = zero_aggregation[0].price

        calculated_spread = price_component_price - zero_component_price
        if calculated_spread != price_trade.price:
            return False

        return True

    def _validate_trader_aggregated_spread_match(
        self,
        exchange_spread: Trade,
        first_aggregation: List[Trade],
        second_aggregation: List[Trade],
    ) -> bool:
        """Validate aggregated trader trades match exchange spread."""
        if not first_aggregation or not second_aggregation:
            logger.debug(
                f"❌ Empty aggregation lists for exchange spread {exchange_spread.trade_id} validation"
            )
            return False

        # Validate total quantities
        first_total = sum(trade.quantity_mt for trade in first_aggregation)
        second_total = sum(trade.quantity_mt for trade in second_aggregation)

        if (
            first_total != exchange_spread.quantity_mt
            or second_total != exchange_spread.quantity_mt
        ):
            return False

        # Validate B/S directions form proper spread pattern
        first_direction = first_aggregation[0].buy_sell
        second_direction = second_aggregation[0].buy_sell

        # Must have opposite directions
        if first_direction == second_direction:
            return False

        # Validate direction logic matches exchange spread
        components = self._parse_hyphenated_product(exchange_spread.product_name)
        if not components:
            return False

        first_product, second_product = components

        # Check direction logic based on exchange spread direction
        if exchange_spread.buy_sell == "B":
            # Buy spread = Buy first + Sell second
            expected_first_direction = "B"
            expected_second_direction = "S"
        else:
            # Sell spread = Sell first + Buy second
            expected_first_direction = "S"
            expected_second_direction = "B"

        if (
            first_direction != expected_first_direction
            or second_direction != expected_second_direction
        ):
            return False

        # Validate price calculation
        first_price = first_aggregation[0].price
        second_price = second_aggregation[0].price
        calculated_spread = first_price - second_price

        return calculated_spread == exchange_spread.price

    def _create_aggregated_spread_match_result(
        self,
        trader_spread_pair: Tuple[Trade, Trade],
        price_aggregation: List[Trade],
        zero_aggregation: List[Trade],
    ) -> MatchResult:
        """Create match result for aggregated exchange → trader spread."""

        price_trade, zero_trade = trader_spread_pair
        all_exchange_trades = price_aggregation + zero_aggregation

        # Generate unique match ID
        match_id = self.generate_match_id(self.rule_number, "AGG_PROD_SPREAD")

        # Rule-specific fields
        rule_specific_fields = [
            "product_components",
            "contract_month",
            "quantity_aggregation",
            "buy_sell_spread",
            "price_differential",
        ]

        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        # Create a synthetic trade representing the spread for display purposes
        display_trade = price_trade.model_copy(
            update={
                "product_name": f"{price_trade.product_name}/{zero_trade.product_name}"
            }
        )

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.AGGREGATED_PRODUCT_SPREAD,
            confidence=self.confidence,
            trader_trade=display_trade,  # Display trade showing spread format
            exchange_trade=all_exchange_trades[0],  # Primary exchange trade
            additional_trader_trades=[zero_trade],  # Zero price trader trade
            additional_exchange_trades=all_exchange_trades[
                1:
            ],  # Remaining exchange trades
            matched_fields=matched_fields,
            tolerances_applied={
                "aggregation": f"{len(price_aggregation)} + {len(zero_aggregation)} exchange trades aggregated",
                "price_differential": "exact",
            },
            rule_order=self.rule_number,
        )

    def _create_trader_aggregated_spread_match_result(
        self,
        exchange_spread: Trade,
        first_aggregation: List[Trade],
        second_aggregation: List[Trade],
    ) -> MatchResult:
        """Create match result for aggregated trader → exchange spread."""

        all_trader_trades = first_aggregation + second_aggregation

        # Generate unique match ID
        match_id = self.generate_match_id(self.rule_number, "AGG_PROD_SPREAD")

        # Rule-specific fields
        rule_specific_fields = [
            "product_spread",
            "contract_month",
            "quantity_aggregation",
            "buy_sell_components",
            "price_calculation",
        ]

        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        # Create a synthetic trade representing the spread for display purposes
        display_trade = all_trader_trades[0].model_copy(
            update={
                "product_name": f"{first_aggregation[0].product_name}/{second_aggregation[0].product_name}"
            }
        )

        return MatchResult(
            match_id=match_id,
            match_type=MatchType.AGGREGATED_PRODUCT_SPREAD,
            confidence=self.confidence,
            trader_trade=display_trade,  # Display trade showing spread format
            exchange_trade=exchange_spread,
            additional_trader_trades=all_trader_trades[1:],  # Remaining trader trades
            matched_fields=matched_fields,
            tolerances_applied={
                "aggregation": f"{len(first_aggregation)} + {len(second_aggregation)} trader trades aggregated",
                "price_calculation": "exact",
            },
            rule_order=self.rule_number,
        )

    def get_rule_info(self) -> Dict[str, Any]:
        """Get information about this matching rule."""
        return {
            "rule_number": self.rule_number,
            "rule_name": "Aggregated Product Spread Match",
            "match_type": MatchType.AGGREGATED_PRODUCT_SPREAD.value,
            "confidence": float(self.confidence),
            "description": "Matches product spreads with aggregation logic (1-to-many, many-to-1)",
            "requirements": [
                "Scenario A: Multiple exchange product trades → Single trader spread pair",
                "Scenario B: Single exchange spread → Multiple trader trades per component",
                "Aggregated quantities must sum to match target quantities exactly",
                "B/S direction logic must follow product spread rules",
                "Price differential must match exactly after aggregation",
                "All trades must have matching universal fields",
                "Handles both hyphenated exchange products and 2-leg formats",
            ],
            "scenarios": [
                "Many exchange component trades → One trader spread pair",
                "One exchange hyphenated spread → Many trader component trades",
            ],
        }
