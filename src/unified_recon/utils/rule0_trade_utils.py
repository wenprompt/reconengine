"""Trade matching utilities for Rule 0."""

from typing import Any, Optional


def determine_tolerance(unit: str, tolerances: dict[str, float]) -> float:
    """Determine tolerance based on unit and available tolerances.

    Args:
        unit: Trade unit (BBL, MT, LOTS, etc.)
        tolerances: Dictionary of tolerance values

    Returns:
        Appropriate tolerance value
    """
    if not tolerances:
        return 0.0

    unit_upper = unit.upper()

    # Check for unit-specific tolerance
    if unit_upper == "BBL" and "tolerance_bbl" in tolerances:
        return tolerances.get("tolerance_bbl", 0)
    elif unit_upper == "MT" and "tolerance_mt" in tolerances:
        return tolerances.get("tolerance_mt", 0)
    elif unit_upper == "LOTS" and "tolerance_lots" in tolerances:
        return tolerances.get("tolerance_lots", 0)

    # Fallback to default tolerances
    if "tolerance_default" in tolerances:
        return tolerances.get("tolerance_default", 0)
    elif "tolerance" in tolerances:
        return tolerances.get("tolerance", 0)

    return 0.0


def find_best_match(
    trader_trade: dict[str, Any],
    exchange_trades: list[dict[str, Any]],
    tolerance: float,
) -> Optional[dict[str, Any]]:
    """Find best matching exchange trade for a trader trade.

    Args:
        trader_trade: Trader trade to match
        exchange_trades: List of exchange trades
        tolerance: Quantity tolerance for matching

    Returns:
        Best matching exchange trade or None
    """
    best_match = None
    best_difference = float("inf")

    t_qty = trader_trade.get("quantity", 0)
    t_broker = trader_trade.get("broker_group_id", "")
    t_clearing = trader_trade.get("exch_clearing_acct_id", "")

    for e_trade in exchange_trades:
        if e_trade.get("matched", False):
            continue

        e_qty = e_trade.get("quantity", 0)

        # Check matching criteria
        if not matches_criteria(
            t_qty,
            e_qty,
            t_broker,
            e_trade.get("broker_group_id", ""),
            t_clearing,
            e_trade.get("exch_clearing_acct_id", ""),
        ):
            continue

        qty_difference = abs(abs(t_qty) - abs(e_qty))

        if qty_difference <= tolerance and qty_difference < best_difference:
            best_match = e_trade
            best_difference = qty_difference

    return best_match


def matches_criteria(
    t_qty: float,
    e_qty: float,
    t_broker: str,
    e_broker: str,
    t_clearing: str,
    e_clearing: str,
) -> bool:
    """Check if trades match on required criteria.

    Args:
        t_qty: Trader quantity
        e_qty: Exchange quantity
        t_broker: Trader broker group ID
        e_broker: Exchange broker group ID
        t_clearing: Trader clearing account ID
        e_clearing: Exchange clearing account ID

    Returns:
        True if trades match criteria
    """
    # Same sign (both buy or both sell)
    if t_qty * e_qty <= 0:
        return False

    # Same broker group
    if t_broker != e_broker:
        return False

    # Same clearing account
    if t_clearing != e_clearing:
        return False

    return True


def generate_match_id(trader_id: str, exchange_id: str) -> str:
    """Generate match ID for matched trades.

    Args:
        trader_id: Trader trade ID
        exchange_id: Exchange trade ID

    Returns:
        Match ID string
    """
    t_id = trader_id if trader_id else "NA"
    e_id = exchange_id if exchange_id else "NA"
    return f"M_{t_id}_{e_id}"


def apply_match(
    trader_trade: dict[str, Any], exchange_trade: dict[str, Any], match_id: str
) -> None:
    """Apply match to both trades.

    Args:
        trader_trade: Trader trade to mark as matched
        exchange_trade: Exchange trade to mark as matched
        match_id: Match ID to apply
    """
    trader_trade["matched"] = True
    trader_trade["match_id"] = match_id
    exchange_trade["matched"] = True
    exchange_trade["match_id"] = match_id


def create_match_id_mapping(
    reconciliation_results: list[dict[str, Any]],
) -> dict[str, str]:
    """Create a mapping from internal trade IDs to reconciliation match IDs.

    Args:
        reconciliation_results: List of reconciliation results from the matching engine

    Returns:
        Dictionary mapping internal trade IDs to match IDs
    """
    mapping: dict[str, str] = {}

    for result in reconciliation_results:
        match_id = result.get("matchId")
        if not match_id:
            continue

        # Map trader trade IDs (prefix with T_)
        trader_ids = result.get("traderTradeIds", [])
        for t_id in trader_ids:
            if t_id:
                mapping[f"T_{t_id}"] = match_id

        # Map exchange trade IDs (prefix with E_)
        exchange_ids = result.get("exchangeTradeIds", [])
        for e_id in exchange_ids:
            if e_id:
                mapping[f"E_{e_id}"] = match_id

    return mapping


def reset_match_status(trades: list[dict[str, Any]]) -> None:
    """Reset match status for all trades.

    Args:
        trades: List of trades to reset
    """
    for trade in trades:
        trade["matched"] = False
        trade["match_id"] = ""


def determine_trade_type(original_product: str, spread_flag: str) -> str:
    """Determine trade type based on product and flags.

    Args:
        original_product: Original product name
        spread_flag: Spread flag indicator

    Returns:
        Trade type (Crack, PS, S, or empty)
    """
    if original_product:
        if "crack" in original_product.lower():
            return "Crack"
        elif "-" in original_product:
            return "PS"
        else:
            return ""
    elif spread_flag == "S":
        return "S"
    else:
        return ""
