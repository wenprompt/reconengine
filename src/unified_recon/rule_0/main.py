"""CLI entry point for unified Rule 0 position decomposition analyzer."""

import argparse
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd

from src.unified_recon.rule_0.position_matrix import UnifiedPositionMatrixBuilder
from src.unified_recon.rule_0.matrix_comparator import UnifiedMatrixComparator
from src.unified_recon.rule_0.display import UnifiedDisplay
from src.unified_recon.rule_0.json_output import Rule0JSONOutput

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)


def load_config(exchange: str) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
    """Load configuration for the specified exchange.
    
    Args:
        exchange: Exchange name (ice_match, sgx_match, etc.)
        
    Returns:
        Tuple of (exchange-specific config, field mappings)
        
    Raises:
        ValueError: If exchange not found in config
    """
    config_path = Path(__file__).resolve().parents[1] / "config" / "unified_config.json"
    
    with open(config_path, 'r') as f:
        unified_config = json.load(f)
    
    rule_0_config = unified_config.get("rule_0_config", {})
    field_mappings = unified_config.get("field_mappings", {})
    
    if exchange not in rule_0_config:
        raise ValueError(f"Exchange '{exchange}' not found in rule_0_config")
    
    return rule_0_config[exchange], field_mappings


def load_csv_data(file_path: str) -> List[Dict[str, Any]]:
    """Load trade data from CSV file.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        List of trade dictionaries
    """
    df = pd.read_csv(file_path)
    
    # Clean column names (remove leading/trailing spaces)
    df.columns = df.columns.str.strip()
    
    # Convert to list of dicts with proper typing
    trades_raw = df.to_dict('records')
    
    # Convert to proper type by ensuring all keys are strings
    trades: List[Dict[str, Any]] = []
    for trade_raw in trades_raw:
        trade: Dict[str, Any] = {str(k): v for k, v in trade_raw.items()}
        trades.append(trade)
    
    return trades


