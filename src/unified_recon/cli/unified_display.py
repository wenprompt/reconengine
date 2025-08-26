"""Rich CLI display for unified reconciliation system."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich import box
from typing import Dict, List, Any, Optional, TYPE_CHECKING
import time

if TYPE_CHECKING:
    import pandas as pd

from ..core.result_aggregator import UnifiedResult, SystemResult

console = Console()

# Constants
MAX_UNMATCHED_DISPLAY = 50


class UnifiedDisplay:
    """Rich terminal display for unified reconciliation results."""
    
    def __init__(self) -> None:
        """Initialize unified display."""
        self.console = Console()
    
    def display_startup_info(self, config: Dict[str, Any]) -> None:
        """Display startup information and configuration. 
        
        Args:
            config: Unified configuration dictionary
        """
        title = Text("🔄 UNIFIED RECONCILIATION SYSTEM", style="bold blue")
        
        # Create configuration info
        config_info = []
        for group_id, system in config['exchange_group_mappings'].items():
            system_desc = config['system_configs'][system]['description']
            config_info.append(f"📊 Group {group_id} → {system.upper()}: {system_desc}")
        
        panel_content = "\n".join([
            "🎯 Data Router for Multiple Exchange Groups",
            "",
            *config_info,
            "",
            f"📁 Data Source: {config['data_settings']['default_data_dir']}",
            f"📄 Files: {config['data_settings']['trader_file']}, {config['data_settings']['exchange_file']}"
        ])
        
        panel = Panel(
            panel_content,
            title="System Configuration", 
            border_style="blue"
        )
        
        self.console.print()
        self.console.print(title, justify="center")
        self.console.print(panel)
        self.console.print()
    
    def display_data_loading_info(self, trader_count: int, exchange_count: int, group_distribution: Dict[int, Dict[str, Any]]) -> None:
        """Display data loading information. 
        
        Args:
            trader_count: Total trader trades loaded
            exchange_count: Total exchange trades loaded  
            group_distribution: Dict mapping group_id to trade counts and system name
        """
        # Create data summary table
        table = Table(title="📊 Data Loading Summary", show_header=True, header_style="bold magenta")
        table.add_column("Exchange Group", style="cyan", width=15)
        table.add_column("System Routed To", style="green", width=50)
        table.add_column("Trader Trades", justify="right", style="yellow", width=14)
        table.add_column("Exchange Trades", justify="right", style="yellow", width=16) 
        table.add_column("Status", style="green", width=12)
        
        for group_id, counts in group_distribution.items():
            # Use the system name passed in from the router, which respects the config file
            system_name = str(counts.get('system_name', 'Unknown'))
            status = "✅ Ready" if counts.get('trader', 0) > 0 and counts.get('exchange', 0) > 0 else "⚠️ No Data"
            
            table.add_row(
                str(group_id),
                system_name,
                str(counts.get('trader', 0)),
                str(counts.get('exchange', 0)),
                status
            )
        
        # Add totals row
        table.add_row(
            "TOTAL", 
            "All Systems",
            str(trader_count), 
            str(exchange_count),
            "📋 Loaded",
            style="bold"
        )
        
        self.console.print(table)
        self.console.print()
    
    def display_processing_progress(self, groups: List[int], systems: Dict[int, str]) -> Progress:
        """Create and display processing progress. 
        
        Args:
            groups: List of exchange group IDs to process
            systems: Mapping of group ID to system name
            
        Returns:
            Progress object for updating
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        )
        
        progress.start()
        
        # Add tasks for each group
        for group_id in groups:
            system_name = systems.get(group_id, 'Unknown')
            task_id = progress.add_task(
                f"Group {group_id} ({system_name}): Preparing...", 
                total=None
            )
        
        return progress
    
    def display_group_results(self, results: List[SystemResult], show_details: bool = True, show_unmatched: bool = True) -> None:
        """Display results for individual exchange groups. 
        
        Args:
            results: List of SystemResult objects
            show_details: Whether to show detailed statistics
            show_unmatched: Whether to show unmatched trades
        """
        for result in results:
            # Create system-specific panel
            system_color = "green" if result.system_name == "ice_match" else "blue"
            
            # Basic stats
            stats_lines = [
                f"📊 Matches Found: {result.matches_found}",
                f"📈 Match Rate: {result.match_rate:.1f}%",
                f"🔢 Trader Trades: {result.trader_count}",
                f"🔢 Exchange Trades: {result.exchange_count}"
            ]
            
            if result.processing_time:
                stats_lines.append(f"⏱️ Processing Time: {result.processing_time:.2f}s")
            
            # Add system-specific details if available
            if show_details and result.statistics:
                stats_lines.append("")
                if result.system_name == "ice_match" and "rule_breakdown" in result.statistics:
                    stats_lines.append("🎯 ICE Rules Breakdown:")
                    for rule, count in result.statistics["rule_breakdown"].items():
                        stats_lines.append(f"   Rule {rule}: {count} matches")
                elif result.system_name == "sgx_match":
                    stats_lines.append("🎯 SGX Exact Matching")
            
            panel_content = "\n".join(stats_lines)
            
            panel = Panel(
                panel_content,
                title=f"Group {result.group_id} - {result.system_name.upper()} Results",
                border_style=system_color
            )
            
            self.console.print(panel)
            
            # Display detailed results if available and details requested
            if show_details:
                # ICE system - show matches and DataFrame
                if result.system_name == "ice_match" and result.detailed_results:
                    self.display_ice_matches(result.detailed_results)
                    if result.statistics and "reconciliation_dataframe" in result.statistics:
                        self.display_reconciliation_dataframe(result.statistics["reconciliation_dataframe"])
                    if show_unmatched and result.statistics and "unmatched_trader_trades" in result.statistics and "unmatched_exchange_trades" in result.statistics:
                        self.display_ice_unmatched_trades(
                            result.statistics["unmatched_trader_trades"],
                            result.statistics["unmatched_exchange_trades"]
                        )
                # SGX system - show match table and unmatched trades
                elif result.detailed_results and result.system_name == "sgx_match":
                    self.display_sgx_matches(result.detailed_results)
                    if show_unmatched and result.statistics and "unmatched_trader_trades" in result.statistics and "unmatched_exchange_trades" in result.statistics:
                        self.display_sgx_unmatched_trades(
                            result.statistics["unmatched_trader_trades"],
                            result.statistics["unmatched_exchange_trades"]
                        )
        
        self.console.print()
    
    def display_reconciliation_dataframe(self, df: "pd.DataFrame") -> None:
        """Display reconciliation DataFrame with basic Rich formatting."""
        if df is None:
            self.console.print("[yellow]No DataFrame to display[/yellow]")
            return
            
        try:
            # Simple display without deep ICE coupling
            import pandas as pd
            
            if df.empty:
                self.console.print("📊 Reconciliation DataFrame: No data to display", style="yellow")
                return
            
            self.console.print(f"\n📊 ICE Reconciliation DataFrame ({len(df)} records)", style="bold cyan")
            
            # Create a simple table showing key metrics
            from rich.table import Table
            
            table = Table(title="DataFrame Summary", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Count", justify="right", style="green")
            
            if 'reconStatus' in df.columns:
                total = len(df)
                matched = len(df[df['reconStatus'] == 'matched'])
                table.add_row("Total Records", str(total))
                table.add_row("Matched Records", str(matched))
                table.add_row("Match Rate", f"{matched/total*100:.1f}%" if total > 0 else "0%")
            else:
                table.add_row("Total Records", str(len(df)))
            
            self.console.print()
            self.console.print(table)
            self.console.print("[dim]📋 Full ICE DataFrame details available in ICE-specific output[/dim]")
            
        except Exception as e:
            self.console.print(f"[yellow]DataFrame display error: {e}[/yellow]")

    
    def display_ice_matches(self, matches: List[Any]) -> None:
        """Display ICE matches in a table format similar to ICE system."""
        
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
        table.add_column("Match Type", style="white")
        
        for match in matches:
            # Handle different ICE match structures
            trader_id = match.trader_trade.display_id if hasattr(match.trader_trade, 'display_id') else str(match.trader_trade.trade_id)
            exchange_id = match.exchange_trade.display_id if hasattr(match.exchange_trade, 'display_id') else str(match.exchange_trade.trade_id)
            
            table.add_row(
                match.match_id,
                str(match.rule_order),
                match.trader_trade.product_name,
                match.trader_trade.contract_month,
                f"{match.trader_trade.quantity}{match.trader_trade.unit}",
                str(match.trader_trade.price),
                match.trader_trade.buy_sell,
                trader_id,
                exchange_id,
                f"{match.confidence}%",
                match.match_type.value if hasattr(match.match_type, 'value') else str(match.match_type)
            )
        
        self.console.print()
        self.console.print(table)

    def display_ice_unmatched_trades(self, trader_trades: List[Any], exchange_trades: List[Any]) -> None:
        """Display ICE unmatched trades similar to ICE system."""
        
        if trader_trades:
            title = f"Unmatched Trader Trades ({len(trader_trades)})"
            if len(trader_trades) > MAX_UNMATCHED_DISPLAY:
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
            table.add_column("Unit", style="dim")
            
            for trade in trader_trades[:MAX_UNMATCHED_DISPLAY]:
                # Handle ICE trade structure
                trade_id = trade.display_id if hasattr(trade, 'display_id') else str(trade.trade_id)
                trade_time = trade.trade_time or "" if hasattr(trade, 'trade_time') else ""
                broker_group = str(trade.broker_group_id or "") if hasattr(trade, 'broker_group_id') else ""
                unit = str(trade.unit or "") if hasattr(trade, 'unit') else ""
                
                table.add_row(
                    trade_id,
                    trade.product_name,
                    trade.contract_month,
                    f"{trade.quantity}{trade.unit}",
                    str(trade.price),
                    trade.buy_sell,
                    trade_time,
                    broker_group,
                    unit
                )
            
            self.console.print()
            self.console.print(table)
        
        if exchange_trades:
            title = f"Unmatched Exchange Trades ({len(exchange_trades)})"
            if len(exchange_trades) > MAX_UNMATCHED_DISPLAY:
                title += f" - Showing first {MAX_UNMATCHED_DISPLAY}"
                
            table = Table(title=title, box=box.ROUNDED)
            table.add_column("ID", style="cyan")
            table.add_column("Deal ID", justify="right")
            table.add_column("Product", style="green")
            table.add_column("Contract", style="yellow")
            table.add_column("Quantity", justify="right", style="blue")
            table.add_column("Price", justify="right", style="magenta")
            table.add_column("B/S", justify="center")
            table.add_column("Unit", style="dim")
            
            for trade in exchange_trades[:MAX_UNMATCHED_DISPLAY]:
                # Handle ICE trade structure
                trade_id = trade.display_id if hasattr(trade, 'display_id') else str(trade.trade_id)
                deal_id = str(trade.deal_id or "") if hasattr(trade, 'deal_id') else ""
                unit = str(trade.unit or "") if hasattr(trade, 'unit') else ""
                
                table.add_row(
                    trade_id,
                    deal_id,
                    trade.product_name,
                    trade.contract_month,
                    f"{trade.quantity}{trade.unit}",
                    str(trade.price),
                    trade.buy_sell,
                    unit
                )
            
            self.console.print()
            self.console.print(table)

    
    def display_sgx_matches(self, matches: List[Any]) -> None:
        """Display SGX matches in a table format similar to SGX system."""
        
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
        
        self.console.print()
        self.console.print(table)

    
    def display_sgx_unmatched_trades(self, trader_trades: List[Any], exchange_trades: List[Any]) -> None:
        """Display SGX unmatched trades similar to SGX system."""
        
        if trader_trades:
            title = f"Unmatched Trader Trades ({len(trader_trades)})"
            if len(trader_trades) > MAX_UNMATCHED_DISPLAY:
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
            table.add_column("Remarks", style="dim")
            
            for trade in trader_trades[:MAX_UNMATCHED_DISPLAY]:
                table.add_row(
                    trade.display_id,
                    trade.product_name,
                    trade.contract_month,
                    f"{trade.quantity}{trade.unit}",
                    str(trade.price),
                    trade.buy_sell,
                    trade.trade_time or "",
                    str(trade.broker_group_id or ""),
                    trade.remarks or ""
                )
            
            self.console.print()
            self.console.print(table)
        
        if exchange_trades:
            title = f"Unmatched Exchange Trades ({len(exchange_trades)})"
            if len(exchange_trades) > MAX_UNMATCHED_DISPLAY:
                title += f" - Showing first {MAX_UNMATCHED_DISPLAY}"
                
            table = Table(title=title, box=box.ROUNDED)
            table.add_column("ID", style="cyan")
            table.add_column("Deal ID", justify="right")
            table.add_column("Product", style="green")
            table.add_column("Contract", style="yellow")
            table.add_column("Quantity", justify="right", style="blue")
            table.add_column("Price", justify="right", style="magenta")
            table.add_column("B/S", justify="center")
            table.add_column("Trader", style="dim")
            
            for trade in exchange_trades[:MAX_UNMATCHED_DISPLAY]:
                table.add_row(
                    trade.display_id,
                    str(trade.deal_id or ""),
                    trade.product_name,
                    trade.contract_month,
                    f"{trade.quantity}{trade.unit}",
                    str(trade.price),
                    trade.buy_sell,
                    trade.trader_name or ""
                )
            
            self.console.print()
            self.console.print(table)
    
    def display_unified_summary(self, unified_result: UnifiedResult) -> None:
        """Display unified summary of all results. 
        
        Args:
            unified_result: Aggregated results from all systems
        """
        # Create summary statistics table
        table = Table(title="🎯 UNIFIED RECONCILIATION SUMMARY", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="white", width=25)
        table.add_column("Value", justify="right", style="bold green", width=15)
        
        table.add_row("Groups Processed", str(unified_result.total_groups_processed))
        table.add_row("Total Matches", str(unified_result.total_matches_found))
        table.add_row("Overall Match Rate", f"{unified_result.overall_match_rate:.1f}%")
        table.add_row("Total Trader Trades", str(unified_result.total_trader_trades))
        table.add_row("Total Exchange Trades", str(unified_result.total_exchange_trades))
        
        if unified_result.processing_summary.get('total_processing_time'):
            table.add_row("Total Processing Time", f"{unified_result.processing_summary['total_processing_time']:.2f}s")
        
        self.console.print(table)
        
        # Create system breakdown table
        if unified_result.processing_summary.get('system_breakdown'):
            breakdown_table = Table(title="📊 System Performance Breakdown", show_header=True, header_style="bold magenta")
            breakdown_table.add_column("System", style="cyan", width=12)
            breakdown_table.add_column("Groups", justify="right", style="yellow", width=8)
            breakdown_table.add_column("Matches", justify="right", style="green", width=10)
            breakdown_table.add_column("Match Rate", justify="right", style="green", width=12)
            breakdown_table.add_column("Trader Trades", justify="right", style="blue", width=14)
            breakdown_table.add_column("Exchange Trades", justify="right", style="blue", width=16)
            
            for system, stats in unified_result.processing_summary['system_breakdown'].items():
                breakdown_table.add_row(
                    system.upper(),
                    str(stats['groups']),
                    str(stats['matches']),
                    f"{stats['avg_match_rate']:.1f}%",
                    str(stats['trader_trades']),
                    str(stats['exchange_trades'])
                )
            
            self.console.print()
            self.console.print(breakdown_table)
        
        self.console.print()
    
    def display_error(self, error_msg: str, details: Optional[str] = None) -> None:
        """Display error message. 
        
        Args:
            error_msg: Main error message
            details: Optional additional details
        """
        content = f"❌ {error_msg}"
        if details:
            content += f"\n\n🔍 Details: {details}"
        
        panel = Panel(
            content,
            title="Error",
            border_style="red"
        )
        
        self.console.print(panel, style="red")
        self.console.print()
    
    def display_warning(self, warning_msg: str) -> None:
        """Display warning message. 
        
        Args:
            warning_msg: Warning message to display
        """
        panel = Panel(
            f"⚠️ {warning_msg}",
            title="Warning",
            border_style="yellow"
        )
        
        self.console.print(panel, style="yellow")
        self.console.print()
    
    def display_success(self, success_msg: str) -> None:
        """Display success message. 
        
        Args:
            success_msg: Success message to display
        """
        panel = Panel(
            f"✅ {success_msg}",
            title="Success",
            border_style="green"
        )
        
        self.console.print(panel, style="green")
        self.console.print()
