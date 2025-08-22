"""Main application entry point for ice trade matching system."""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from decimal import Decimal

from .models import MatchResult, Trade
from .loaders import CSVTradeLoader
from .normalizers import TradeNormalizer
from .config import ConfigManager
from .core import UnmatchedPoolManager
from .matchers import (
    ExactMatcher,
    SpreadMatcher,
    CrackMatcher,
    ComplexCrackMatcher,
    ProductSpreadMatcher,
    AggregationMatcher,
    AggregatedComplexCrackMatcher,
    AggregatedSpreadMatcher,
    AggregatedCrackMatcher,
    ComplexCrackRollMatcher,
    AggregatedProductSpreadMatcher,
)
from .cli import MatchDisplayer
from .utils.dataframe_output import create_reconciliation_dataframe, display_reconciliation_dataframe

# Default file paths and constants - package-relative
DEFAULT_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_TRADER_FILE = "sourceTraders.csv"
DEFAULT_EXCHANGE_FILE = "sourceExchange.csv"


def setup_logging(log_level: str = "INFO", show_logs: bool = False):
    """Setup logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        show_logs: Whether to show log output to console
    """
    if show_logs:
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )
    else:
        # Disable console logging, only keep ERROR and above
        logging.basicConfig(level=logging.ERROR, handlers=[logging.NullHandler()])


