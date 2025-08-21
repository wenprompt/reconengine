"""Main entry point for SGX trade matching system."""

import logging
from pathlib import Path
from typing import List, Optional
import argparse
import sys

from .config import SGXConfigManager
from .loaders import SGXCSVLoader
from .core import SGXUnmatchedPool
from .matchers import SGXExactMatcher
from .models import SGXMatchResult
from .cli import SGXDisplay


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SGXMatchingEngine:
    """Main SGX trade matching engine."""
    
    def __init__(self, config_manager: Optional[SGXConfigManager] = None):
        """Initialize SGX matching engine.
        
        Args:
            config_manager: Optional config manager. Creates default if None.
        """
        self.config_manager = config_manager or SGXConfigManager()
        self.csv_loader = SGXCSVLoader(self.config_manager)
        self.display = SGXDisplay()
        
        # Initialize matchers based on config
        self.matchers = [
            SGXExactMatcher(self.config_manager)
        ]
        
        logger.info("Initialized SGX matching engine")
    
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
            # Load data
            logger.info("Loading SGX trade data...")
            trader_trades = self.csv_loader.load_trader_trades(trader_csv_path)
            exchange_trades = self.csv_loader.load_exchange_trades(exchange_csv_path)
            
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
            
            self.display.show_success(f"SGX matching completed. Found {len(all_matches)} total matches.")
            return all_matches
            
        except Exception as e:
            logger.error(f"SGX matching failed: {e}")
            self.display.show_error(str(e))
            raise
    
    def _get_matcher_for_rule(self, rule_number: int):
        """Get matcher for specific rule number.
        
        Args:
            rule_number: Rule number to get matcher for
            
        Returns:
            Matcher instance or None if not found
        """
        # For now, we only have Rule 1 (exact matching)
        if rule_number == 1:
            return self.matchers[0]  # SGXExactMatcher
        return None


def main():
    """Main entry point for SGX matching CLI."""
    parser = argparse.ArgumentParser(
        description="SGX Trade Matching System",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--trader-csv",
        type=Path,
        default=Path(__file__).parent / "data" / "sourceTraders.csv",
        help="Path to trader CSV file"
    )
    
    parser.add_argument(
        "--exchange-csv", 
        type=Path,
        default=Path(__file__).parent / "data" / "sourceExchange.csv",
        help="Path to exchange CSV file"
    )
    
    parser.add_argument(
        "--show-unmatched",
        action="store_true",
        help="Show unmatched trades in output"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Validate input files
    if not args.trader_csv.exists():
        print(f"Error: Trader CSV file not found: {args.trader_csv}")
        sys.exit(1)
    
    if not args.exchange_csv.exists():
        print(f"Error: Exchange CSV file not found: {args.exchange_csv}")
        sys.exit(1)
    
    # Run matching
    try:
        engine = SGXMatchingEngine()
        matches = engine.run_matching(
            args.trader_csv,
            args.exchange_csv,
            args.show_unmatched
        )
        
        # Exit with appropriate code
        sys.exit(0 if matches else 1)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()