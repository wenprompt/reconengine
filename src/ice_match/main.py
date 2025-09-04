"""Main application entry point for ice trade matching system."""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Protocol
from decimal import Decimal

from .models import MatchResult, Trade, TradeSource
from .normalizers import TradeNormalizer
from .config import ConfigManager
from .core import UnmatchedPoolManager
from .core.trade_factory import ICETradeFactory
from .matchers import (
    ExactMatcher,
    SpreadMatcher,
    CrackMatcher,
    ComplexCrackMatcher,
    ProductSpreadMatcher,
    FlyMatcher,
    AggregationMatcher,
    AggregatedComplexCrackMatcher,
    AggregatedSpreadMatcher,
    MultilegSpreadMatcher,
    AggregatedCrackMatcher,
    ComplexCrackRollMatcher,
    AggregatedProductSpreadMatcher,
)
from .cli import MatchDisplayer
from .utils.dataframe_output import create_reconciliation_dataframe, display_reconciliation_dataframe


class MatcherProtocol(Protocol):
    """Protocol for matcher classes with a find_matches method."""
    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]: ...


# Default file paths and constants - package-relative
DEFAULT_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_TRADER_FILE = "sourceTraders.csv"
DEFAULT_EXCHANGE_FILE = "sourceExchange.csv"


def setup_logging(log_level: str = "NONE") -> None:
    """Setup logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL, NONE)
    """
    # Remove any existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # If level is NONE, set root logger to CRITICAL to suppress all output
    if log_level.upper() == "NONE":
        logging.getLogger().setLevel(logging.CRITICAL + 1)  # Higher than CRITICAL
        return

    # Set up logging based on level, with uppercasing and fallback
    log_level_upper = log_level.upper()
    level = getattr(logging, log_level_upper, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )


