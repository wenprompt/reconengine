"""Main entry point for EEX trade matching system."""

import logging
from pathlib import Path
from typing import List, Optional, Any, Tuple, Dict
import argparse
import sys
import pandas as pd

from .config import EEXConfigManager
from .core import EEXUnmatchedPool, EEXTradeFactory
from .matchers.exact_matcher import ExactMatcher
from .models import EEXMatchResult, EEXTradeSource
from .cli import EEXDisplay
from .normalizers import EEXTradeNormalizer

# Default file paths
DEFAULT_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_TRADER_FILE = "sourceTraders.csv"
DEFAULT_EXCHANGE_FILE = "sourceExchange.csv"


logger = logging.getLogger(__name__)


class EEXMatchingEngine:
    """Main EEX trade matching engine."""

    config_manager: EEXConfigManager
    normalizer: EEXTradeNormalizer
    trade_factory: EEXTradeFactory
    display: EEXDisplay
    exact_matcher: ExactMatcher
    matchers: Dict[int, ExactMatcher]

    def __init__(self, config_manager: Optional[EEXConfigManager] = None):
        """Initialize EEX matching engine.

        Args:
            config_manager: Optional config manager. Creates default if None.
        """
        self.config_manager = config_manager or EEXConfigManager()
        self.normalizer = EEXTradeNormalizer(self.config_manager)
        self.trade_factory = EEXTradeFactory(self.normalizer)
        self.display = EEXDisplay()

        # Initialize matchers based on config (only exact matching for EEX)
        self.exact_matcher = ExactMatcher(self.config_manager)

        # Build matcher registry for scalable rule lookup
        self.matchers = {1: self.exact_matcher}

        logger.info("Initialized EEX matching engine with exact matcher only")

    def run_matching(
        self,
        trader_csv_path: Path,
        exchange_csv_path: Path,
        show_unmatched: bool = False,
    ) -> List[EEXMatchResult]:
        """Run the complete EEX matching process.

        Args:
            trader_csv_path: Path to trader CSV file
            exchange_csv_path: Path to exchange CSV file
            show_unmatched: Whether to display unmatched trades

        Returns:
            List of all match results
        """
        self.display.show_header()

        try:
            # Load data
            logger.info("Loading EEX trade data...")
            trader_trades = self.trade_factory.from_csv(
                trader_csv_path, EEXTradeSource.TRADER
            )
            exchange_trades = self.trade_factory.from_csv(
                exchange_csv_path, EEXTradeSource.EXCHANGE
            )

            self.display.show_loading_summary(len(trader_trades), len(exchange_trades))

            # Initialize pool manager
            pool_manager = EEXUnmatchedPool(trader_trades, exchange_trades)

            # Run matching rules in sequence (only Rule 1 for EEX)
            all_matches = []
            processing_order = self.config_manager.get_processing_order()

            for rule_number in processing_order:
                logger.info(f"Running Rule {rule_number}")

                # Get appropriate matcher for this rule
                matcher = self._get_matcher_for_rule(rule_number)
                if not matcher:
                    logger.warning(f"No matcher found for rule {rule_number}")
                    continue

                # Find matches (now atomically records matches internally)
                matches = matcher.find_matches(pool_manager)
                all_matches.extend(matches)

                logger.info(f"Rule {rule_number} found {len(matches)} matches")

            # Display results
            statistics = pool_manager.get_match_statistics()
            self.display.show_match_results(all_matches, statistics)

            # Show unmatched trades if requested
            if show_unmatched:
                unmatched_trader = pool_manager.get_unmatched_trader_trades()
                unmatched_exchange = pool_manager.get_unmatched_exchange_trades()
                self.display.show_unmatched_trades(unmatched_trader, unmatched_exchange)

            return all_matches

        except Exception as e:
            logger.error(f"Error in EEX matching process: {e}")
            self.display.show_error(f"{e!s}")
            return []

    def _get_matcher_for_rule(self, rule_number: int):
        """Get matcher for specific rule number.

        Args:
            rule_number: Rule number to get matcher for

        Returns:
            Matcher object or None if not found
        """
        return self.matchers.get(rule_number)

    def run_matching_from_dataframes(
        self, trader_df: pd.DataFrame, exchange_df: pd.DataFrame
    ) -> Tuple[List[EEXMatchResult], dict[str, Any]]:
        """Run EEX matching process directly from DataFrames without CSV files.

        Args:
            trader_df: Pandas DataFrame containing trader data
            exchange_df: Pandas DataFrame containing exchange data

        Returns:
            Tuple of (matches, statistics)
        """
        try:
            # Create trades from DataFrames
            logger.info("Creating EEX trades from DataFrames...")
            trader_trades = self.trade_factory.from_dataframe(
                trader_df, EEXTradeSource.TRADER
            )
            exchange_trades = self.trade_factory.from_dataframe(
                exchange_df, EEXTradeSource.EXCHANGE
            )

            logger.info(
                f"Created {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades"
            )

            # Initialize pool manager
            pool_manager = EEXUnmatchedPool(trader_trades, exchange_trades)

            # Run matching rules in sequence
            all_matches = []
            processing_order = self.config_manager.get_processing_order()

            for rule_number in processing_order:
                logger.info(f"Running Rule {rule_number}")

                # Get appropriate matcher for this rule
                matcher = self._get_matcher_for_rule(rule_number)
                if not matcher:
                    continue

                matches = matcher.find_matches(pool_manager)
                all_matches.extend(matches)

            # Get statistics and unmatched trades
            statistics = pool_manager.get_match_statistics()
            unmatched_trader = pool_manager.get_unmatched_trader_trades()
            unmatched_exchange = pool_manager.get_unmatched_exchange_trades()

            # Add unmatched trades to statistics for unified system
            statistics["unmatched_trader_trades"] = unmatched_trader
            statistics["unmatched_exchange_trades"] = unmatched_exchange

            # Calculate overall match rate for unified system
            total_trades = (
                statistics["original_trader_count"]
                + statistics["original_exchange_count"]
            )
            matched_trades = (
                statistics["matched_trader_count"]
                + statistics["matched_exchange_count"]
            )
            statistics["match_rate"] = (matched_trades / max(total_trades, 1)) * 100

            return all_matches, statistics

        except Exception as e:
            logger.error(f"Error in EEX matching from DataFrames: {e}")
            raise

    def show_rules(self) -> None:
        """Display information about all available matching rules."""
        self.display.show_header()

        for rule_number in sorted(self.matchers.keys()):
            matcher = self.matchers[rule_number]
            if hasattr(matcher, "get_rule_info"):
                rule_info = matcher.get_rule_info()
                self.display.show_rule_info(rule_info)