def load_json_data(file_path: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load trade data from JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Tuple of (trader_trades, exchange_trades)
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    trader_trades = data.get("traderTrades", data.get("trader_trades", []))
    exchange_trades = data.get("exchangeTrades", data.get("exchange_trades", []))
    
    return trader_trades, exchange_trades


def get_default_data_paths(exchange: str) -> tuple[Path, Path]:
    """Get default data file paths for an exchange.
    
    Args:
        exchange: Exchange name
        
    Returns:
        Tuple of (trader_csv_path, exchange_csv_path)
    """
    # Always use unified_recon data since this is the unified command
    base_path = Path(__file__).resolve().parents[3] / "src" / "unified_recon" / "data"
    
    # Default file names
    trader_file = "sourceTraders.csv"
    exchange_file = "sourceExchange.csv"
    
    return base_path / trader_file, base_path / exchange_file


def get_tolerances(exchange: str, config: Dict[str, Any]) -> tuple[Decimal, Dict[str, float]]:
    """Get tolerance values for the exchange.
    
    Args:
        exchange: Exchange name
        config: Exchange config
        
    Returns:
        Tuple of (default_tolerance for comparisons, tolerance_dict for matching)
    """
    tolerance_dict: Dict[str, float] = {}
    default_tolerance = Decimal("0.01")
    
    # Load normalizer config if available
    if "normalizer_config" in config:
        config_path = Path(config["normalizer_config"])
        if config_path.exists():
            with open(config_path, 'r') as f:
                normalizer_config = json.load(f)
                tolerances = normalizer_config.get("universal_tolerances", {})
                
                if tolerances:
                    # Load all tolerance values from config
                    tolerance_dict = {}
                    
                    # Add any tolerance values found in config
                    for key, value in tolerances.items():
                        if key.startswith("tolerance"):
                            tolerance_dict[key] = value
                    
                    # Determine default tolerance for position comparisons
                    if 'tolerance_default' in tolerances:
                        default_tolerance = Decimal(str(tolerances['tolerance_default']))
                    elif 'tolerance' in tolerances:
                        default_tolerance = Decimal(str(tolerances['tolerance']))
                    elif 'tolerance_mt' in tolerances:
                        # Use MT tolerance as fallback default
                        default_tolerance = Decimal(str(tolerances['tolerance_mt']))
                    else:
                        # Use first tolerance value found
                        for key, value in tolerances.items():
                            if key.startswith("tolerance") and not key.endswith("description"):
                                default_tolerance = Decimal(str(value))
                                break
    
    return default_tolerance, tolerance_dict


def load_unified_config() -> Dict[str, Any]:
    """Load the unified configuration file.
    
    Returns:
        Unified configuration dictionary
        
    Raises:
        SystemExit: If config cannot be loaded
    """
    config_path = Path(__file__).resolve().parents[1] / "config" / "unified_config.json"
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file {config_path}: {e}")
        sys.exit(1)
    except Exception:
        logger.exception(f"Failed to load configuration from {config_path}")
        sys.exit(1)


def load_trade_data(args: argparse.Namespace, unified_config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load trade data from JSON or CSV files.
    
    Args:
        args: Command line arguments
        unified_config: Unified configuration
        
    Returns:
        Tuple of (trader_trades, exchange_trades)
        
    Raises:
        SystemExit: If data files cannot be loaded
    """
    if args.json_file:
        # Load from JSON
        trader_trades, exchange_trades = load_json_data(args.json_file)
        logger.info(f"Loaded {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades from JSON")
    else:
        # Load from CSV files
        if args.trader_csv and args.exchange_csv:
            trader_path = Path(args.trader_csv)
            exchange_path = Path(args.exchange_csv)
        else:
            # Use default paths from config
            data_settings = unified_config.get("data_settings", {})
            data_dir = Path(__file__).resolve().parents[3] / data_settings.get("default_data_dir", "src/unified_recon/data")
            trader_path = data_dir / data_settings.get("trader_file", "sourceTraders.csv")
            exchange_path = data_dir / data_settings.get("exchange_file", "sourceExchange.csv")
        
        if not trader_path.exists():
            logger.error(f"Trader file not found: {trader_path}")
            sys.exit(1)
        if not exchange_path.exists():
            logger.error(f"Exchange file not found: {exchange_path}")
            sys.exit(1)
        
        trader_trades = load_csv_data(str(trader_path))
        exchange_trades = load_csv_data(str(exchange_path))
        logger.info(f"Loaded {len(trader_trades)} trader trades from {trader_path}")
        logger.info(f"Loaded {len(exchange_trades)} exchange trades from {exchange_path}")
    
    return trader_trades, exchange_trades


def detect_exchanges_to_process(
    args: argparse.Namespace,
    trader_trades: List[Dict[str, Any]],
    exchange_trades: List[Dict[str, Any]],
    unified_config: Dict[str, Any],
    exchange_map: Dict[str, str]
) -> List[str]:
    """Determine which exchanges to process based on arguments or data.
    
    Args:
        args: Command line arguments
        trader_trades: List of trader trades
        exchange_trades: List of exchange trades
        unified_config: Unified configuration
        exchange_map: Mapping of CLI names to exchange names
        
    Returns:
        List of exchange names to process
        
    Raises:
        SystemExit: If no valid exchanges found
    """
    def get_exchange_group(trade: Dict[str, Any]) -> int:
        """Extract exchange group ID from trade."""
        group = trade.get("exchangeGroupId", trade.get("exchangegroupid", 0))
        return int(group) if group else 0
    
    exchanges_to_process = []
    
    if args.exchange:
        # Specific exchange requested
        exchange_name = exchange_map[args.exchange]
        exchanges_to_process.append(exchange_name)
    else:
        # Auto-detect exchanges from data
        all_groups = set()
        for trade in trader_trades + exchange_trades:
            group_id = get_exchange_group(trade)
            if group_id > 0:
                all_groups.add(group_id)
        
        # Map groups to exchanges
        for group_id in all_groups:
            exchange_name = unified_config["exchange_group_mappings"].get(str(group_id))
            if exchange_name and exchange_name not in exchanges_to_process:
                exchanges_to_process.append(exchange_name)
        
        if not exchanges_to_process:
            logger.error("No valid exchange groups found in data")
            sys.exit(1)
        
        logger.info(f"Auto-detected exchanges: {exchanges_to_process}")
    
    return exchanges_to_process


def save_json_output(
    exchange_results: Dict[str, Any],
    unified_config: Dict[str, Any],
    debug_mode: bool = False
) -> None:
    """Save results to JSON file.
    
    Args:
        exchange_results: Results grouped by exchange
        unified_config: Unified configuration
        debug_mode: Whether to print JSON to stdout
    """
    from datetime import datetime
    
    # Generate JSON output
    first_key = list(exchange_results.keys())[0]
    tolerances = exchange_results.get(first_key, {}).get('tolerance_dict', {})
    json_output = Rule0JSONOutput(tolerances=tolerances)
    json_str = json_output.to_json_string(exchange_results)
    
    # Save to json_output directory from config
    json_output_dir = Path(unified_config.get("output_settings", {}).get("json_output_dir", "json_output"))
    json_output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = json_output_dir / f"rule_0_output_{timestamp}.json"
    
    with open(json_file, 'w') as f:
        f.write(json_str)
    
    print(f"\nJSON output saved to: {json_file}")
    
    # Also print to stdout for API integration if in debug mode
    if debug_mode:
        print("\nJSON Output:")
        print(json_str)


def process_exchange(exchange_name: str, trader_trades: List[Dict[str, Any]], 
                     exchange_trades: List[Dict[str, Any]], show_details: bool,
                     return_data: bool = False) -> Optional[Dict[str, Any]]:
    """Process a single exchange's trades.
    
    Args:
        exchange_name: Exchange identifier (ice_match, sgx_match, etc.)
        trader_trades: List of trader trades for this exchange
        exchange_trades: List of exchange trades for this exchange
        show_details: Whether to show detailed breakdown
        return_data: Whether to return matrices and comparisons for JSON output
        
    Returns:
        Summary statistics for this exchange (optionally with matrices and comparisons)
    """
    try:
        # Load configuration and field mappings
        config, field_mappings = load_config(exchange_name)
        logger.info(f"Processing {exchange_name}")
        
        # Build position matrices with field mappings
        builder = UnifiedPositionMatrixBuilder(exchange_name, config, field_mappings)
        trader_matrix = builder.build_matrix(trader_trades, source="trader")
        exchange_matrix = builder.build_matrix(exchange_trades, source="exchange")
        
        # Compare matrices
        default_tolerance, tolerance_dict = get_tolerances(exchange_name, config)
        comparator = UnifiedMatrixComparator(exchange_name, default_tolerance)
        comparisons = comparator.compare_matrices(trader_matrix, exchange_matrix)
        
        # Get summary statistics
        stats = comparator.get_summary_statistics(comparisons)
        
        # Display results if not in JSON mode
        if not return_data:
            display_name = exchange_name.replace("_match", "").upper()
            display = UnifiedDisplay(display_name, tolerance_dict)
            display.show_header()
            display.show_summary(stats)
            display.show_comparison_by_product(comparisons)
            
            # Show detailed breakdown if requested
            if show_details:
                display.show_position_details(trader_matrix, exchange_matrix)
        
        # Return data for JSON output if requested
        if return_data:
            stats['trader_matrix'] = trader_matrix
            stats['exchange_matrix'] = exchange_matrix
            stats['comparisons'] = comparisons
            stats['tolerance_dict'] = tolerance_dict
        
        return stats
    except Exception:
        logger.exception(f"Error processing {exchange_name}")
        return None


def get_exchange_group(trade: Dict[str, Any]) -> int:
    """Extract exchange group ID from trade."""
    group = trade.get("exchangeGroupId", trade.get("exchangegroupid", 0))
    return int(group) if group else 0


def process_exchanges(
    exchanges_to_process: List[str],
    trader_trades: List[Dict[str, Any]],
    exchange_trades: List[Dict[str, Any]],
    unified_config: Dict[str, Any],
    args: argparse.Namespace
) -> Dict[str, Any]:
    """Process all exchanges and collect results.
    
    Args:
        exchanges_to_process: List of exchange names to process
        trader_trades: All trader trades
        exchange_trades: All exchange trades
        unified_config: Unified configuration
        args: Command line arguments
        
    Returns:
        Dictionary of results by exchange group ID
    """
    exchange_results = {}
    
    for exchange_name in exchanges_to_process:
        # Find exchange group IDs for this exchange
        exchange_groups = []
        for group_id, mapped_exchange in unified_config["exchange_group_mappings"].items():
            if mapped_exchange == exchange_name:
                exchange_groups.append(int(group_id))
        
        # Filter trades for this exchange
        exchange_trader_trades = [t for t in trader_trades if get_exchange_group(t) in exchange_groups]
        exchange_exchange_trades = [t for t in exchange_trades if get_exchange_group(t) in exchange_groups]
        
        if not exchange_trader_trades and not exchange_exchange_trades:
            logger.warning(f"No trades found for {exchange_name} (exchange groups: {exchange_groups})")
            if not args.json_output:
                all_groups = sorted(set(get_exchange_group(t) for t in trader_trades + exchange_trades if get_exchange_group(t) > 0))
                print(f"\nNo trades found for {exchange_name.replace('_match', '').upper()} exchange.")
                print(f"The data file contains trades for exchange groups: {all_groups}")
            continue
        
        logger.info(f"Processing {exchange_name}: {len(exchange_trader_trades)} trader trades, {len(exchange_exchange_trades)} exchange trades")
        
        # Process this exchange
        stats = process_exchange(
            exchange_name, 
            exchange_trader_trades, 
            exchange_exchange_trades,
            args.show_details, 
            return_data=args.json_output
        )
        
        if stats and args.json_output:
            # Group by each exchange group ID
            for group_id in exchange_groups:
                group_str = str(group_id)
                exchange_results[group_str] = {
                    'trader_matrix': stats['trader_matrix'],
                    'exchange_matrix': stats['exchange_matrix'],
                    'comparisons': stats['comparisons'],
                    'tolerance_dict': stats.get('tolerance_dict', {})
                }
    
    return exchange_results


def main():
    """Main entry point for unified Rule 0."""
    # Load configuration first
    unified_config = load_unified_config()
    
    # Create argument parser with config-based choices
    parser = argparse.ArgumentParser(
        description="Unified Rule 0: Position Decomposition Analyzer"
    )
    
    # Get available exchange choices from config
    available_exchanges = [key.replace("_match", "") for key in unified_config.get("rule_0_config", {}).keys()]
    
    parser.add_argument(
        "--exchange",
        choices=available_exchanges,
        help="Optional: Specific exchange to analyze. If not provided, analyzes all exchanges found in data"
    )
    parser.add_argument(
        "--trader-csv",
        help="Path to trader CSV file (defaults to exchange's standard data)"
    )
    parser.add_argument(
        "--exchange-csv",
        help="Path to exchange CSV file (defaults to exchange's standard data)"
    )
    parser.add_argument(
        "--json-file",
        help="Path to JSON file with both trader and exchange data"
    )
    parser.add_argument(
        "--show-details",
        action="store_true",
        help="Show detailed trade breakdown for each position"
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Output results as JSON to json_output directory"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Set logging level"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create exchange mapping from config
    exchange_map = {}
    for exchange_key in unified_config.get("rule_0_config", {}).keys():
        cli_name = exchange_key.replace("_match", "")
        exchange_map[cli_name] = exchange_key
    
    try:
        # Load trade data
        trader_trades, exchange_trades = load_trade_data(args, unified_config)
        
        # Determine which exchanges to process
        exchanges_to_process = detect_exchanges_to_process(
            args, trader_trades, exchange_trades, unified_config, exchange_map
        )
        
        # Process all exchanges
        exchange_results = process_exchanges(
            exchanges_to_process,
            trader_trades,
            exchange_trades,
            unified_config,
            args
        )
        
        # Save JSON output if requested
        if args.json_output and exchange_results:
            save_json_output(
                exchange_results,
                unified_config,
                debug_mode=(args.log_level == "DEBUG")
            )
        
        # Exit 0 for successful processing
        # Rule 0's job is to analyze and report positions from the input data
        # Discrepancies are expected analytical output, not processing errors
        sys.exit(0)
            
    except Exception:
        logger.exception("Error in main")
        sys.exit(1)


if __name__ == "__main__":
    main()