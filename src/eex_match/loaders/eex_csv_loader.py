"""CSV loader for EEX trade data with normalization."""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import logging

from ..models import EEXTrade, EEXTradeSource
from ..normalizers import EEXTradeNormalizer
from ..config import EEXConfigManager

logger = logging.getLogger(__name__)


class EEXCSVLoader:
    """Loads and normalizes EEX trade data from CSV files."""
    
    def __init__(self, config_manager: EEXConfigManager):
        """Initialize CSV loader with configuration.
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        self.normalizer = EEXTradeNormalizer(config_manager)
        
        logger.info("Initialized EEX CSV loader")
    
    def load_trader_trades(self, csv_path: Path) -> List[EEXTrade]:
        """Load trader trades from CSV file.
        
        Args:
            csv_path: Path to trader CSV file
            
        Returns:
            List of normalized EEX trader trades
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV has invalid format
        """
        return self._load_trades(csv_path, self._create_trader_trade, "trader")
    
    def load_exchange_trades(self, csv_path: Path) -> List[EEXTrade]:
        """Load exchange trades from CSV file.
        
        Args:
            csv_path: Path to exchange CSV file
            
        Returns:
            List of normalized EEX exchange trades
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV has invalid format
        """
        return self._load_trades(csv_path, self._create_exchange_trade, "exchange")
    
    def _load_trades(self, csv_path: Path, create_trade_func: Callable[..., Optional[EEXTrade]], trade_type: str) -> List[EEXTrade]:
        """Generic method to load EEX CSV data and create trade objects.
        
        Args:
            csv_path: Path to CSV file
            create_trade_func: Function to create trade objects (self._create_trader_trade or self._create_exchange_trade)
            trade_type: Type of trades ('trader' or 'exchange') for logging
            
        Returns:
            List of EEXTrade objects created from the CSV data
            
        Raises:
            FileNotFoundError: If CSV file not found
            ValueError: If CSV format is invalid
        """
        try:
            logger.info(f"Loading {trade_type} CSV from: {csv_path}")
            
            # Load CSV with proper encoding
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            
            # Clean column names
            df.columns = df.columns.str.strip()
            
            logger.info(f"Successfully loaded {len(df)} rows from {trade_type} CSV")
            
            # Get field mappings for the trade type
            field_mappings = self.config_manager.get_field_mappings()[f"{trade_type}_mappings"]
            
            trades = []
            # Ensure deterministic 0-based integer indices for IDs
            df = df.reset_index(drop=True)
            for i, row in df.iterrows():
                try:
                    trade = create_trade_func(row, field_mappings, i)
                    if trade:
                        trades.append(trade)
                except Exception as e:
                    logger.error(f"Failed to create {trade_type} trade from row {i}: {e}")
                    continue
            
            logger.info(f"Successfully created {len(trades)} EEX {trade_type} trades")
            return trades
            
        except FileNotFoundError:
            logger.error(f"{trade_type.capitalize()} CSV file not found: {csv_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to load {trade_type} trades: {e}")
            raise ValueError(f"Invalid {trade_type} CSV format: {e}") from e

    def _extract_common_fields(self, row: pd.Series, field_mappings: Dict[str, str], 
                              index: int, source: EEXTradeSource) -> Optional[Dict[str, Any]]:
        """Extract and normalize common fields from CSV row.
        
        Args:
            row: Pandas series representing CSV row
            field_mappings: Field name mappings
            index: Row index for ID generation
            source: Trade source (TRADER or EXCHANGE)
            
        Returns:
            Dict of common normalized fields or None if essential fields missing
        """
        try:
            # Generate deterministic trade ID using row index
            prefix = "T" if source == EEXTradeSource.TRADER else "E"
            trade_id = f"{prefix}_{index}"
            
            # Extract and normalize core fields - using quantityunits for EEX
            product_name = self.normalizer.normalize_product_name(
                self._get_field_value(row, "productname", field_mappings, "")
            )
            
            quantity_units = self.normalizer.normalize_quantity(
                self._get_field_value(row, "quantityunits", field_mappings)
            )
            
            price = self.normalizer.normalize_price(
                self._get_field_value(row, "price", field_mappings)
            )
            
            contract_month = self.normalizer.normalize_contract_month(
                self._get_field_value(row, "contractmonth", field_mappings, "")
            )
            
            buy_sell = self.normalizer.normalize_buy_sell(
                self._get_field_value(row, "b/s", field_mappings, "")
            )
            
            # Skip if essential fields are missing
            if not all([product_name, quantity_units is not None, price is not None, 
                       contract_month, buy_sell]):
                logger.warning(f"Skipping {source.value} trade {index}: missing essential fields")
                return None
            
            # Extract universal fields
            broker_group_id = self.normalizer.normalize_integer_field(
                self._get_field_value(row, "brokergroupid", field_mappings)
            )
            
            exch_clearing_acct_id = self.normalizer.normalize_integer_field(
                self._get_field_value(row, "exchclearingacctid", field_mappings)
            )
            
            # Extract common optional fields
            exchange_group_id = self.normalizer.normalize_integer_field(
                self._get_field_value(row, "exchangegroupid", field_mappings)
            )
            
            strike = self.normalizer.normalize_price(
                self._get_field_value(row, "strike", field_mappings)
            )
            
            put_call = self.normalizer.normalize_string_field(
                self._get_field_value(row, "put/call", field_mappings)
            ) or None
            
            product_id = self.normalizer.normalize_string_field(
                self._get_field_value(row, "productid", field_mappings)
            ) or None
            
            product_group_id = self.normalizer.normalize_integer_field(
                self._get_field_value(row, "productgroupid", field_mappings)
            )
            
            trade_date = self.normalizer.normalize_string_field(
                self._get_field_value(row, "tradedate", field_mappings)
            ) or None
            
            unit = self.normalizer.normalize_string_field(
                self._get_field_value(row, "unit", field_mappings)
            ) or None
            
            return {
                # Core fields
                "trade_id": trade_id,
                "source": source,
                "product_name": product_name,
                "quantity_units": quantity_units,
                "unit": unit,
                "price": price,
                "contract_month": contract_month,
                "buy_sell": buy_sell,
                
                # Universal fields
                "broker_group_id": broker_group_id,
                "exch_clearing_acct_id": exch_clearing_acct_id,
                
                # Common optional fields
                "exchange_group_id": exchange_group_id,
                "strike": strike,
                "put_call": put_call,
                "product_id": product_id,
                "product_group_id": product_group_id,
                "trade_date": trade_date,
            }
            
        except Exception as e:
            logger.error(f"Error extracting common fields from row {index}: {e}")
            return None
    
    def _create_trader_trade(self, row: pd.Series, field_mappings: Dict[str, str], 
                           index: int) -> Optional[EEXTrade]:
        """Create EEX trader trade from CSV row.
        
        Args:
            row: Pandas series representing CSV row
            field_mappings: Field name mappings
            index: Row index for ID generation
            
        Returns:
            EEXTrade object or None if invalid
        """
        try:
            # Extract common fields
            common_fields = self._extract_common_fields(row, field_mappings, index, EEXTradeSource.TRADER)
            if not common_fields:
                return None
            
            # Extract trader-specific fields
            spread = self.normalizer.normalize_string_field(
                self._get_field_value(row, "spread", field_mappings)
            ) or None
            
            trade_time = self.normalizer.normalize_string_field(
                self._get_field_value(row, "tradetime", field_mappings)
            ) or None
            
            trader_id = self.normalizer.normalize_string_field(
                self._get_field_value(row, "traderid", field_mappings)
            ) or None
            
            special_comms = self.normalizer.normalize_string_field(
                self._get_field_value(row, "specialComms", field_mappings)
            ) or None
            
            remarks = self.normalizer.normalize_string_field(
                self._get_field_value(row, "RMKS", field_mappings)
            ) or None
            
            broker = self.normalizer.normalize_string_field(
                self._get_field_value(row, "BKR", field_mappings)
            ) or None
            
            return EEXTrade(
                # Common fields
                **common_fields,
                
                # Trader-specific fields
                spread=spread,
                trade_time=trade_time,
                trade_datetime=None,  # Trader data doesn't have combined datetime
                trader_id=trader_id,
                special_comms=special_comms,
                remarks=remarks,
                broker=broker,
                
                # Fields not present in trader data
                deal_id=None,
                clearing_status=None,
                trader_name=None,
                trading_session=None,
                cleared_date=None
            )
            
        except Exception as e:
            logger.error(f"Error creating trader trade from row {index}: {e}")
            return None
    
    def _create_exchange_trade(self, row: pd.Series, field_mappings: Dict[str, str], 
                             index: int) -> Optional[EEXTrade]:
        """Create EEX exchange trade from CSV row.
        
        Args:
            row: Pandas series representing CSV row
            field_mappings: Field name mappings
            index: Row index for ID generation
            
        Returns:
            EEXTrade object or None if invalid
        """
        try:
            # Extract common fields
            common_fields = self._extract_common_fields(row, field_mappings, index, EEXTradeSource.EXCHANGE)
            if not common_fields:
                return None
            
            # Extract exchange-specific fields
            trade_datetime = self.normalizer.normalize_string_field(
                self._get_field_value(row, "tradedatetime", field_mappings)
            ) or None
            
            deal_id = self.normalizer.normalize_integer_field(
                self._get_field_value(row, "dealid", field_mappings)
            )
            
            clearing_status = self.normalizer.normalize_string_field(
                self._get_field_value(row, "clearingstatus", field_mappings)
            ) or None
            
            trader_name = self.normalizer.normalize_string_field(
                self._get_field_value(row, "traderid", field_mappings)
            ) or None
            
            trading_session = self.normalizer.normalize_string_field(
                self._get_field_value(row, "tradingsession", field_mappings)
            ) or None
            
            cleared_date = self.normalizer.normalize_string_field(
                self._get_field_value(row, "cleareddate", field_mappings)
            ) or None
            
            return EEXTrade(
                # Common fields
                **common_fields,
                
                # Exchange-specific fields
                spread=None,  # Exchange data doesn't have spread field
                trade_time=None,  # Exchange data doesn't have separate trade_time
                trade_datetime=trade_datetime,
                trader_id=None,  # Exchange data doesn't have trader_id
                special_comms=None,  # Exchange data doesn't have special_comms
                remarks=None,  # Exchange data doesn't have remarks
                broker=None,  # Exchange data doesn't have broker
                deal_id=deal_id,
                clearing_status=clearing_status,
                trader_name=trader_name,
                trading_session=trading_session,
                cleared_date=cleared_date
            )
            
        except Exception as e:
            logger.error(f"Error creating exchange trade from row {index}: {e}")
            return None
    
    def _get_field_value(self, row: pd.Series, field_name: str, 
                        field_mappings: Dict[str, str], default: Any = None) -> Any:
        """Get field value from row using field mappings.
        
        Args:
            row: Pandas series representing CSV row
            field_name: Field name to look up
            field_mappings: Field name mappings
            default: Default value if field not found
            
        Returns:
            Field value or default
        """
        # Use original field name if no mapping exists
        actual_field_name = field_mappings.get(field_name, field_name)
        
        # Get value, handling NaN/missing values
        value = row.get(actual_field_name, default)
        
        # Convert pandas NaN to None/default
        if pd.isna(value):
            return default
        
        return value