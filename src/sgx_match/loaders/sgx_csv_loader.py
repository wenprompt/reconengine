"""CSV loader for SGX trade data with normalization."""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import uuid

from ..models import SGXTrade, SGXTradeSource
from ..normalizers import SGXTradeNormalizer
from ..config import SGXConfigManager

logger = logging.getLogger(__name__)


class SGXCSVLoader:
    """Loads and normalizes SGX trade data from CSV files."""
    
    def __init__(self, config_manager: SGXConfigManager):
        """Initialize CSV loader with configuration.
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        self.normalizer = SGXTradeNormalizer(config_manager)
        
        logger.info("Initialized SGX CSV loader")
    
    def load_trader_trades(self, csv_path: Path) -> List[SGXTrade]:
        """Load trader trades from CSV file.
        
        Args:
            csv_path: Path to trader CSV file
            
        Returns:
            List of normalized SGX trader trades
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV has invalid format
        """
        logger.info(f"Loading SGX trader trades from {csv_path}")
        
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(df)} raw trader records")
            
            trades = []
            # Use empty dict since we'll work directly with column names
            field_mappings: Dict[str, str] = {}
            
            for idx, row in df.iterrows():
                try:
                    index = int(idx) if isinstance(idx, (int, float)) else 0
                    trade = self._create_trader_trade(row, field_mappings, index)
                    if trade:
                        trades.append(trade)
                except Exception as e:
                    logger.error(f"Failed to create trader trade from row {idx}: {e}")
                    continue
            
            logger.info(f"Successfully created {len(trades)} SGX trader trades")
            return trades
            
        except FileNotFoundError:
            logger.error(f"Trader CSV file not found: {csv_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to load trader trades: {e}")
            raise ValueError(f"Invalid trader CSV format: {e}")
    
    def load_exchange_trades(self, csv_path: Path) -> List[SGXTrade]:
        """Load exchange trades from CSV file.
        
        Args:
            csv_path: Path to exchange CSV file
            
        Returns:
            List of normalized SGX exchange trades
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV has invalid format
        """
        logger.info(f"Loading SGX exchange trades from {csv_path}")
        
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(df)} raw exchange records")
            
            trades = []
            # Use empty dict since we'll work directly with column names
            field_mappings: Dict[str, str] = {}
            
            for idx, row in df.iterrows():
                try:
                    index = int(idx) if isinstance(idx, (int, float)) else 0
                    trade = self._create_exchange_trade(row, field_mappings, index)
                    if trade:
                        trades.append(trade)
                except Exception as e:
                    logger.error(f"Failed to create exchange trade from row {idx}: {e}")
                    continue
            
            logger.info(f"Successfully created {len(trades)} SGX exchange trades")
            return trades
            
        except FileNotFoundError:
            logger.error(f"Exchange CSV file not found: {csv_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to load exchange trades: {e}")
            raise ValueError(f"Invalid exchange CSV format: {e}")
    
    def _create_trader_trade(self, row: pd.Series, field_mappings: Dict[str, str], 
                           index: int) -> Optional[SGXTrade]:
        """Create SGX trader trade from CSV row.
        
        Args:
            row: Pandas series representing CSV row
            field_mappings: Field name mappings
            index: Row index for ID generation
            
        Returns:
            SGXTrade object or None if invalid
        """
        try:
            # Generate trade ID if not present
            trade_id = self._get_field_value(row, "traderid", field_mappings)
            if not trade_id:
                trade_id = f"T_{index}_{uuid.uuid4().hex[:6]}"
            
            # Extract and normalize core fields
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
                logger.warning(f"Skipping trader trade {index}: missing essential fields")
                return None
            
            # Ensure quantity_units and price are not None before passing to SGXTrade
            if quantity_units is None or price is None:
                logger.warning(f"Skipping trader trade {index}: quantity or price is None")
                return None
            
            # Extract other fields
            quantity_lots = self.normalizer.normalize_quantity(
                self._get_field_value(row, "quantitylots", field_mappings)
            )
            
            broker_group_id = self.normalizer.normalize_integer_field(
                self._get_field_value(row, "brokergroupid", field_mappings)
            )
            
            exch_clearing_acct_id = self.normalizer.normalize_integer_field(
                self._get_field_value(row, "exchclearingacctid", field_mappings)
            )
            
            return SGXTrade(
                trade_id=trade_id,
                source=SGXTradeSource.TRADER,
                product_name=product_name,
                quantity_lots=quantity_lots,
                quantity_units=quantity_units,
                unit=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "unit", field_mappings)
                ),
                price=price,
                contract_month=contract_month,
                buy_sell=buy_sell,
                broker_group_id=broker_group_id,
                exch_clearing_acct_id=exch_clearing_acct_id,
                exchange_group_id=self.normalizer.normalize_integer_field(
                    self._get_field_value(row, "exchangegroupid", field_mappings)
                ),
                strike=self.normalizer.normalize_price(
                    self._get_field_value(row, "strike", field_mappings)
                ),
                put_call=None,  # Trader data doesn't have put/call
                spread=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "spread", field_mappings)
                ),
                trade_date=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "tradedate", field_mappings)
                ),
                trade_time=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "tradetime", field_mappings)
                ),
                trade_datetime=None,  # Trader data doesn't have combined datetime
                trader_id=trade_id,
                product_id=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "productid", field_mappings)
                ),
                product_group_id=self.normalizer.normalize_integer_field(
                    self._get_field_value(row, "productgroupid", field_mappings)
                ),
                special_comms=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "specialComms", field_mappings)
                ),
                remarks=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "RMKS", field_mappings)
                ),
                broker=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "BKR", field_mappings)
                ),
                deal_id=None,  # Trader data doesn't have deal_id
                clearing_status=None,  # Trader data doesn't have clearing_status
                trader_name=None,  # Trader data doesn't have trader_name
                trading_session=None,  # Trader data doesn't have trading_session
                cleared_date=None  # Trader data doesn't have cleared_date
            )
            
        except Exception as e:
            logger.error(f"Error creating trader trade from row {index}: {e}")
            return None
    
    def _create_exchange_trade(self, row: pd.Series, field_mappings: Dict[str, str], 
                             index: int) -> Optional[SGXTrade]:
        """Create SGX exchange trade from CSV row.
        
        Args:
            row: Pandas series representing CSV row
            field_mappings: Field name mappings
            index: Row index for ID generation
            
        Returns:
            SGXTrade object or None if invalid
        """
        try:
            # Extract trade ID
            trade_id = self.normalizer.normalize_string_field(
                self._get_field_value(row, "tradeid", field_mappings)
            )
            
            if not trade_id:
                trade_id = f"E_{index}_{uuid.uuid4().hex[:6]}"
            
            # Extract and normalize core fields
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
                logger.warning(f"Skipping exchange trade {index}: missing essential fields")
                return None
            
            # Ensure quantity_units and price are not None before passing to SGXTrade
            if quantity_units is None or price is None:
                logger.warning(f"Skipping exchange trade {index}: quantity or price is None")
                return None
            
            # Extract other fields
            quantity_lots = self.normalizer.normalize_quantity(
                self._get_field_value(row, "quantitylots", field_mappings)
            )
            
            broker_group_id = self.normalizer.normalize_integer_field(
                self._get_field_value(row, "brokergroupid", field_mappings)
            )
            
            exch_clearing_acct_id = self.normalizer.normalize_integer_field(
                self._get_field_value(row, "exchclearingacctid", field_mappings)
            )
            
            return SGXTrade(
                trade_id=trade_id,
                source=SGXTradeSource.EXCHANGE,
                product_name=product_name,
                quantity_lots=quantity_lots,
                quantity_units=quantity_units,
                unit=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "unit", field_mappings)
                ),
                price=price,
                contract_month=contract_month,
                buy_sell=buy_sell,
                broker_group_id=broker_group_id,
                exch_clearing_acct_id=exch_clearing_acct_id,
                exchange_group_id=self.normalizer.normalize_integer_field(
                    self._get_field_value(row, "exchangegroupid", field_mappings)
                ),
                strike=self.normalizer.normalize_price(
                    self._get_field_value(row, "strike", field_mappings)
                ),
                put_call=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "put/call", field_mappings)
                ),
                spread=None,  # Exchange data doesn't have spread field
                trade_date=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "tradedate", field_mappings)
                ),
                trade_time=None,  # Exchange data doesn't have separate trade_time
                trade_datetime=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "tradedatetime", field_mappings)
                ),
                trader_id=None,  # Exchange data doesn't have trader_id
                product_id=None,  # Exchange data doesn't have product_id
                product_group_id=None,  # Exchange data doesn't have product_group_id
                special_comms=None,  # Exchange data doesn't have special_comms
                remarks=None,  # Exchange data doesn't have remarks
                broker=None,  # Exchange data doesn't have broker
                deal_id=self.normalizer.normalize_integer_field(
                    self._get_field_value(row, "dealid", field_mappings)
                ),
                clearing_status=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "clearingstatus", field_mappings)
                ),
                trader_name=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "trader", field_mappings)
                ),
                trading_session=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "tradingsession", field_mappings)
                ),
                cleared_date=self.normalizer.normalize_string_field(
                    self._get_field_value(row, "cleareddate", field_mappings)
                )
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