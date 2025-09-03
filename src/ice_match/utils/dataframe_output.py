"""DataFrame output utilities for standardized reconciliation reporting."""

from datetime import datetime
from typing import List
from decimal import Decimal
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

from ..models import MatchResult, ReconStatus
from ..core import UnmatchedPoolManager


def get_primary_product_name(match_result: MatchResult) -> str:
    """Extract primary product name, handling spreads and cracks."""
    primary_product = match_result.trader_trade.product_name

    # Handle spread/crack display names by extracting the base product
    if "/" in primary_product:
        # For spreads like "marine 0.5%/380cst", take the first product
        return primary_product.split("/")[0].strip()

    return primary_product


def get_primary_contract_month(match_result: MatchResult) -> str:
    """Extract primary contract month from match result."""
    return match_result.trader_trade.contract_month


def get_primary_price(match_result: MatchResult) -> Decimal:
    """Extract primary price from match result."""
    return match_result.trader_trade.price


def get_total_quantity(match_result: MatchResult) -> Decimal:
    """Calculate appropriate quantity for match result.
    
    For spread matches, returns the quantity of one leg (since both legs represent the same spread size).
    For aggregation matches, returns the sum of all quantities.
    """
    from ..models import MatchType

    # For spread-type matches, return quantity of primary leg only (avoid double-counting)
    if match_result.match_type in [
        MatchType.SPREAD,
        MatchType.PRODUCT_SPREAD,
        MatchType.AGGREGATED_SPREAD,
        MatchType.AGGREGATED_PRODUCT_SPREAD
    ]:
        return match_result.trader_trade.quantity_mt

    # For aggregation matches and others, sum all quantities
    total = match_result.trader_trade.quantity_mt
    for trade in match_result.additional_trader_trades:
        total += trade.quantity_mt

    return total


def create_reconciliation_dataframe(
    matches: List[MatchResult],
    unmatched_pool: UnmatchedPoolManager,
    execution_time: datetime
) -> pd.DataFrame:
    """Create standardized reconciliation DataFrame for all matches and unmatched trades."""

    records = []

    # Process matched trades
    for i, match in enumerate(matches, 1):
        # Collect all trader and exchange trade IDs
        trader_ids = [match.trader_trade.trade_id]
        trader_ids.extend([t.trade_id for t in match.additional_trader_trades])

        exchange_ids = [match.exchange_trade.trade_id]
        exchange_ids.extend([t.trade_id for t in match.additional_exchange_trades])

        # All matches are now MATCHED status
        recon_status = ReconStatus.MATCHED

        record = {
            'reconid': f"RECON_{i:06d}",
            'source_traders_id': trader_ids,
            'source_exch_id': exchange_ids,
            'reconStatus': recon_status.value,
            'recon_run_datetime': execution_time,
            'remarks': f"ICE_rule{match.rule_order}",
            'confidence_score': float(match.confidence),
            'quantity': float(get_total_quantity(match)),
            'price': float(get_primary_price(match)),
            'contract_month': get_primary_contract_month(match),
            'product_name': get_primary_product_name(match),
            'match_id': match.match_id
        }
        records.append(record)

    # Process unmatched trader trades
    unmatched_traders = unmatched_pool.get_unmatched_trader_trades()
    for i, trade in enumerate(unmatched_traders, len(matches) + 1):
        record = {
            'reconid': f"RECON_{i:06d}",
            'source_traders_id': [trade.trade_id],
            'source_exch_id': [],
            'reconStatus': ReconStatus.UNMATCHED_TRADERS.value,
            'recon_run_datetime': execution_time,
            'remarks': "ICE_unmatched_trader",
            'confidence_score': 0.0,
            'quantity': float(trade.quantity_mt),
            'price': float(trade.price),
            'contract_month': trade.contract_month,
            'product_name': trade.product_name,
            'match_id': None
        }
        records.append(record)

    # Process unmatched exchange trades
    unmatched_exchanges = unmatched_pool.get_unmatched_exchange_trades()
    for i, trade in enumerate(unmatched_exchanges, len(matches) + len(unmatched_traders) + 1):
        record = {
            'reconid': f"RECON_{i:06d}",
            'source_traders_id': [],
            'source_exch_id': [trade.trade_id],
            'reconStatus': ReconStatus.UNMATCHED_EXCH.value,
            'recon_run_datetime': execution_time,
            'remarks': "ICE_unmatched_exchange",
            'confidence_score': 0.0,
            'quantity': float(trade.quantity_mt),
            'price': float(trade.price),
            'contract_month': trade.contract_month,
            'product_name': trade.product_name,
            'match_id': None
        }
        records.append(record)

    # Create DataFrame
    df = pd.DataFrame(records)

    # Ensure proper column order
    column_order = [
        'reconid', 'source_traders_id', 'source_exch_id', 'reconStatus',
        'recon_run_datetime', 'remarks', 'confidence_score', 'quantity', 'price',
        'contract_month', 'product_name', 'match_id'
    ]

    return df[column_order] if not df.empty else pd.DataFrame(columns=column_order)


