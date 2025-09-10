"""Rich CLI display for ice trade matching results."""

from decimal import Decimal
from typing import List, Dict, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.align import Align
from rich import box

from ..models import MatchResult, Trade
from ..core import UnmatchedPoolManager
from ..config import ConfigManager


class MatchDisplayer:
    """Rich CLI display for ice trade matching results.

    Provides comprehensive, colored display of matches, unmatched trades,
    statistics, and configuration information.
    """

    def __init__(self, config_manager: ConfigManager):
        """Initialize the display manager.

        Args:
            config_manager: Configuration manager for display settings
        """
        self.config_manager = config_manager
        self.console = Console()

    def _format_confidence(self, confidence: Decimal) -> str:
        """Format confidence percentage with color based on value.

        Args:
            confidence: Confidence percentage (0-100)

        Returns:
            Formatted confidence string with color
        """
        confidence_str = f"{confidence}%"
        if confidence >= 90:
            return f"[green]{confidence_str}[/green]"
        elif confidence >= 70:
            return f"[yellow]{confidence_str}[/yellow]"
        else:
            return f"[red]{confidence_str}[/red]"

    def _format_side(self, buy_sell: str) -> str:
        """Format buy/sell side with appropriate color.

        Args:
            buy_sell: "B" for buy or "S" for sell

        Returns:
            Formatted side string with color
        """
        if buy_sell == "B":
            return f"[green]{buy_sell}[/green]"
        else:
            return f"[red]{buy_sell}[/red]"

    def _format_match_rate(self, rate_str: str) -> str:
        """Format match rate percentage with color based on value.

        Args:
            rate_str: Match rate string with % sign

        Returns:
            Formatted rate string with color
        """
        if "%" not in rate_str:
            return rate_str

        rate_value = float(rate_str.replace("%", ""))
        if rate_value >= 80:
            return f"[green]{rate_str}[/green]"
        elif rate_value >= 60:
            return f"[yellow]{rate_str}[/yellow]"
        else:
            return f"[red]{rate_str}[/red]"

    def show_header(self):
        """Display application header."""
        header_text = Text("🔋 ICE Trade Matching System", style="bold blue")
        header_panel = Panel(Align.center(header_text), box=box.DOUBLE, style="blue")
        self.console.print(header_panel)
        self.console.print()

    def show_configuration(self):
        """Display current configuration summary."""
        config_summary = self.config_manager.get_summary()

        config_table = Table(title="⚙️  Configuration", box=box.ROUNDED)
        config_table.add_column("Setting", style="cyan", no_wrap=True)
        config_table.add_column("Value", style="white")

        config_table.add_row("Quantity Tolerance (MT)", "150")
        config_table.add_row("Rule Count", str(config_summary["rule_count"]))
        config_table.add_row("Output Format", config_summary["output_format"])
        config_table.add_row("Log Level", config_summary["log_level"])

        self.console.print(config_table)
        self.console.print()

    def show_data_summary(self, trader_count: int, exchange_count: int):
        """Display data loading summary.

        Args:
            trader_count: Number of trader trades loaded
            exchange_count: Number of exchange trades loaded
        """
        data_table = Table(title="📊 Data Summary", box=box.ROUNDED)
        data_table.add_column("Source", style="cyan", no_wrap=True)
        data_table.add_column("Count", justify="right", style="white")

        data_table.add_row("Trader Trades", str(trader_count))
        data_table.add_row("Exchange Trades", str(exchange_count))
        data_table.add_row(
            "[bold]Total[/bold]", f"[bold]{trader_count + exchange_count}[/bold]"
        )

        self.console.print(data_table)
        self.console.print()

    def show_matches_by_type(self, matches: List[MatchResult]):
        """Display matches grouped by matching type.

        Args:
            matches: List of all matches found
        """
        if not matches:
            self.console.print("[yellow]ℹ️  No matches found[/yellow]")
            return

        # Group matches by type
        matches_by_type: Dict[str, List[MatchResult]] = {}
        for match in matches:
            match_type = match.match_type.value
            if match_type not in matches_by_type:
                matches_by_type[match_type] = []
            matches_by_type[match_type].append(match)

        # Display each match type
        for match_type, type_matches in matches_by_type.items():
            self._show_match_type_section(match_type, type_matches)

    def _show_match_type_section(self, match_type: str, matches: List[MatchResult]):
        """Display matches for a specific match type.

        Args:
            match_type: Type of matches to display
            matches: List of matches of this type
        """
        # Create title with match count
        title = f"✅ {match_type.replace('_', ' ').title()} Matches ({len(matches)})"

        match_table = Table(title=title, box=box.ROUNDED, width=160)
        match_table.add_column("Match ID", style="cyan", no_wrap=True, width=14)
        match_table.add_column("Trade ID (T)", style="green", no_wrap=True, width=18)
        match_table.add_column("Trade ID (E)", style="blue", no_wrap=True, width=18)
        match_table.add_column("Product", style="white", width=14)
        match_table.add_column("Qty (MT)", justify="right", style="white", width=10)
        match_table.add_column("Price", justify="right", style="white", width=8)
        match_table.add_column("Contract", style="white", width=18)
        match_table.add_column("Sides", style="white", width=8)
        match_table.add_column("Status", style="yellow", width=10)
        match_table.add_column("Conf", justify="right", style="white", width=6)

        for match in matches:
            # Check if this is a spread match (has additional trades)
            if match.is_multi_leg_match:
                # For multi-leg matches, show all legs
                all_trader_trades = match.all_trader_trades
                all_exchange_trades = match.all_exchange_trades

                # Format trader IDs (show all trades)
                trader_ids = " + ".join(
                    [trade.internal_trade_id for trade in all_trader_trades]
                )

                # Format exchange IDs (show all trades)
                exchange_ids = " + ".join(
                    [trade.internal_trade_id for trade in all_exchange_trades]
                )

                # Format contract months (show all legs)
                trader_months = sorted(
                    set(trade.contract_month for trade in all_trader_trades)
                )
                contract_display = "/".join(trader_months)

                # Format sides (show all combinations)
                trader_sides = [trade.buy_sell for trade in all_trader_trades]
                exchange_sides = [trade.buy_sell for trade in all_exchange_trades]
                sides = f"{'/'.join(trader_sides)}↔{'/'.join(exchange_sides)}"

                # Use primary trade for product, quantity, price (assuming primary trade is representative)
                primary_trade = match.trader_trade

            else:
                # For single-leg matches, show single trade
                trader_ids = match.trader_trade.internal_trade_id
                exchange_ids = match.exchange_trade.internal_trade_id
                contract_display = match.trader_trade.contract_month
                sides = f"{match.trader_trade.buy_sell}↔{match.exchange_trade.buy_sell}"
                primary_trade = match.trader_trade

            # Format confidence using helper method
            confidence_str = self._format_confidence(match.confidence)

            match_table.add_row(
                match.match_id,
                trader_ids,
                exchange_ids,
                primary_trade.product_name,
                f"{primary_trade.quantity_mt:,.0f}",
                f"{primary_trade.price:,.2f}",
                contract_display,
                sides,
                match.status.value.title() if match.status else "Matched",
                confidence_str,
            )

        self.console.print(match_table)
        self.console.print()

    def show_unmatched_summary(self, pool_manager: UnmatchedPoolManager):
        """Display summary of unmatched trades.

        Args:
            pool_manager: Pool manager with unmatched trade information
        """
        trader_unmatched = pool_manager.get_unmatched_trader_trades()
        exchange_unmatched = pool_manager.get_unmatched_exchange_trades()

        if not trader_unmatched and not exchange_unmatched:
            self.console.print("[green]🎉 All trades matched![/green]")
            return

        # Summary table
        unmatched_table = Table(title="❌ Unmatched Trades Summary", box=box.ROUNDED)
        unmatched_table.add_column("Source", style="cyan", no_wrap=True)
        unmatched_table.add_column("Count", justify="right", style="white")
        unmatched_table.add_column("Sample Products", style="white")

        # Trader unmatched
        trader_products = list(
            set(trade.product_name for trade in trader_unmatched[:5])
        )
        trader_sample = ", ".join(trader_products[:3])
        if len(trader_products) > 3:
            trader_sample += f" (+{len(trader_products) - 3} more)"

        unmatched_table.add_row(
            "Trader",
            str(len(trader_unmatched)),
            trader_sample if trader_unmatched else "None",
        )

        # Exchange unmatched
        exchange_products = list(
            set(trade.product_name for trade in exchange_unmatched[:5])
        )
        exchange_sample = ", ".join(exchange_products[:3])
        if len(exchange_products) > 3:
            exchange_sample += f" (+{len(exchange_products) - 3} more)"

        unmatched_table.add_row(
            "Exchange",
            str(len(exchange_unmatched)),
            exchange_sample if exchange_unmatched else "None",
        )

        self.console.print(unmatched_table)
        self.console.print()

    def show_detailed_unmatched(
        self, pool_manager: UnmatchedPoolManager, limit: Optional[int] = None
    ):
        """Display detailed unmatched trades.

        Args:
            pool_manager: Pool manager with unmatched trades
            limit: Maximum number of trades to show per source (None for all)
        """
        trader_unmatched = pool_manager.get_unmatched_trader_trades()
        exchange_unmatched = pool_manager.get_unmatched_exchange_trades()

        # Show trader unmatched
        if trader_unmatched:
            trades_to_show = (
                trader_unmatched if limit is None else trader_unmatched[:limit]
            )
            self._show_unmatched_trades("Trader", trades_to_show)

        # Show exchange unmatched
        if exchange_unmatched:
            trades_to_show = (
                exchange_unmatched if limit is None else exchange_unmatched[:limit]
            )
            self._show_unmatched_trades("Exchange", trades_to_show)

    def _show_unmatched_trades(self, source: str, trades: List[Trade]):
        """Display unmatched trades for a specific source.

        Args:
            source: Source name (Trader or Exchange)
            trades: List of unmatched trades
        """
        title = f"📋 Unmatched {source} Trades ({len(trades)})"

        trade_table = Table(title=title, box=box.ROUNDED)
        trade_table.add_column("Trade ID", style="cyan", no_wrap=True)
        trade_table.add_column("Product", style="white")
        trade_table.add_column("Quantity", justify="right", style="white")
        trade_table.add_column("Unit", style="white")
        trade_table.add_column("Price", justify="right", style="white")
        trade_table.add_column("Contract", style="white")
        trade_table.add_column("Side", style="white")
        trade_table.add_column("Broker", justify="right", style="white")

        for trade in trades:
            # Format side using helper method
            side_str = self._format_side(trade.buy_sell)

            trade_table.add_row(
                trade.internal_trade_id,
                trade.product_name,
                f"{trade.quantityunit:,.0f}",
                trade.unit.upper(),
                f"{trade.price:,.2f}",
                trade.contract_month,
                side_str,
                str(trade.broker_group_id) if trade.broker_group_id else "N/A",
            )

        self.console.print(trade_table)
        self.console.print()

    def show_statistics(
        self, pool_manager: UnmatchedPoolManager, matches: List[MatchResult]
    ):
        """Display comprehensive matching statistics.

        Args:
            pool_manager: Pool manager with trade statistics
            matches: List of all matches found
        """
        stats = pool_manager.get_statistics()

        # Overall statistics
        stats_table = Table(title="📈 Matching Statistics", box=box.ROUNDED)
        stats_table.add_column("Metric", style="cyan", no_wrap=True)
        stats_table.add_column("Value", justify="right", style="white")

        stats_table.add_row("Total Trades Loaded", str(stats["original"]["total"]))
        stats_table.add_row("├─ Trader Trades", str(stats["original"]["trader"]))
        stats_table.add_row("└─ Exchange Trades", str(stats["original"]["exchange"]))
        stats_table.add_row("", "")  # Spacer

        stats_table.add_row("Total Trades Matched", str(stats["matched"]["total"]))
        stats_table.add_row("├─ Trader Trades", str(stats["matched"]["trader"]))
        stats_table.add_row("└─ Exchange Trades", str(stats["matched"]["exchange"]))
        stats_table.add_row("Match Pairs Created", str(stats["matched"]["pairs"]))
        stats_table.add_row("", "")  # Spacer

        stats_table.add_row("Total Trades Unmatched", str(stats["unmatched"]["total"]))
        stats_table.add_row("├─ Trader Trades", str(stats["unmatched"]["trader"]))
        stats_table.add_row("└─ Exchange Trades", str(stats["unmatched"]["exchange"]))
        stats_table.add_row("", "")  # Spacer

        # Format match rate using helper method
        overall_rate = self._format_match_rate(stats["match_rates"]["overall"])

        stats_table.add_row("Overall Match Rate", overall_rate)
        stats_table.add_row("├─ Trader Match Rate", stats["match_rates"]["trader"])
        stats_table.add_row("└─ Exchange Match Rate", stats["match_rates"]["exchange"])

        self.console.print(stats_table)

        # Matches by rule type
        if stats["matches_by_rule"]:
            rule_table = Table(title="📋 Matches by Rule Type", box=box.ROUNDED)
            rule_table.add_column("Rule Type", style="cyan")
            rule_table.add_column("Count", justify="right", style="white")
            rule_table.add_column("Percentage", justify="right", style="white")

            total_matches = sum(stats["matches_by_rule"].values())
            for rule_type, count in stats["matches_by_rule"].items():
                percentage = (count / total_matches * 100) if total_matches > 0 else 0
                rule_table.add_row(
                    rule_type.replace("_", " ").title(),
                    str(count),
                    f"{percentage:.1f}%",
                )

            self.console.print()
            self.console.print(rule_table)

        self.console.print()

    def show_processing_complete(self, processing_time: float):
        """Display processing completion message.

        Args:
            processing_time: Time taken for processing in seconds
        """
        completion_text = Text(
            f"✅ Processing completed in {processing_time:.2f} seconds",
            style="bold green",
        )
        completion_panel = Panel(
            Align.center(completion_text), box=box.ROUNDED, style="green"
        )
        self.console.print(completion_panel)

    def show_error(self, error_message: str):
        """Display error message.

        Args:
            error_message: Error message to display
        """
        error_text = Text(f"❌ Error: {error_message}", style="bold red")
        error_panel = Panel(error_text, box=box.ROUNDED, style="red", title="Error")
        self.console.print(error_panel)

    def create_progress_context(self, description: str):
        """Create a progress context for long-running operations.

        Args:
            description: Description of the operation

        Returns:
            Progress context manager
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        )
