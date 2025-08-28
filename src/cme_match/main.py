"""Main entry point for CME trade matching system."""

import logging
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
import argparse

from .config import CMEConfigManager
from .loaders import CMECSVLoader
from .core import CMEUnmatchedPool
from .matchers.exact_matcher import ExactMatcher
from .models import CMEMatchResult
from .cli import CMEDisplay
from .normalizers import CMETradeNormalizer

# Default file paths
DEFAULT_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_TRADER_FILE = "sourceTraders.csv"
DEFAULT_EXCHANGE_FILE = "sourceExchange.csv"


logger = logging.getLogger(__name__)


class CMEMatchingEngine:
    """Main CME trade matching engine."""
    
    def __init__(self, config_manager: Optional[CMEConfigManager] = None):
        """Initialize CME matching engine. 
        
        Args:
            config_manager: Optional config manager. Creates default if None.
        """
        self.config_manager = config_manager or CMEConfigManager()
        self.csv_loader = CMECSVLoader(self.config_manager)
        self.normalizer = CMETradeNormalizer(self.config_manager)
        self.display = CMEDisplay()
        
        # Initialize matchers based on config (only exact matching for CME)
        self.exact_matcher = ExactMatcher(self.config_manager)
        
        # Build matcher registry for scalable rule lookup
        self.matchers = {
            1: self.exact_matcher
        }
        
        logger.info("Initialized CME matching engine with exact matcher only")
    
    def run_matching(self, trader_csv_path: Path, exchange_csv_path: Path,
                     show_unmatched: bool = False) -> List[CMEMatchResult]:
        """Run the complete CME matching process.
        
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
            logger.info("Loading CME trade data...")
            trader_trades = self.csv_loader.load_trader_trades(trader_csv_path)
            exchange_trades = self.csv_loader.load_exchange_trades(exchange_csv_path)
            
            self.display.show_loading_summary(len(trader_trades), len(exchange_trades))
            
            # Initialize pool manager
            pool_manager = CMEUnmatchedPool(trader_trades, exchange_trades)
            
            # Run matching rules in sequence (only Rule 1 for CME)
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
                
                # Record matches in pool
                for match in matches:
                    pool_manager.record_match(
                        match.trader_trade.trade_id, 
                        match.exchange_trade.trade_id, 
                        match.match_type.value
                    )
                
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
            logger.error(f"Error in CME matching process: {e}")
            self.display.show_error(str(e))
            return []
    
    def _get_matcher_for_rule(self, rule_number: int):
        """Get matcher for specific rule number.
        
        Args:
            rule_number: Rule number to get matcher for
            
        Returns:
            Matcher object or None if not found
        """
        return self.matchers.get(rule_number)
    
    def show_rules(self) -> None:
        """Display information about all available matching rules."""
        self.display.show_header()
        
        for rule_number in sorted(self.matchers.keys()):
            matcher = self.matchers[rule_number]
            if hasattr(matcher, 'get_rule_info'):
                rule_info = matcher.get_rule_info()
                self.display.show_rule_info(rule_info)


def setup_logging(log_level: str = "NONE") -> None:
    """Set up logging configuration for CME matching.
    
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
    """Main entry point for CME matching system."""
    parser = argparse.ArgumentParser(description="CME Trade Matching System")
    parser.add_argument(
        "--trader-file", 
        type=Path,
        help="Path to trader CSV file"
    )
    parser.add_argument(
        "--exchange-file",
        type=Path, 
        help="Path to exchange CSV file"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Data directory containing CSV files (default: {DEFAULT_DATA_DIR})"
    )
    parser.add_argument(
        "--show-unmatched",
        action="store_true",
        help="Display unmatched trades after processing"
    )
    parser.add_argument(
        "--show-rules",
        action="store_true",
        help="Display information about matching rules and exit"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "NONE"],
        default="NONE",
        help="Set logging level"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    try:
        # Initialize matching engine
        engine = CMEMatchingEngine()
        
        # Show rules if requested
        if args.show_rules:
            engine.show_rules()
            return
        
        # Determine file paths
        trader_path = args.trader_file or args.data_dir / DEFAULT_TRADER_FILE
        exchange_path = args.exchange_file or args.data_dir / DEFAULT_EXCHANGE_FILE
        
        # Check files exist
        if not trader_path.exists():
            print(f"Error: Trader file not found: {trader_path}")
            sys.exit(1)
        
        if not exchange_path.exists():
            print(f"Error: Exchange file not found: {exchange_path}")
            sys.exit(1)
        
        # Run matching process
        matches = engine.run_matching(
            trader_path, 
            exchange_path, 
            show_unmatched=args.show_unmatched or args.log_level == "DEBUG"
        )
        
        logger.info(f"CME matching completed. Total matches: {len(matches)}")
        
    except KeyboardInterrupt:
        print("\nMatching process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()