"""Rich terminal display for Rule 0 position analysis."""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns

from src.ice_match.rule_0.matrix_comparator import MatchStatus, PositionComparison
from src.ice_match.rule_0.position_matrix import PositionMatrix

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
    
    def show_position_details(
        self,
        trader_matrix: PositionMatrix,
        exchange_matrix: PositionMatrix
    ) -> None:
        """Display detailed trade breakdown for each product.
        
        Shows side-by-side comparison of trader and exchange trades
        that contribute to each position, sorted by size.
        
        Args:
            trader_matrix: Trader position matrix with trade details
            exchange_matrix: Exchange position matrix with trade details
        """
        # Get all products
        all_products = trader_matrix.products.union(exchange_matrix.products)
        
        for product in sorted(all_products):
            # Get all contract months for this product
            months_with_product = set()
            
            for (month, prod) in trader_matrix.positions.keys():
                if prod == product:
                    months_with_product.add(month)
            
            for (month, prod) in exchange_matrix.positions.keys():
                if prod == product:
                    months_with_product.add(month)
            
            if not months_with_product:
                continue
            
            # Determine unit for this product
            unit = "BBL" if product.lower() == "brent swap" else "MT"
            
            # Create header for product
            self.console.print()
            self.console.print("=" * 80)
            self.console.print(f"[bold cyan]TRADE DETAILS - {product} ({unit})[/bold cyan]")
            self.console.print("=" * 80)
            self.console.print()
            
            # Process each contract month
            for month in sorted(months_with_product):
                self._show_month_details(product, month, unit, trader_matrix, exchange_matrix)
    
    def _show_month_details(
        self,
        product: str,
        month: str,
        unit: str,
        trader_matrix: PositionMatrix,
        exchange_matrix: PositionMatrix
    ) -> None:
        """Show trade details for a specific product and month.
        
        Args:
            product: Product name
            month: Contract month
            unit: Unit (MT or BBL)
            trader_matrix: Trader position matrix
            exchange_matrix: Exchange position matrix
        """
        # Get positions
        trader_pos = trader_matrix.get_position(month, product)
        exchange_pos = exchange_matrix.get_position(month, product)
        
        # Get trade details
        trader_details = trader_pos.trade_details if trader_pos else []
        exchange_details = exchange_pos.trade_details if exchange_pos else []
        
        # Sort by absolute quantity (largest first)
        trader_details = sorted(
            trader_details,
            key=lambda x: abs(x.get("quantity_bbl" if unit == "BBL" else "quantity_mt", 0)),
            reverse=True
        )
        exchange_details = sorted(
            exchange_details,
            key=lambda x: abs(x.get("quantity_bbl" if unit == "BBL" else "quantity_mt", 0)),
            reverse=True
        )
        
        # Create table
        table = Table(
            title=f"[bold]{month}[/bold]",
            show_header=True,
            header_style="bold",
            box=None,
            padding=(0, 1)
        )
        
        table.add_column("TRADER", style="cyan", width=38)
        table.add_column("EXCHANGE", style="yellow", width=38)
        
        # Add rows (max of trader/exchange details)
        max_rows = max(len(trader_details), len(exchange_details))
        
        for i in range(max_rows):
            trader_str = ""
            exchange_str = ""
            
            # Format trader detail
            if i < len(trader_details):
                detail = trader_details[i]
                trade_id = detail["internal_trade_id"]
                qty = detail.get("quantity_bbl" if unit == "BBL" else "quantity_mt", 0)
                
                # Format quantity with sign
                qty_str = self._format_decimal(qty, show_sign=True)
                
                # Add synthetic indicator and original product
                if detail.get("is_synthetic"):
                    orig = detail.get("original_product", "")
                    trader_str = f"{trade_id}*: {qty_str} (from {orig})"
                else:
                    trader_str = f"{trade_id}: {qty_str}"
            
            # Format exchange detail
            if i < len(exchange_details):
                detail = exchange_details[i]
                trade_id = detail["internal_trade_id"]
                qty = detail.get("quantity_bbl" if unit == "BBL" else "quantity_mt", 0)
                
                # Format quantity with sign
                qty_str = self._format_decimal(qty, show_sign=True)
                
                # Add synthetic indicator and original product
                if detail.get("is_synthetic"):
                    orig = detail.get("original_product", "")
                    exchange_str = f"{trade_id}*: {qty_str} (from {orig})"
                else:
                    exchange_str = f"{trade_id}: {qty_str}"
            
            table.add_row(trader_str, exchange_str)
        
        # Add separator row
        table.add_row("─" * 36, "─" * 36)
        
        # Add totals row
        trader_total = Decimal("0")
        exchange_total = Decimal("0")
        
        if trader_pos:
            if unit == "BBL":
                trader_total = trader_pos.quantity_bbl or Decimal("0")
            else:
                trader_total = trader_pos.quantity_mt or Decimal("0")
        
        if exchange_pos:
            if unit == "BBL":
                exchange_total = exchange_pos.quantity_bbl or Decimal("0")
            else:
                exchange_total = exchange_pos.quantity_mt or Decimal("0")
        
        trader_total_str = f"Total: {self._format_decimal(trader_total, show_sign=True)}"
        exchange_total_str = f"Total: {self._format_decimal(exchange_total, show_sign=True)}"
        
        table.add_row(
            f"[bold]{trader_total_str}[/bold]",
            f"[bold]{exchange_total_str}[/bold]"
        )
        
        self.console.print(table)
        self.console.print()