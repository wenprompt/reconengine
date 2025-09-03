"""CSV loader for SGX trade data with normalization."""

import pandas as pd
from pathlib import Path
from typing import List, Any, Optional, Callable
import logging

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
        return self._load_trades(csv_path, self._create_trader_trade, "trader")
    
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
        return self._load_trades(csv_path, self._create_exchange_trade, "exchange")
    
    def _load_trades(self, csv_path: Path, create_trade_func: Callable[..., Optional[SGXTrade]], trade_type: str) -> List[SGXTrade]:
        """Generic method to load SGX CSV data and create trade objects.
        
        Args:
            csv_path: Path to CSV file
            create_trade_func: Function to create trade objects (self._create_trader_trade or self._create_exchange_trade)
            trade_type: Type of trades ('trader' or 'exchange') for logging
            
        Returns:
            List of SGXTrade objects created from the CSV data
            
        Raises:
            FileNotFoundError: If CSV file not found
            ValueError: If CSV format is invalid
        """
        try:
            logger.info(f"Loading {trade_type} CSV from: {csv_path}")
            
            # Load CSV with proper encoding
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            
            # Normalize column names to lowercase and replace special chars
            df.columns = df.columns.str.strip().str.lower().str.replace('/', '_')
            
            logger.info(f"Successfully loaded {len(df)} rows from {trade_type} CSV")
            
            trades = []
            # Ensure deterministic 0-based integer indices for IDs
            df = df.reset_index(drop=True)
            for i, row in df.iterrows():
                try:
                    trade = create_trade_func(row, i)
                    if trade:
                        trades.append(trade)
                except Exception as e:
                    logger.error(f"Failed to create {trade_type} trade from row {i}: {e}")
                    continue
            
            logger.info(f"Successfully created {len(trades)} SGX {trade_type} trades")
            return trades
            
        except FileNotFoundError:
            logger.error(f"{trade_type.capitalize()} CSV file not found: {csv_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to load {trade_type} trades: {e}")
            raise ValueError(f"Invalid {trade_type} CSV format: {e}") from e
    
    def _create_trader_trade(self, row: pd.Series, index: int) -> Optional[SGXTrade]:
        """Create SGX trader trade from CSV row.
        
        Args:
            row: Pandas series representing CSV row
            index: Row index for ID generation
            
        Returns:
            SGXTrade object or None if invalid
        """
        try:
            # Extract trader ID from CSV (keep distinct from trade_id)
            trader_id = self._safe_str(row.get("traderid"))
            
            # Generate unique trade ID (always generate, don't conflate with trader_id)
            internal_trade_id = f"T_{index}"
            
            # Extract and normalize core fields
            product_name = self.normalizer.normalize_product_name(
                self._safe_str(row.get("productname", ""))
            )
            
            quantity_units = self.normalizer.normalize_quantity(
                row.get("quantityunits")
            )
            
            price = self.normalizer.normalize_price(
                row.get("price")
            )
            
            contract_month = self.normalizer.normalize_contract_month(
                self._safe_str(row.get("contractmonth", ""))
            )
            
            buy_sell = self.normalizer.normalize_buy_sell(
                self._safe_str(row.get("b_s", ""))
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
            
            # Log PS trades specifically during loading
            spread = self.normalizer.normalize_string_field(
                row.get("spread")
            )
            if spread and 'PS' in str(spread).upper():
                logger.debug(f"Loading PS trade: {product_name}/{buy_sell}, price={price}, spread={spread}, index={index}")
            
            # Extract other fields
            quantity_lots = self.normalizer.normalize_quantity(
                row.get("quantitylots")
            )
            
            broker_group_id = self.normalizer.normalize_integer_field(
                row.get("brokergroupid")
            )
            
            exch_clearing_acct_id = self.normalizer.normalize_integer_field(
                row.get("exchclearingacctid")
            )
            
            return SGXTrade(
                internal_trade_id=internal_trade_id,
                source=SGXTradeSource.TRADER,
                product_name=product_name,
                quantity_lots=quantity_lots,
                quantity_units=quantity_units,
                unit=self.normalizer.normalize_string_field(
                    row.get("unit")
                ),
                price=price,
                contract_month=contract_month,
                buy_sell=buy_sell,
                broker_group_id=broker_group_id,
                exch_clearing_acct_id=exch_clearing_acct_id,
                exchange_group_id=self.normalizer.normalize_integer_field(
                    row.get("exchangegroupid")
                ),
                strike=self.normalizer.normalize_price(
                    row.get("strike")
                ),
                put_call=None,  # Trader data doesn't have put/call
                spread=self.normalizer.normalize_string_field(
                    row.get("spread")
                ),
                trade_date=self.normalizer.normalize_string_field(
                    row.get("tradedate")
                ),
                trade_time=self.normalizer.normalize_string_field(
                    row.get("tradetime")
                ),
                trader_id=trader_id,
                product_id=self.normalizer.normalize_string_field(
                    row.get("productid")
                ),
                product_group_id=self.normalizer.normalize_integer_field(
                    row.get("productgroupid")
                ),
                special_comms=self.normalizer.normalize_string_field(
                    row.get("specialcomms")
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
    
    def _create_exchange_trade(self, row: pd.Series, index: int) -> Optional[SGXTrade]:
        """Create SGX exchange trade from CSV row.
        
        Args:
            row: Pandas series representing CSV row
            index: Row index for ID generation
            
        Returns:
            SGXTrade object or None if invalid
        """
        try:
            # Always generate consistent trade ID with row index for easy identification
            internal_trade_id = f"E_{index}"
            
            # Extract and normalize core fields
            product_name = self.normalizer.normalize_product_name(
                row.get("productname", "")
            )
            
            quantity_units = self.normalizer.normalize_quantity(
                row.get("quantityunits")
            )
            
            price = self.normalizer.normalize_price(
                row.get("price")
            )
            
            contract_month = self.normalizer.normalize_contract_month(
                row.get("contractmonth", "")
            )
            
            buy_sell = self.normalizer.normalize_buy_sell(
                row.get("b_s", "")
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
                row.get("quantitylots")
            )
            
            broker_group_id = self.normalizer.normalize_integer_field(
                row.get("brokergroupid")
            )
            
            exch_clearing_acct_id = self.normalizer.normalize_integer_field(
                row.get("exchclearingacctid")
            )
            
            return SGXTrade(
                internal_trade_id=internal_trade_id,
                source=SGXTradeSource.EXCHANGE,
                product_name=product_name,
                quantity_lots=quantity_lots,
                quantity_units=quantity_units,
                unit=self.normalizer.normalize_string_field(
                    row.get("unit")
                ),
                price=price,
                contract_month=contract_month,
                buy_sell=buy_sell,
                broker_group_id=broker_group_id,
                exch_clearing_acct_id=exch_clearing_acct_id,
                exchange_group_id=self.normalizer.normalize_integer_field(
                    row.get("exchangegroupid")
                ),
                strike=self.normalizer.normalize_price(
                    row.get("strike")
                ),
                put_call=self.normalizer.normalize_string_field(
                    row.get("put_call")
                ),
                spread=None,  # Exchange data doesn't have spread field
                trade_date=self.normalizer.normalize_string_field(
                    row.get("tradedate")
                ),
                trade_time=self.normalizer.normalize_string_field(
                    row.get("tradetime")  # Exchange now uses standardized tradetime column
                ),
                trader_id=None,  # Exchange data doesn't have trader_id
                product_id=None,  # Exchange data doesn't have product_id
                product_group_id=None,  # Exchange data doesn't have product_group_id
                special_comms=None,  # Exchange data doesn't have special_comms
                deal_id=self.normalizer.normalize_id_field(
                    row.get("dealid")
                ),
                clearing_status=self.normalizer.normalize_string_field(
                    row.get("clearingstatus")
                ),
                trader_name=self.normalizer.normalize_string_field(
                    row.get("traderid")
                ),
                trading_session=self.normalizer.normalize_string_field(
                    row.get("tradingsession")
                ),
                cleared_date=self.normalizer.normalize_string_field(
                    row.get("cleareddate")
                )
            )
            
        except Exception as e:
            logger.error(f"Error creating exchange trade from row {index}: {e}")
            return None
    
    def _safe_str(self, value: Any) -> str:
        """Safely convert value to string, handling NaN and None."""
        if pd.isna(value) or value is None:
            return ""
        return str(value).strip()
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert value to int, returning None for invalid values."""
        if pd.isna(value) or value is None or value == "":
            return None
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return None