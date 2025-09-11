"""Main entry point for Rule 0: Position Decomposition Analyzer."""

import argparse
import logging
import sys
from decimal import Decimal
from pathlib import Path
from typing import Optional

from rich.console import Console

from src.ice_match.config.config_manager import ConfigManager
from src.ice_match.core.trade_factory import ICETradeFactory
from src.ice_match.models.trade import Trade, TradeSource
from src.ice_match.normalizers.trade_normalizer import TradeNormalizer
from src.ice_match.rule_0.display import PositionDisplay
from src.ice_match.rule_0.matrix_comparator import MatrixComparator
from src.ice_match.rule_0.position_matrix import PositionMatrixBuilder

# Setup logging - default to WARNING to suppress logs unless requested
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Rule0Analyzer:
    """Main analyzer for Rule 0 position decomposition."""

    trader_file: Path
    exchange_file: Path
    config_manager: ConfigManager
    normalizer: TradeNormalizer
    trade_factory: ICETradeFactory
    matrix_builder: PositionMatrixBuilder
    comparator: MatrixComparator
    display: PositionDisplay

    def __init__(
        self, trader_file: Path, exchange_file: Path, config_path: Optional[Path] = None
    ):
        """Initialize the analyzer.

        Args:
            trader_file: Path to trader CSV file
            exchange_file: Path to exchange CSV file
            config_path: Path to normalizer config (optional)
        """
        self.trader_file = trader_file
        self.exchange_file = exchange_file

        # Initialize components
        self.config_manager = ConfigManager.default()
        self.normalizer = TradeNormalizer(self.config_manager)
        self.trade_factory = ICETradeFactory(self.normalizer)
        self.matrix_builder = PositionMatrixBuilder(config_path)

        # Get conversion ratios from config for comparator
        conversion_ratios = self.config_manager.get_product_conversion_ratios()

        # Get the default ratio from config
        default_ratio = Decimal(str(conversion_ratios["default"]))

        # For the comparator, we use the default ratio for BBL tolerance calculation
        self.comparator = MatrixComparator(default_ratio)

        # Get products that use BBL from config
        unit_defaults = self.config_manager.get_traders_product_unit_defaults()
        bbl_products = [
            prod
            for prod, unit in unit_defaults.items()
            if unit.lower() == "bbl" and prod != "default"
        ]
        self.display = PositionDisplay(bbl_products=bbl_products)

        # Set default conversion ratio for Trade model (not used in Rule 0 but needed for compatibility)
        Trade.set_conversion_ratio(default_ratio)

    def run(
        self, contract_month: Optional[str] = None, show_details: bool = False
    ) -> None:
        """Run the position analysis.

        Args:
            contract_month: Optional filter for specific month
            show_details: Whether to show detailed trade breakdown
        """
        console = Console()

        try:
            # Show header
            self.display.show_header()

            # Load trades
            console.print("[cyan]Loading trade data...[/cyan]")
            trader_trades = self._load_trades(self.trader_file, TradeSource.TRADER)
            exchange_trades = self._load_trades(
                self.exchange_file, TradeSource.EXCHANGE
            )

            console.print(
                f"[green]✓[/green] Loaded {len(trader_trades)} trader trades and "
                f"{len(exchange_trades)} exchange trades\n"
            )

            # Build position matrices
            console.print("[cyan]Building position matrices...[/cyan]")
            trader_matrix = self.matrix_builder.build_matrix(trader_trades)
            exchange_matrix = self.matrix_builder.build_matrix(exchange_trades)

            console.print(
                f"[green]✓[/green] Built matrices with {len(trader_matrix.products)} products "
                f"across {len(trader_matrix.contract_months)} contract months\n"
            )

            # Compare matrices
            console.print("[cyan]Comparing positions...[/cyan]\n")
            comparisons = self.comparator.compare_matrices(
                trader_matrix, exchange_matrix
            )

            # Display position matrix
            self.display.show_position_matrix(comparisons, contract_month)

            # Show detailed trade breakdown if requested
            if show_details:
                self.display.show_position_details(trader_matrix, exchange_matrix)

        except FileNotFoundError as e:
            console.print(f"[red]Error: File not found - {e}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            logger.exception("Unexpected error in Rule 0 analysis")
            sys.exit(1)

    def _load_trades(self, filepath: Path, source: TradeSource) -> list[Trade]:
        """Load trades from CSV file.

        Args:
            filepath: Path to CSV file
            source: Trade source (TRADER or EXCHANGE)

        Returns:
            List of trades
        """
        return self.trade_factory.from_csv(filepath, source)


def main() -> None:
    """Main entry point for Rule 0 CLI."""
    parser = argparse.ArgumentParser(
        description="Rule 0: Position Decomposition Analyzer - "
        "Break down complex products and verify positions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run basic position analysis (default to ICE data if no files specified)
  python -m src.ice_match.rule_0.main
  
  # Specify custom files
  python -m src.ice_match.rule_0.main --trader-file data/traders.csv --exchange-file data/exchange.csv
  
  # Filter by specific contract month
  python -m src.ice_match.rule_0.main --month "Sep 25"
  
  # Run with INFO logging to see details
  python -m src.ice_match.rule_0.main --log-level INFO
        """,
    )

    # Optional arguments (default to ICE sample data)
    parser.add_argument(
        "-t",
        "--trader-file",
        type=Path,
        default=Path("src/ice_match/data/sourceTraders.csv"),
        help="Path to trader CSV file (default: src/ice_match/data/sourceTraders.csv)",
    )
    parser.add_argument(
        "-e",
        "--exchange-file",
        type=Path,
        default=Path("src/ice_match/data/sourceExchange.csv"),
        help="Path to exchange CSV file (default: src/ice_match/data/sourceExchange.csv)",
    )

    # Optional arguments
    parser.add_argument(
        "-m",
        "--month",
        dest="contract_month",
        help="Filter by specific contract month (e.g., 'Sep 25')",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to normalizer_config.json (uses default if not specified)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Set the logging level (default: WARNING - no logs shown)",
    )
    parser.add_argument(
        "--show-details",
        action="store_true",
        help="Show detailed trade breakdown for each position",
    )

    args = parser.parse_args()

    # Set logging level based on argument
    log_level = getattr(logging, args.log_level)
    logging.getLogger().setLevel(log_level)

    # Create analyzer and run
    analyzer = Rule0Analyzer(
        trader_file=args.trader_file,
        exchange_file=args.exchange_file,
        config_path=args.config,
    )

    analyzer.run(contract_month=args.contract_month, show_details=args.show_details)


if __name__ == "__main__":
    main()
