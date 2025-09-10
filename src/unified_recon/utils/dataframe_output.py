"""DataFrame output utilities for unified reconciliation system."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import json
import re
from pathlib import Path

from ..models import ReconStatus


def create_unified_dataframe(unified_result: Any) -> pd.DataFrame:
    """
    Create standardized DataFrame from aggregated reconciliation results.

    Args:
        unified_result: UnifiedResult object from ResultAggregator

    Returns:
        DataFrame with columns: matchId, traderTradeIds, exchangeTradeIds,
        status, remarks, confidence
    """
    records = []

    # Process each system's results
    if hasattr(unified_result, "system_results"):
        for system_result in unified_result.system_results:
            # Get system name without _match suffix
            system_name = system_result.system_name.upper().replace("_MATCH", "")

            # Process matched trades (even if detailed_results is empty, we still need to process unmatched)
            if isinstance(system_result.detailed_results, dict):
                matches = system_result.detailed_results.get("matches", [])
            elif isinstance(system_result.detailed_results, list):
                # If it's a list, it might be the matches directly
                matches = system_result.detailed_results
            else:
                matches = []

            for match in matches:
                # Normalize match to dictionary format
                match_dict = _normalize_to_dict(match)

                # Extract trade IDs
                trader_ids = _extract_trade_ids(match_dict, "trader")
                exchange_ids = _extract_trade_ids(match_dict, "exchange")

                record = {
                    "matchId": match_dict.get("match_id", ""),
                    "traderTradeIds": trader_ids,
                    "exchangeTradeIds": exchange_ids,
                    "status": match_dict.get("status", ReconStatus.MATCHED.value),
                    "remarks": f"{system_name}_rule{match_dict.get('rule_order', 1)}",
                    "confidence": float(match_dict.get("confidence", 0)),
                }
                records.append(record)

            # Process unmatched trader trades
            # The unmatched trades are stored in statistics (which contains the full result dict)
            unmatched_traders = []
            if hasattr(system_result, "statistics") and isinstance(
                system_result.statistics, dict
            ):
                unmatched_traders = system_result.statistics.get(
                    "unmatched_trader_trades", []
                )

            for trade in unmatched_traders:
                # Normalize trade to dictionary format
                trade_dict = _normalize_to_dict(trade)
                trade_id = _convert_to_number(trade_dict.get("internal_trade_id", ""))

                record = {
                    "matchId": None,
                    "traderTradeIds": [trade_id] if trade_id is not None else [],
                    "exchangeTradeIds": [],
                    "status": ReconStatus.UNMATCHED_TRADERS.value,
                    "remarks": f"{system_name}_unmatched_trader",
                    "confidence": 0.0,
                }
                records.append(record)

            # Process unmatched exchange trades
            # The unmatched trades are stored in statistics (which contains the full result dict)
            unmatched_exchange = []
            if hasattr(system_result, "statistics") and isinstance(
                system_result.statistics, dict
            ):
                unmatched_exchange = system_result.statistics.get(
                    "unmatched_exchange_trades", []
                )

            for trade in unmatched_exchange:
                # Normalize trade to dictionary format
                trade_dict = _normalize_to_dict(trade)
                trade_id = _convert_to_number(trade_dict.get("internal_trade_id", ""))

                record = {
                    "matchId": None,
                    "traderTradeIds": [],
                    "exchangeTradeIds": [trade_id] if trade_id is not None else [],
                    "status": ReconStatus.UNMATCHED_EXCH.value,
                    "remarks": f"{system_name}_unmatched_exchange",
                    "confidence": 0.0,
                }
                records.append(record)

    # Create DataFrame
    df = pd.DataFrame(records)

    # Ensure all columns exist even if empty
    required_columns = [
        "matchId",
        "traderTradeIds",
        "exchangeTradeIds",
        "status",
        "remarks",
        "confidence",
    ]

    for col in required_columns:
        if col not in df.columns:
            if col in ["traderTradeIds", "exchangeTradeIds"]:
                df[col] = [[] for _ in range(len(df))]
            else:
                df[col] = None

    # Ensure proper column order
    return (
        df[required_columns] if not df.empty else pd.DataFrame(columns=required_columns)
    )


def _normalize_to_dict(item: Any) -> Dict[str, Any]:
    """
    Normalize an item (object or dict) to dictionary format.

    Args:
        item: Object with attributes or dictionary

    Returns:
        Dictionary representation of the item
    """
    if isinstance(item, dict):
        return item

    # Convert object to dictionary
    result = {}

    # Handle standard fields
    for field in [
        "match_id",
        "rule_order",
        "confidence",
        "internal_trade_id",
        "status",
    ]:
        if hasattr(item, field):
            result[field] = getattr(item, field)

    # Handle nested trade objects
    for trade_type in ["trader", "exchange"]:
        # Primary trade
        primary_attr = f"{trade_type}_trade"
        if hasattr(item, primary_attr):
            primary_trade = getattr(item, primary_attr)
            if primary_trade:
                result[primary_attr] = _normalize_to_dict(primary_trade)

        # Additional trades
        additional_attr = f"additional_{trade_type}_trades"
        if hasattr(item, additional_attr):
            additional_trades = getattr(item, additional_attr, [])
            if additional_trades:
                result[additional_attr] = [
                    _normalize_to_dict(t) for t in additional_trades
                ]

    return result


def _extract_trade_ids(data: Dict, trade_type: str) -> List[int]:
    """
    Extract and convert trade IDs to numbers from a normalized dictionary.

    Args:
        data: Dictionary (could be a match dict with nested trades, or a simple trade dict)
        trade_type: "trader" or "exchange"

    Returns:
        List of trade IDs as numbers
    """
    trade_ids = []

    # Check if this is a simple trade dict with internal_trade_id directly
    if "internal_trade_id" in data and trade_type not in ["trader", "exchange"]:
        # This shouldn't happen in normal flow, but handle gracefully
        trade_id = _convert_to_number(data["internal_trade_id"])
        if trade_id is not None:
            return [trade_id]

    # Handle nested trade structure (for match objects)
    primary_key = f"{trade_type}_trade"
    if primary_key in data:
        primary_trade = data[primary_key]
        if isinstance(primary_trade, dict) and "internal_trade_id" in primary_trade:
            trade_id = _convert_to_number(primary_trade["internal_trade_id"])
            if trade_id is not None:
                trade_ids.append(trade_id)

    # Get additional trade IDs
    additional_key = f"additional_{trade_type}_trades"
    if additional_key in data:
        additional_trades = data[additional_key]
        if isinstance(additional_trades, list):
            for trade in additional_trades:
                if isinstance(trade, dict) and "internal_trade_id" in trade:
                    trade_id = _convert_to_number(trade["internal_trade_id"])
                    if trade_id is not None:
                        trade_ids.append(trade_id)

    return trade_ids


def _convert_to_number(trade_id: Any) -> Optional[int]:
    """
    Convert trade ID to number if possible.
    Handles numeric strings and integers.

    Args:
        trade_id: Trade ID (string or number)

    Returns:
        Integer trade ID or None if conversion fails
    """
    if trade_id is None:
        return None

    try:
        # Try direct conversion to integer
        return int(trade_id)
    except (ValueError, TypeError):
        # If conversion fails, try extracting numbers from string
        trade_id_str = str(trade_id)
        match = re.search(r"\d+", trade_id_str)
        if match:
            return int(match.group())
        return None


def save_dataframe_to_json(
    df: pd.DataFrame, output_path: Optional[Path] = None, filename: Optional[str] = None
) -> Path:
    """
    Save DataFrame to JSON file in json_output directory.

    Args:
        df: DataFrame to save
        output_path: Optional output directory path
        filename: Optional filename (defaults to timestamp)

    Returns:
        Path to saved JSON file
    """
    # Default output directory at root level (not under src/)
    if output_path is None:
        output_path = Path("json_output")

    # Ensure directory exists
    output_path.mkdir(parents=True, exist_ok=True)

    # Default filename with timestamp
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"unified_recon_output_{timestamp}.json"

    # Full file path
    file_path = output_path / filename

    # Convert DataFrame to records format for JSON
    json_data = df.to_dict(orient="records")

    # Save to JSON file with UTF-8 encoding and preserve Unicode characters
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, default=str, ensure_ascii=False)

    return file_path


def display_dataframe_summary(df: pd.DataFrame) -> None:
    """
    Display a summary of the DataFrame.

    Args:
        df: DataFrame to summarize
    """
    if df.empty:
        print("\n📊 DataFrame: No data to display")
        return

    print("\n📊 Reconciliation DataFrame Summary")
    print("=" * 50)
    print(f"Total Records: {len(df)}")

    # Count by status
    status_counts = df["status"].value_counts()
    for status, count in status_counts.items():
        percentage = (count / len(df)) * 100
        print(f"  {status}: {count} ({percentage:.1f}%)")

    # Average confidence for matched and pending trades
    matched_statuses = [ReconStatus.MATCHED.value, ReconStatus.PENDING_EXCHANGE.value]
    matched_df = df[df["status"].isin(matched_statuses)]
    if not matched_df.empty:
        avg_confidence = matched_df["confidence"].mean()
        print(f"\nAverage Match Confidence: {avg_confidence:.1f}%")

    print("=" * 50)
