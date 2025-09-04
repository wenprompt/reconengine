"""Trade factory for creating CME Trade objects from various input formats."""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from decimal import Decimal
import logging

from ..models import CMETrade, CMETradeSource
from ..normalizers import CMETradeNormalizer

logger = logging.getLogger(__name__)


class CMETradeFactory:
    """Factory for creating CME Trade objects from various input formats.

    This factory abstracts the creation of CMETrade objects from different
    input sources (CSV, DataFrame, JSON, API) to support flexible data ingestion.
    """

    def __init__(self, normalizer: CMETradeNormalizer):
        """Initialize the trade factory.

        Args:
            normalizer: The CMETradeNormalizer instance for data standardization
        """
        self.normalizer = normalizer

    def from_dataframe(
        self, df: pd.DataFrame, source: CMETradeSource
    ) -> List[CMETrade]:
        """Create trades from a pandas DataFrame.

        Args:
            df: DataFrame containing trade data
            source: Whether this is trader or exchange data

        Returns:
            List of CMETrade objects

        Raises:
            ValueError: If required fields are missing
        """
        if df.empty:
            logger.warning(f"Empty DataFrame provided for {source.value} trades")
            return []

        logger.info(f"Creating {len(df)} {source.value} trades from DataFrame")

        # Ensure DataFrame has proper column names (lowercase)
        df = df.copy()
        df.columns = df.columns.str.strip().str.lower().str.replace("/", "_")

        # Validate and prepare DataFrame
        self._validate_required_fields(df, source)
        df = self._fill_optional_fields(df, source)

        trades = []
        # Reset index to ensure consistent 0-based indices
        df = df.reset_index(drop=True)

        # Enumerate over rows for guaranteed integer index
        for i, (_, row) in enumerate(df.iterrows()):
            try:
                if source == CMETradeSource.TRADER:
                    trade = self._create_trader_trade(row, i)
                else:
                    trade = self._create_exchange_trade(row, i)

                if trade:
                    trades.append(trade)
            except Exception as e:
                logger.warning(f"Skipping {source.value} row {i}: {e}")
                continue

        logger.info(f"Successfully created {len(trades)} {source.value} trades")
        return trades

    def from_csv(self, csv_path: Path, source: CMETradeSource) -> List[CMETrade]:
        """Create trades from a CSV file (backward compatibility).

        Args:
            csv_path: Path to CSV file
            source: Whether this is trader or exchange data

        Returns:
            List of CMETrade objects

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV has invalid format
        """
        logger.info(f"Loading {source.value} data from {csv_path}")

        if not csv_path.exists():
            raise FileNotFoundError(
                f"{source.value.capitalize()} CSV file not found: {csv_path}"
            )

        try:
            # Force ID columns to be read as strings to prevent scientific notation
            dtype_spec: Any = {"dealid": "str", "tradeid": "str"}
            df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=dtype_spec)
            logger.info(f"Loaded {len(df)} rows from {source.value} CSV")

            return self.from_dataframe(df, source)

        except Exception as e:
            logger.error(f"Error loading {source.value} CSV {csv_path}: {e}")
            raise ValueError(f"Failed to load {source.value} CSV: {e}") from e

    def from_json(
        self, json_data: List[Dict[str, Any]], source: CMETradeSource
    ) -> List[CMETrade]:
        """Create trades directly from JSON data.

        Args:
            json_data: List of trade dictionaries from JSON
            source: Whether this is trader or exchange data

        Returns:
            List of CMETrade objects
        """
        if not json_data:
            logger.warning(f"Empty JSON data provided for {source.value} trades")
            return []

        logger.info(f"Creating {len(json_data)} {source.value} trades from JSON")

        # Convert JSON to DataFrame with proper field handling
        df = self._json_to_dataframe(json_data, source)
        return self.from_dataframe(df, source)

    def _json_to_dataframe(
        self, json_data: List[Dict], source: CMETradeSource
    ) -> pd.DataFrame:
        """Convert JSON data to DataFrame with field normalization.

        Args:
            json_data: List of trade dictionaries
            source: Trade source type

        Returns:
            Normalized DataFrame ready for trade creation
        """
        if not json_data:
            return pd.DataFrame()

        # Normalize field names and ensure all fields exist
        normalized_records = []
        for record in json_data:
            # Convert camelCase to snake_case
            normalized = self._normalize_json_fields(record)
            # Ensure all fields exist (add None for missing optional fields)
            normalized = self._ensure_all_fields(normalized, source)
            normalized_records.append(normalized)

        return pd.DataFrame(normalized_records)

    def _normalize_json_fields(self, record: Dict) -> Dict:
        """Convert JSON field names from camelCase to snake_case.

        Args:
            record: Single trade record from JSON

        Returns:
            Record with normalized field names
        """
        field_mappings = {
            "internalTradeId": "internaltradeid",
            "exchangeGroupId": "exchangegroupid",
            "brokerGroupId": "brokergroupid",
            "exchangeClearingAccountId": "exchclearingacctid",
            "productName": "productname",
            "contractMonth": "contractmonth",
            "quantityLot": "quantitylot",
            "traderId": "traderid",
            "tradeDate": "tradedate",
            "tradeTime": "tradetime",
            "dealId": "dealid",
            "tradeId": "tradeid",
            "b/s": "b_s",
            "put/call": "put_call",
        }

        normalized = {}
        for key, value in record.items():
            # Use mapping if exists, otherwise just lowercase
            normalized_key = field_mappings.get(key, key.lower())
            normalized[normalized_key] = value

        return normalized

    def _ensure_all_fields(self, record: Dict, source: CMETradeSource) -> Dict:
        """Ensure all required and optional fields exist in the record.

        Args:
            record: Trade record dictionary
            source: Trade source type

        Returns:
            Record with all fields present

        Raises:
            ValueError: If required fields are missing
        """
        # Define required fields based on source
        required_fields = self._get_required_fields(source)
        optional_fields = self._get_optional_fields(source)

        # Check required fields
        for field in required_fields:
            if field not in record or record[field] is None:
                raise ValueError(
                    f"Required field '{field}' missing in {source.value} record"
                )

        # Add missing optional fields with None (not NaN)
        for field in optional_fields:
            if field not in record:
                record[field] = None

        return record

    def _get_required_fields(self, source: CMETradeSource) -> List[str]:
        """Get required fields for the given source type."""
        # Common required fields - CME uses quantitylot as required
        required = [
            "productname",
            "quantitylot",
            "price",
            "contractmonth",
            "b_s",
            "exchclearingacctid",
            "brokergroupid",
            "exchangegroupid",
        ]

        # Source-specific required fields
        if source == CMETradeSource.EXCHANGE:
            required.append("tradetime")  # Exchange files require tradetime

        return required

    def _get_optional_fields(self, source: CMETradeSource) -> List[str]:
        """Get optional fields for the given source type."""
        optional = [
            "tradedate",
            "unit",
            "strike",
            "put_call",
        ]  # Common optional fields

        if source == CMETradeSource.TRADER:
            optional.extend(
                [
                    "tradetime",
                    "traderid",
                    "spread",
                    "specialcomms",
                ]
            )
            # Trader CSV has 'tradetime' column which maps to trade_time
        else:  # Exchange
            optional.extend(
                [
                    "dealid",
                    "tradeid",
                    "tradetime",
                    "clearingstatus",
                    "traderid",
                    "productid",
                    "productgroupid",
                    "quantitylot",
                ]
            )

        return optional

    def _validate_required_fields(
        self, df: pd.DataFrame, source: CMETradeSource
    ) -> None:
        """Validate that all required fields are present in DataFrame.

        Args:
            df: DataFrame to validate
            source: Trade source type

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = self._get_required_fields(source)
        missing_fields = [field for field in required_fields if field not in df.columns]

        if missing_fields:
            raise ValueError(
                f"Missing required fields for {source.value}: {missing_fields}"
            )

        # Check for null values in required fields
        for field in required_fields:
            null_count = df[field].isna().sum()
            if null_count > 0:
                raise ValueError(
                    f"Required field '{field}' has {null_count} null values"
                )

    def _fill_optional_fields(
        self, df: pd.DataFrame, source: CMETradeSource
    ) -> pd.DataFrame:
        """Add missing optional fields to DataFrame with appropriate defaults.

        Args:
            df: DataFrame to fill
            source: Trade source type

        Returns:
            DataFrame with all optional fields present
        """
        optional_fields = self._get_optional_fields(source)

        for field in optional_fields:
            if field not in df.columns:
                df[field] = None
                logger.debug(f"Added missing optional field '{field}' with None values")

        return df

    def _create_trader_trade(self, row: pd.Series, index: int) -> Optional[CMETrade]:
        """Create a CMETrade object from a trader data row.

        Args:
            row: Pandas Series containing trade data
            index: Row index for trade ID generation

        Returns:
            CMETrade object or None if creation fails
        """
        try:
            # Get raw values
            raw_product = self._safe_str(row.get("productname"))
            raw_month = self._safe_str(row.get("contractmonth"))
            raw_buy_sell = self._safe_str(row.get("b_s"))
            quantity_lot = self._safe_str(row.get("quantitylot"))
            price = self._safe_str(row.get("price"))

            # Normalize critical fields
            product_name = self.normalizer.normalize_product_name(raw_product)
            contract_month = self.normalizer.normalize_contract_month(raw_month)
            buy_sell = self.normalizer.normalize_buy_sell(raw_buy_sell)

            if not all([product_name, quantity_lot, price, contract_month, buy_sell]):
                return None

            # Use internaltradeid from JSON mapping or fallback to T_{index}
            internal_trade_id_raw = self._safe_str(row.get("internaltradeid"))
            internal_trade_id = (
                internal_trade_id_raw if internal_trade_id_raw else f"T_{index}"
            )

            return CMETrade(
                internal_trade_id=internal_trade_id,
                source=CMETradeSource.TRADER,
                product_name=product_name,
                quantitylot=Decimal(self._clean_numeric_string(quantity_lot)),
                unit=self._safe_str(row.get("unit")),
                price=Decimal(price),
                contract_month=contract_month,
                buy_sell=buy_sell,
                broker_group_id=self._safe_int(row.get("brokergroupid")),
                exchange_group_id=self._safe_int(row.get("exchangegroupid")),
                exch_clearing_acct_id=self._safe_int(row.get("exchclearingacctid")),
                strike=self._safe_decimal(row.get("strike")),
                put_call=self._safe_str(row.get("put_call")),
                trader_id=self._safe_str(row.get("traderid")),
                trade_date=self._safe_str(row.get("tradedate")),
                trade_time=self._safe_str(row.get("tradetime")),
                # Trader-specific optional fields
                spread=self._safe_str(row.get("spread")),
                product_id=self._safe_str(row.get("productid")),
                product_group_id=self._safe_int(row.get("productgroupid")),
                special_comms=self._safe_str(row.get("specialcomms")),
                # Exchange-specific fields not needed for trader trades
                # They will automatically be None due to Field(default=None) in the model
            )
        except Exception as e:
            logger.error(f"Error creating trader trade from row {index}: {e}")
            return None

    def _create_exchange_trade(self, row: pd.Series, index: int) -> Optional[CMETrade]:
        """Create a CMETrade object from an exchange data row.

        Args:
            row: Pandas Series containing trade data
            index: Row index for trade ID generation

        Returns:
            CMETrade object or None if creation fails
        """
        try:
            # Get raw values
            raw_product = self._safe_str(row.get("productname"))
            raw_month = self._safe_str(row.get("contractmonth"))
            raw_buy_sell = self._safe_str(row.get("b_s"))
            quantity_lot = self._safe_str(row.get("quantitylot"))
            price = self._safe_str(row.get("price"))

            # Normalize critical fields
            product_name = self.normalizer.normalize_product_name(raw_product)
            contract_month = self.normalizer.normalize_contract_month(raw_month)
            buy_sell = self.normalizer.normalize_buy_sell(raw_buy_sell)

            if not all([product_name, quantity_lot, price, contract_month, buy_sell]):
                return None

            # Use internaltradeid from JSON mapping or fallback to E_{index}
            internal_trade_id_raw = self._safe_str(row.get("internaltradeid"))
            internal_trade_id = (
                internal_trade_id_raw if internal_trade_id_raw else f"E_{index}"
            )

            return CMETrade(
                internal_trade_id=internal_trade_id,
                source=CMETradeSource.EXCHANGE,
                product_name=product_name,
                quantitylot=Decimal(self._clean_numeric_string(quantity_lot)),
                unit=self._safe_str(row.get("unit")),
                price=Decimal(price),
                contract_month=contract_month,
                buy_sell=buy_sell,
                broker_group_id=self._safe_int(row.get("brokergroupid")),
                exchange_group_id=self._safe_int(row.get("exchangegroupid")),
                exch_clearing_acct_id=self._safe_int(row.get("exchclearingacctid")),
                strike=self._safe_decimal(row.get("strike")),
                put_call=self._safe_str(row.get("put_call")),
                deal_id=self._safe_int(row.get("dealid")),
                trade_date=self._safe_str(row.get("tradedate")),
                trade_time=self._safe_str(
                    row.get("tradetime")
                ),  # Exchange now uses tradetime (standardized)
                # Exchange-specific optional fields
                clearing_status=self._safe_str(row.get("clearingstatus")),
                # Common optional fields
                trader_id=self._safe_str(row.get("traderid")),
                spread=self._safe_str(row.get("spread")),
                special_comms=self._safe_str(row.get("specialcomms")),
                # Trader-specific fields not needed for exchange trades
                # They will automatically be None due to Field(default=None) in the model
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

    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        """Safely convert value to Decimal, returning None for invalid values."""
        if pd.isna(value) or value is None or value == "":
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    def _clean_numeric_string(self, value: str) -> str:
        """Clean numeric string by removing commas and quotes.

        Handles formats like:
        - "1,000" -> "1000"
        - '"1,000"' -> "1000"
        - "1000" -> "1000"
        """
        if not value:
            return ""
        return value.replace(",", "").replace('"', "").strip()
