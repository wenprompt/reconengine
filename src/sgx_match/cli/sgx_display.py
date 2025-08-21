"""Display utilities for SGX trade matching results."""

from typing import List, Dict, Any
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from ..models import SGXMatchResult, SGXTrade


class SGXDisplay:
    """Rich console display for SGX matching results."""
    
    def __init__(self):
        """Initialize display with Rich console."""
        self.console = Console()
    
    def show_header(self) -> None:
        """Display SGX matching system header."""
        header = Text("SGX Trade Matching System", style="bold blue")
        subheader = Text("Singapore Exchange Trade Reconciliation", style="italic")
        
        self.console.print(Panel.fit(
            Group(header, subheader),
            border_style="blue"
        ))
    
    def show_loading_summary(self, trader_count: int, exchange_count: int) -> None:
        """Display data loading summary.
        
        Args:
            trader_count: Number of trader trades loaded
            exchange_count: Number of exchange trades loaded
        """
        summary = f"Loaded [bold green]{trader_count}[/bold green] trader trades and [bold green]{exchange_count}[/bold green] exchange trades"
        self.console.print(summary)
    
    def show_match_results(self, matches: List[SGXMatchResult], statistics: Dict[str, Any]) -> None:
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
            str(stats.get("original_trader_count", 0) + stats.get("original_exchange_count", 0))
        )
        
        table.add_row(
            "Matched Count",
            str(stats.get("matched_trader_count", 0)),
            str(stats.get("matched_exchange_count", 0)),
            str(stats.get("total_matches", 0))
        )
        
        table.add_row(
            "Unmatched Count",
            str(stats.get("unmatched_trader_count", 0)),
            str(stats.get("unmatched_exchange_count", 0)),
            str(stats.get("unmatched_trader_count", 0) + stats.get("unmatched_exchange_count", 0))
        )
        
        table.add_row(
            "Match Rate",
            f"{stats.get('trader_match_rate', 0):.1f}%",
            f"{stats.get('exchange_match_rate', 0):.1f}%",
            f"{(stats.get('total_matches', 0) / max(stats.get('original_trader_count', 0) + stats.get('original_exchange_count', 0), 1)) * 100:.1f}%"
        )
        
        self.console.print("\n")
        self.console.print(table)
    
    def _show_detailed_matches(self, matches: List[SGXMatchResult]) -> None:
        """Show detailed match results."""
        table = Table(title=f"Detailed Matches ({len(matches)} found)", box=box.ROUNDED)
        table.add_column("Match ID", style="cyan")
        table.add_column("Rule", justify="center")
        table.add_column("Product", style="green")
        table.add_column("Contract", style="yellow")
        table.add_column("Quantity", justify="right", style="blue")
        table.add_column("Price", justify="right", style="magenta")
        table.add_column("B/S", justify="center")
        table.add_column("Trader ID", style="dim")
        table.add_column("Exchange ID", style="dim")
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
                f"{match.confidence}%"
            )
        
        self.console.print("\n")
        self.console.print(table)
    
    def show_unmatched_trades(self, trader_trades: List[SGXTrade], 
                            exchange_trades: List[SGXTrade]) -> None:
        """Show unmatched trades.
        
        Args:
            trader_trades: Unmatched trader trades
            exchange_trades: Unmatched exchange trades
        """
        if trader_trades:
            self._show_unmatched_trader_table(trader_trades)
        
        if exchange_trades:
            self._show_unmatched_exchange_table(exchange_trades)
    
    def _show_unmatched_trader_table(self, trades: List[SGXTrade]) -> None:
        """Show unmatched trader trades table."""
        table = Table(title=f"Unmatched Trader Trades ({len(trades)})", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Product", style="green")
        table.add_column("Contract", style="yellow")
        table.add_column("Quantity", justify="right", style="blue")
        table.add_column("Price", justify="right", style="magenta")
        table.add_column("B/S", justify="center")
        table.add_column("Trade Time", style="dim")
        table.add_column("Broker Group", justify="right")
        table.add_column("Remarks", style="dim")
        
        for trade in trades:  # Show all trades
            table.add_row(
                trade.display_id,
                trade.product_name,
                trade.contract_month,
                str(trade.quantity_units),
                str(trade.price),
                trade.buy_sell,
                trade.trade_time or "",
                str(trade.broker_group_id or ""),
                trade.remarks or ""
            )
        
        self.console.print("\n")
        self.console.print(table)
    
    def _show_unmatched_exchange_table(self, trades: List[SGXTrade]) -> None:
        """Show unmatched exchange trades table."""
        table = Table(title=f"Unmatched Exchange Trades ({len(trades)})", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Deal ID", justify="right")
        table.add_column("Product", style="green")
        table.add_column("Contract", style="yellow")
        table.add_column("Quantity", justify="right", style="blue")
        table.add_column("Price", justify="right", style="magenta")
        table.add_column("B/S", justify="center")
        table.add_column("Trader", style="dim")
        
        for trade in trades:  # Show all trades
            table.add_row(
                trade.display_id,
                str(trade.deal_id or ""),
                trade.product_name,
                trade.contract_month,
                str(trade.quantity_units),
                str(trade.price),
                trade.buy_sell,
                trade.trader_name or ""
            )
        
        self.console.print("\n")
        self.console.print(table)
    
    def show_error(self, message: str) -> None:
        """Display error message.
        
        Args:
            message: Error message to display
        """
        self.console.print(f"[bold red]Error:[/bold red] {message}")
    
    def show_success(self, message: str) -> None:
        """Display success message.
        
        Args:
            message: Success message to display
        """
        self.console.print(f"[bold green]Success:[/bold green] {message}")
    
    def show_warning(self, message: str) -> None:
        """Display warning message.
        
        Args:
            message: Warning message to display
        """
        self.console.print(f"[bold yellow]Warning:[/bold yellow] {message}")