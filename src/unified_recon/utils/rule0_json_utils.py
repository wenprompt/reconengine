"""JSON generation utilities for Rule 0."""

from typing import Any, Set
from src.unified_recon.rule_0.position_matrix import PositionMatrix
from src.unified_recon.rule_0.matrix_comparator import PositionComparison, MatchStatus


def group_comparisons_by_product(
    comparisons: list[PositionComparison],
) -> dict[str, list[PositionComparison]]:
    """Group position comparisons by product.

    Args:
        comparisons: List of position comparisons

    Returns:
        Dictionary mapping product to list of comparisons
    """
    by_product: dict[str, list[PositionComparison]] = {}
    for comp in comparisons:
        if comp.product not in by_product:
            by_product[comp.product] = []
        by_product[comp.product].append(comp)
    return by_product


def should_skip_position(comp: PositionComparison) -> bool:
    """Determine if position should be skipped in summary.

    Args:
        comp: Position comparison

    Returns:
        True if position should be skipped
    """
    # Skip zero positions unless they have trades
    return (
        comp.status == MatchStatus.ZERO_POSITION
        and comp.trader_trades == 0
        and comp.exchange_trades == 0
    )


def get_status_string(status: MatchStatus) -> str:
    """Convert MatchStatus enum to string.

    Args:
        status: MatchStatus enum value

    Returns:
        Status string for JSON output
    """
    if status == MatchStatus.MATCHED:
        return "MATCHED"
    elif status == MatchStatus.QUANTITY_MISMATCH:
        return "MISMATCH"
    elif status == MatchStatus.MISSING_IN_EXCHANGE:
        return "MISSING_IN_EXCHANGE"
    elif status == MatchStatus.MISSING_IN_TRADER:
        return "MISSING_IN_TRADER"
    else:
        return "ZERO"


def collect_contract_months(
    trader_matrix: PositionMatrix, exchange_matrix: PositionMatrix, product: str
) -> Set[str]:
    """Collect all contract months for a product.

    Args:
        trader_matrix: Trader position matrix
        exchange_matrix: Exchange position matrix
        product: Product name

    Returns:
        Set of contract months
    """
    all_months = set()

    for month, prod in trader_matrix.positions.keys():
        if prod == product:
            all_months.add(month)

    for month, prod in exchange_matrix.positions.keys():
        if prod == product:
            all_months.add(month)

    return all_months


def get_trades_for_position(
    matrix: PositionMatrix, month: str, product: str
) -> list[dict[str, Any]]:
    """Get trades for a specific position.

    Args:
        matrix: Position matrix
        month: Contract month
        product: Product name

    Returns:
        List of trade details
    """
    pos = matrix.get_position(month, product)
    if pos and pos.trade_details:
        return list(pos.trade_details)
    return []


def create_product_data_structure() -> dict[str, list[Any]]:
    """Create empty product data structure.

    Returns:
        Dictionary with positionSummary and tradeDetails lists
    """
    return {"positionSummary": [], "tradeDetails": []}


def has_product_data(product_data: dict[str, list[Any]]) -> bool:
    """Check if product data has any content.

    Args:
        product_data: Product data dictionary

    Returns:
        True if product has data
    """
    return bool(product_data["positionSummary"] or product_data["tradeDetails"])


def get_exchange_groups_for_trades(trades: list[dict[str, Any]]) -> Set[int]:
    """Extract unique exchange group IDs from trades.

    Args:
        trades: List of trades

    Returns:
        Set of exchange group IDs
    """
    groups = set()
    for trade in trades:
        group = trade.get("exchangeGroupId", trade.get("exchangegroupid", 0))
        group_id = int(group) if group else 0
        if group_id > 0:
            groups.add(group_id)
    return groups


def filter_trades_by_exchange_groups(
    trades: list[dict[str, Any]], exchange_groups: list[int]
) -> list[dict[str, Any]]:
    """Filter trades by exchange group IDs.

    Args:
        trades: List of all trades
        exchange_groups: List of exchange group IDs to include

    Returns:
        Filtered list of trades
    """

    def get_exchange_group(trade: dict[str, Any]) -> int:
        group = trade.get("exchangeGroupId", trade.get("exchangegroupid", 0))
        return int(group) if group else 0

    return [t for t in trades if get_exchange_group(t) in exchange_groups]
