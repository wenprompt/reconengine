"""CSV loader for CME trade data with normalization."""

import pandas as pd
from pathlib import Path
from typing import List, Any, Optional, Callable
import logging

from ..models import CMETrade, CMETradeSource
from ..normalizers import CMETradeNormalizer
from ..config import CMEConfigManager

logger = logging.getLogger(__name__)


class CMECSVLoader:
    """Loads and normalizes CME trade data from CSV files."""
    
    def __init__(self, config_manager: CMEConfigManager):
        """Initialize CSV loader with configuration.
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        self.normalizer = CMETradeNormalizer(config_manager)
        
        logger.info("Initialized CME CSV loader")
    
    def load_trader_trades(self, csv_path: Path) -> List[CMETrade]:
        """Load trader trades from CSV file.
        
        Args:
            csv_path: Path to trader CSV file
            
        Returns:
            List of normalized CME trader trades
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV has invalid format
        """
        return self._load_trades(csv_path, self._create_trader_trade, "trader")
    
    def load_exchange_trades(self, csv_path: Path) -> List[CMETrade]:
        """Load exchange trades from CSV file.
        
        Args:
            csv_path: Path to exchange CSV file
            
        Returns:
            List of normalized CME exchange trades
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV has invalid format
        """
        return self._load_trades(csv_path, self._create_exchange_trade, "exchange")
    
    def _load_trades(self, csv_path: Path, create_trade_func: Callable[..., Optional[CMETrade]], trade_type: str) -> List[CMETrade]:
        """Generic method to load CME CSV data and create trade objects.
        
        Args:
            csv_path: Path to CSV file
            create_trade_func: Function to create trade objects (self._create_trader_trade or self._create_exchange_trade)
            trade_type: Type of trades ('trader' or 'exchange') for logging
            
        Returns:
            List of CMETrade objects created from the CSV data
            
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
            
            logger.info(f"Successfully created {len(trades)} CME {trade_type} trades")
            return trades
            
        except FileNotFoundError:
            logger.error(f"{trade_type.capitalize()} CSV file not found: {csv_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to load {trade_type} trades: {e}")
            raise ValueError(f"Invalid {trade_type} CSV format: {e}") from e
    
    def _create_trader_trade(self, row: pd.Series, index: int) -> Optional[CMETrade]:
        """Create CME trader trade from CSV row.
        
        Args:
            row: Pandas series representing CSV row
            index: Row index for ID generation
            
        Returns:
            CMETrade object or None if invalid
        """
        try:
            # Generate unique trade ID
            trade_id = f"T_{index}"
            
            # Extract and normalize core fields
            product_name = self.normalizer.normalize_product_name(
                self._safe_str(row.get("productname", ""))
            )
            
            quantity_lots = self.normalizer.normalize_quantity(
                row.get("quantitylots")
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
            if not all([product_name, quantity_lots is not None, price is not None, 
                       contract_month, buy_sell]):
                logger.warning(f"Skipping trader trade {index}: missing essential fields")
                return None
            
            # Ensure quantity_lots and price are not None before passing to CMETrade
            if quantity_lots is None or price is None:
                logger.warning(f"Skipping trader trade {index}: quantity or price is None")
                return None
            
            # Extract other fields
            broker_group_id = self.normalizer.normalize_integer_field(
                row.get("brokergroupid")
            )
            
            exch_clearing_acct_id = self.normalizer.normalize_integer_field(
                row.get("exchclearingacctid")
            )
            
            return CMETrade(
                trade_id=trade_id,
                source=CMETradeSource.TRADER,
                product_name=product_name,
                quantitylots=quantity_lots,
                unit=self.normalizer.normalize_string_field(
                    row.get("unit")
                ) or None,
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
                ) or None,
                spread=self.normalizer.normalize_string_field(
                    row.get("spread")
                ) or None,
                trade_date=self.normalizer.normalize_string_field(
                    row.get("tradedate")
                ) or None,
                trade_time=self.normalizer.normalize_string_field(
                    row.get("tradetime")
                ) or None,
                trade_datetime=None,  # Trader data doesn't have combined datetime
                trader_id=self.normalizer.normalize_string_field(
                    row.get("traderid")
                ) or None,
                product_id=self.normalizer.normalize_string_field(
                    row.get("productid")
                ) or None,
                product_group_id=self.normalizer.normalize_integer_field(
                    row.get("productgroupid")
                ),
                special_comms=self.normalizer.normalize_string_field(
                    row.get("specialcomms")
                ) or None,
                deal_id=None,  # Trader data doesn't have deal_id
                clearing_status=None,  # Trader data doesn't have clearing_status
                trader_name=None,  # Trader data doesn't have trader_name
                trading_session=None,  # Trader data doesn't have trading_session
                cleared_date=None  # Trader data doesn't have cleared_date
            )
            
        except Exception as e:
            logger.error(f"Error creating trader trade from row {index}: {e}")
            return None
    
    def _create_exchange_trade(self, row: pd.Series, index: int) -> Optional[CMETrade]:
        """Create CME exchange trade from CSV row.
        
        Args:
            row: Pandas series representing CSV row
            index: Row index for ID generation
            
        Returns:
            CMETrade object or None if invalid
        """
        try:
            # Always generate consistent trade ID with row index for easy identification
            trade_id = f"E_{index}"
            
            # Extract and normalize core fields
            product_name = self.normalizer.normalize_product_name(
                self._safe_str(row.get("productname", ""))
            )
            
            quantity_lots = self.normalizer.normalize_quantity(
                row.get("quantitylots")
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
            if not all([product_name, quantity_lots is not None, price is not None, 
                       contract_month, buy_sell]):
                logger.warning(f"Skipping exchange trade {index}: missing essential fields")
                return None
            
            # Ensure quantity_lots and price are not None before passing to CMETrade
            if quantity_lots is None or price is None:
                logger.warning(f"Skipping exchange trade {index}: quantity or price is None")
                return None
            
            # Extract other fields
            broker_group_id = self.normalizer.normalize_integer_field(
                row.get("brokergroupid")
            )
            
            exch_clearing_acct_id = self.normalizer.normalize_integer_field(
                row.get("exchclearingacctid")
            )
            
            return CMETrade(
                trade_id=trade_id,
                source=CMETradeSource.EXCHANGE,
                product_name=product_name,
                quantitylots=quantity_lots,
                unit=self.normalizer.normalize_string_field(
                    row.get("unit")
                ) or None,
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
                ) or None,
                spread=None,  # Exchange data doesn't have spread field
                trade_date=self.normalizer.normalize_string_field(
                    row.get("tradedate")
                ) or None,
                trade_time=None,  # Exchange data doesn't have separate trade_time
                trade_datetime=self.normalizer.normalize_string_field(
                    row.get("tradedatetime")
                ) or None,
                trader_id=None,  # Exchange data doesn't have trader_id
                product_id=self.normalizer.normalize_string_field(
                    row.get("productid")
                ) or None,
                product_group_id=self.normalizer.normalize_integer_field(
                    row.get("productgroupid")
                ),
                special_comms=None,  # Exchange data doesn't have special_comms
                deal_id=self.normalizer.normalize_integer_field(
                    row.get("dealid")
                ),
                clearing_status=self.normalizer.normalize_string_field(
                    row.get("clearingstatus")
                ) or None,
                trader_name=self.normalizer.normalize_string_field(
                    row.get("traderid")
                ) or None,
                trading_session=self.normalizer.normalize_string_field(
                    row.get("tradingsession")
                ) or None,
                cleared_date=self.normalizer.normalize_string_field(
                    row.get("cleareddate")
                ) or None
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