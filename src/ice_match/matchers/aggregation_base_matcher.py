"""Base aggregation matcher providing shared aggregation logic for Rules 6, 7, 8, 9."""

import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from decimal import Decimal

from ..models import Trade, MatchResult
from ..config import ConfigManager
from ..core import UnmatchedPoolManager
from .base_matcher import BaseMatcher

logger = logging.getLogger(__name__)


class AggregationBaseMatcher(BaseMatcher):
    """Base class providing shared aggregation logic for aggregation-based rules.

    This class provides reusable methods for:
    - Grouping trades by aggregation characteristics
    - Validating aggregation matches
    - Creating aggregation signatures
    - Handling both many→one and one→many scenarios

    Used by:
    - Rule 7: AggregationMatcher (basic aggregation)
    - Rule 8: AggregatedComplexCrackMatcher (aggregation + complex crack)
    - Rule 9: AggregatedSpreadMatcher (aggregation + spread)
    - Rule 11: AggregatedCrackMatcher (aggregation + crack)
    """

    def __init__(self, config_manager: ConfigManager):
        """Initialize the aggregation base matcher.

        Args:
            config_manager: Configuration manager with rule settings
        """
        super().__init__(config_manager)
        logger.debug(
            "Initialized AggregationBaseMatcher for rule-agnostic aggregation logic"
        )

    def group_trades_by_aggregation_signature(
        self, trades: List[Trade], aggregation_fields: List[str]
    ) -> Dict[tuple, List[Trade]]:
        """Group trades by aggregation signature using specified fields.

        Args:
            trades: List of trades to group
            aggregation_fields: List of trade attribute names to use for grouping

        Returns:
            Dictionary mapping aggregation signatures to trade lists
        """
        groups: Dict[tuple, List[Trade]] = defaultdict(list)

        for trade in trades:
            # Extract values for aggregation fields
            field_values = []
            for field_name in aggregation_fields:
                field_values.append(getattr(trade, field_name))

            # Create aggregation signature with universal fields
            signature = self.create_universal_signature(trade, field_values)
            groups[signature].append(trade)

        logger.debug(
            f"Grouped {len(trades)} trades into {len(groups)} aggregation groups"
        )
        return groups

    def find_many_to_one_aggregations(
        self,
        many_source: List[Trade],
        one_source: List[Trade],
        pool_manager: UnmatchedPoolManager,
        aggregation_fields: List[str],
        min_aggregation_size: int = 2,
    ) -> List[Tuple[List[Trade], Trade]]:
        """Find many-to-one aggregation patterns.

        Args:
            many_source: Source with potentially multiple smaller trades
            one_source: Source with potentially single aggregated trades
            pool_manager: Pool manager for validation
            aggregation_fields: Fields to use for aggregation grouping
            min_aggregation_size: Minimum number of trades to form aggregation

        Returns:
            List of (aggregated_trades_list, single_trade) tuples
        """
        aggregations = []

        # Group many_source trades by aggregation signature
        many_groups = self.group_trades_by_aggregation_signature(
            many_source, aggregation_fields
        )

        # Create lookup index for one_source trades (including quantity)
        one_index = self._create_full_trade_index(one_source, aggregation_fields)

        logger.debug(
            f"Searching {len(many_groups)} groups against {len(one_index)} single trade signatures"
        )

        for group_signature, group_trades in many_groups.items():
            # Skip if any trade in group is already matched
            if any(pool_manager.is_trade_matched(trade) for trade in group_trades):
                continue

            # Only consider groups with sufficient trades for aggregation
            if len(group_trades) < min_aggregation_size:
                continue

            logger.debug(
                f"Processing group with {len(group_trades)} trades: {[t.internal_trade_id for t in group_trades]}"
            )

            # Calculate total quantity for this group
            total_quantity = sum(trade.quantity_mt for trade in group_trades)
            logger.debug(f"  Total quantity: {total_quantity}")

            # Look for matching single trade with this total quantity
            match_signature = (*group_signature, total_quantity)
            logger.debug(f"  Looking for match signature: {match_signature}")

            if match_signature in one_index:
                candidate_trades = one_index[match_signature]
                logger.debug(
                    f"  Found {len(candidate_trades)} candidate trades: {[t.internal_trade_id for t in candidate_trades]}"
                )

                # Find first unmatched candidate
                for candidate_trade in candidate_trades:
                    if not pool_manager.is_trade_matched(candidate_trade):
                        # Validate the aggregation
                        if self.validate_aggregation_consistency(
                            group_trades, candidate_trade
                        ):
                            aggregations.append((group_trades, candidate_trade))
                            logger.debug(
                                f"✅ Found many-to-one aggregation: {len(group_trades)} trades → 1 trade ({candidate_trade.internal_trade_id})"
                            )
                            break
                        else:
                            logger.debug(
                                f"❌ Aggregation validation failed for {candidate_trade.internal_trade_id}"
                            )
            else:
                logger.debug(f"  No match found for signature: {match_signature}")
                # Debug: show what signatures are available
                logger.debug(f"  Available signatures: {list(one_index.keys())[:5]}...")

        return aggregations

    def validate_aggregation_consistency(
        self, aggregated_trades: List[Trade], single_trade: Trade
    ) -> bool:
        """Validate that multiple trades can aggregate to a single trade.

        Args:
            aggregated_trades: List of trades that should aggregate
            single_trade: Single trade that represents the aggregation

        Returns:
            True if valid aggregation, False otherwise
        """
        try:
            # Must have at least 2 trades to aggregate
            if len(aggregated_trades) < 2:
                logger.debug(
                    "Aggregation validation failed: less than 2 trades to aggregate"
                )
                return False

            # All aggregated trades must have identical characteristics (except quantity)
            first_trade = aggregated_trades[0]
            for trade in aggregated_trades[1:]:
                if not self._trades_have_matching_characteristics(
                    first_trade, trade, ignore_quantity=True
                ):
                    logger.debug(
                        "Aggregation validation failed: aggregated trades have different characteristics"
                    )
                    return False

            # Aggregated trades must match single trade characteristics (except quantity)
            if not self._trades_have_matching_characteristics(
                first_trade, single_trade, ignore_quantity=True
            ):
                logger.debug(
                    "Aggregation validation failed: aggregated and single trade characteristics don't match"
                )
                return False

            # Quantity sum validation: sum of aggregated trades must equal single trade quantity
            total_quantity = sum(trade.quantity_mt for trade in aggregated_trades)
            if total_quantity != single_trade.quantity_mt:
                logger.debug(
                    f"Aggregation validation failed: quantity sum {total_quantity} != {single_trade.quantity_mt}"
                )
                return False

            logger.debug(
                f"✅ Aggregation validation passed: {len(aggregated_trades)} trades sum to {total_quantity} MT"
            )
            return True

        except (AttributeError, TypeError, ValueError, ArithmeticError) as e:
            logger.error(f"Error validating aggregation consistency: {e}")
            return False

    def aggregate_trades_by_contract_and_characteristics(
        self,
        trades: List[Trade],
        pool_manager: UnmatchedPoolManager,
        target_product: str,
        reference_trade: Trade,
        additional_grouping_fields: Optional[List[str]] = None,
    ) -> Dict[str, List[Tuple[List[Trade], Decimal, Decimal]]]:
        """Aggregate trades by contract month and additional characteristics.

        Args:
            trades: Trades to aggregate
            pool_manager: Pool manager to check availability
            target_product: Product name to filter by
            reference_trade: Reference trade for universal field validation
            additional_grouping_fields: Additional fields for grouping (e.g., ['price', 'buy_sell'])

        Returns:
            Dict mapping contract_month -> list of (trades_list, total_quantity, representative_value)
        """
        if additional_grouping_fields is None:
            additional_grouping_fields = ["price", "buy_sell"]

        # Group trades by aggregation characteristics
        aggregation_groups = defaultdict(list)

        for trade in trades:
            if pool_manager.is_trade_matched(trade):
                continue

            # Only consider trades for the target product with matching universal fields
            if (
                trade.product_name != target_product
                or not self.validate_universal_fields(reference_trade, trade)
            ):
                continue

            # Create grouping key with contract month and additional characteristics
            group_key_values = [trade.contract_month]
            for field_name in additional_grouping_fields:
                field_value = getattr(trade, field_name)
                group_key_values.append(field_value)

            group_key = tuple(group_key_values)
            aggregation_groups[group_key].append(trade)

        # Create aggregated positions per contract month
        aggregated_by_contract: Dict[
            str, List[Tuple[List[Trade], Decimal, Decimal]]
        ] = defaultdict(list)

        for group_key, trades_group in aggregation_groups.items():
            contract_month = group_key[0]
            # Representative value - convert to Decimal if needed
            representative_value = group_key[1] if len(group_key) > 1 else Decimal("0")
            if not isinstance(representative_value, Decimal):
                representative_value = Decimal(str(representative_value))

            # Calculate total quantity for this aggregation
            total_quantity = Decimal(sum(trade.quantity_mt for trade in trades_group))

            # Store as (trades_list, total_quantity, representative_value)
            aggregated_position = (trades_group, total_quantity, representative_value)
            aggregated_by_contract[contract_month].append(aggregated_position)

        return dict(aggregated_by_contract)

    def _create_full_trade_index(
        self, trades: List[Trade], base_fields: List[str]
    ) -> Dict[tuple, List[Trade]]:
        """Create index for trades by full signature including quantity.

        Args:
            trades: List of trades to index
            base_fields: Base fields for signature (quantity will be added)

        Returns:
            Dictionary mapping full signatures to trade lists
        """
        index: Dict[tuple, List[Trade]] = defaultdict(list)

        for trade in trades:
            # Create base signature
            field_values = []
            for field_name in base_fields:
                field_values.append(getattr(trade, field_name))

            base_signature = self.create_universal_signature(trade, field_values)

            # Add quantity to create full signature
            full_signature = (*base_signature, trade.quantity_mt)
            index[full_signature].append(trade)

        logger.debug(f"Created trade index with {len(index)} unique full signatures")
        return index

    def _trades_have_matching_characteristics(
        self, trade1: Trade, trade2: Trade, ignore_quantity: bool = False
    ) -> bool:
        """Check if two trades have matching characteristics for aggregation.

        Args:
            trade1: First trade
            trade2: Second trade
            ignore_quantity: Whether to ignore quantity in comparison

        Returns:
            True if trades have matching characteristics
        """
        # Check universal fields
        if not self.validate_universal_fields(trade1, trade2):
            return False

        # Check standard aggregation fields
        if (
            trade1.product_name != trade2.product_name
            or trade1.contract_month != trade2.contract_month
            or trade1.price != trade2.price
            or trade1.buy_sell != trade2.buy_sell
        ):
            return False

        # Check quantity if not ignored
        if not ignore_quantity and trade1.quantity_mt != trade2.quantity_mt:
            return False

        return True

    def create_aggregation_match_result(
        self,
        match_id: str,
        match_type,
        confidence: Decimal,
        aggregated_trades: List[Trade],
        single_trade: Trade,
        direction: str,
        rule_specific_fields: List[str],
        rule_order: int,
    ) -> MatchResult:
        """Create MatchResult for aggregation matches.

        Args:
            match_id: Unique match identifier
            match_type: Type of match (from MatchType enum)
            confidence: Confidence level for this match
            aggregated_trades: List of trades that aggregate
            single_trade: Single trade that represents the aggregation
            direction: Direction of aggregation ("trader_to_exchange" or "exchange_to_trader")
            rule_specific_fields: Rule-specific fields that match exactly
            rule_order: Rule number for ordering

        Returns:
            MatchResult for the aggregation match
        """
        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        # Quantity is the aggregated field
        differing_fields = ["quantity_aggregation"]

        # Create match result based on direction
        if direction == "trader_to_exchange":
            # Multiple trader trades → Single exchange trade
            return MatchResult(
                match_id=match_id,
                match_type=match_type,
                confidence=confidence,
                trader_trade=aggregated_trades[0],  # Primary trader trade
                exchange_trade=single_trade,  # Single exchange trade
                additional_trader_trades=aggregated_trades[
                    1:
                ],  # Additional aggregated trader trades
                matched_fields=matched_fields,
                differing_fields=differing_fields,
                tolerances_applied={
                    "quantity_aggregation": f"{len(aggregated_trades)} trader trades → 1 exchange trade"
                },
                rule_order=rule_order,
            )
        else:  # direction == "exchange_to_trader"
            # Single trader trade → Multiple exchange trades
            return MatchResult(
                match_id=match_id,
                match_type=match_type,
                confidence=confidence,
                trader_trade=single_trade,  # Single trader trade
                exchange_trade=aggregated_trades[0],  # Primary exchange trade
                additional_exchange_trades=aggregated_trades[
                    1:
                ],  # Additional aggregated exchange trades
                matched_fields=matched_fields,
                differing_fields=differing_fields,
                tolerances_applied={
                    "quantity_aggregation": f"1 trader trade → {len(aggregated_trades)} exchange trades"
                },
                rule_order=rule_order,
            )

    def get_aggregation_statistics(self, aggregations: List[Tuple]) -> Dict[str, int]:
        """Get statistics about aggregation patterns found.

        Args:
            aggregations: List of aggregation tuples

        Returns:
            Dictionary with aggregation statistics
        """
        stats = {
            "total_aggregations": len(aggregations),
            "total_trades_involved": 0,
            "max_aggregation_size": 0,
            "min_aggregation_size": 0,
        }

        if not aggregations:
            return stats

        min_size = float("inf")

        for aggregation in aggregations:
            if isinstance(aggregation[0], list):  # Many-to-one pattern
                size = len(aggregation[0])
            else:  # One-to-many pattern
                size = len(aggregation[1]) if isinstance(aggregation[1], list) else 1

            stats["total_trades_involved"] += size + 1  # +1 for the single trade
            stats["max_aggregation_size"] = max(stats["max_aggregation_size"], size)
            min_size = min(min_size, size)

        # Set min_aggregation_size as int
        stats["min_aggregation_size"] = int(min_size) if min_size != float("inf") else 0

        return stats