class ICEMatchingEngine:
    """Main engine for ice trade matching system.

    Orchestrates the complete matching process from data loading through
    result display with proper non-duplication handling.
    """

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        show_logs: bool = False,
    ):
        """Initialize the matching engine.

        Args:
            config_manager: Optional configuration manager, uses defaults if None
            show_logs: Whether to show log output to console
        """
        self.config_manager = config_manager or ConfigManager.default()
        self.normalizer = TradeNormalizer(self.config_manager)
        self.loader = CSVTradeLoader(self.normalizer)  # Pass normalizer to loader
        self.displayer = MatchDisplayer(self.config_manager)

        # Setup logging
        setup_logging(self.config_manager.config.log_level, show_logs)
        self.logger = logging.getLogger(__name__)

    def run_matching(
        self,
        trader_csv_path: Path,
        exchange_csv_path: Path,
    ) -> List[MatchResult]:
        """Run the complete matching process.

        Args:
            trader_csv_path: Path to trader CSV file
            exchange_csv_path: Path to exchange CSV file

        Returns:
            List of all matches found

        Raises:
            FileNotFoundError: If CSV files don't exist
            ValueError: If CSV data is invalid
        """
        start_time = time.time()
        execution_datetime = datetime.now()

        try:
            # Show header
            self.displayer.show_header()
            self.displayer.show_configuration()

            # Set conversion ratio for all Trade instances
            Trade.set_conversion_ratio(self.config_manager.get_conversion_ratio())

            # Step 1: Load data
            self.logger.info("Loading trade data...")
            with self.displayer.create_progress_context(
                "Loading CSV data..."
            ) as progress:
                task = progress.add_task("Loading...", total=None)

                trader_trades, exchange_trades = self.loader.load_both_files(
                    trader_csv_path, exchange_csv_path
                )

                progress.remove_task(task)

            self.displayer.show_data_summary(len(trader_trades), len(exchange_trades))

            # Step 2: Normalize data (happens in Trade model)
            self.logger.info("Data normalization handled by Trade models")

            # Step 3: Initialize pool manager
            self.logger.info("Initializing unmatched pool manager...")
            pool_manager = UnmatchedPoolManager(trader_trades, exchange_trades)

            # Step 4: Apply matching rules in order (Rules 1, 2, and 3)
            all_matches = []

            # Rule 1: Exact matching
            self.logger.info("Applying Rule 1: Exact matching...")
            exact_matcher = ExactMatcher(self.config_manager)
            exact_matches = exact_matcher.find_matches(pool_manager)
            all_matches.extend(exact_matches)

            # Rule 2: Spread matching
            self.logger.info("Applying Rule 2: Spread matching...")
            spread_matcher = SpreadMatcher(self.config_manager, self.normalizer)
            spread_matches = spread_matcher.find_matches(pool_manager)
            all_matches.extend(spread_matches)

            # Rule 3: Crack matching
            self.logger.info("Applying Rule 3: Crack matching...")
            crack_matcher = CrackMatcher(self.config_manager, self.normalizer)
            crack_matches = crack_matcher.find_matches(pool_manager)
            all_matches.extend(crack_matches)

            # Rule 4: Complex crack matching
            self.logger.info("Applying Rule 4: Complex crack matching...")
            complex_crack_matcher = ComplexCrackMatcher(
                self.config_manager, self.normalizer
            )
            complex_crack_matches = complex_crack_matcher.find_matches(
                pool_manager  # Pass pool_manager directly
            )
            all_matches.extend(complex_crack_matches)

            # Rule 5: Product spread matching
            self.logger.info("Applying Rule 5: Product spread matching...")
            product_spread_matcher = ProductSpreadMatcher(
                self.config_manager, self.normalizer
            )
            product_spread_matches = product_spread_matcher.find_matches(
                pool_manager
            )
            all_matches.extend(product_spread_matches)

            # Rule 6: Aggregation matching
            self.logger.info("Applying Rule 6: Aggregation matching...")
            aggregation_matcher = AggregationMatcher(self.config_manager)
            aggregation_matches = aggregation_matcher.find_matches(pool_manager)
            all_matches.extend(aggregation_matches)

            # Rule 7: Aggregated complex crack matching
            self.logger.info("Applying Rule 7: Aggregated complex crack matching...")
            aggregated_complex_crack_matcher = AggregatedComplexCrackMatcher(
                self.config_manager, self.normalizer
            )
            aggregated_complex_crack_matches = aggregated_complex_crack_matcher.find_matches(pool_manager)
            all_matches.extend(aggregated_complex_crack_matches)

            # Rule 8: Aggregated spread matching
            self.logger.info("Applying Rule 8: Aggregated spread matching...")
            aggregated_spread_matcher = AggregatedSpreadMatcher(
                self.config_manager, self.normalizer
            )
            aggregated_spread_matches = aggregated_spread_matcher.find_matches(
                pool_manager
            )
            all_matches.extend(aggregated_spread_matches)

            # Rule 9: Aggregated crack matching
            self.logger.info("Applying Rule 9: Aggregated crack matching...")
            aggregated_crack_matcher = AggregatedCrackMatcher(
                self.config_manager, self.normalizer
            )
            aggregated_crack_matches = aggregated_crack_matcher.find_matches(
                pool_manager
            )
            all_matches.extend(aggregated_crack_matches)

            # Rule 10: Complex crack roll matching
            self.logger.info("Applying Rule 10: Complex crack roll matching...")
            complex_crack_roll_matcher = ComplexCrackRollMatcher(
                self.config_manager, self.normalizer
            )
            complex_crack_roll_matches = complex_crack_roll_matcher.find_matches(pool_manager)
            all_matches.extend(complex_crack_roll_matches)

            # Rule 11: Aggregated product spread matching
            self.logger.info("Applying Rule 11: Aggregated product spread matching...")
            aggregated_product_spread_matcher = AggregatedProductSpreadMatcher(
                self.config_manager, self.normalizer
            )
            aggregated_product_spread_matches = aggregated_product_spread_matcher.find_matches(
                pool_manager
            )
            all_matches.extend(aggregated_product_spread_matches)

            # Step 5: Display results
            self.logger.info("Displaying results...")

            # Show matches by type
            self.displayer.show_matches_by_type(all_matches)

            # Show unmatched summary
            if self.config_manager.config.show_unmatched:
                self.displayer.show_unmatched_summary(pool_manager)
                # Show ALL detailed unmatched trades
                self.displayer.show_detailed_unmatched(pool_manager, limit=None)

            # Show statistics
            if self.config_manager.config.show_statistics:
                self.displayer.show_statistics(pool_manager, all_matches)

            # Show completion
            processing_time = time.time() - start_time
            self.displayer.show_processing_complete(processing_time)

            # Generate and display standardized reconciliation DataFrame
            try:
                recon_df = create_reconciliation_dataframe(all_matches, pool_manager, execution_datetime)
                display_reconciliation_dataframe(recon_df)
            except Exception as df_error:
                self.logger.warning(f"Could not generate reconciliation DataFrame: {df_error}")

            # Validate pool integrity
            if not pool_manager.validate_integrity():
                self.logger.error("Pool integrity validation failed!")

            return all_matches

        except Exception as e:
            self.logger.error(f"Error during matching process: {e}")
            self.displayer.show_error(str(e))
            raise

    def get_match_summary(self, matches: List[MatchResult]) -> dict:
        """Get summary statistics for matches.

        Args:
            matches: List of matches to summarize

        Returns:
            Dictionary with match summary statistics
        """
        if not matches:
            return {"total_matches": 0, "by_type": {}, "avg_confidence": 0}

        # Group by type
        by_type = {}
        total_confidence = Decimal(0)

        for match in matches:
            match_type = match.match_type.value
            if match_type not in by_type:
                by_type[match_type] = 0
            by_type[match_type] += 1
            total_confidence += match.confidence

        avg_confidence = total_confidence / len(matches)

        return {
            "total_matches": len(matches),
            "by_type": by_type,
            "avg_confidence": float(avg_confidence),
        }


