"""Helper functions for fly pattern matching optimization."""

from decimal import Decimal

from ..models import Trade


def group_trades_by_month(trades: list[Trade]) -> dict[str, list[Trade]]:
    """Group trades by contract month for efficient fly pattern analysis.

    Args:
        trades: List of trades to group

    Returns:
        dict mapping contract months to lists of trades
    """
    groups: dict[str, list[Trade]] = {}
    for trade in trades:
        groups.setdefault(trade.contract_month, []).append(trade)
    return groups


def build_month_quantity_lookups(
    month_groups: dict[str, list[Trade]],
) -> dict[str, dict[Decimal, list[Trade]]]:
    """Build quantity-based lookup indexes for O(1) middle leg searches.

    Args:
        month_groups: Trades grouped by contract month

    Returns:
        dict mapping month -> quantity -> list of trades with that quantity
    """
    lookups: dict[str, dict[Decimal, list[Trade]]] = {}
    
    for month, trades_list in month_groups.items():
        month_lookup: dict[Decimal, list[Trade]] = {}
        for trade in trades_list:
            month_lookup.setdefault(trade.quantity_mt, []).append(trade)
        lookups[month] = month_lookup

    return lookups


def generate_month_triplets(sorted_months: list[str]) -> list[tuple[str, str, str]]:
    """Generate all valid month triplets (i < j < k) for fly pattern matching.

    Args:
        sorted_months: Contract months sorted chronologically

    Returns:
        List of (month1, month2, month3) triplets in chronological order
    """
    triplets = []

    for i in range(len(sorted_months)):
        for j in range(i + 1, len(sorted_months)):
            for k in range(j + 1, len(sorted_months)):
                triplets.append((sorted_months[i], sorted_months[j], sorted_months[k]))

    return triplets


def find_fly_candidates_for_triplet(
    month1: str,
    month2: str,
    month3: str,
    month_groups: dict[str, list[Trade]],
    month_qty_lookups: dict[str, dict[Decimal, list[Trade]]],
) -> list[list[Trade]]:
    """Find fly candidates for a specific month triplet using optimized lookups.

    Args:
        month1: Earliest month in triplet
        month2: Middle month in triplet
        month3: Latest month in triplet
        month_groups: Trades grouped by month
        month_qty_lookups: Quantity lookup indexes

    Returns:
        List of 3-trade fly candidate groups for this triplet
    """
    candidates = []

    # Iterate through outer legs to find matching middle leg - O(n1 * n3)
    for outer1_trade in month_groups[month1]:
        for outer2_trade in month_groups[month3]:
            required_middle_qty = outer1_trade.quantity_mt + outer2_trade.quantity_mt

            # O(1) lookup for middle leg trades with required quantity
            if required_middle_qty in month_qty_lookups[month2]:
                for middle_trade in month_qty_lookups[month2][required_middle_qty]:
                    candidate = [outer1_trade, middle_trade, outer2_trade]
                    candidates.append(candidate)

    return candidates
