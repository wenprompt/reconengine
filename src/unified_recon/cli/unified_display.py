"""Streamlined unified reconciliation display that reuses existing CLI components."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from typing import Dict, List, Any

from ..core.result_aggregator import UnifiedResult, SystemResult

# Import existing display components and configs
from src.ice_match.cli.display import MatchDisplayer
from src.sgx_match.cli.sgx_display import SGXDisplay
from src.cme_match.cli.cme_display import CMEDisplay
from src.eex_match.cli.eex_display import EEXDisplay
from src.ice_match.config.config_manager import ConfigManager


class UnifiedDisplay:
    """Unified display that delegates to existing ICE and SGX CLI components."""

    def __init__(self) -> None:
        """Initialize unified display with existing components."""
        self.console = Console()

    def _create_result_panel(
        self, result: SystemResult, title: str, border_style: str
    ) -> Panel:
        """Create a result panel with consistent formatting.

        Args:
            result: System result data
            title: Panel title
            border_style: Border color style

        Returns:
            Formatted panel
        """
        content = f"📊 Matches: {result.matches_found} | 📈 Rate: {result.match_rate:.1f}% | ⏱️  Time: {result.processing_time:.2f}s"
        return Panel(content, title=title, border_style=border_style)

    def _display_unmatched_trades_generic(
        self,
        result: SystemResult,
        show_unmatched: bool,
        trader_display_func,
        exchange_display_func,
    ) -> None:
        """Generic method to display unmatched trades.

        Args:
            result: System result with statistics
            show_unmatched: Whether to show unmatched trades
            trader_display_func: Function to display trader unmatched trades
            exchange_display_func: Function to display exchange unmatched trades
        """
        if show_unmatched and result.statistics:
            unmatched_trader = result.statistics.get("unmatched_trader_trades", [])
            unmatched_exchange = result.statistics.get("unmatched_exchange_trades", [])

            if unmatched_trader:
                trader_display_func(unmatched_trader)
            if unmatched_exchange:
                exchange_display_func(unmatched_exchange)

    def display_startup_info(self, config: Dict[str, Any]) -> None:
        """Display startup information and configuration."""
        title = Text("🔄 UNIFIED RECONCILIATION SYSTEM", style="bold blue")

        # Create configuration info
        config_info = []
        for group_id, system in config["exchange_group_mappings"].items():
            system_desc = config["system_configs"][system]["description"]
            config_info.append(f"📊 Group {group_id} → {system.upper()}: {system_desc}")

        panel_content = "\n".join(
            [
                "🎯 Data Router for Multiple Exchange Groups",
                "",
                *config_info,
                "",
                f"📁 Data Source: {config['data_settings']['default_data_dir']}",
                f"📄 Files: {config['data_settings']['trader_file']}, {config['data_settings']['exchange_file']}",
            ]
        )

        panel = Panel(panel_content, title=title, border_style="blue", padding=(1, 2))

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def display_data_loading_info(
        self,
        total_trader_count: int,
        total_exchange_count: int,
        group_distribution: Dict[str, Dict[str, Any]],
    ) -> None:
        """Display data loading and grouping information."""
        # Data loading summary
        total_trades = total_trader_count + total_exchange_count

        self.console.print(
            f"Loaded {total_trader_count} trader trades and {total_exchange_count} exchange trades"
        )

        # Show group distribution
        for group_id, info in group_distribution.items():
            group_total = info["trader"] + info["exchange"]
            percentage = (group_total / total_trades * 100) if total_trades > 0 else 0
            self.console.print(
                f"📊 Group {group_id} ({info['system_name']}): "
                f"{info['trader']} trader + {info['exchange']} exchange = {group_total} trades ({percentage:.1f}%)"
            )

        self.console.print()

    def display_group_results(
        self,
        results: List[SystemResult],
        show_details: bool = True,
        show_unmatched: bool = True,
    ) -> None:
        """Display results by delegating to existing system-specific CLI components."""
        for result in results:
            if result.system_name == "ice_match":
                self._display_ice_group_result(result, show_details, show_unmatched)
            elif result.system_name == "sgx_match":
                self._display_sgx_group_result(result, show_details, show_unmatched)
            elif result.system_name == "cme_match":
                self._display_cme_group_result(result, show_details, show_unmatched)
            elif result.system_name == "eex_match":
                self._display_eex_group_result(result, show_details, show_unmatched)
            else:
                self.console.print(f"[red]Unknown system: {result.system_name}[/red]")

    def _display_ice_group_result(
        self, result: SystemResult, show_details: bool, show_unmatched: bool
    ) -> None:
        """Display ICE group results using existing ICE display component."""
        panel = self._create_result_panel(
            result, f"🧊 Group {result.group_id} - ICE Match Results", "green"
        )
        self.console.print(panel)

        if show_details:
            # Reuse ICE display component with minimal config
            # Create a minimal config manager for display purposes
            config_manager = ConfigManager()
            ice_display = MatchDisplayer(config_manager)

            # Display matches by type using existing ICE logic
            if result.detailed_results:
                ice_display.show_matches_by_type(result.detailed_results)

            # Display unmatched trades using generic helper
            self._display_unmatched_trades_generic(
                result,
                show_unmatched,
                lambda trades: ice_display._show_unmatched_trades("Trader", trades),
                lambda trades: ice_display._show_unmatched_trades("Exchange", trades),
            )

    def _display_sgx_group_result(
        self, result: SystemResult, show_details: bool, show_unmatched: bool
    ) -> None:
        """Display SGX group results using existing SGX display component."""
        panel = self._create_result_panel(
            result, f"🏛️  Group {result.group_id} - SGX Match Results", "blue"
        )
        self.console.print(panel)

        if show_details:
            # Reuse SGX display component
            sgx_display = SGXDisplay()

            # Display matches using existing SGX logic (this fixes the product spread display issue)
            if result.detailed_results:
                sgx_display._show_detailed_matches(result.detailed_results)

            # Display unmatched trades using generic helper
            self._display_unmatched_trades_generic(
                result,
                show_unmatched,
                lambda trades: sgx_display._show_unmatched_trader_table(trades),
                lambda trades: sgx_display._show_unmatched_exchange_table(trades),
            )

    def _display_cme_group_result(
        self, result: SystemResult, show_details: bool, show_unmatched: bool
    ) -> None:
        """Display CME group results using existing CME display component."""
        panel = self._create_result_panel(
            result, f"🌽 Group {result.group_id} - CME Match Results", "yellow"
        )
        self.console.print(panel)

        if show_details:
            # Reuse CME display component
            cme_display = CMEDisplay()

            # Display matches using existing CME logic
            if result.detailed_results:
                cme_display._show_detailed_matches(result.detailed_results)

            # Display unmatched trades using generic helper
            self._display_unmatched_trades_generic(
                result,
                show_unmatched,
                lambda trades: cme_display._show_unmatched_trader_trades(trades),
                lambda trades: cme_display._show_unmatched_exchange_trades(trades),
            )

    def _display_eex_group_result(
        self, result: SystemResult, show_details: bool, show_unmatched: bool
    ) -> None:
        """Display EEX group results using existing EEX display component."""
        panel = self._create_result_panel(
            result, f"⚡ Group {result.group_id} - EEX Match Results", "magenta"
        )
        self.console.print(panel)

        if show_details:
            # Reuse EEX display component
            eex_display = EEXDisplay()

            # Display matches using existing EEX logic
            if result.detailed_results:
                eex_display._show_detailed_matches(result.detailed_results)

            # Display unmatched trades using generic helper
            self._display_unmatched_trades_generic(
                result,
                show_unmatched,
                lambda trades: eex_display._show_unmatched_trader_table(trades),
                lambda trades: eex_display._show_unmatched_exchange_table(trades),
            )

    def display_unified_summary(self, unified_result: UnifiedResult) -> None:
        """Display unified summary."""
        # Calculate total processing time from system results
        total_processing_time = sum(
            result.processing_time or 0.0 for result in unified_result.system_results
        )

        summary_lines = [
            f"🎯 Total Systems Processed: {len(unified_result.system_results)}",
            f"📊 Total Matches Found: {unified_result.total_matches_found}",
            f"📈 Overall Match Rate: {unified_result.overall_match_rate:.1f}%",
            f"⏱️  Total Processing Time: {total_processing_time:.2f}s",
        ]

        panel = Panel(
            "\n".join(summary_lines),
            title="🔄 Unified Reconciliation Summary",
            border_style="yellow",
            padding=(1, 2),
        )

        self.console.print(panel)
        self.console.print()

    def display_success(self, message: str) -> None:
        """Display success message."""
        self.console.print(f"[bold green]✅ {message}[/bold green]")

    def display_error(self, title: str, message: str) -> None:
        """Display error message."""
        self.console.print(f"[bold red]❌ {title}:[/bold red] {message}")

    def display_warning(self, message: str) -> None:
        """Display warning message."""
        self.console.print(f"[bold yellow]⚠️  {message}[/bold yellow]")
