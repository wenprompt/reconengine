"""Main entry point for SGX trade matching system."""

import logging
from pathlib import Path
from typing import List, Optional
import argparse
import sys

from .config import SGXConfigManager
from .core import SGXUnmatchedPool
from .core.trade_factory import SGXTradeFactory
from .matchers.exact_matcher import ExactMatcher
from .matchers.spread_matcher import SpreadMatcher
from .matchers.product_spread_matcher import ProductSpreadMatcher
from .models import SGXMatchResult, SGXTradeSource
from .cli import SGXDisplay
from .normalizers import SGXTradeNormalizer

# Default file paths
DEFAULT_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_TRADER_FILE = "sourceTraders.csv"
DEFAULT_EXCHANGE_FILE = "sourceExchange.csv"


logger = logging.getLogger(__name__)


class SGXMatchingEngine:
    """Main SGX trade matching engine."""
    
    def __init__(self, config_manager: Optional[SGXConfigManager] = None):
        """Initialize SGX matching engine. 
        
        Args:
            config_manager: Optional config manager. Creates default if None.
        """
        self.config_manager = config_manager or SGXConfigManager()
        self.normalizer = SGXTradeNormalizer(self.config_manager)
        self.trade_factory = SGXTradeFactory(self.normalizer)
        self.display = SGXDisplay()
        
        # Initialize matchers based on config
        self.exact_matcher = ExactMatcher(self.config_manager)
        self.spread_matcher = SpreadMatcher(self.config_manager, self.normalizer)
        self.product_spread_matcher = ProductSpreadMatcher(self.config_manager, self.normalizer)
        
        # Build matcher registry for scalable rule lookup
        self.matchers = {
            1: self.exact_matcher,
            2: self.spread_matcher,
            3: self.product_spread_matcher
        }
        
        logger.info("Initialized SGX matching engine with multiple matchers")
    
    def run_matching(self, trader_csv_path: Path, exchange_csv_path: Path,
                     show_unmatched: bool = False) -> List[SGXMatchResult]:
        """Run the complete SGX matching process.
        
        Args:
            trader_csv_path: Path to trader CSV file
            exchange_csv_path: Path to exchange CSV file
            show_unmatched: Whether to display unmatched trades
            
        Returns:
            List of all match results
        """
        self.display.show_header()
        
        try:
            # Load data using trade factory
            logger.info("Loading SGX trade data...")
            trader_trades = self.trade_factory.from_csv(trader_csv_path, SGXTradeSource.TRADER)
            exchange_trades = self.trade_factory.from_csv(exchange_csv_path, SGXTradeSource.EXCHANGE)
            
            self.display.show_loading_summary(len(trader_trades), len(exchange_trades))
            
            # Initialize pool manager
            pool_manager = SGXUnmatchedPool(trader_trades, exchange_trades)
            
            # Run matching rules in sequence
            all_matches = []
            processing_order = self.config_manager.get_processing_order()
            
            for rule_number in processing_order:
                logger.info(f"Running Rule {rule_number}")
                
                # Get appropriate matcher for this rule
                matcher = self._get_matcher_for_rule(rule_number)
                if not matcher:
                    logger.warning(f"No matcher found for rule {rule_number}")
                    continue
                
                # Find matches
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
            
            self.display.show_success(f"SGX matching completed. Found {len(all_matches)} total matches.")
            return all_matches
            
        except Exception as e:
            logger.error(f"SGX matching failed: {e}")
            self.display.show_error(str(e))
            raise RuntimeError(f"SGX matching failed: {e}") from e

    def run_matching_from_dataframes(self, trader_df, exchange_df) -> tuple:
        """Run SGX matching process directly from DataFrames without CSV files.
        
        Args:
            trader_df: Pandas DataFrame containing trader data
            exchange_df: Pandas DataFrame containing exchange data
            
        Returns:
            Tuple of (matches, statistics)
        """
        try:
            # Create trades from DataFrames
            logger.info("Creating SGX trades from DataFrames...")
            trader_trades = self.trade_factory.from_dataframe(trader_df, SGXTradeSource.TRADER)
            exchange_trades = self.trade_factory.from_dataframe(exchange_df, SGXTradeSource.EXCHANGE)
            
            logger.info(f"Created {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades")
            
            # Initialize pool manager
            pool_manager = SGXUnmatchedPool(trader_trades, exchange_trades)
            
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
            statistics['unmatched_trader_trades'] = unmatched_trader
            statistics['unmatched_exchange_trades'] = unmatched_exchange
            
            return all_matches, statistics
            
        except Exception as e:
            logger.error(f"SGX DataFrame matching failed: {e}")
            raise RuntimeError(f"SGX DataFrame matching failed: {e}") from e
    
    def _get_matcher_for_rule(self, rule_number: int):
        """Get matcher for specific rule number. 
        
        Args:
            rule_number: Rule number to get matcher for
            
        Returns:
            Matcher instance or None if not found
        """
        return self.matchers.get(rule_number)


def setup_logging(log_level: str = "NONE") -> None:
    """Set up logging configuration for SGX matching. 
    
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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def main() -> None:
    """Main entry point for SGX matching CLI."""
    parser = argparse.ArgumentParser(
        description="SGX Trade Matching System",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--trader-csv",
        type=Path,
        default=DEFAULT_DATA_DIR / DEFAULT_TRADER_FILE,
        help="Path to trader CSV file"
    )
    
    parser.add_argument(
        "--exchange-csv", 
        type=Path,
        default=DEFAULT_DATA_DIR / DEFAULT_EXCHANGE_FILE,
        help="Path to exchange CSV file"
    )
    
    parser.add_argument(
        "--no-unmatched",
        action="store_true",
        help="Hide unmatched trades in output (default: show unmatched)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "NONE"],
        default="NONE",
        help="Set logging level"
    )
    
    parser.add_argument(
        "--show-rules",
        action="store_true",
        help="Display detailed information about all matching rules and exit"
    )
    
    args = parser.parse_args()
    
    # Handle --show-rules option
    if args.show_rules:
        try:
            config_manager = SGXConfigManager()
            normalizer = SGXTradeNormalizer(config_manager)
            display = SGXDisplay()
            
            # Get rule information from matchers
            exact_matcher = ExactMatcher(config_manager)
            spread_matcher = SpreadMatcher(config_manager, normalizer)
            product_spread_matcher = ProductSpreadMatcher(config_manager, normalizer)
            
            rules_info = [
                exact_matcher.get_rule_info(),
                spread_matcher.get_rule_info(),
                product_spread_matcher.get_rule_info()
            ]
            
            display.show_rules_information(rules_info)
            sys.exit(0)
            
        except Exception as e:
            print(f"Error displaying rules: {e}")
            sys.exit(1)
    
    # Set up logging
    setup_logging(args.log_level)
    
    # Validate input files
    if not args.trader_csv.exists():
        logger.error(f"Trader data file not found at '{args.trader_csv}'. Please check the file path and try again.")
        sys.exit(1)
    
    if not args.exchange_csv.exists():
        logger.error(f"Exchange data file not found at '{args.exchange_csv}'. Please check the file path and try again.")
        sys.exit(1)
    
    # Run matching
    try:
        engine = SGXMatchingEngine()
        matches = engine.run_matching(
            args.trader_csv,
            args.exchange_csv,
            show_unmatched=not args.no_unmatched  # Show unmatched by default, hide if --no-unmatched
        )
        
        # Exit with appropriate code
        sys.exit(0 if matches else 1)
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")  # Use logger.exception to capture full traceback
        sys.exit(1)


if __name__ == "__main__":
    main()
