"""Rich terminal display for Rule 0 position analysis."""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns

from src.ice_match.rule_0.matrix_comparator import MatchStatus, PositionComparison

logger = logging.getLogger(__name__)


class PositionDisplay:
    """Display position analysis results using Rich terminal formatting."""
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize the display.
        
        Args:
            console: Rich console instance, creates new if None
        """
        self.console = console or Console()
    
    def show_header(self) -> None:
        """Display the header for Rule 0."""
        header = Panel(
            "[bold cyan]Rule 0: Position Decomposition Analyzer[/bold cyan]\n"
            "[dim]Breaking down complex products to base components for position verification[/dim]",
            style="cyan",
            expand=False
        )
        self.console.print(header)
        self.console.print()
    
    def show_position_matrix(
        self,
        comparisons: List[PositionComparison],
        contract_month: Optional[str] = None
    ) -> None:
        """Display position comparison matrix with products as tables.
        
        Args:
            comparisons: List of position comparisons
            contract_month: Optional filter for specific month
        """
        # Filter by month if specified
        if contract_month:
            comparisons = [c for c in comparisons if c.contract_month == contract_month]
        
        # Group by product
        by_product: Dict[str, List[PositionComparison]] = {}
        for comp in comparisons:
            if comp.product not in by_product:
                by_product[comp.product] = []
            by_product[comp.product].append(comp)
        
        # Display each product as a separate table
        for product in sorted(by_product.keys()):
            self._display_product_matrix(product, by_product[product])
            self.console.print()
    
    def _display_product_matrix(self, product: str, comparisons: List[PositionComparison]) -> None:
        """Display matrix for a single product across all months.
        
        Args:
            product: Product name
            comparisons: Comparisons for this product
        """
        # Skip if all positions are zero
        if all(comp.status == MatchStatus.ZERO_POSITION for comp in comparisons):
            return
        
        # Check if this is brent swap
        is_brent = product.lower() == "brent swap"
        
        table = Table(
            title=f"[bold cyan]{product}[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
            title_style="bold cyan",
            show_lines=True
        )
        
        # Add columns based on product type
        table.add_column("Contract Month", style="yellow", width=15)
        
        if is_brent:
            # Brent swap - only show BBL
            table.add_column("Trader BBL", justify="right", style="green")
            table.add_column("Exchange BBL", justify="right", style="blue")
            table.add_column("Diff BBL", justify="right")
        else:
            # All other products - only show MT
            table.add_column("Trader MT", justify="right", style="green")
            table.add_column("Exchange MT", justify="right", style="blue")
            table.add_column("Diff MT", justify="right")
        
        table.add_column("Status", justify="center")
        
        # Sort by contract month
        comparisons.sort(key=lambda x: x.contract_month)
        
        for comp in comparisons:
            # Skip zero positions
            if comp.status == MatchStatus.ZERO_POSITION:
                continue
            
            # Status formatting
            status = self._format_status(comp.status)
            
            if is_brent:
                # Format BBL quantities for brent
                trader_bbl = self._format_decimal(comp.trader_bbl) if comp.trader_bbl is not None else "N/A"
                exchange_bbl = self._format_decimal(comp.exchange_bbl) if comp.exchange_bbl is not None else "N/A"
                diff_bbl = self._format_decimal(comp.difference_bbl, show_sign=True) if comp.difference_bbl is not None else "N/A"
                
                # Style difference column
                if comp.difference_bbl and comp.difference_bbl > 0:
                    diff_display = f"[red]{diff_bbl}[/red]"
                elif comp.difference_bbl and comp.difference_bbl < 0:
                    diff_display = f"[blue]{diff_bbl}[/blue]"
                else:
                    diff_display = diff_bbl
                
                table.add_row(
                    comp.contract_month,
                    trader_bbl,
                    exchange_bbl,
                    diff_display,
                    status
                )
            else:
                # Format MT quantities for other products
                trader_mt = self._format_decimal(comp.trader_mt) if comp.trader_mt is not None else "N/A"
                exchange_mt = self._format_decimal(comp.exchange_mt) if comp.exchange_mt is not None else "N/A"
                diff_mt = self._format_decimal(comp.difference_mt, show_sign=True) if comp.difference_mt is not None else "N/A"
                
                # Style difference column
                if comp.difference_mt and comp.difference_mt > 0:
                    diff_display = f"[red]{diff_mt}[/red]"
                elif comp.difference_mt and comp.difference_mt < 0:
                    diff_display = f"[blue]{diff_mt}[/blue]"
                else:
                    diff_display = diff_mt
                
                table.add_row(
                    comp.contract_month,
                    trader_mt,
                    exchange_mt,
                    diff_display,
                    status
                )
        
        self.console.print(table)
    
    def show_summary_statistics(self, stats: Dict[str, Any]) -> None:
        """Display summary statistics.
        
        Args:
            stats: Dictionary of statistics
        """
        # Create summary panels
        panels = []
        
        # Match statistics
        match_panel = Panel(
            f"[bold green]Matched:[/bold green] {stats['matched_positions']}\n"
            f"[bold yellow]Mismatches:[/bold yellow] {stats['quantity_mismatches']}\n"
            f"[bold red]Missing:[/bold red] {int(stats['missing_in_exchange']) + int(stats['missing_in_trader'])}\n"
            f"[bold]Match Rate:[/bold] {stats['match_rate']:.1f}%",
            title="Position Matching",
            border_style="green"
        )
        panels.append(match_panel)
        
        # Discrepancy breakdown
        disc_panel = Panel(
            f"[bold]Total Positions:[/bold] {stats['total_positions']}\n"
            f"[yellow]Missing in Exchange:[/yellow] {stats['missing_in_exchange']}\n"
            f"[yellow]Missing in Trader:[/yellow] {stats['missing_in_trader']}\n"
            f"[red]Total Discrepancies:[/red] {stats['total_discrepancies']}",
            title="Position Analysis",
            border_style="yellow"
        )
        panels.append(disc_panel)
        
        # Display panels side by side
        self.console.print(Columns(panels))
        self.console.print()
    
    def show_discrepancies(
        self,
        comparisons: List[PositionComparison],
        limit: Optional[int] = None
    ) -> None:
        """Display detailed discrepancies.
        
        Args:
            comparisons: List of position comparisons
            limit: Optional limit on number to display
        """
        # Filter to only discrepancies
        discrepancies = [c for c in comparisons if c.has_discrepancy]
        
        if not discrepancies:
            self.console.print("[green]✓ No discrepancies found![/green]")
            return
        
        # Sort by absolute difference
        discrepancies.sort(key=lambda x: abs(x.difference_mt), reverse=True)
        
        if limit:
            discrepancies = discrepancies[:limit]
        
        table = Table(
            title=f"[bold red]Position Discrepancies{f' (Top {limit})' if limit else ''}[/bold red]",
            show_header=True,
            header_style="bold red"
        )
        
        table.add_column("Month", style="cyan")
        table.add_column("Product", style="yellow")
        table.add_column("Type", style="magenta")
        table.add_column("Trader MT", justify="right")
        table.add_column("Exchange MT", justify="right")
        table.add_column("Difference MT", justify="right", style="red")
        table.add_column("Diff %", justify="right")
        
        for comp in discrepancies:
            # Determine discrepancy type
            if comp.status == MatchStatus.MISSING_IN_EXCHANGE:
                disc_type = "Missing in Exchange"
            elif comp.status == MatchStatus.MISSING_IN_TRADER:
                disc_type = "Missing in Trader"
            else:
                disc_type = "Quantity Mismatch"
            
            # Format percentage
            pct = comp.percentage_diff
            pct_str = f"{pct:.1f}%" if pct is not None else "N/A"
            
            table.add_row(
                comp.contract_month,
                comp.product,
                disc_type,
                self._format_decimal(comp.trader_mt),
                self._format_decimal(comp.exchange_mt),
                self._format_decimal(comp.difference_mt, show_sign=True),
                pct_str
            )
        
        self.console.print(table)
    
    def _format_decimal(self, value: Decimal, show_sign: bool = False) -> str:
        """Format decimal for display.
        
        Args:
            value: Decimal value
            show_sign: Whether to show + for positive values
            
        Returns:
            Formatted string
        """
        if value == 0:
            return "0"
        
        # Format with thousand separators
        formatted = f"{value:,.2f}".rstrip("0").rstrip(".")
        
        if show_sign and value > 0:
            formatted = f"+{formatted}"
        
        return formatted
    
    def _format_status(self, status: MatchStatus) -> str:
        """Format status for display with icons and colors.
        
        Args:
            status: Match status
            
        Returns:
            Formatted status string
        """
        if status == MatchStatus.MATCHED:
            return "[green]✓ Match[/green]"
        elif status == MatchStatus.QUANTITY_MISMATCH:
            return "[yellow]⚠ Qty Diff[/yellow]"
        elif status == MatchStatus.MISSING_IN_EXCHANGE:
            return "[red]✗ No Exch[/red]"
        elif status == MatchStatus.MISSING_IN_TRADER:
            return "[red]✗ No Trader[/red]"
        else:
            return "[dim]-[/dim]"
    
    def show_export_confirmation(self, filepath: str) -> None:
        """Show confirmation of export.
        
        Args:
            filepath: Path where data was exported
        """
        self.console.print(
            f"\n[green]✓[/green] Position matrix exported to: [cyan]{filepath}[/cyan]"
        )