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


def get_tolerance(exchange: str, config: Dict[str, Any]) -> Decimal:
    """Get tolerance value for the exchange.
    
    Args:
        exchange: Exchange name
        config: Exchange config
        
    Returns:
        Tolerance value for comparisons
    """
    # Load normalizer config if available
    if "normalizer_config" in config:
        config_path = Path(config["normalizer_config"])
        if config_path.exists():
            with open(config_path, 'r') as f:
                normalizer_config = json.load(f)
                tolerances = normalizer_config.get("universal_tolerances", {})
                
                # For ICE, use different tolerances for MT vs BBL
                if exchange == "ice_match":
                    # We'll use MT tolerance as default
                    return Decimal(str(tolerances.get("tolerance_mt", 150)))
                else:
                    # For other exchanges, use a sensible default
                    return Decimal("0.01")
    
    # Default tolerance
    return Decimal("0.01")


def process_exchange(exchange_name: str, trader_trades: List[Dict[str, Any]], 
                     exchange_trades: List[Dict[str, Any]], show_details: bool) -> Optional[Dict[str, Any]]:
    """Process a single exchange's trades.
    
    Args:
        exchange_name: Exchange identifier (ice_match, sgx_match, etc.)
        trader_trades: List of trader trades for this exchange
        exchange_trades: List of exchange trades for this exchange
        show_details: Whether to show detailed breakdown
        
    Returns:
        Summary statistics for this exchange
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
        tolerance = get_tolerance(exchange_name, config)
        comparator = UnifiedMatrixComparator(exchange_name, tolerance)
        comparisons = comparator.compare_matrices(trader_matrix, exchange_matrix)
        
        # Get summary statistics
        stats = comparator.get_summary_statistics(comparisons)
        
        # Display results
        display_name = exchange_name.replace("_match", "").upper()
        display = UnifiedDisplay(display_name)
        display.show_header()
        display.show_summary(stats)
        display.show_comparison_by_product(comparisons)
        
        # Show detailed breakdown if requested
        if show_details:
            display.show_position_details(trader_matrix, exchange_matrix)
        
        return stats
    except Exception as e:
        logger.error(f"Error processing {exchange_name}: {e}")
        return None


def main():
    """Main entry point for unified Rule 0."""
    parser = argparse.ArgumentParser(
        description="Unified Rule 0: Position Decomposition Analyzer"
    )
    
    parser.add_argument(
        "--exchange",
        choices=["ice", "sgx", "cme", "eex"],
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
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Set logging level"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Map exchange argument to config key
    exchange_map = {
        "ice": "ice_match",
        "sgx": "sgx_match",
        "cme": "cme_match",
        "eex": "eex_match"
    }
    
    try:
        # Load trade data first
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
                # Use default paths from unified_recon
                trader_path = Path(__file__).resolve().parents[3] / "src" / "unified_recon" / "data" / "sourceTraders.csv"
                exchange_path = Path(__file__).resolve().parents[3] / "src" / "unified_recon" / "data" / "sourceExchange.csv"
            
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
        
        # Load exchange group mappings
        config_path = Path(__file__).resolve().parents[1] / "config" / "unified_config.json"
        with open(config_path, 'r') as f:
            unified_config = json.load(f)
        
        # Helper function to get exchange group
        def get_exchange_group(trade):
            group = trade.get("exchangeGroupId", trade.get("exchangegroupid", 0))
            return int(group) if group else 0
        
        # Determine which exchanges to process
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
        
        # Process each exchange
        total_discrepancies = 0
        
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
                logger.info(f"No trades found for {exchange_name}")
                continue
            
            logger.info(f"Processing {exchange_name}: {len(exchange_trader_trades)} trader trades, {len(exchange_exchange_trades)} exchange trades")
            
            # Process this exchange
            stats = process_exchange(exchange_name, exchange_trader_trades, exchange_exchange_trades, args.show_details)
            
            if stats and stats["total_discrepancies"] > 0:
                total_discrepancies += stats["total_discrepancies"]
        
        # Return appropriate exit code
        if total_discrepancies > 0:
            sys.exit(1)  # Discrepancies found
        else:
            sys.exit(0)  # All matched
            
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()