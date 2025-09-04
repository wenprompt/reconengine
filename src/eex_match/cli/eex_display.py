"""Display module for EEX trade matching results with rich terminal output."""

from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from ..models import EEXTrade, EEXMatchResult, EEXMatchType


class EEXDisplay:
    """Handles all display output for EEX trade matching system."""
    
    def __init__(self):
        """Initialize display with Rich console."""
        self.console = Console()
    
    def show_header(self) -> None:
        """Display the EEX matching system header."""
        header_text = Text("⚡ EEX TRADE MATCHING SYSTEM", style="bold blue")
        subtitle = "European Energy Exchange Matching Engine v1.0"
        
        panel = Panel(
            f"{subtitle}\n\n"
            "📊 Products: CAPE (Capesize Freight) and derivatives\n"
            "🎯 Single Rule: Exact matching with 100% confidence\n"
            "🔄 Sequential Processing: Non-duplication guaranteed",
            title=header_text,
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print()
        self.console.print(panel)
        self.console.print()
    
    def show_loading_summary(self, trader_count: int, exchange_count: int) -> None:
        """Display summary of loaded trades.
        
        Args:
            trader_count: Number of trader trades loaded
            exchange_count: Number of exchange trades loaded
        """
        total = trader_count + exchange_count
        
        summary = Panel(
            f"📁 Trader Trades: {trader_count:,}\n"
            f"📁 Exchange Trades: {exchange_count:,}\n"
            f"📊 Total Trades: {total:,}",
            title="[bold green]Data Loaded Successfully[/bold green]",
            border_style="green"
        )
        
        self.console.print(summary)
        self.console.print()
    
    def show_match_results(
        self,
        matches: List[EEXMatchResult],
        statistics: Dict[str, Any]
    ) -> None:
        """Display match results and statistics.
        
        Args:
            matches: List of all matches found
            statistics: Matching statistics from pool manager
        """
        # Overall statistics panel
        match_rate = statistics.get("trader_match_rate", 0)
        
        stats_text = (
            f"✅ Total Matches: {len(matches)}\n"
            f"📊 Trader Match Rate: {match_rate:.1f}%\n"
            f"📈 Exchange Match Rate: {statistics.get('exchange_match_rate', 0):.1f}%\n"
            f"🎯 Unmatched Trader: {statistics.get('unmatched_trader_count', 0)}\n"
            f"🎯 Unmatched Exchange: {statistics.get('unmatched_exchange_count', 0)}"
        )
        
        stats_panel = Panel(
            stats_text,
            title="[bold yellow]Matching Results[/bold yellow]",
            border_style="yellow"
        )
        
        self.console.print(stats_panel)
        self.console.print()
        
        # Show detailed matches if any
        if matches:
            self._show_detailed_matches(matches)
    
    def _show_detailed_matches(self, matches: List[EEXMatchResult]) -> None:
        """Show detailed match information in a table.
        
        Args:
            matches: List of matches to display
        """
        # Group matches by type (only EXACT for EEX)
        exact_matches = [m for m in matches if m.match_type == EEXMatchType.EXACT]
        
        if exact_matches:
            self.console.print("[bold cyan]Exact Matches:[/bold cyan]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Match ID", style="dim", width=12)
            table.add_column("Trader ID", width=10)
            table.add_column("Exchange ID", width=10)
            table.add_column("Product", width=10)
            table.add_column("Contract", width=10)
            table.add_column("Qty", justify="right", width=8)
            table.add_column("Price", justify="right", width=10)
            table.add_column("B/S", width=5)
            
            for match in exact_matches[:20]:  # Show first 20 matches
                table.add_row(
                    match.match_id[-8:],  # Last 8 chars of match ID
                    match.trader_trade.internal_trade_id,
                    match.exchange_trade.internal_trade_id,
                    match.matched_product,
                    match.matched_contract,
                    str(match.matched_quantity),
                    str(match.trader_trade.price),
                    f"{match.trader_trade.buy_sell}/{match.exchange_trade.buy_sell}"
                )
            
            self.console.print(table)
            
            if len(exact_matches) > 20:
                self.console.print(
                    f"[dim]... and {len(exact_matches) - 20} more exact matches[/dim]"
                )
            
            self.console.print()
    
    def show_unmatched_trades(
        self,
        unmatched_trader: List[EEXTrade],
        unmatched_exchange: List[EEXTrade]
    ) -> None:
        """Display unmatched trades.
        
        Args:
            unmatched_trader: List of unmatched trader trades
            unmatched_exchange: List of unmatched exchange trades
        """
        if unmatched_trader:
            self._show_unmatched_trader_trades(unmatched_trader)
        
        if unmatched_exchange:
            self._show_unmatched_exchange_trades(unmatched_exchange)
    
    def _show_unmatched_trader_trades(self, trades: List[EEXTrade]) -> None:
        """Display unmatched trader trades in a table.
        
        Args:
            trades: List of unmatched trader trades
        """
        self.console.print(f"[bold red]Unmatched Trader Trades ({len(trades)}):[/bold red]")
        
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Trade ID", width=10)
        table.add_column("Product", width=10)
        table.add_column("Contract", width=10)
        table.add_column("Qty Unit", justify="right", width=10)
        table.add_column("Qty Lot", justify="right", width=8)
        table.add_column("Price", justify="right", width=10)
        table.add_column("B/S", width=5)
        table.add_column("Broker", width=8)
        table.add_column("Clearing", width=8)
        
        # Show first 10 unmatched trades
        for trade in trades[:10]:
            table.add_row(
                trade.internal_trade_id,
                trade.product_name,
                trade.contract_month,
                str(trade.quantityunit),
                str(trade.quantitylot) if trade.quantitylot else "-",
                str(trade.price),
                trade.buy_sell,
                str(trade.broker_group_id) if trade.broker_group_id else "-",
                str(trade.exch_clearing_acct_id) if trade.exch_clearing_acct_id else "-"
            )
        
        self.console.print(table)
        
        if len(trades) > 10:
            self.console.print(f"[dim]... and {len(trades) - 10} more unmatched trader trades[/dim]")
        
        self.console.print()
    
    def _show_unmatched_exchange_trades(self, trades: List[EEXTrade]) -> None:
        """Display unmatched exchange trades in a table.
        
        Args:
            trades: List of unmatched exchange trades
        """
        self.console.print(f"[bold red]Unmatched Exchange Trades ({len(trades)}):[/bold red]")
        
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Trade ID", width=10)
        table.add_column("Product", width=10)
        table.add_column("Contract", width=10)
        table.add_column("Qty Unit", justify="right", width=10)
        table.add_column("Qty Lot", justify="right", width=8)
        table.add_column("Price", justify="right", width=10)
        table.add_column("B/S", width=5)
        table.add_column("Broker", width=8)
        table.add_column("Clearing", width=8)
        
        # Show first 10 unmatched trades
        for trade in trades[:10]:
            table.add_row(
                trade.internal_trade_id,
                trade.product_name,
                trade.contract_month,
                str(trade.quantityunit),
                str(trade.quantitylot) if trade.quantitylot else "-",
                str(trade.price),
                trade.buy_sell,
                str(trade.broker_group_id) if trade.broker_group_id else "-",
                str(trade.exch_clearing_acct_id) if trade.exch_clearing_acct_id else "-"
            )
        
        self.console.print(table)
        
        if len(trades) > 10:
            self.console.print(f"[dim]... and {len(trades) - 10} more unmatched exchange trades[/dim]")
        
        self.console.print()
    
    def show_error(self, message: str) -> None:
        """Display an error message.
        
        Args:
            message: Error message to display
        """
        error_panel = Panel(
            f"❌ {message}",
            title="[bold red]Error[/bold red]",
            border_style="red"
        )
        self.console.print(error_panel)
    
    def show_rule_info(self, rule_info: Dict) -> None:
        """Display information about a matching rule.
        
        Args:
            rule_info: Dictionary with rule metadata
        """
        rule_text = (
            f"📋 Rule {rule_info['rule_number']}: {rule_info['name']}\n"
            f"📝 {rule_info['description']}\n"
            f"🎯 Confidence: {rule_info['confidence']}%\n"
            f"🔍 Matched Fields: {', '.join(rule_info['matched_fields'])}"
        )
        
        if "notes" in rule_info:
            rule_text += f"\n💡 Notes: {rule_info['notes']}"
        
        panel = Panel(
            rule_text,
            title=f"[bold blue]Rule {rule_info['rule_number']} Information[/bold blue]",
            border_style="blue"
        )
        
        self.console.print(panel)
        self.console.print()