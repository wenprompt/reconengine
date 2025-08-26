"""Trade grouping and routing logic for unified reconciliation system."""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, cast
import logging
import json

from ..utils.data_validator import DataValidator, DataValidationError

logger = logging.getLogger(__name__)


class UnifiedTradeRouter:
    """Routes trades to appropriate matching systems based on exchange group."""
    
    def __init__(self, config_path: Path):
        """Initialize router with configuration.
        
        Args:
            config_path: Path to unified configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.validator = DataValidator(self.config['data_settings']['required_columns'])
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file.
        
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file not found
            ValueError: If config file has invalid JSON
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config: Dict[str, Any] = json.load(f)
            logger.info(f"Loaded unified configuration from {self.config_path}")
            return config
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file {self.config_path}: {e}") from e
    
    def load_and_validate_data(self, data_dir: Optional[Path] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load and validate trader and exchange data.
        
        Args:
            data_dir: Optional custom data directory, uses config default if None
            
        Returns:
            Tuple of (trader_df, exchange_df)
            
        Raises:
            DataValidationError: If data validation fails
        """
        # Use provided data_dir or default from config
        if data_dir is None:
            data_dir = Path(self.config['data_settings']['default_data_dir'])
        
        trader_file = data_dir / self.config['data_settings']['trader_file']
        exchange_file = data_dir / self.config['data_settings']['exchange_file']
        
        logger.info(f"Loading data from: {data_dir}")
        
        # Validate files exist
        self.validator.validate_file_exists(trader_file)
        self.validator.validate_file_exists(exchange_file)
        
        # Load CSV files
        try:
            trader_df = pd.read_csv(trader_file)
            exchange_df = pd.read_csv(exchange_file)
        except Exception as e:
            raise DataValidationError(f"Failed to load CSV files: {e}") from e
        
        # Validate structure
        self.validator.validate_csv_structure(trader_df, 'trader', trader_file)
        self.validator.validate_csv_structure(exchange_df, 'exchange', exchange_file)
        
        # Validate and get exchange groups
        trader_groups, trader_counts = self.validator.validate_exchange_groups(trader_df, trader_file)
        exchange_groups, exchange_counts = self.validator.validate_exchange_groups(exchange_df, exchange_file)
        
        # Validate consistency between datasets
        self.validator.validate_data_consistency(trader_groups, exchange_groups)
        
        logger.info(f"Successfully loaded and validated data: {len(trader_df)} trader trades, {len(exchange_df)} exchange trades")
        return trader_df, exchange_df
        
        # Validate structure
    
    def group_trades_by_exchange_group(self, trader_df: pd.DataFrame, exchange_df: pd.DataFrame) -> Dict[int, Dict[str, Any]]:
        """Group trades by exchange group and prepare for routing.
        
        Args:
            trader_df: Trader trades DataFrame
            exchange_df: Exchange trades DataFrame
            
        Returns:
            Dict mapping group_id to group info with DataFrames and system info
        """
        # Get all unique exchange groups from both datasets
        trader_groups = set(trader_df['exchangegroupid'].dropna().astype(int))
        exchange_groups = set(exchange_df['exchangegroupid'].dropna().astype(int))
        all_groups = trader_groups | exchange_groups
        
        grouped_trades = {}
        
        for group_id in sorted(all_groups):
            # Filter data for this group
            group_trader_df = trader_df[trader_df['exchangegroupid'] == group_id].copy()
            group_exchange_df = exchange_df[exchange_df['exchangegroupid'] == group_id].copy()
            
            # Determine matching system for this group
            system_name = self._get_system_for_group(group_id)
            system_config = self.config['system_configs'].get(system_name, {})
            
            # Validate group data quality
            trader_stats = self.validator.validate_group_data_quality(group_trader_df, group_id, 'trader') if not group_trader_df.empty else None
            exchange_stats = self.validator.validate_group_data_quality(group_exchange_df, group_id, 'exchange') if not group_exchange_df.empty else None
            
            grouped_trades[group_id] = {
                'group_id': group_id,
                'system': system_name,
                'system_config': system_config,
                'trader_data': group_trader_df,
                'exchange_data': group_exchange_df,
                'trader_count': len(group_trader_df),
                'exchange_count': len(group_exchange_df),
                'trader_stats': trader_stats,
                'exchange_stats': exchange_stats,
                'has_data': len(group_trader_df) > 0 and len(group_exchange_df) > 0
            }
            
            logger.info(f"Group {group_id}: {len(group_trader_df)} trader trades, {len(group_exchange_df)} exchange trades → {system_name}")
        
        return grouped_trades
    
    def _get_system_for_group(self, group_id: int) -> str:
        """Determine which matching system to use for an exchange group.
        
        Args:
            group_id: Exchange group ID
            
        Returns:
            System name ('ice_match', 'sgx_match', etc.)
        """
        group_str = str(group_id)
        system_name = cast(str, self.config['exchange_group_mappings'].get(group_str, 'unknown'))
        
        if system_name == 'unknown':
            logger.warning(f"No system mapping found for exchange group {group_id}, skipping")
        
        return system_name
    
    def get_processable_groups(self, grouped_trades: Dict[int, Dict[str, Any]]) -> List[int]:
        """Get list of exchange groups that can be processed.
        
        Args:
            grouped_trades: Grouped trade data from group_trades_by_exchange_group
            
        Returns:
            List of group IDs that have data and known system mappings
        """
        processable = []
        
        for group_id, group_info in grouped_trades.items():
            if (group_info['has_data'] and 
                group_info['system'] != 'unknown' and
                group_info['system'] in self.config['system_configs']):
                processable.append(group_id)
            else:
                reasons = []
                if not group_info['has_data']:
                    reasons.append("no data")
                if group_info['system'] == 'unknown':
                    reasons.append("no system mapping")
                if group_info['system'] not in self.config['system_configs']:
                    reasons.append("unknown system")
                
                logger.warning(f"Group {group_id} not processable: {', '.join(reasons)}")
        
        logger.info(f"Found {len(processable)} processable groups: {processable}")
        return processable
    
    def prepare_data_for_system(self, group_info: Dict[str, Any], system_name: str) -> Dict[str, Any]:
        """Prepare group data for specific matching system.
        
        Args:
            group_info: Group information from group_trades_by_exchange_group
            system_name: Target system name ('ice_match', 'sgx_match')
            
        Returns:
            Dict with data prepared for the target system
        """
        # Derive system_config from the requested system
        resolved_config = self.config["system_configs"].get(system_name, {})
        if group_info["system"] != system_name:
            logger.warning(
                f"System override for group {group_info['group_id']}: "
                f"{group_info['system']} -> {system_name}"
            )

        prepared_data = {
            'group_id': group_info['group_id'],
            'system': system_name,
            'trader_data': group_info['trader_data'],
            'exchange_data': group_info['exchange_data'],
            'trader_count': group_info['trader_count'],
            'exchange_count': group_info['exchange_count'],
            'system_config': resolved_config,
        }
        
        logger.debug(f"Prepared data for group {group_info['group_id']} → {system_name}: "
                    f"{group_info['trader_count']} trader, {group_info['exchange_count']} exchange trades")
        
        return prepared_data