def setup_logging(log_level: str = "NONE") -> None:
    """Set up logging configuration for EEX matching.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, NONE)
    """
    # Remove any existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if log_level.upper() == "NONE":
        logging.getLogger().setLevel(logging.CRITICAL + 1)  # Higher than CRITICAL
        return

    # Set up logging based on level
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    """Main entry point for EEX matching system."""
    parser = argparse.ArgumentParser(description="EEX Trade Matching System")
    parser.add_argument("--trader-file", type=Path, help="Path to trader CSV file")
    parser.add_argument("--exchange-file", type=Path, help="Path to exchange CSV file")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Data directory containing CSV files (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--no-unmatched",
        action="store_true",
        help="Hide unmatched trades after processing",
    )
    parser.add_argument(
        "--show-rules",
        action="store_true",
        help="Display information about matching rules and exit",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "NONE"],
        default="NONE",
        help="Set logging level",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    try:
        # Initialize matching engine
        engine = EEXMatchingEngine()

        # Show rules if requested
        if args.show_rules:
            engine.show_rules()
            return

        # Determine file paths
        trader_path = args.trader_file or args.data_dir / DEFAULT_TRADER_FILE
        exchange_path = args.exchange_file or args.data_dir / DEFAULT_EXCHANGE_FILE

        # Check files exist
        if not trader_path.exists():
            logger.error(
                f"Trader data file not found at '{trader_path}'. Please check the file path and try again."
            )
            sys.exit(1)

        if not exchange_path.exists():
            logger.error(
                f"Exchange data file not found at '{exchange_path}'. Please check the file path and try again."
            )
            sys.exit(1)

        # Run matching process
        matches = engine.run_matching(
            trader_path,
            exchange_path,
            show_unmatched=not args.no_unmatched,  # Show unmatched by default like SGX
        )

        logger.info(f"EEX matching completed. Total matches: {len(matches)}")

    except KeyboardInterrupt:
        logger.info("Matching process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(
            f"Fatal error during matching process: {e}. Please check the input data and try again."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