class ICEMatchingEngine:
    """Main engine for ice trade matching system.

    Orchestrates the complete matching process from data loading through
    result display with proper non-duplication handling.
    """

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
    ):
        """Initialize the matching engine.

        Args:
            config_manager: Optional configuration manager, uses defaults if None
        """
        self.config_manager = config_manager or ConfigManager.default()
        self.normalizer = TradeNormalizer(self.config_manager)
        self.trade_factory = ICETradeFactory(self.normalizer)  # Trade factory for flexible input
        self.displayer = MatchDisplayer(self.config_manager)

        # Setup logging
        setup_logging(self.config_manager.config.log_level)
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

                # Use trade factory for consistency
                trader_trades = self.trade_factory.from_csv(trader_csv_path, TradeSource.TRADER)
                exchange_trades = self.trade_factory.from_csv(exchange_csv_path, TradeSource.EXCHANGE)

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

            # Rule 6: Fly matching
            self.logger.info("Applying Rule 6: Fly matching...")
            fly_matcher = FlyMatcher(self.config_manager, self.normalizer)
            fly_matches = fly_matcher.find_matches(pool_manager)
            all_matches.extend(fly_matches)

            # Rule 7: Aggregation matching
            self.logger.info("Applying Rule 7: Aggregation matching...")
            aggregation_matcher = AggregationMatcher(self.config_manager)
            aggregation_matches = aggregation_matcher.find_matches(pool_manager)
            all_matches.extend(aggregation_matches)

            # Rule 8: Aggregated complex crack matching
            self.logger.info("Applying Rule 8: Aggregated complex crack matching...")
            aggregated_complex_crack_matcher = AggregatedComplexCrackMatcher(
                self.config_manager, self.normalizer
            )
            aggregated_complex_crack_matches = aggregated_complex_crack_matcher.find_matches(pool_manager)
            all_matches.extend(aggregated_complex_crack_matches)

            # Rule 9: Aggregated spread matching
            self.logger.info("Applying Rule 9: Aggregated spread matching...")
            aggregated_spread_matcher = AggregatedSpreadMatcher(
                self.config_manager, self.normalizer
            )
            aggregated_spread_matches = aggregated_spread_matcher.find_matches(
                pool_manager
            )
            all_matches.extend(aggregated_spread_matches)

            # Rule 10: Multileg spread matching
            self.logger.info("Applying Rule 10: Multileg spread matching...")
            multileg_spread_matcher = MultilegSpreadMatcher(
                self.config_manager, self.normalizer
            )
            multileg_spread_matches = multileg_spread_matcher.find_matches(
                pool_manager
            )
            all_matches.extend(multileg_spread_matches)

            # Rule 11: Aggregated crack matching
            self.logger.info("Applying Rule 11: Aggregated crack matching...")
            aggregated_crack_matcher = AggregatedCrackMatcher(
                self.config_manager, self.normalizer
            )
            aggregated_crack_matches = aggregated_crack_matcher.find_matches(
                pool_manager
            )
            all_matches.extend(aggregated_crack_matches)

            # Rule 12: Complex crack roll matching
            self.logger.info("Applying Rule 12: Complex crack roll matching...")
            complex_crack_roll_matcher = ComplexCrackRollMatcher(
                self.config_manager, self.normalizer
            )
            complex_crack_roll_matches = complex_crack_roll_matcher.find_matches(pool_manager)
            all_matches.extend(complex_crack_roll_matches)

            # Rule 13: Aggregated product spread matching
            self.logger.info("Applying Rule 13: Aggregated product spread matching...")
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

    def run_matching_minimal(self, trader_csv_path: Path, exchange_csv_path: Path) -> tuple[List[MatchResult], Dict[str, Any]]:
        """Run ICE matching process without display output for unified system.
        
        Args:
            trader_csv_path: Path to trader CSV file
            exchange_csv_path: Path to exchange CSV file
            
        Returns:
            Tuple of (matches, statistics) for unified system integration
        """
        from datetime import datetime
        from .utils.dataframe_output import create_reconciliation_dataframe

        start_time = time.time()
        execution_datetime = datetime.now()

        try:
            # Set conversion ratio for all Trade instances
            Trade.set_conversion_ratio(self.config_manager.get_conversion_ratio())

            # Load data using trade factory
            trader_trades = self.trade_factory.from_csv(trader_csv_path, TradeSource.TRADER)
            exchange_trades = self.trade_factory.from_csv(exchange_csv_path, TradeSource.EXCHANGE)

            # Initialize pool manager
            pool_manager = UnmatchedPoolManager(trader_trades, exchange_trades)

            # Run all matching rules in sequence
            all_matches = []

            # Get processing order from config
            processing_order = self.config_manager.get_processing_order()

            # Create matcher instances based on config
            matchers: Dict[int, MatcherProtocol] = {
                1: ExactMatcher(self.config_manager),
                2: SpreadMatcher(self.config_manager, self.normalizer),
                3: CrackMatcher(self.config_manager, self.normalizer),
                4: ComplexCrackMatcher(self.config_manager, self.normalizer),
                5: ProductSpreadMatcher(self.config_manager, self.normalizer),
                6: FlyMatcher(self.config_manager, self.normalizer),
                7: AggregationMatcher(self.config_manager),
                8: AggregatedComplexCrackMatcher(self.config_manager, self.normalizer),
                9: AggregatedSpreadMatcher(self.config_manager, self.normalizer),
                10: MultilegSpreadMatcher(self.config_manager, self.normalizer),
                11: AggregatedCrackMatcher(self.config_manager, self.normalizer),
                12: ComplexCrackRollMatcher(self.config_manager, self.normalizer),
                13: AggregatedProductSpreadMatcher(self.config_manager, self.normalizer)
            }

            # Process through all rules in sequence
            for rule_num in processing_order:
                if rule_num in matchers:
                    matcher = matchers[rule_num]
                    rule_matches = matcher.find_matches(pool_manager)
                    all_matches.extend(rule_matches)

            processing_time = time.time() - start_time

            # Get statistics from pool manager (same as ICE system)
            pool_stats = pool_manager.get_statistics()

            # Extract match rates using ICE system's calculation method
            trader_match_rate = float(pool_stats['match_rates']['trader'].replace('%', ''))
            exchange_match_rate = float(pool_stats['match_rates']['exchange'].replace('%', ''))
            overall_match_rate = float(pool_stats['match_rates']['overall'].replace('%', ''))

            # Get rule breakdown
            rule_breakdown: Dict[int, int] = {}
            for match in all_matches:
                rule_num = match.rule_order
                rule_breakdown[rule_num] = rule_breakdown.get(rule_num, 0) + 1

            # Generate DataFrame output like ICE system
            df = create_reconciliation_dataframe(all_matches, pool_manager, execution_datetime)

            # Get unmatched trades like SGX does
            unmatched_trader = pool_manager.get_unmatched_trader_trades()
            unmatched_exchange = pool_manager.get_unmatched_exchange_trades()

            # Prepare statistics dictionary for unified system
            statistics = {
                'matches_found': len(all_matches),
                'match_rate': overall_match_rate,
                'trader_match_rate': trader_match_rate,
                'exchange_match_rate': exchange_match_rate,
                'processing_time': processing_time,
                'rule_breakdown': rule_breakdown,
                'reconciliation_dataframe': df,
                'pool_statistics': pool_stats,
                'unmatched_trader_trades': unmatched_trader,
                'unmatched_exchange_trades': unmatched_exchange
            }

            return all_matches, statistics

        except Exception as e:
            self.logger.error(f"ICE minimal matching failed: {e}")
            raise RuntimeError(f"ICE matching failed: {e}") from e
    
    def run_matching_from_dataframes(self, trader_df, exchange_df) -> tuple[List[MatchResult], Dict[str, Any]]:
        """Run ICE matching process directly from DataFrames without CSV files.
        
        Args:
            trader_df: DataFrame containing trader trades
            exchange_df: DataFrame containing exchange trades
            
        Returns:
            Tuple of (matches, statistics) for unified system integration
        """
        from datetime import datetime
        from .utils.dataframe_output import create_reconciliation_dataframe
        
        start_time = time.time()
        execution_datetime = datetime.now()
        
        try:
            # Set conversion ratio for all Trade instances
            Trade.set_conversion_ratio(self.config_manager.get_conversion_ratio())
            
            # Create trades directly from DataFrames using trade factory
            trader_trades = self.trade_factory.from_dataframe(trader_df, TradeSource.TRADER)
            exchange_trades = self.trade_factory.from_dataframe(exchange_df, TradeSource.EXCHANGE)
            
            # Initialize pool manager
            pool_manager = UnmatchedPoolManager(trader_trades, exchange_trades)
            
            # Run all matching rules in sequence
            all_matches = []
            
            # Get processing order from config
            processing_order = self.config_manager.get_processing_order()
            
            # Create matcher instances based on config
            matchers: Dict[int, MatcherProtocol] = {
                1: ExactMatcher(self.config_manager),
                2: SpreadMatcher(self.config_manager, self.normalizer),
                3: CrackMatcher(self.config_manager, self.normalizer),
                4: ComplexCrackMatcher(self.config_manager, self.normalizer),
                5: ProductSpreadMatcher(self.config_manager, self.normalizer),
                6: FlyMatcher(self.config_manager, self.normalizer),
                7: AggregationMatcher(self.config_manager),
                8: AggregatedComplexCrackMatcher(self.config_manager, self.normalizer),
                9: AggregatedSpreadMatcher(self.config_manager, self.normalizer),
                10: MultilegSpreadMatcher(self.config_manager, self.normalizer),
                11: AggregatedCrackMatcher(self.config_manager, self.normalizer),
                12: ComplexCrackRollMatcher(self.config_manager, self.normalizer),
                13: AggregatedProductSpreadMatcher(self.config_manager, self.normalizer)
            }
            
            # Process through all rules in sequence
            for rule_num in processing_order:
                if rule_num in matchers:
                    matcher = matchers[rule_num]
                    rule_matches = matcher.find_matches(pool_manager)
                    all_matches.extend(rule_matches)
            
            processing_time = time.time() - start_time
            
            # Get statistics from pool manager
            pool_stats = pool_manager.get_statistics()
            
            # Extract match rates
            trader_match_rate = float(pool_stats['match_rates']['trader'].replace('%', ''))
            exchange_match_rate = float(pool_stats['match_rates']['exchange'].replace('%', ''))
            overall_match_rate = float(pool_stats['match_rates']['overall'].replace('%', ''))
            
            # Get rule breakdown
            rule_breakdown: Dict[int, int] = {}
            for match in all_matches:
                rule_num = match.rule_order
                rule_breakdown[rule_num] = rule_breakdown.get(rule_num, 0) + 1
            
            # Generate DataFrame output
            df = create_reconciliation_dataframe(all_matches, pool_manager, execution_datetime)
            
            # Get unmatched trades
            unmatched_trader = pool_manager.get_unmatched_trader_trades()
            unmatched_exchange = pool_manager.get_unmatched_exchange_trades()
            
            # Prepare statistics dictionary
            statistics = {
                'matches_found': len(all_matches),
                'match_rate': overall_match_rate,
                'trader_match_rate': trader_match_rate,
                'exchange_match_rate': exchange_match_rate,
                'processing_time': processing_time,
                'rule_breakdown': rule_breakdown,
                'reconciliation_dataframe': df,
                'pool_statistics': pool_stats,
                'unmatched_trader_trades': unmatched_trader,
                'unmatched_exchange_trades': unmatched_exchange
            }
            
            return all_matches, statistics
            
        except Exception as e:
            self.logger.error(f"ICE DataFrame matching failed: {e}")
            raise RuntimeError(f"ICE matching failed: {e}") from e


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
  python -m ice_match.main --log-level DEBUG custom_traders.csv custom_exchange.csv
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
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE"],
        default="NONE",
        help="Set logging level (default: NONE)",
    )

    parser.add_argument(
        "--no-unmatched", action="store_true", help="Don't show unmatched trades"
    )

    parser.add_argument("--no-stats", action="store_true", help="Don't show statistics")

    parser.add_argument(
        "--show-rules",
        action="store_true",
        help="Display information about all matching rules.",
    )

    args = parser.parse_args()

    # Validate file paths
    if not args.trader_csv.exists():
        logger.error(f"Trader data file not found at '{args.trader_csv}'. Please check the file path and try again.")
        return 1

    if not args.exchange_csv.exists():
        logger.error(f"Exchange data file not found at '{args.exchange_csv}'. Please check the file path and try again.")
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
        fly_matcher = FlyMatcher(config_manager, normalizer)
        aggregation_matcher = AggregationMatcher(config_manager)
        aggregated_complex_crack_matcher = AggregatedComplexCrackMatcher(
            config_manager, normalizer
        )
        aggregated_spread_matcher = AggregatedSpreadMatcher(config_manager, normalizer)
        multileg_spread_matcher = MultilegSpreadMatcher(config_manager, normalizer)
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
            fly_matcher,
            aggregation_matcher,
            aggregated_complex_crack_matcher,
            aggregated_spread_matcher,
            multileg_spread_matcher,
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
    engine = ICEMatchingEngine(config_manager)

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
