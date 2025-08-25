"""Main entry point for unified reconciliation system."""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any
import tempfile
import pandas as pd

from .core.group_router import UnifiedTradeRouter
from .core.result_aggregator import ResultAggregator
from .cli.unified_display import UnifiedDisplay
from .utils.data_validator import DataValidationError

# Constants
DEFAULT_TRADER_CSV = "sourceTraders.csv"
DEFAULT_EXCHANGE_CSV = "sourceExchange.csv"
DEFAULT_CONFIG_FILE = "unified_config.json"


def setup_logging(log_level: str = "INFO") -> None:
    """Set up logging configuration for unified reconciliation.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Remove any existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Only set up logging if DEBUG level is requested
    if log_level == "DEBUG":
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
    elif log_level == "INFO":
        # For INFO and above, only show warnings and errors to keep output clean
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
    else:
        # For WARNING and ERROR, use the specified level
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )


def call_ice_match_system(trader_df: pd.DataFrame, exchange_df: pd.DataFrame, temp_data_dir: Path) -> Dict[str, Any]:
    """Call ICE match system with filtered data.
    
    Args:
        trader_df: Filtered trader DataFrame for group 1
        exchange_df: Filtered exchange DataFrame for group 1
        temp_data_dir: Temporary directory to write CSV files
        
    Returns:
        Dict with ICE match results and statistics
    """
    # Write filtered data to temporary CSV files
    trader_csv = temp_data_dir / DEFAULT_TRADER_CSV
    exchange_csv = temp_data_dir / DEFAULT_EXCHANGE_CSV
    
    trader_df.to_csv(trader_csv, index=False)
    exchange_df.to_csv(exchange_csv, index=False)
    
    # Import and call ICE match system
    try:
        from ..ice_match.loaders.csv_loader import CSVTradeLoader  # type: ignore
        from ..ice_match.config import ConfigManager  # type: ignore
        from ..ice_match.normalizers import TradeNormalizer  # type: ignore
        from ..ice_match.core import UnmatchedPoolManager  # type: ignore
        
        # Set up ICE system components
        config_manager = ConfigManager()
        normalizer = TradeNormalizer(config_manager)
        loader = CSVTradeLoader(normalizer)
        
        # Load and process data through ICE system
        start_time = time.time()
        
        # Load data using ICE system's loader
        trader_trades = loader.load_trader_csv(trader_csv)
        exchange_trades = loader.load_exchange_csv(exchange_csv)
        
        # Create pool manager and process through ICE rules
        pool_manager = UnmatchedPoolManager(trader_trades, exchange_trades)
        
        # Get ICE rule processing order and matchers
        processing_order = config_manager.get_processing_order()
        
        # Import all ICE matchers
        from ..ice_match.matchers import (  # type: ignore
            ExactMatcher, SpreadMatcher, CrackMatcher, ComplexCrackMatcher,
            ProductSpreadMatcher, AggregationMatcher, AggregatedComplexCrackMatcher,
            AggregatedSpreadMatcher, MultilegSpreadMatcher, AggregatedCrackMatcher,
            ComplexCrackRollMatcher, AggregatedProductSpreadMatcher
        )
        
        # Create matcher instances
        matchers = {
            1: ExactMatcher(config_manager),
            2: SpreadMatcher(config_manager, normalizer), 
            3: CrackMatcher(config_manager, normalizer),
            4: ComplexCrackMatcher(config_manager, normalizer),
            5: ProductSpreadMatcher(config_manager, normalizer),
            6: AggregationMatcher(config_manager),
            7: AggregatedComplexCrackMatcher(config_manager, normalizer),
            8: AggregatedSpreadMatcher(config_manager, normalizer),
            9: MultilegSpreadMatcher(config_manager, normalizer),
            10: AggregatedCrackMatcher(config_manager, normalizer),
            11: ComplexCrackRollMatcher(config_manager, normalizer),
            12: AggregatedProductSpreadMatcher(config_manager, normalizer)
        }
        
        # Process through all rules in sequence
        all_matches = []
        for rule_num in processing_order:
            if rule_num in matchers:
                matcher = matchers[rule_num]
                rule_matches = matcher.find_matches(pool_manager)
                all_matches.extend(rule_matches)
        
        processing_time = time.time() - start_time
        
        # Calculate statistics using ICE system convention
        # Get statistics from pool manager (same as ICE system)
        pool_stats = pool_manager.get_statistics()
        
        # Extract match rates using ICE system's calculation method
        trader_match_rate = float(pool_stats['match_rates']['trader'].replace('%', ''))
        exchange_match_rate = float(pool_stats['match_rates']['exchange'].replace('%', ''))
        overall_match_rate = float(pool_stats['match_rates']['overall'].replace('%', ''))
        
        total_trader_trades = len(trader_trades)
        total_matches = len(all_matches)
        match_rate = overall_match_rate  # Use ICE system's overall calculation
        
        # Get rule breakdown
        rule_breakdown: Dict[int, int] = {}
        for match in all_matches:
            rule_num = match.rule_order
            rule_breakdown[rule_num] = rule_breakdown.get(rule_num, 0) + 1
        
        # Generate DataFrame output like ICE system
        from ..ice_match.utils.dataframe_output import create_reconciliation_dataframe  # type: ignore
        from datetime import datetime
        
        execution_time = datetime.now()
        df = create_reconciliation_dataframe(all_matches, pool_manager, execution_time)
        
        return {
            'matches_found': total_matches,
            'match_rate': match_rate,  # Overall match rate (ICE convention)
            'trader_match_rate': trader_match_rate,
            'exchange_match_rate': exchange_match_rate,
            'processing_time': processing_time,
            'rule_breakdown': rule_breakdown,
            'detailed_results': all_matches,
            'reconciliation_dataframe': df,
            'pool_statistics': pool_stats  # Full ICE statistics
        }
        
    except ImportError as e:
        raise ImportError(f"Failed to import ICE match system: {e}")
    except Exception as e:
        raise RuntimeError(f"ICE match system processing failed: {e}")


def call_sgx_match_system(trader_df: pd.DataFrame, exchange_df: pd.DataFrame, temp_data_dir: Path) -> Dict[str, Any]:
    """Call SGX match system with filtered data.
    
    Args:
        trader_df: Filtered trader DataFrame for group 2
        exchange_df: Filtered exchange DataFrame for group 2
        temp_data_dir: Temporary directory to write CSV files
        
    Returns:
        Dict with SGX match results and statistics
    """
    # Write filtered data to temporary CSV files
    trader_csv = temp_data_dir / DEFAULT_TRADER_CSV
    exchange_csv = temp_data_dir / DEFAULT_EXCHANGE_CSV
    
    trader_df.to_csv(trader_csv, index=False)
    exchange_df.to_csv(exchange_csv, index=False)
    
    # Import and call SGX match system
    try:
        from ..sgx_match.main import SGXMatchingEngine  # type: ignore
        
        # Set up SGX system engine
        engine = SGXMatchingEngine()
        
        # Load and process data through SGX system
        start_time = time.time()
        
        # Use SGX engine to run minimal matching process (no display, optimized for unified system)
        matches, statistics = engine.run_matching_minimal(trader_csv, exchange_csv)
        
        processing_time = time.time() - start_time
        
        # Extract statistics from SGX pool manager
        total_matches = len(matches)
        total_trader_trades = statistics['original_trader_count']
        total_exchange_trades = statistics['original_exchange_count']
        
        # Calculate match rate using SGX convention (total matches / total trades)
        total_trades = total_trader_trades + total_exchange_trades
        sgx_total_match_rate = (total_matches / total_trades * 100) if total_trades > 0 else 0.0
        
        match_rate = sgx_total_match_rate
        
        return {
            'matches_found': total_matches,
            'match_rate': match_rate, 
            'processing_time': processing_time,
            'detailed_results': matches,
            'unmatched_trader_trades': statistics.get('unmatched_trader_trades', []),
            'unmatched_exchange_trades': statistics.get('unmatched_exchange_trades', [])
        }
        
    except ImportError as e:
        raise ImportError(f"Failed to import SGX match system: {e}")
    except Exception as e:
        raise RuntimeError(f"SGX match system processing failed: {e}")


def main() -> int:
    """Main entry point for unified reconciliation system.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Unified Reconciliation System - Routes trades to appropriate matching systems"
    )
    parser.add_argument(
        "--data-dir", 
        type=str, 
        help="Custom data directory (default: uses config)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    parser.add_argument(
        "--no-unmatched",
        action="store_true",
        help="Hide unmatched trades in output (default: show unmatched)"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Initialize components
    display = UnifiedDisplay()
    result_aggregator = ResultAggregator()
    
    try:
        # Load configuration and initialize router
        config_path = Path(__file__).parent / "config" / DEFAULT_CONFIG_FILE
        router = UnifiedTradeRouter(config_path)
        
        # Display startup information
        display.display_startup_info(router.config)
        
        # Load and validate data
        data_dir = Path(args.data_dir) if args.data_dir else None
        trader_df, exchange_df = router.load_and_validate_data(data_dir)
        
        # Group trades by exchange group
        grouped_trades = router.group_trades_by_exchange_group(trader_df, exchange_df)
        
        # Display data loading info
        group_distribution = {}
        for group_id, group_info in grouped_trades.items():
            system_config = group_info.get("system_config", {})
            group_distribution[group_id] = {
                'trader': group_info['trader_count'],
                'exchange': group_info['exchange_count'],
                'system_name': system_config.get('description', group_info['system'])
            }
        
        display.display_data_loading_info(len(trader_df), len(exchange_df), group_distribution)
        
        # Get processable groups
        processable_groups = router.get_processable_groups(grouped_trades)
        
        if not processable_groups:
            display.display_warning("No processable exchange groups found!")
            return 1
        
        # Process each group through its matching system
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_data_dir = Path(temp_dir)
            
            for group_id in processable_groups:
                group_info = grouped_trades[group_id]
                system_name = group_info['system']
                
                logger.info(f"Processing group {group_id} with {system_name} system...")
                
                try:
                    # Route data to appropriate system
                    if system_name == "ice_match":
                        results = call_ice_match_system(
                            group_info['trader_data'], 
                            group_info['exchange_data'],
                            temp_data_dir
                        )
                    elif system_name == "sgx_match":
                        results = call_sgx_match_system(
                            group_info['trader_data'],
                            group_info['exchange_data'], 
                            temp_data_dir
                        )
                    else:
                        logger.warning(f"Unknown system: {system_name}")
                        continue
                    
                    # Add results to aggregator
                    result_aggregator.add_system_result(
                        group_id=group_id,
                        system_name=system_name,
                        matches_found=results['matches_found'],
                        trader_count=group_info['trader_count'],
                        exchange_count=group_info['exchange_count'],
                        system_config=group_info['system_config'],
                        processing_time=results.get('processing_time'),
                        detailed_results=results.get('detailed_results'),
                        statistics=results,
                        match_rate=results['match_rate']  # Use ICE system's overall match rate
                    )
                    
                    logger.info(f"Group {group_id} completed: {results['matches_found']} matches ({results['match_rate']:.1f}%)")
                    
                except Exception as e:
                    logger.error(f"Failed to process group {group_id}: {e}")
                    display.display_error(f"Failed to process group {group_id}", str(e))
                    continue
        
        # Display results
        unified_results = result_aggregator.get_aggregated_results()
        
        # Always show detailed results (like ICE and SGX systems do by default)
        display.display_group_results(unified_results.system_results, show_details=True, show_unmatched=not args.no_unmatched)
        
        display.display_unified_summary(unified_results)
        display.display_success(f"Unified reconciliation completed successfully! {unified_results.total_matches_found} total matches found.")
        
        return 0
        
    except DataValidationError as e:
        display.display_error("Data validation failed", str(e))
        return 1
    except ImportError as e:
        display.display_error("System import failed", str(e))
        return 1
    except Exception as e:
        logger.exception("Unexpected error occurred")
        display.display_error("Unexpected error occurred", str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())