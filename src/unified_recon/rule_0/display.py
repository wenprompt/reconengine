"""Rich terminal display for unified Rule 0."""

from typing import List, Dict, Any, Set, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.unified_recon.rule_0.position_matrix import PositionMatrix
from src.unified_recon.rule_0.matrix_comparator import PositionComparison, MatchStatus

console = Console()


class UnifiedDisplay:
    """Display handler for unified Rule 0 results."""
    
    def __init__(self, exchange: str):
        """Initialize display for specific exchange."""
        self.exchange = exchange
        self.console = console
    
    def _determine_trade_type(self, original_product: str, spread_flag: str) -> str:
        """Determine trade type based on product and flags.
        
        Args:
            original_product: Original product name (for decomposed products)
            spread_flag: Spread flag from trade data
            
        Returns:
            Trade type: 'Crack', 'PS', 'S', or empty string
        """
        if original_product:
            if "crack" in original_product.lower():
                return "Crack"
            elif "-" in original_product:
                # Product spread (different products joined by -)
                return "PS"
            else:
                return ""
        elif spread_flag == "S":
            return "S"
        else:
            return ""
    
    def show_header(self) -> None:
        """Display the header."""
        header = Panel(
            f"[bold cyan]Rule 0: Position Decomposition Analysis[/bold cyan]\n"
            f"[yellow]Exchange: {self.exchange.upper()}[/yellow]",
            style="bold blue"
        )
        self.console.print(header)
    
    def show_summary(self, stats: Dict[str, Any]) -> None:
        """Display summary statistics."""
        summary_table = Table(title="Summary Statistics", show_header=True)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="white")
        
        summary_table.add_row("Total Positions", str(stats["total_positions"]))
        summary_table.add_row("Matched", f"[green]{stats['matched_positions']}[/green]")
        summary_table.add_row("Quantity Mismatches", f"[yellow]{stats['quantity_mismatches']}[/yellow]")
        summary_table.add_row("Missing in Exchange", f"[red]{stats['missing_in_exchange']}[/red]")
        summary_table.add_row("Missing in Trader", f"[red]{stats['missing_in_trader']}[/red]")
        summary_table.add_row("Zero Positions", f"[dim]{stats['zero_positions']}[/dim]")
        summary_table.add_row("Match Rate", f"{stats['match_rate']:.1f}%")
        
        self.console.print(summary_table)
    
    def show_comparison_by_product(self, comparisons: List[PositionComparison]) -> None:
        """Display comparison results grouped by product."""
        # Group by product
        by_product: Dict[str, List[PositionComparison]] = {}
        for comp in comparisons:
            if comp.product not in by_product:
                by_product[comp.product] = []
            by_product[comp.product].append(comp)
        
        for product, product_comps in sorted(by_product.items()):
            # Skip if all positions are zero
            if all(c.status == MatchStatus.ZERO_POSITION for c in product_comps):
                continue
            
            # Create table for this product
            table = Table(
                title=f"Product: {product}",
                show_header=True,
                title_style="bold cyan"
            )
            
            table.add_column("Contract Month", style="cyan")
            table.add_column("Trader", justify="right")
            table.add_column("Exchange", justify="right")
            table.add_column("Difference", justify="right")
            table.add_column("Status", justify="center")
            table.add_column("Trades (T/E)", justify="center")
            
            for comp in sorted(product_comps, key=lambda x: x.contract_month):
                # Format quantities
                trader_str = f"{comp.trader_quantity:,.2f}"
                exchange_str = f"{comp.exchange_quantity:,.2f}"
                diff_str = f"{comp.difference:+,.2f}"
                
                # Only show units for non-zero quantities and when unit is defined
                if comp.unit:
                    if comp.trader_quantity != 0:
                        trader_str += f" {comp.unit}"
                    if comp.exchange_quantity != 0:
                        exchange_str += f" {comp.unit}"
                    if comp.trader_quantity != 0 or comp.exchange_quantity != 0:
                        diff_str += f" {comp.unit}"
                
                # Status styling
                if comp.status == MatchStatus.MATCHED:
                    status_str = "[green]✓ MATCHED[/green]"
                elif comp.status == MatchStatus.QUANTITY_MISMATCH:
                    status_str = "[yellow]⚠ MISMATCH[/yellow]"
                elif comp.status == MatchStatus.MISSING_IN_EXCHANGE:
                    status_str = "[red]✗ MISSING (E)[/red]"
                elif comp.status == MatchStatus.MISSING_IN_TRADER:
                    status_str = "[red]✗ MISSING (T)[/red]"
                else:
                    status_str = "[dim]ZERO[/dim]"
                
                # Trade counts
                trade_counts = f"{comp.trader_trades}/{comp.exchange_trades}"
                
                table.add_row(
                    comp.contract_month,
                    trader_str,
                    exchange_str,
                    diff_str,
                    status_str,
                    trade_counts
                )
            
            self.console.print(table)
            self.console.print()  # Add spacing between products
    
    def show_position_details(
        self,
        trader_matrix: PositionMatrix,
        exchange_matrix: PositionMatrix
    ) -> None:
        """Show detailed trade breakdown for each position."""
        # Group positions by product
        all_positions: Set[Tuple[str, str]] = set()
        all_positions.update(trader_matrix.positions.keys())
        all_positions.update(exchange_matrix.positions.keys())
        
        products: Dict[str, List[str]] = {}
        for month, product in all_positions:
            if product not in products:
                products[product] = []
            products[product].append(month)
        
        for product, months in sorted(products.items()):
            # Create table for this product
            table = Table(
                title=f"Trade Details: {product}",
                show_header=True,
                title_style="bold cyan"
            )
            
            table.add_column("Contract", style="cyan", width=10)
            table.add_column("Side", style="yellow", width=8)
            table.add_column("Trade ID", style="white", width=12)
            table.add_column("Quantity", justify="right", width=15)
            table.add_column("Price", justify="right", width=10)
            table.add_column("Broker", justify="center", width=8)
            table.add_column("Clearing", justify="center", width=10)
            table.add_column("Type", style="dim", width=10)
            
            sorted_months = sorted(months)
            for i, month in enumerate(sorted_months):
                # Add trader trades
                trader_pos = trader_matrix.get_position(month, product)
                if trader_pos and trader_pos.trade_details:
                    for detail in trader_pos.trade_details:
                        qty_str = f"{detail['quantity']:+,.2f}"
                        if detail.get('unit'):
                            qty_str += f" {detail['unit']}"
                        
                        # Determine trade type based on rules
                        trade_type = self._determine_trade_type(
                            detail.get('original_product', ''),
                            detail.get('spread_flag', '')
                        )
                        
                        table.add_row(
                            month,
                            "1",  # 1 for TRADER
                            detail.get('internal_trade_id', 'N/A'),
                            qty_str,
                            f"{detail.get('price', 0):g}",  # Format float, removing trailing zeros
                            detail.get('broker_group_id', ''),
                            detail.get('exch_clearing_acct_id', ''),
                            trade_type
                        )
                
                # Add exchange trades
                exchange_pos = exchange_matrix.get_position(month, product)
                if exchange_pos and exchange_pos.trade_details:
                    for detail in exchange_pos.trade_details:
                        qty_str = f"{detail['quantity']:+,.2f}"
                        if detail.get('unit'):
                            qty_str += f" {detail['unit']}"
                        
                        # Determine trade type based on rules
                        trade_type = self._determine_trade_type(
                            detail.get('original_product', ''),
                            detail.get('spread_flag', '')
                        )
                        
                        table.add_row(
                            month,
                            "2",  # 2 for EXCHANGE
                            detail.get('internal_trade_id', 'N/A'),
                            qty_str,
                            f"{detail.get('price', 0):g}",  # Format float, removing trailing zeros
                            detail.get('broker_group_id', ''),
                            detail.get('exch_clearing_acct_id', ''),
                            trade_type
                        )
                
                # Add separator after each month except the last one
                # Only add if this month had trades
                if i < len(sorted_months) - 1:
                    if (trader_pos and trader_pos.trade_details) or (exchange_pos and exchange_pos.trade_details):
                        # Add a more visible separator row
                        table.add_row("", "", "", "", "", "", "", "", end_section=True)
            
            # Only show table if there are trades
            has_trades = False
            for month in months:
                trader_pos = trader_matrix.get_position(month, product)
                exchange_pos = exchange_matrix.get_position(month, product)
                if (trader_pos and trader_pos.trade_details) or (exchange_pos and exchange_pos.trade_details):
                    has_trades = True
                    break
            
            if has_trades:
                self.console.print(table)
                self.console.print()  # Add spacing between products