def display_reconciliation_dataframe(df: pd.DataFrame) -> None:
    """Display the reconciliation DataFrame with beautiful RICH formatting."""
    if df.empty:
        console = Console()
        console.print("\n📊 Reconciliation DataFrame: No data to display", style="yellow")
        return

    console = Console()

    # Create header
    console.print(f"\n📊 Standardized Reconciliation DataFrame ({len(df)} records)",
                 style="bold cyan", justify="center")
    console.print("=" * 100, style="cyan")

    # Create Rich table
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")

    # Add columns with appropriate styling
    table.add_column("ReconID", style="green", width=12)
    table.add_column("Trader IDs", style="blue", width=12)
    table.add_column("Exchange IDs", style="purple", width=12)
    table.add_column("Status", style="bold", width=10)
    table.add_column("Remarks", style="magenta", width=15)
    table.add_column("Confidence", style="yellow", width=8, justify="right")
    table.add_column("Quantity", style="cyan", width=8, justify="right")
    table.add_column("Price", style="bright_green", width=8, justify="right")
    table.add_column("Month", style="white", width=8)
    table.add_column("Product", style="green", width=15)
    table.add_column("Match ID", style="bright_cyan", width=15)

    # Add rows with color coding based on status
    for _, row in df.iterrows():  # Show ALL rows including unmatched
        # Format trader IDs
        trader_ids = str(row['source_traders_id'])[:12] + "..." if len(str(row['source_traders_id'])) > 15 else str(row['source_traders_id'])
        trader_ids = trader_ids.replace("'", "").replace("[", "").replace("]", "")

        # Format exchange IDs
        exch_ids = str(row['source_exch_id'])[:12] + "..." if len(str(row['source_exch_id'])) > 15 else str(row['source_exch_id'])
        exch_ids = exch_ids.replace("'", "").replace("[", "").replace("]", "")

        # Color code status
        status = row['reconStatus']
        if status == 'matched':
            status_text = Text(status, style="bold green")
        elif status == 'unmatched_traders':
            status_text = Text(status, style="bold red")
        elif status == 'unmatched_exch':
            status_text = Text(status, style="bold bright_yellow")
        elif status == 'pending_exchange':
            status_text = Text(status, style="bold cyan")
        elif status == 'pending_approval':
            status_text = Text(status, style="bold magenta")
        else:
            status_text = Text(status, style="white")

        # Format other fields
        confidence = f"{row['confidence_score']:.1f}%" if row['confidence_score'] > 0 else "N/A"
        quantity = f"{row['quantity']:,.0f}"
        price = f"{row['price']:,.2f}" if pd.notna(row['price']) else "N/A"
        product = str(row['product_name'])[:13] + "..." if len(str(row['product_name'])) > 15 else str(row['product_name'])
        remarks = str(row['remarks'])[:13] + "..." if len(str(row['remarks'])) > 15 else str(row['remarks'])
        match_id = str(row['match_id']) if pd.notna(row['match_id']) else "N/A"
        if len(match_id) > 15:
            match_id = match_id[:13] + "..."

        table.add_row(
            row['reconid'],
            trader_ids,
            exch_ids,
            status_text,
            remarks,
            confidence,
            quantity,
            price,
            row['contract_month'],
            product,
            match_id
        )

    console.print(table)

    # Show summary with Rich styling
    console.print("\n📈 Reconciliation Summary", style="bold cyan")
    summary_table = Table(box=box.SIMPLE, show_header=False)
    summary_table.add_column("Metric", style="white")
    summary_table.add_column("Count", style="bold white", justify="right")
    summary_table.add_column("Percentage", style="green", justify="right")

    total = len(df)
    matched = len(df[df['reconStatus'] == 'matched'])
    unmatched_traders = len(df[df['reconStatus'] == 'unmatched_traders'])
    unmatched_exch = len(df[df['reconStatus'] == 'unmatched_exch'])
    pending_exchange = len(df[df['reconStatus'] == 'pending_exchange'])
    pending_approval = len(df[df['reconStatus'] == 'pending_approval'])

    summary_table.add_row("Total Records", str(total), "100.0%")
    summary_table.add_row("✅ Matched", str(matched), f"{matched/total*100:.1f}%" if total > 0 else "0.0%")
    summary_table.add_row("❌ Unmatched Traders", str(unmatched_traders), f"{unmatched_traders/total*100:.1f}%" if total > 0 else "0.0%")
    summary_table.add_row("❌ Unmatched Exchange", str(unmatched_exch), f"{unmatched_exch/total*100:.1f}%" if total > 0 else "0.0%")
    if pending_exchange > 0:
        summary_table.add_row("⏳ Pending Exchange", str(pending_exchange), f"{pending_exchange/total*100:.1f}%")
    if pending_approval > 0:
        summary_table.add_row("📝 Pending Approval", str(pending_approval), f"{pending_approval/total*100:.1f}%")

    console.print(summary_table)

    console.print(f"\n[green]✅ Showing all {len(df)} records (matched + unmatched)[/green]")
