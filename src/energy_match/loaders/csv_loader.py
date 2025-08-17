"""CSV data loader for energy trade data."""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import logging

from ..models import Trade, TradeSource

logger = logging.getLogger(__name__)


class CSVTradeLoader:
    """Loads trade data from CSV files with column mapping and validation.
    
    Handles both trader and exchange CSV formats with different column names
    and provides unified Trade objects for matching.
    """
    
    # Column mappings for different CSV formats
    TRADER_COLUMN_MAPPING = {
        "teamid": "team_id",
        "traderid": "trader_id", 
        "tradedate": "trade_date",
        "tradetime": "trade_time",
        "productid": "product_id",
        "productname": "product_name",
        "productgroupid": "product_group_id",
        "exchangegroupid": "exchange_group_id",
        "brokergroupid": "broker_group_id",
        "exchclearingacctid": "exch_clearing_acct_id",
        "quantitylots": "quantity_lots",
        "quantityunits": "quantity_units",
        "unit": "unit",
        "price": "price",
        "contractmonth": "contract_month",
        "strike": "strike",
        "specialComms": "special_comms",
        "spread": "spread",
        "B/S": "buy_sell"
    }
    
    EXCHANGE_COLUMN_MAPPING = {
        "tradedate": "trade_date",
        "tradedatetime": "trade_time",
        "cleareddate": "cleared_date",
        "dealid": "deal_id",
        "tradeid": "trade_id",
        "productid": "product_id",
        "productname": "product_name",
        "productgroupid": "product_group_id",
        "contractmonth": "contract_month",
        "quantitylots": "quantity_lots",
        "quantityunits": "quantity_units",
        "b/s": "buy_sell",
        "price": "price",
        "strike": "strike",
        "put/call": "put_call",
        "brokergroupid": "broker_group_id",
        "exchangegroupid": "exchange_group_id",
        "exchclearingacctid": "exch_clearing_acct_id",
        "trader": "trader",
        "clearingstatus": "clearing_status",
        "tradingsession": "trading_session",
        "unit": "unit",
        "source": "source"
    }
    
    def __init__(self):
        """Initialize the CSV loader."""
        pass
    
    def load_trader_csv(self, file_path: Path) -> List[Trade]:
        """Load trades from trader CSV file.
        
        Args:
            file_path: Path to the trader CSV file
            
        Returns:
            List of Trade objects from trader data
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV format is invalid
        """
        logger.info(f"Loading trader data from {file_path}")
        
        if not file_path.exists():
            raise FileNotFoundError(f"Trader CSV file not found: {file_path}")
        
        try:
            # Read CSV with pandas
            df = pd.read_csv(file_path, encoding='utf-8-sig')  # Handle BOM
            
            # Clean column names
            df.columns = df.columns.str.strip()
            
            logger.info(f"Loaded {len(df)} rows from trader CSV")
            
            # Convert to Trade objects
            trades = []
            for index, row in df.iterrows():
                try:
                    row_index = int(index) if isinstance(index, (int, str)) else 0
                    trade = self._create_trader_trade(row, row_index)
                    if trade:
                        trades.append(trade)
                except Exception as e:
                    logger.warning(f"Skipping trader row {index}: {e}")
                    continue
            
            logger.info(f"Successfully created {len(trades)} trader trades")
            return trades
            
        except Exception as e:
            logger.error(f"Error loading trader CSV {file_path}: {e}")
            raise ValueError(f"Failed to load trader CSV: {e}")
    
    def load_exchange_csv(self, file_path: Path) -> List[Trade]:
        """Load trades from exchange CSV file.
        
        Args:
            file_path: Path to the exchange CSV file
            
        Returns:
            List of Trade objects from exchange data
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV format is invalid
        """
        logger.info(f"Loading exchange data from {file_path}")
        
        if not file_path.exists():
            raise FileNotFoundError(f"Exchange CSV file not found: {file_path}")
        
        try:
            # Read CSV with pandas
            df = pd.read_csv(file_path, encoding='utf-8-sig')  # Handle BOM
            
            # Clean column names
            df.columns = df.columns.str.strip()
            
            logger.info(f"Loaded {len(df)} rows from exchange CSV")
            
            # Convert to Trade objects
            trades = []
            for index, row in df.iterrows():
                try:
                    row_index = int(index) if isinstance(index, (int, str)) else 0
                    trade = self._create_exchange_trade(row, row_index)
                    if trade:
                        trades.append(trade)
                except Exception as e:
                    logger.warning(f"Skipping exchange row {index}: {e}")
                    continue
            
            logger.info(f"Successfully created {len(trades)} exchange trades")
            return trades
            
        except Exception as e:
            logger.error(f"Error loading exchange CSV {file_path}: {e}")
            raise ValueError(f"Failed to load exchange CSV: {e}")
    
    def _create_trader_trade(self, row: pd.Series, index: int) -> Optional[Trade]:
        """Create a Trade object from a trader CSV row.
        
        Args:
            row: Pandas Series representing one row
            index: Row index for ID generation
            
        Returns:
            Trade object or None if row is invalid
        """
        try:
            # Extract required fields
            product_name = self._safe_str(row.get("productname", ""))
            quantity_str = self._safe_str(row.get("quantityunits", ""))
            price_str = self._safe_str(row.get("price", ""))
            contract_month = self._safe_str(row.get("contractmonth", ""))
            buy_sell = self._safe_str(row.get("B/S", ""))
            unit = self._safe_str(row.get("unit", "mt")).lower()
            
            # Skip empty rows
            if not all([product_name, quantity_str, price_str, contract_month, buy_sell]):
                return None
            
            # Parse numeric values
            quantity = Decimal(str(quantity_str).replace(",", ""))
            price = Decimal(str(price_str))
            
            # Validate buy/sell
            if buy_sell not in ["B", "S"]:
                logger.warning(f"Invalid B/S value '{buy_sell}' in trader row {index}")
                return None
            
            # Generate trade ID
            trade_id = f"T_{index:04d}"
            
            # Optional fields
            broker_group_id = self._safe_int(row.get("brokergroupid"))
            exchange_group_id = self._safe_int(row.get("exchangegroupid"))
            exch_clearing_acct_id = self._safe_int(row.get("exchclearingacctid"))
            special_comms = self._safe_str(row.get("specialComms"))
            spread = self._safe_str(row.get("spread"))
            
            return Trade(
                trade_id=trade_id,
                source=TradeSource.TRADER,
                product_name=product_name,
                quantity=quantity,
                unit=unit,
                price=price,
                contract_month=contract_month,
                buy_sell=buy_sell,
                broker_group_id=broker_group_id,
                exchange_group_id=exchange_group_id,
                exch_clearing_acct_id=exch_clearing_acct_id,
                trade_date=None,
                trade_time=None,
                special_comms=special_comms,
                spread=spread,
                raw_data=row.to_dict()
            )
            
        except Exception as e:
            logger.error(f"Error creating trader trade from row {index}: {e}")
            return None
    
    def _create_exchange_trade(self, row: pd.Series, index: int) -> Optional[Trade]:
        """Create a Trade object from an exchange CSV row.
        
        Args:
            row: Pandas Series representing one row
            index: Row index for ID generation
            
        Returns:
            Trade object or None if row is invalid
        """
        try:
            # Extract required fields
            product_name = self._safe_str(row.get("productname", ""))
            quantity_str = self._safe_str(row.get("quantityunits", ""))
            price_str = self._safe_str(row.get("price", ""))
            contract_month = self._safe_str(row.get("contractmonth", ""))
            buy_sell_raw = self._safe_str(row.get("b/s", ""))
            unit = self._safe_str(row.get("unit", "mt")).lower()
            
            # Skip empty rows
            if not all([product_name, quantity_str, price_str, contract_month, buy_sell_raw]):
                return None
            
            # Parse numeric values (handle commas and quotes)
            quantity_clean = str(quantity_str).replace(",", "").replace('"', "")
            quantity = Decimal(quantity_clean)
            price = Decimal(str(price_str))
            
            # Normalize buy/sell (exchange uses "Bought"/"Sold")
            buy_sell = self._normalize_buy_sell(buy_sell_raw)
            if not buy_sell:
                logger.warning(f"Invalid b/s value '{buy_sell_raw}' in exchange row {index}")
                return None
            
            # Generate trade ID
            trade_id = f"E_{index:04d}"
            
            # Optional fields
            broker_group_id = self._safe_int(row.get("brokergroupid"))
            exchange_group_id = self._safe_int(row.get("exchangegroupid"))
            exch_clearing_acct_id = self._safe_int(row.get("exchclearingacctid"))
            
            # Detect spread trades: fallback logic since DealId/tradeId cannot be read properly as integers
            # Per rules.md: if tradeid is not empty, the trade MIGHT be part of a spread
            trade_id_raw = self._safe_str(row.get("tradeid"))
            spread = None
            if trade_id_raw:  # If tradeid is not empty, mark as potential spread
                spread = "S"  # Mark as spread trade
            
            return Trade(
                trade_id=trade_id,
                source=TradeSource.EXCHANGE,
                product_name=product_name,
                quantity=quantity,
                unit=unit,
                price=price,
                contract_month=contract_month,
                buy_sell=buy_sell,
                broker_group_id=broker_group_id,
                exchange_group_id=exchange_group_id,
                exch_clearing_acct_id=exch_clearing_acct_id,
                trade_date=None,
                trade_time=None,
                special_comms=None,
                spread=spread,
                raw_data=row.to_dict()
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
    
    def _normalize_buy_sell(self, value: str) -> Optional[str]:
        """Normalize buy/sell indicator to B or S.
        
        Args:
            value: Raw buy/sell value from exchange data
            
        Returns:
            "B" for buy, "S" for sell, None for invalid
        """
        if not value:
            return None
        
        value_clean = str(value).strip().lower()
        
        if value_clean in ["bought", "buy", "b"]:
            return "B"
        elif value_clean in ["sold", "sell", "s"]:
            return "S"
        else:
            return None
    
    def load_both_files(self, trader_path: Path, exchange_path: Path) -> tuple[List[Trade], List[Trade]]:
        """Load both trader and exchange CSV files.
        
        Args:
            trader_path: Path to trader CSV file
            exchange_path: Path to exchange CSV file
            
        Returns:
            Tuple of (trader_trades, exchange_trades)
        """
        trader_trades = self.load_trader_csv(trader_path)
        exchange_trades = self.load_exchange_csv(exchange_path)
        
        logger.info(f"Loaded {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades")
        
        return trader_trades, exchange_trades