from typing import List, Dict, Any
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from ..models import CMEMatchResult, CMETrade

# Display configuration constants
MAX_UNMATCHED_DISPLAY = 100  # Maximum unmatched trades to show


class CMEDisplay:
    """Rich console display for CME matching results."""

    def __init__(self):
        """Initialize display with Rich console."""
        self.console = Console()

    def show_header(self) -> None:
        """Display CME matching system header."""
        header = Text("CME Trade Matching System", style="bold blue")
        subheader = Text(
            "Chicago Mercantile Exchange Trade Reconciliation", style="italic"
        )

        self.console.print(Panel.fit(Group(header, subheader), border_style="blue"))

    def show_loading_summary(self, trader_count: int, exchange_count: int) -> None:
        """Display data loading summary.

        Args:
            trader_count: Number of trader trades loaded
            exchange_count: Number of exchange trades loaded
        """
        summary = f"Loaded [bold green]{trader_count}[/bold green] trader trades and [bold green]{exchange_count}[/bold green] exchange trades"
        self.console.print(summary)

    def show_match_results(
        self, matches: List[CMEMatchResult], statistics: Dict[str, Any]
    ) -> None:
        """Display matching results with statistics.

        Args:
            matches: List of match results
            statistics: Matching statistics
        """
        # Summary statistics
        self._show_statistics(statistics)

        # Detailed matches
        if matches:
            self._show_detailed_matches(matches)
        else:
            self.console.print("\n[yellow]No matches found.[/yellow]")

    def _show_statistics(self, stats: Dict[str, Any]) -> None:
        """Show matching statistics."""
        table = Table(title="Matching Statistics", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Trader", justify="right")
        table.add_column("Exchange", justify="right")
        table.add_column("Total", justify="right")

        table.add_row(
            "Original Count",
            str(stats.get("original_trader_count", 0)),
            str(stats.get("original_exchange_count", 0)),
            str(
                stats.get("original_trader_count", 0)
                + stats.get("original_exchange_count", 0)
            ),
        )

        table.add_row(
            "Matched Count",
            str(stats.get("matched_trader_count", 0)),
            str(stats.get("matched_exchange_count", 0)),
            str(stats.get("total_matches", 0)),
        )

        table.add_row(
            "Unmatched Count",
            str(stats.get("unmatched_trader_count", 0)),
            str(stats.get("unmatched_exchange_count", 0)),
            str(
                stats.get("unmatched_trader_count", 0)
                + stats.get("unmatched_exchange_count", 0)
            ),
        )

        table.add_row(
            "Match Rate",
            f"{stats.get('trader_match_rate', 0):.1f}%",
            f"{stats.get('exchange_match_rate', 0):.1f}%",
            f"{(stats.get('trader_match_rate', 0) + stats.get('exchange_match_rate', 0)) / 2:.1f}%",
        )

        self.console.print("\n")
        self.console.print(table)

    def _show_detailed_matches(self, matches: List[CMEMatchResult]) -> None:
        """Show detailed match results."""
        if not matches:
            return

        # CME only has exact matches, so we show them in SGX format
        self._show_single_leg_matches(matches)

    def _show_single_leg_matches(self, matches: List[CMEMatchResult]) -> None:
        """Show single-leg match results."""
        table = Table(title=f"Detailed Matches ({len(matches)} found)", box=box.ROUNDED)
        table.add_column("Match ID", style="cyan")
        table.add_column("Rule", justify="center")
        table.add_column("Product", style="green")
        table.add_column("Contract", style="yellow")
        table.add_column("Quantity", justify="right", style="blue")
        table.add_column("Price", justify="right", style="magenta")
        table.add_column("B/S", justify="center")
        table.add_column("Trade ID (T)", style="dim")
        table.add_column("Trade ID (E)", style="dim")
        table.add_column("Confidence", justify="right", style="bold green")

        for match in matches:
            table.add_row(
                match.match_id,
                str(match.rule_order),
                match.matched_product,
                match.matched_contract,
                str(match.matched_quantity),
                str(match.trader_trade.price),
                match.trader_trade.buy_sell,
                match.trader_trade.display_id,
                match.exchange_trade.display_id,
                f"{match.confidence}%",
            )

        self.console.print("\n")
        self.console.print(table)

    def show_unmatched_trades(
        self, trader_trades: List[CMETrade], exchange_trades: List[CMETrade]
    ) -> None:
        """Display unmatched trades."""
        if trader_trades:
            self._show_unmatched_trader_trades(trader_trades)

        if exchange_trades:
            self._show_unmatched_exchange_trades(exchange_trades)

        if not trader_trades and not exchange_trades:
            self.console.print("\n[green]All trades successfully matched![/green]")

    def _show_unmatched_trader_trades(self, trades: List[CMETrade]) -> None:
        """Show unmatched trader trades."""
        display_count = min(len(trades), MAX_UNMATCHED_DISPLAY)
        title = f"Unmatched Trader Trades ({len(trades)} total"
        if len(trades) > MAX_UNMATCHED_DISPLAY:
            title += f", showing first {display_count}"
        title += ")"

        table = Table(title=title, box=box.SIMPLE)
        table.add_column("Trade ID", style="dim", no_wrap=True)
        table.add_column("Product", style="green")
        table.add_column("Contract", justify="center")
        table.add_column("Quantity", justify="right")
        table.add_column("Price", justify="right")
        table.add_column("B/S", justify="center")

        for trade in trades[:display_count]:
            table.add_row(
                trade.display_id,
                trade.product_name,
                trade.contract_month,
                str(trade.quantitylots),
                str(trade.price),
                trade.buy_sell,
            )

        self.console.print("\n")
        self.console.print(table)

    def _show_unmatched_exchange_trades(self, trades: List[CMETrade]) -> None:
        """Show unmatched exchange trades."""
        display_count = min(len(trades), MAX_UNMATCHED_DISPLAY)
        title = f"Unmatched Exchange Trades ({len(trades)} total"
        if len(trades) > MAX_UNMATCHED_DISPLAY:
            title += f", showing first {display_count}"
        title += ")"

        table = Table(title=title, box=box.SIMPLE)
        table.add_column("Trade ID", style="dim", no_wrap=True)
        table.add_column("Product", style="blue")
        table.add_column("Contract", justify="center")
        table.add_column("Quantity", justify="right")
        table.add_column("Price", justify="right")
        table.add_column("B/S", justify="center")

        for trade in trades[:display_count]:
            table.add_row(
                trade.display_id,
                trade.product_name,
                trade.contract_month,
                str(trade.quantitylots),
                str(trade.price),
                trade.buy_sell,
            )

        self.console.print("\n")
        self.console.print(table)

    def show_error(self, message: str) -> None:
        """Display error message.

        Args:
            message: Error message to display
        """
        self.console.print(f"\n[red]Error: {message}[/red]")

    def show_rule_info(self, rule_info: Dict[str, Any]) -> None:
        """Display information about a matching rule."""
        table = Table(
            title=f"Rule {rule_info.get('rule_number', 'Unknown')}: {rule_info.get('rule_name', 'Unknown')}",
            box=box.ROUNDED,
        )
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Rule Number", str(rule_info.get("rule_number", "Unknown")))
        table.add_row("Rule Name", rule_info.get("rule_name", "Unknown"))
        table.add_row("Match Type", rule_info.get("match_type", "Unknown"))
        table.add_row("Confidence", f"{rule_info.get('confidence', 0)}%")
        table.add_row("Description", rule_info.get("description", "No description"))

        requirements = rule_info.get("requirements", [])
        if requirements:
            table.add_row("Requirements", "\n".join(f"• {req}" for req in requirements))

        self.console.print("\n")
        self.console.print(table)
