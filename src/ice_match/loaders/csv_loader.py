"""CSV data loader for ice trade data."""

import pandas as pd
from pathlib import Path
from typing import List, Any, Optional, Dict, cast
from decimal import Decimal
import logging

from ..models import Trade, TradeSource
from ..normalizers import TradeNormalizer

logger = logging.getLogger(__name__)


class CSVTradeLoader:
    """Loads trade data from CSV files with column mapping and validation.
    
    Handles both trader and exchange CSV formats with different column names
    and provides unified Trade objects for matching.
    """

    def __init__(self, normalizer: TradeNormalizer):
        """Initialize the CSV loader.
        
        Args:
            normalizer: The TradeNormalizer instance to use for cleaning data.
        """
        self.normalizer = normalizer

    def load_trader_csv(self, file_path: Path) -> List[Trade]:
        """Load trades from trader CSV file."""
        logger.info(f"Loading trader data from {file_path}")
        if not file_path.exists():
            raise FileNotFoundError(f"Trader CSV file not found: {file_path}")

        try:
            # Force ID columns to be read as strings to prevent scientific notation conversion
            dtype_spec: Dict[str, Any] = {'dealid': 'str', 'tradeid': 'str'}
            df = pd.read_csv(file_path, encoding='utf-8-sig', dtype=dtype_spec)  # type: ignore[arg-type]
            # Normalize column names to lowercase and replace special chars
            df.columns = df.columns.str.strip().str.lower().str.replace('/', '_')
            logger.info(f"Loaded {len(df)} rows from trader CSV")

            trades = []
            # Ensure deterministic 0-based integer indices for IDs
            df = df.reset_index(drop=True)
            for i, row in df.iterrows():
                try:
                    trade = self._create_trader_trade(row, cast(int, i))
                    if trade:
                        trades.append(trade)
                except Exception as e:
                    logger.warning(f"Skipping trader row {i}: {e}")
                    continue

            logger.info(f"Successfully created {len(trades)} trader trades")
            return trades

        except Exception as e:
            logger.error(f"Error loading trader CSV {file_path}: {e}")
            raise ValueError(f"Failed to load trader CSV: {e}") from e

    def load_exchange_csv(self, file_path: Path) -> List[Trade]:
        """Load trades from exchange CSV file."""
        logger.info(f"Loading exchange data from {file_path}")
        if not file_path.exists():
            raise FileNotFoundError(f"Exchange CSV file not found: {file_path}")

        try:
            # Force dealid and tradeid to be read as strings to prevent scientific notation conversion
            dtype_spec: Dict[str, Any] = {'dealid': 'str', 'tradeid': 'str'}
            df = pd.read_csv(file_path, encoding='utf-8-sig', dtype=dtype_spec)  # type: ignore[arg-type]
            # Normalize column names to lowercase and replace special chars
            df.columns = df.columns.str.strip().str.lower().str.replace('/', '_')
            logger.info(f"Loaded {len(df)} rows from exchange CSV")

            trades = []
            # Ensure deterministic 0-based integer indices for IDs
            df = df.reset_index(drop=True)
            for i, row in df.iterrows():
                try:
                    trade = self._create_exchange_trade(row, cast(int, i))
                    if trade:
                        trades.append(trade)
                except Exception as e:
                    logger.warning(f"Skipping exchange row {i}: {e}")
                    continue

            logger.info(f"Successfully created {len(trades)} exchange trades")
            return trades

        except Exception as e:
            logger.error(f"Error loading exchange CSV {file_path}: {e}")
            raise ValueError(f"Failed to load exchange CSV: {e}") from e

    def _create_trader_trade(self, row: pd.Series, index: int) -> Optional[Trade]:
        """Create a Trade object from a trader CSV row after normalization."""
        try:
            # Get raw values
            raw_product = self._safe_str(row.get("productname"))
            raw_month = self._safe_str(row.get("contractmonth"))
            raw_buy_sell = self._safe_str(row.get("b_s"))
            quantity_str = self._safe_str(row.get("quantityunits"))
            price_str = self._safe_str(row.get("price"))

            # Normalize critical fields
            product_name = self.normalizer.normalize_product_name(raw_product)
            contract_month = self.normalizer.normalize_contract_month(raw_month)
            buy_sell = self.normalizer.normalize_buy_sell(raw_buy_sell)

            if not all([product_name, quantity_str, price_str, contract_month, buy_sell]):
                return None

            # Determine unit with product-specific defaults for trader data
            raw_unit = self._safe_str(row.get("unit", ""))
            if raw_unit:
                unit = raw_unit.lower()
            else:
                # Use normalizer to get product-specific unit defaults
                unit = self.normalizer.get_trader_product_unit_default(product_name)

            return Trade(
                trade_id=f"T_{index}",
                source=TradeSource.TRADER,
                product_name=product_name,
                quantity=Decimal(quantity_str.replace(",", "")),
                unit=unit,
                price=Decimal(price_str),
                contract_month=contract_month,
                buy_sell=buy_sell,
                broker_group_id=self._safe_int(row.get("brokergroupid")),
                exchange_group_id=self._safe_int(row.get("exchangegroupid")),
                exch_clearing_acct_id=self._safe_int(row.get("exchclearingacctid")),
                trade_date=None,  # Pass optional fields
                trade_time=None,
                special_comms=self._safe_str(row.get("specialcomms")),
                spread=self._safe_str(row.get("spread")),
                raw_data=row.to_dict()
            )
        except Exception as e:
            logger.error(f"Error creating trader trade from row {index}: {e}")
            return None

    def _create_exchange_trade(self, row: pd.Series, index: int) -> Optional[Trade]:
        """Create a Trade object from an exchange CSV row after normalization."""
        try:
            # Get raw values
            raw_product = self._safe_str(row.get("productname"))
            raw_month = self._safe_str(row.get("contractmonth"))
            raw_buy_sell = self._safe_str(row.get("b_s"))
            quantity_str = self._safe_str(row.get("quantityunits"))
            price_str = self._safe_str(row.get("price"))

            # Normalize critical fields
            product_name = self.normalizer.normalize_product_name(raw_product)
            contract_month = self.normalizer.normalize_contract_month(raw_month)
            buy_sell = self.normalizer.normalize_buy_sell(raw_buy_sell)

            if not all([product_name, quantity_str, price_str, contract_month, buy_sell]):
                return None

            trade_id_raw = self._safe_str(row.get("tradeid"))
            spread = "S" if trade_id_raw else None

            return Trade(
                trade_id=f"E_{index}",
                source=TradeSource.EXCHANGE,
                product_name=product_name,
                quantity=Decimal(quantity_str.replace(",", "").replace('"', "")),
                unit=self._safe_str(row.get("unit", "mt")).lower(),
                price=Decimal(price_str),
                contract_month=contract_month,
                buy_sell=buy_sell,
                broker_group_id=self._safe_int(row.get("brokergroupid")),
                exchange_group_id=self._safe_int(row.get("exchangegroupid")),
                exch_clearing_acct_id=self._safe_int(row.get("exchclearingacctid")),
                trade_date=None,  # Pass optional fields
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

    def load_both_files(self, trader_path: Path, exchange_path: Path) -> tuple[List[Trade], List[Trade]]:
        """Load both trader and exchange CSV files."""
        trader_trades = self.load_trader_csv(trader_path)
        exchange_trades = self.load_exchange_csv(exchange_path)
        logger.info(f"Loaded {len(trader_trades)} trader trades and {len(exchange_trades)} exchange trades")
        return trader_trades, exchange_trades
