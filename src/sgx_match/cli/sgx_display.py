"""Display utilities for SGX trade matching results."""

from typing import List, Dict, Any
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from ..models import SGXMatchResult, SGXTrade

# Display configuration constants
MAX_UNMATCHED_DISPLAY = 100  # Maximum unmatched trades to show


class SGXDisplay:
    """Rich console display for SGX matching results."""

    def __init__(self):
        """Initialize display with Rich console."""
        self.console = Console()

    def show_header(self) -> None:
        """Display SGX matching system header."""
        header = Text("SGX Trade Matching System", style="bold blue")
        subheader = Text("Singapore Exchange Trade Reconciliation", style="italic")

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
        self, matches: List[SGXMatchResult], statistics: Dict[str, Any]
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
            f"{(stats.get('total_matches', 0) / max(stats.get('original_trader_count', 0) + stats.get('original_exchange_count', 0), 1)) * 100:.1f}%",
        )

        self.console.print("\n")
        self.console.print(table)

    def _show_detailed_matches(self, matches: List[SGXMatchResult]) -> None:
        """Show detailed match results, separating single-leg and multi-leg matches."""
        if not matches:
            return

        # Separate single-leg and multi-leg matches in a single pass
        single_leg_matches = []
        spread_matches = []
        product_spread_matches = []

        for match in matches:
            if match.additional_trader_trades or match.additional_exchange_trades:
                if match.match_type.value == "spread":
                    spread_matches.append(match)
                elif match.match_type.value == "product_spread":
                    product_spread_matches.append(match)
            else:
                single_leg_matches.append(match)

        # Show single-leg matches
        if single_leg_matches:
            self._show_single_leg_matches(single_leg_matches)

        # Show spread matches
        if spread_matches:
            self._show_spread_matches(spread_matches)

        # Show product spread matches
        if product_spread_matches:
            self._show_product_spread_matches(product_spread_matches)

    def _show_single_leg_matches(self, matches: List[SGXMatchResult]) -> None:
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
        table.add_column("Status", style="yellow")
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
                match.status.value.title() if match.status else "Matched",
                f"{match.confidence}%",
            )

        self.console.print("\n")
        self.console.print(table)

    def _show_spread_matches(self, matches: List[SGXMatchResult]) -> None:
        """Show multi-leg match results (spreads)."""
        # Import here to avoid circular imports
        from ..utils.trade_helpers import get_month_order_tuple

        table = Table(title=f"Spread Matches ({len(matches)} found)", box=box.ROUNDED)
        table.add_column("Match ID", style="cyan")
        table.add_column("Rule", justify="center")
        table.add_column("Product", style="green")
        table.add_column("Contracts", style="yellow")
        table.add_column("Quantity", justify="right", style="blue")
        table.add_column("Spread Price", justify="right", style="magenta")
        table.add_column("Directions", justify="center")
        table.add_column("Trade IDs (T)", style="dim")
        table.add_column("Trade IDs (E)", style="dim")
        table.add_column("Status", style="yellow")
        table.add_column("Confidence", justify="right", style="bold green")

        for match in matches:
            # Get all trades
            all_trader_trades = [match.trader_trade] + match.additional_trader_trades
            all_exchange_trades = [
                match.exchange_trade
            ] + match.additional_exchange_trades

            # Sort trades chronologically by contract month for consistent display
            # Handle None return values by providing a fallback sort key
            def sort_key(trade):
                order_tuple = get_month_order_tuple(trade.contract_month)
                return (
                    order_tuple if order_tuple is not None else (9999, 99)
                )  # Put invalid dates last

            all_trader_trades.sort(key=sort_key)
            all_exchange_trades.sort(key=sort_key)

            # Format trader IDs (in chronological order)
            trader_ids = " + ".join([trade.display_id for trade in all_trader_trades])

            # Format exchange IDs (in chronological order)
            exchange_ids = " + ".join(
                [trade.display_id for trade in all_exchange_trades]
            )

            # Format contract months (chronologically sorted)
            trader_months = [trade.contract_month for trade in all_trader_trades]
            contract_display = "/".join(trader_months)

            # Format directions (B/S for each leg in chronological order)
            trader_directions = [trade.buy_sell for trade in all_trader_trades]
            exchange_directions = [trade.buy_sell for trade in all_exchange_trades]
            directions = (
                f"{'/'.join(trader_directions)}↔{'/'.join(exchange_directions)}"
            )

            # Use spread price from trader (should be same for both legs in new pattern)
            spread_price = match.trader_trade.price

            table.add_row(
                match.match_id,
                str(match.rule_order),
                match.matched_product,
                contract_display,
                str(match.matched_quantity),
                str(spread_price),
                directions,
                trader_ids,
                exchange_ids,
                match.status.value.title() if match.status else "Matched",
                f"{match.confidence}%",
            )

        self.console.print("\n")
        self.console.print(table)

    def _show_product_spread_matches(self, matches: List[SGXMatchResult]) -> None:
        """Show product spread match results."""
        # Import here to avoid circular imports

        table = Table(
            title=f"Product Spread Matches ({len(matches)} found)", box=box.ROUNDED
        )
        table.add_column("Match ID", style="cyan")
        table.add_column("Rule", justify="center")
        table.add_column("Products", style="green")
        table.add_column("Contract", style="yellow")
        table.add_column("Quantity", justify="right", style="blue")
        table.add_column("Spread Price", justify="right", style="magenta")
        table.add_column("Directions", justify="center")
        table.add_column("Trade IDs (T)", style="dim")
        table.add_column("Trade IDs (E)", style="dim")
        table.add_column("Status", style="yellow")
        table.add_column("Confidence", justify="right", style="bold green")

        for match in matches:
            # Get all trades
            all_trader_trades = [match.trader_trade] + match.additional_trader_trades
            all_exchange_trades = [
                match.exchange_trade
            ] + match.additional_exchange_trades

            # Sort trades alphabetically by product for consistent display
            all_trader_trades.sort(key=lambda t: t.product_name)
            all_exchange_trades.sort(key=lambda t: t.product_name)

            # Format trader IDs (in alphabetical product order)
            trader_ids = " + ".join([trade.display_id for trade in all_trader_trades])

            # Format exchange IDs (in alphabetical product order)
            exchange_ids = " + ".join(
                [trade.display_id for trade in all_exchange_trades]
            )

            # Format products (alphabetically sorted)
            trader_products = [trade.product_name for trade in all_trader_trades]
            product_display = "/".join(trader_products)

            # Format directions (B/S for each product in alphabetical order)
            trader_directions = [trade.buy_sell for trade in all_trader_trades]
            exchange_directions = [trade.buy_sell for trade in all_exchange_trades]
            directions = (
                f"{'/'.join(trader_directions)}↔{'/'.join(exchange_directions)}"
            )

            # Use spread price from trader (should be same for both legs in product spread)
            spread_price = match.trader_trade.price

            # Contract month should be same for all trades
            contract_month = match.trader_trade.contract_month

            table.add_row(
                match.match_id,
                str(match.rule_order),
                product_display,
                contract_month,
                str(match.matched_quantity),
                str(spread_price),
                directions,
                trader_ids,
                exchange_ids,
                match.status.value.title() if match.status else "Matched",
                f"{match.confidence}%",
            )

        self.console.print("\n")
        self.console.print(table)

    def show_unmatched_trades(
        self, trader_trades: List[SGXTrade], exchange_trades: List[SGXTrade]
    ) -> None:
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
        min(len(trades), MAX_UNMATCHED_DISPLAY)
        title = f"Unmatched Trader Trades ({len(trades)})"
        if len(trades) > MAX_UNMATCHED_DISPLAY:
            title += f" - Showing first {MAX_UNMATCHED_DISPLAY}"
        table = Table(title=title, box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Product", style="green")
        table.add_column("Contract", style="yellow")
        table.add_column("Quantity", justify="right", style="blue")
        table.add_column("Price", justify="right", style="magenta")
        table.add_column("B/S", justify="center")
        table.add_column("Trade Time", style="dim")
        table.add_column("Broker Group", justify="right")

        for trade in trades[:MAX_UNMATCHED_DISPLAY]:  # Limit display for performance
            table.add_row(
                trade.display_id,
                trade.product_name,
                trade.contract_month,
                str(trade.quantityunit),
                str(trade.price),
                trade.buy_sell,
                trade.trade_time or "",
                str(trade.broker_group_id or ""),
            )

        self.console.print("\n")
        self.console.print(table)

    def _show_unmatched_exchange_table(self, trades: List[SGXTrade]) -> None:
        """Show unmatched exchange trades table."""
        min(len(trades), MAX_UNMATCHED_DISPLAY)
        title = f"Unmatched Exchange Trades ({len(trades)})"
        if len(trades) > MAX_UNMATCHED_DISPLAY:
            title += f" - Showing first {MAX_UNMATCHED_DISPLAY}"
        table = Table(title=title, box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Deal ID", justify="right")
        table.add_column("Product", style="green")
        table.add_column("Contract", style="yellow")
        table.add_column("Quantity", justify="right", style="blue")
        table.add_column("Price", justify="right", style="magenta")
        table.add_column("B/S", justify="center")
        table.add_column("Trader ID", style="dim")

        for trade in trades[:MAX_UNMATCHED_DISPLAY]:  # Limit display for performance
            table.add_row(
                trade.display_id,
                str(trade.deal_id or ""),
                trade.product_name,
                trade.contract_month,
                str(trade.quantityunit),
                str(trade.price),
                trade.buy_sell,
                trade.trader_id or "",
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

    def show_rules_information(self, rules_info: List[Dict[str, Any]]) -> None:
        """Display detailed information about matching rules.

        Args:
            rules_info: List of rule information dictionaries
        """
        self.console.print("\n")

        # Header
        header = Text("SGX Trade Matching Rules", style="bold blue")
        self.console.print(Panel.fit(header, border_style="blue"))

        # Rules table
        table = Table(title="Rule Overview", box=box.ROUNDED)
        table.add_column("Rule", justify="center", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Type", style="green")
        table.add_column("Confidence", justify="right", style="yellow")
        table.add_column("Description", style="dim")

        for rule in rules_info:
            table.add_row(
                str(rule.get("rule_number", "N/A")),
                rule.get("rule_name", "Unknown"),
                rule.get("match_type", "unknown"),
                f"{rule.get('confidence', 0):.1f}%",
                rule.get("description", "No description available"),
            )

        self.console.print("\n")
        self.console.print(table)

        # Detailed requirements for each rule
        for rule in rules_info:
            self._show_rule_details(rule)

    def _show_rule_details(self, rule: Dict[str, Any]) -> None:
        """Show detailed requirements for a single rule.

        Args:
            rule: Rule information dictionary
        """
        rule_name = rule.get("rule_name", "Unknown Rule")
        rule_number = rule.get("rule_number", "N/A")

        # Requirements
        requirements = rule.get("requirements", [])

        if requirements:
            req_text = "\n".join([f"• {req}" for req in requirements])

            panel_content = Group(
                Text(f"Rule {rule_number}: {rule_name}", style="bold cyan"),
                Text(""),
                Text("Requirements:", style="bold"),
                Text(req_text, style="dim"),
            )

            self.console.print("\n")
            self.console.print(
                Panel(
                    panel_content,
                    title=f"Rule {rule_number}",
                    border_style="green",
                    padding=(1, 2),
                )
            )