def main():
    """Main entry point for command line execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="ICE Trade Matching System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m ice_match.main                              # Use default sample data
  python -m ice_match.main --log-level DEBUG            # Use default data with debug logging
  python -m ice_match.main data/traders.csv data/exchange.csv    # Use custom files
  python -m ice_match.main --show-logs custom_traders.csv custom_exchange.csv
        """,
    )

    parser.add_argument(
        "trader_csv",
        type=Path,
        nargs="?",
        default=DEFAULT_DATA_DIR / DEFAULT_TRADER_FILE,
        help=f"Path to trader CSV file (default: {DEFAULT_DATA_DIR / DEFAULT_TRADER_FILE})",
    )

    parser.add_argument(
        "exchange_csv",
        type=Path,
        nargs="?",
        default=DEFAULT_DATA_DIR / DEFAULT_EXCHANGE_FILE,
        help=f"Path to exchange CSV file (default: {DEFAULT_DATA_DIR / DEFAULT_EXCHANGE_FILE})",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",  # Reverted default to INFO
        help="Set logging level (default: INFO)",
    )

    parser.add_argument(
        "--no-unmatched", action="store_true", help="Don't show unmatched trades"
    )

    parser.add_argument("--no-stats", action="store_true", help="Don't show statistics")

    parser.add_argument(
        "--show-logs", action="store_true", help="Show detailed logging output"
    )

    parser.add_argument(
        "--show-rules",
        action="store_true",
        help="Display information about all matching rules.",
    )

    args = parser.parse_args()

    # Validate file paths
    if not args.trader_csv.exists():
        print(f"Error: Trader CSV file not found: {args.trader_csv}")
        return 1

    if not args.exchange_csv.exists():
        print(f"Error: Exchange CSV file not found: {args.exchange_csv}")
        return 1

    # Handle --show-rules argument
    if args.show_rules:
        # Initialize necessary components to get rule info
        config_manager = ConfigManager.default()
        normalizer = TradeNormalizer(config_manager)

        # Create instances of your matchers
        exact_matcher = ExactMatcher(config_manager)
        spread_matcher = SpreadMatcher(config_manager, normalizer)
        crack_matcher = CrackMatcher(config_manager, normalizer)
        complex_crack_matcher = ComplexCrackMatcher(config_manager, normalizer)
        product_spread_matcher = ProductSpreadMatcher(config_manager, normalizer)
        aggregation_matcher = AggregationMatcher(config_manager)
        aggregated_complex_crack_matcher = AggregatedComplexCrackMatcher(
            config_manager, normalizer
        )
        aggregated_spread_matcher = AggregatedSpreadMatcher(config_manager, normalizer)
        aggregated_crack_matcher = AggregatedCrackMatcher(config_manager, normalizer)
        complex_crack_roll_matcher = ComplexCrackRollMatcher(config_manager, normalizer)
        aggregated_product_spread_matcher = AggregatedProductSpreadMatcher(config_manager, normalizer)

        # Collect all matchers that have a get_rule_info method
        all_matchers = [
            exact_matcher,
            spread_matcher,
            crack_matcher,
            complex_crack_matcher,
            product_spread_matcher,
            aggregation_matcher,
            aggregated_complex_crack_matcher,
            aggregated_spread_matcher,
            aggregated_crack_matcher,
            complex_crack_roll_matcher,
            aggregated_product_spread_matcher,
        ]

        print("\n--- ICE Trade Matching Rules ---")
        for matcher in all_matchers:
            if hasattr(matcher, "get_rule_info"):  # Safely check if the method exists
                rule_info = matcher.get_rule_info()
                print(f"\nRule {rule_info['rule_number']}: {rule_info['rule_name']}")
                print(f"  Confidence: {rule_info['confidence']}%")
                print(f"  Description: {rule_info['description']}")
                print("  Requirements:")
                for req in rule_info["requirements"]:
                    print(f"    - {req}")
                if "tolerances" in rule_info and rule_info["tolerances"]:
                    print("  Tolerances:")
                    for k, v in rule_info["tolerances"].items():
                        print(f"    - {k}: {v}")
        print("\n-----------------------------------")
        return 0  # Exit the program after showing rules

    # Create configuration
    config_manager = ConfigManager.default().update_config(
        log_level=args.log_level,
        show_unmatched=not args.no_unmatched,
        show_statistics=not args.no_stats,
    )

    # Run matching
    engine = ICEMatchingEngine(config_manager, show_logs=args.show_logs)

    try:
        matches = engine.run_matching(args.trader_csv, args.exchange_csv)

        # Print summary for scripting

        summary = engine.get_match_summary(matches)
        print(f"\nMatching completed: {summary['total_matches']} matches found")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())