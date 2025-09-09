"""Rich terminal display for unified Rule 0."""

from decimal import Decimal
from typing import List, Dict, Any, Set, Tuple, Optional, Union

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.unified_recon.rule_0.position_matrix import PositionMatrix
from src.unified_recon.rule_0.matrix_comparator import PositionComparison, MatchStatus


class UnifiedDisplay:
    """Display handler for unified Rule 0 results."""

    exchange: str
    console: Console
    tolerances: Dict[str, float]

    def __init__(self, exchange: str, tolerances: Optional[Dict[str, float]] = None):
        """Initialize display for specific exchange.

        Args:
            exchange: Exchange name
            tolerances: Optional tolerance values for matching (tolerance_mt, tolerance_bbl)
        """
        self.exchange = exchange
        self.console = Console()
        self.tolerances = tolerances or {}

    def _format_status(self, status: MatchStatus) -> str:
        """Format status with appropriate color and icon.

        Args:
            status: The match status

        Returns:
            Formatted status string
        """
        if status == MatchStatus.MATCHED:
            return "[green]✓ MATCHED[/green]"
        elif status == MatchStatus.QUANTITY_MISMATCH:
            return "[yellow]⚠ MISMATCH[/yellow]"
        elif status == MatchStatus.MISSING_IN_EXCHANGE:
            return "[red]✗ MISSING (E)[/red]"
        elif status == MatchStatus.MISSING_IN_TRADER:
            return "[red]✗ MISSING (T)[/red]"
        else:
            return "[dim]ZERO[/dim]"

    def _format_quantity(
        self,
        quantity: Union[float, Decimal],
        unit: Optional[str] = None,
        show_sign: bool = True,
    ) -> str:
        """Format quantity with unit and thousand separators.

        Args:
            quantity: The quantity value (float or Decimal)
            unit: Optional unit string
            show_sign: Whether to show + for positive values

        Returns:
            Formatted quantity string
        """
        if show_sign:
            qty_str = f"{quantity:+,.2f}"
        else:
            qty_str = f"{quantity:,.2f}"

        if unit and quantity != 0:
            qty_str += f" {unit}"

        return qty_str

    def _get_tolerance_for_unit(self, unit: str) -> float:
        """Get tolerance value for a specific unit type.

        Args:
            unit: Unit type (BBL, MT, LOTS, etc.)

        Returns:
            Tolerance value for the unit
        """
        if not self.tolerances:
            return 0.0

        unit_upper = unit.upper() if unit else ""

        # Check for unit-specific tolerances
        unit_tolerance_map = {
            "BBL": "tolerance_bbl",
            "MT": "tolerance_mt",
            "LOTS": "tolerance_lots",
        }

        if unit_upper in unit_tolerance_map:
            specific_key = unit_tolerance_map[unit_upper]
            if specific_key in self.tolerances:
                return self.tolerances[specific_key]

        # Fall back to default or generic tolerance
        return self.tolerances.get(
            "tolerance_default", self.tolerances.get("tolerance", 0.0)
        )

    def _trades_are_compatible(
        self, trader_trade: Dict[str, Any], exchange_trade: Dict[str, Any]
    ) -> bool:
        """Check if two trades are compatible for matching.

        Args:
            trader_trade: Trader trade details
            exchange_trade: Exchange trade details

        Returns:
            True if trades can be matched
        """
        # Get quantities
        t_qty = trader_trade.get("quantity", 0)
        e_qty = exchange_trade.get("quantity", 0)

        # Check: same sign (direction), same broker group, same clearing account
        return (
            t_qty * e_qty > 0  # Same sign check
            and trader_trade.get("broker_group_id", "")
            == exchange_trade.get("broker_group_id", "")
            and trader_trade.get("exch_clearing_acct_id", "")
            == exchange_trade.get("exch_clearing_acct_id", "")
        )

    def _find_best_match(
        self,
        trader_trade: Dict[str, Any],
        exchange_trades: List[Dict[str, Any]],
        tolerance: float,
    ) -> Optional[Dict[str, Any]]:
        """Find the best matching exchange trade for a trader trade.

        Args:
            trader_trade: Trader trade to match
            exchange_trades: List of potential exchange trades
            tolerance: Quantity tolerance for matching

        Returns:
            Best matching exchange trade or None
        """
        best_match = None
        best_difference = float("inf")
        t_qty = trader_trade.get("quantity", 0)

        for e_trade in exchange_trades:
            # Skip if already matched
            if e_trade.get("matched", False):
                continue

            # Check compatibility
            if not self._trades_are_compatible(trader_trade, e_trade):
                continue

            # Calculate quantity difference
            e_qty = e_trade.get("quantity", 0)
            qty_difference = abs(abs(t_qty) - abs(e_qty))

            # Check if within tolerance and better than current best
            if qty_difference <= tolerance and qty_difference < best_difference:
                best_match = e_trade
                best_difference = qty_difference

        return best_match

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

    def _match_trades(
        self, trader_trades: List[Dict[str, Any]], exchange_trades: List[Dict[str, Any]],
        external_match_ids: Optional[Dict[str, str]] = None
    ) -> None:
        """Match trader and exchange trades based on quantity, broker, and clearing account.

        Uses a best-match algorithm that finds the closest quantity match within tolerance.
        If external_match_ids are provided, uses those instead of generating new ones.

        Args:
            trader_trades: List of trader trade details
            exchange_trades: List of exchange trade details
            external_match_ids: Optional mapping of "T_<id>" or "E_<id>" to match IDs
        """
        # Reset match status for all trades
        for trade in trader_trades + exchange_trades:
            trade["matched"] = False
            trade["match_id"] = ""

        # If external match IDs provided, use them first
        if external_match_ids:
            # Apply external match IDs to trades
            for t_trade in trader_trades:
                t_id = str(t_trade.get("internal_trade_id", ""))
                external_match_id = external_match_ids.get(f"T_{t_id}")
                if external_match_id:
                    t_trade["matched"] = True
                    t_trade["match_id"] = external_match_id
            
            for e_trade in exchange_trades:
                e_id = str(e_trade.get("internal_trade_id", ""))
                external_match_id = external_match_ids.get(f"E_{e_id}")
                if external_match_id:
                    e_trade["matched"] = True
                    e_trade["match_id"] = external_match_id
        else:
            # Fall back to position-based matching (original logic)
            # Try to match each trader trade with the best exchange trade
            for t_trade in trader_trades:
                # Get tolerance for this trade's unit
                t_unit = t_trade.get("unit", "")
                tolerance = self._get_tolerance_for_unit(t_unit)

                # Find best matching exchange trade
                best_match = self._find_best_match(t_trade, exchange_trades, tolerance)

                # Apply best match if found
                if best_match:
                    # Generate match ID
                    t_id = t_trade.get("internal_trade_id", "NA")
                    e_id = best_match.get("internal_trade_id", "NA")
                    match_id = f"M_{t_id}_{e_id}"

                    # Mark both trades as matched
                    t_trade["matched"] = True
                    t_trade["match_id"] = match_id
                    best_match["matched"] = True
                    best_match["match_id"] = match_id

    def show_header(self) -> None:
        """Display the header."""
        header = Panel(
            f"[bold cyan]Rule 0: Position Decomposition Analysis[/bold cyan]\n"
            f"[yellow]Exchange: {self.exchange.upper()}[/yellow]",
            style="bold blue",
        )
        self.console.print(header)

    def show_summary(self, stats: Dict[str, Any]) -> None:
        """Display summary statistics."""
        summary_table = Table(title="Summary Statistics", show_header=True)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="white")

        summary_table.add_row("Total Positions", str(stats["total_positions"]))
        summary_table.add_row("Matched", f"[green]{stats['matched_positions']}[/green]")
        summary_table.add_row(
            "Quantity Mismatches", f"[yellow]{stats['quantity_mismatches']}[/yellow]"
        )
        summary_table.add_row(
            "Missing in Exchange", f"[red]{stats['missing_in_exchange']}[/red]"
        )
        summary_table.add_row(
            "Missing in Trader", f"[red]{stats['missing_in_trader']}[/red]"
        )
        summary_table.add_row("Zero Positions", f"[dim]{stats['zero_positions']}[/dim]")
        summary_table.add_row("Match Rate", f"{stats['match_rate']:.1f}%")

        self.console.print(summary_table)

    def _group_comparisons_by_product(
        self, comparisons: List[PositionComparison]
    ) -> Dict[str, List[PositionComparison]]:
        """Group position comparisons by product.

        Args:
            comparisons: List of position comparisons

        Returns:
            Dictionary mapping product to list of comparisons
        """
        by_product: Dict[str, List[PositionComparison]] = {}
        for comp in comparisons:
            if comp.product not in by_product:
                by_product[comp.product] = []
            by_product[comp.product].append(comp)
        return by_product

    def _create_product_comparison_table(self, product: str) -> Table:
        """Create a table for product comparison display.

        Args:
            product: Product name

        Returns:
            Configured Rich Table
        """
        table = Table(
            title=f"Product: {product}", show_header=True, title_style="bold cyan"
        )
        table.add_column("Contract Month", style="cyan")
        table.add_column("Trader", justify="right")
        table.add_column("Exchange", justify="right")
        table.add_column("Difference", justify="right")
        table.add_column("Status", justify="center")
        table.add_column("Trades (T/E)", justify="center")
        return table

    def _format_comparison_row(
        self, comp: PositionComparison
    ) -> Tuple[str, str, str, str, str]:
        """Format a comparison into table row values.

        Args:
            comp: Position comparison

        Returns:
            Tuple of (trader_str, exchange_str, diff_str, status_str, trade_counts)
        """
        # Format quantities
        trader_str = self._format_quantity(
            comp.trader_quantity,
            comp.unit if comp.trader_quantity != 0 else None,
            show_sign=False,
        )
        exchange_str = self._format_quantity(
            comp.exchange_quantity,
            comp.unit if comp.exchange_quantity != 0 else None,
            show_sign=False,
        )

        # Format difference with unit only if at least one side is non-zero
        diff_unit = (
            comp.unit
            if (comp.trader_quantity != 0 or comp.exchange_quantity != 0)
            else None
        )
        diff_str = self._format_quantity(comp.difference, diff_unit, show_sign=True)

        # Format status and trade counts
        status_str = self._format_status(comp.status)
        trade_counts = f"{comp.trader_trades}/{comp.exchange_trades}"

        return trader_str, exchange_str, diff_str, status_str, trade_counts

    def show_comparison_by_product(self, comparisons: List[PositionComparison]) -> None:
        """Display comparison results grouped by product."""
        # Group by product
        by_product = self._group_comparisons_by_product(comparisons)

        for product, product_comps in sorted(by_product.items()):
            # Skip if all positions are zero
            if all(c.status == MatchStatus.ZERO_POSITION for c in product_comps):
                continue

            # Create table for this product
            table = self._create_product_comparison_table(product)

            # Add rows for each comparison
            for comp in sorted(product_comps, key=lambda x: x.contract_month):
                trader_str, exchange_str, diff_str, status_str, trade_counts = (
                    self._format_comparison_row(comp)
                )

                table.add_row(
                    comp.contract_month,
                    trader_str,
                    exchange_str,
                    diff_str,
                    status_str,
                    trade_counts,
                )

            self.console.print(table)
            self.console.print()  # Add spacing between products

    def show_position_details(
        self, trader_matrix: PositionMatrix, exchange_matrix: PositionMatrix,
        external_match_ids: Optional[Dict[str, str]] = None
    ) -> None:
        """Show detailed trade breakdown for each position.
        
        Args:
            trader_matrix: Trader position matrix
            exchange_matrix: Exchange position matrix
            external_match_ids: Optional mapping of "T_<id>" or "E_<id>" to match IDs
        """
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
                title_style="bold cyan",
            )

            table.add_column("Contract", style="cyan", width=10)
            table.add_column("Source", style="yellow", width=8)
            table.add_column("Internal ID", style="white", width=15)
            table.add_column("Qty", justify="right", width=15)
            table.add_column("Price", justify="right", width=10)
            table.add_column("Broker", justify="center", width=8)
            table.add_column("ClearingAcct", justify="center", width=12)
            table.add_column("Type", style="dim", width=10)
            table.add_column("Match", style="green", width=20)

            sorted_months = sorted(months)
            for i, month in enumerate(sorted_months):
                # Collect trades for this month
                trader_trades = []
                exchange_trades = []

                # Get trader trades
                trader_pos = trader_matrix.get_position(month, product)
                if trader_pos and trader_pos.trade_details:
                    trader_trades = list(trader_pos.trade_details)  # Create a copy

                # Get exchange trades
                exchange_pos = exchange_matrix.get_position(month, product)
                if exchange_pos and exchange_pos.trade_details:
                    exchange_trades = list(exchange_pos.trade_details)  # Create a copy

                # Perform matching if there are trades on both sides
                if trader_trades and exchange_trades:
                    self._match_trades(trader_trades, exchange_trades, external_match_ids)

                # Helper function to add trade rows
                def add_trade_row(detail: Dict[str, Any], source_code: str) -> None:
                    qty_str = self._format_quantity(
                        detail.get("quantity", 0), detail.get("unit"), show_sign=True
                    )

                    # Determine trade type based on rules
                    trade_type = self._determine_trade_type(
                        detail.get("original_product", ""),
                        detail.get("spread_flag", ""),
                    )

                    table.add_row(
                        month,
                        source_code,  # 1 for TRADER, 2 for EXCHANGE
                        detail.get("internal_trade_id", "N/A"),
                        qty_str,
                        f"{detail.get('price', 0):g}",  # Format float, removing trailing zeros
                        detail.get("broker_group_id", ""),
                        detail.get("exch_clearing_acct_id", ""),
                        trade_type,
                        detail.get("match_id", ""),  # Add match ID
                    )

                # Display trader trades
                for detail in trader_trades:
                    add_trade_row(detail, "1")

                # Display exchange trades
                for detail in exchange_trades:
                    add_trade_row(detail, "2")

                # Add separator after each month except the last one
                # Only add if this month had trades
                if i < len(sorted_months) - 1:
                    if (trader_pos and trader_pos.trade_details) or (
                        exchange_pos and exchange_pos.trade_details
                    ):
                        # Add a more visible separator row
                        table.add_row("", "", "", "", "", "", "", "", end_section=True)

            # Only show table if there are trades
            has_trades = False
            for month in months:
                trader_pos = trader_matrix.get_position(month, product)
                exchange_pos = exchange_matrix.get_position(month, product)
                if (trader_pos and trader_pos.trade_details) or (
                    exchange_pos and exchange_pos.trade_details
                ):
                    has_trades = True
                    break

            if has_trades:
                self.console.print(table)
                self.console.print()  # Add spacing between products
