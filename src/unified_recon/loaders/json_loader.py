"""JSON loader for unified reconciliation system with field mapping."""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class UnifiedJSONLoader:
    """Loader for JSON data with field mapping for different exchange groups."""
    
    def __init__(self):
        """Initialize the JSON loader."""
        # Define field mappings for JSON to CSV conversion
        # These handle differences between JSON field names and CSV column names
        self.trader_field_mappings = {
            # JSON field -> CSV column (for trader trades)
            "internalTradeId": "internalTradeId",  # Optional, keep as-is
            "traderId": "traderid",
            "tradeDate": "tradedate",
            "tradeTime": "tradetime",
            "productId": "productid",
            "productName": "productname",
            "productGroupId": "productgroupid",
            "exchangeGroupId": "exchangegroupid",
            "brokerGroupId": "brokergroupid",
            "exchangeClearingAccountId": "exchclearingacctid",  # camelCase to snake_case
            "quantityLot": "quantitylots",  # singular to plural
            "quantityUnit": "quantityunits",  # singular to plural
            "unit": "unit",
            "price": "price",
            "contractMonth": "contractmonth",
            "strike": "strike",
            "specialComms": "specialcomms",
            "spread": "spread",
            "b/s": "b/s",  # Already in correct format
            "put/call": "put/call",  # Already in correct format
            "source": "source",  # Optional field
            "RMKS": "RMKS",  # Optional field
            "BKR": "BKR",  # Optional field
        }
        
        self.exchange_field_mappings = {
            # JSON field -> CSV column (for exchange trades)
            "internalTradeId": "internalTradeId",  # Optional, keep as-is
            "dealId": "dealid",
            "tradeId": "tradeid",
            "tradingSession": "tradingsession", 
            "traderName": "tradername",
            "traderId": "traderid",  # Added for exchange trades
            "tradeDate": "tradedate",  # Added for exchange trades
            "tradeTime": "tradedatetime",  # Special: JSON tradeTime -> CSV tradedatetime for exchange
            "exchangeGroupId": "exchangegroupid",
            "brokerGroupId": "brokergroupid",
            "exchangeClearingAccountId": "exchclearingacctid",  # camelCase to snake_case
            "quantityLot": "quantitylots",  # singular to plural
            "quantityUnit": "quantityunits",  # singular to plural
            "unit": "unit",
            "price": "price",
            "productName": "productname",
            "contractMonth": "contractmonth",
            "strike": "strike",
            "b/s": "b/s",  # Already in correct format
            "put/call": "put/call",  # Already in correct format
            "clearingStatus": "clearingstatus",
            "clearedDate": "cleareddate",
            "source": "source",  # Optional field
            "spread": "spread",  # Optional field
            "specialComms": "specialcomms",  # Optional field
        }
        
        # Define all possible fields for each trade type to ensure None values
        self.all_trader_fields = set(self.trader_field_mappings.values())
        self.all_exchange_fields = set(self.exchange_field_mappings.values())
    
    def load_json(self, json_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load JSON file and return trader and exchange DataFrames.
        
        Args:
            json_path: Path to the JSON file
            
        Returns:
            Tuple of (trader_df, exchange_df)
            
        Raises:
            FileNotFoundError: If JSON file doesn't exist
            ValueError: If JSON structure is invalid
        """
        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")
        
        logger.info(f"Loading JSON data from {json_path}")
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate JSON structure
            if not isinstance(data, dict):
                raise ValueError("JSON must be a dictionary with 'traderTrades' and 'exchangeTrades' keys")
            
            # Check for both old and new JSON key formats
            trader_key = 'traderTrades' if 'traderTrades' in data else 'trader'
            exchange_key = 'exchangeTrades' if 'exchangeTrades' in data else 'exchange'
            
            if trader_key not in data or exchange_key not in data:
                raise ValueError("JSON must contain 'traderTrades' and 'exchangeTrades' arrays")
            
            # Convert to DataFrames with field mapping
            trader_df = self._json_to_dataframe(data[trader_key], 'trader')
            exchange_df = self._json_to_dataframe(data[exchange_key], 'exchange')
            
            logger.info(f"Loaded {len(trader_df)} trader records and {len(exchange_df)} exchange records")
            
            return trader_df, exchange_df
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from {json_path}: {e}")
            raise ValueError(f"Invalid JSON format: {e}") from e
        except Exception as e:
            logger.error(f"Error loading JSON from {json_path}: {e}")
            raise
    
    def _json_to_dataframe(self, records: List[Dict[str, Any]], record_type: str) -> pd.DataFrame:
        """Convert JSON records to DataFrame with field mapping.
        
        Args:
            records: List of JSON records
            record_type: Either 'trader' or 'exchange'
            
        Returns:
            DataFrame with mapped column names matching CSV format
        """
        if not records:
            # Return empty DataFrame with expected columns
            return pd.DataFrame()
        
        # Get the appropriate field mapping and all fields set
        if record_type == 'trader':
            field_map = self.trader_field_mappings
            all_fields = self.all_trader_fields
        else:
            field_map = self.exchange_field_mappings
            all_fields = self.all_exchange_fields
        
        # Convert records with field mapping
        mapped_records = []
        for record in records:
            # Start with None for all possible fields
            mapped_record = {field: None for field in all_fields}
            
            # Map fields from JSON to CSV column names
            for json_field, value in record.items():
                if json_field in field_map:
                    csv_column = field_map[json_field]
                    mapped_record[csv_column] = value
                else:
                    # Handle unmapped fields - add them as lowercase
                    mapped_record[json_field.lower()] = value
            
            mapped_records.append(mapped_record)
        
        # Create DataFrame
        df = pd.DataFrame(mapped_records)
        
        # Ensure consistent column naming (lowercase)
        df.columns = df.columns.str.lower()
        
        return df
    
    def load_and_group_by_exchange(self, json_path: Path) -> Dict[int, Tuple[pd.DataFrame, pd.DataFrame]]:
        """Load JSON and group by exchange group ID.
        
        Args:
            json_path: Path to the JSON file
            
        Returns:
            Dictionary mapping exchange group ID to (trader_df, exchange_df) tuples
        """
        # Load the full data
        trader_df, exchange_df = self.load_json(json_path)
        
        # Group by exchangegroupid
        grouped_data = {}
        
        # Get unique exchange group IDs from both datasets
        trader_groups = set()
        exchange_groups = set()
        
        if 'exchangegroupid' in trader_df.columns and not trader_df.empty:
            trader_groups = set(trader_df['exchangegroupid'].dropna().unique())
        
        if 'exchangegroupid' in exchange_df.columns and not exchange_df.empty:
            exchange_groups = set(exchange_df['exchangegroupid'].dropna().unique())
        
        all_groups = trader_groups.union(exchange_groups)
        
        for group_id in all_groups:
            # Filter dataframes for this group
            group_trader_df = trader_df[trader_df['exchangegroupid'] == group_id] if not trader_df.empty else pd.DataFrame()
            group_exchange_df = exchange_df[exchange_df['exchangegroupid'] == group_id] if not exchange_df.empty else pd.DataFrame()
            
            # Only add if there's data for this group
            if not group_trader_df.empty or not group_exchange_df.empty:
                grouped_data[int(group_id)] = (group_trader_df, group_exchange_df)
                logger.info(f"Group {group_id}: {len(group_trader_df)} trader, {len(group_exchange_df)} exchange records")
        
        return grouped_data