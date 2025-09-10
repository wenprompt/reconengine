"""Trade grouping and routing logic for unified reconciliation system."""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import logging
import json

# Import trade factories for JSON processing
from ...ice_match.core.trade_factory import ICETradeFactory
from ...ice_match.normalizers import TradeNormalizer as ICETradeNormalizer
from ...ice_match.models import TradeSource as ICETradeSource
from ...ice_match.config import ConfigManager as ICEConfigManager
from ...sgx_match.core.trade_factory import SGXTradeFactory
from ...sgx_match.normalizers import SGXTradeNormalizer
from ...sgx_match.models import SGXTradeSource
from ...sgx_match.config import SGXConfigManager
from ...cme_match.core.trade_factory import CMETradeFactory
from ...cme_match.normalizers import CMETradeNormalizer
from ...cme_match.models import CMETradeSource
from ...cme_match.config import CMEConfigManager
from ...eex_match.core.trade_factory import EEXTradeFactory
from ...eex_match.normalizers import EEXTradeNormalizer
from ...eex_match.models import EEXTradeSource
from ...eex_match.config import EEXConfigManager

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
        self.validator = DataValidator()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file not found
            ValueError: If config file has invalid JSON
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config: Dict[str, Any] = json.load(f)
            logger.info(f"Loaded unified configuration from {self.config_path}")
            return config
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in configuration file {self.config_path}: {e}"
            ) from e

    def load_and_validate_data(
        self, data_dir: Optional[Path] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
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
            data_dir = Path(self.config["data_settings"]["default_data_dir"])

        trader_file = data_dir / self.config["data_settings"]["trader_file"]
        exchange_file = data_dir / self.config["data_settings"]["exchange_file"]

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
        self.validator.validate_csv_structure(trader_df, "trader", trader_file)
        self.validator.validate_csv_structure(exchange_df, "exchange", exchange_file)

        # Validate and get exchange groups
        trader_groups, trader_counts = self.validator.validate_exchange_groups(
            trader_df, trader_file
        )
        exchange_groups, exchange_counts = self.validator.validate_exchange_groups(
            exchange_df, exchange_file
        )

        # Validate consistency between datasets
        self.validator.validate_data_consistency(trader_groups, exchange_groups)

        logger.info(
            f"Successfully loaded and validated data: {len(trader_df)} trader trades, {len(exchange_df)} exchange trades"
        )
        return trader_df, exchange_df

    def load_and_validate_json_data(
        self, json_path: Path
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load and validate JSON data from file using trade factories for sophisticated field handling.

        This method loads JSON from a file and delegates to load_and_validate_json_dict
        for processing, avoiding code duplication.

        Args:
            json_path: Path to JSON file

        Returns:
            Tuple of (trader_df, exchange_df)

        Raises:
            DataValidationError: If JSON validation fails
            FileNotFoundError: If JSON file doesn't exist
        """
        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")

        logger.info(f"Loading JSON data from: {json_path}")

        try:
            # Load raw JSON data
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Delegate to the dictionary-based method for processing
            return self.load_and_validate_json_dict(data)

        except json.JSONDecodeError as e:
            raise DataValidationError(
                f"Invalid JSON format in file {json_path}: {e}"
            ) from e
        except DataValidationError:
            # Re-raise validation errors with file context
            raise
        except Exception as e:
            logger.exception(f"Error loading JSON from {json_path}")
            raise DataValidationError(f"Failed to load JSON data from file: {e}") from e

    def load_and_validate_json_dict(
        self, data: Dict[str, Any]
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Process and validate JSON data from dictionary, using trade factories for sophisticated field handling.

        This method avoids filesystem I/O by accepting data directly.

        Args:
            data: Dictionary with 'traderTrades' and 'exchangeTrades' arrays

        Returns:
            Tuple of (trader_df, exchange_df)

        Raises:
            DataValidationError: If JSON validation fails
        """
        logger.info("Processing JSON data from dictionary")

        try:
            # Validate JSON structure
            if not isinstance(data, dict):
                raise DataValidationError(
                    "JSON must be a dictionary with 'traderTrades' and 'exchangeTrades' keys"
                )

            # Check for both old and new JSON key formats
            trader_key = "traderTrades" if "traderTrades" in data else "trader"
            exchange_key = "exchangeTrades" if "exchangeTrades" in data else "exchange"

            if trader_key not in data or exchange_key not in data:
                raise DataValidationError(
                    "JSON must contain 'traderTrades' and 'exchangeTrades' arrays"
                )

            # Group JSON data by exchangeGroupId
            grouped_json = self._group_json_by_exchange_group(
                data, trader_key, exchange_key
            )

            # Process each group through appropriate trade factory
            all_trader_trades: List[Any] = []
            all_exchange_trades: List[Any] = []

            for group_id, group_data in grouped_json.items():
                system_name = self._get_system_for_group(group_id)

                group_trader_trades: List[Any]
                group_exchange_trades: List[Any]

                if system_name == "ice_match":
                    # Use ICE trade factory for sophisticated field handling
                    ice_config_manager = ICEConfigManager()
                    ice_normalizer = ICETradeNormalizer(ice_config_manager)
                    ice_factory = ICETradeFactory(ice_normalizer)

                    group_trader_trades = ice_factory.from_json(
                        group_data["trader_trades"], ICETradeSource.TRADER
                    )
                    group_exchange_trades = ice_factory.from_json(
                        group_data["exchange_trades"], ICETradeSource.EXCHANGE
                    )

                elif system_name == "sgx_match":
                    # Use SGX trade factory for sophisticated field handling
                    sgx_config_manager = SGXConfigManager()
                    sgx_normalizer = SGXTradeNormalizer(sgx_config_manager)
                    sgx_factory = SGXTradeFactory(sgx_normalizer)

                    group_trader_trades = sgx_factory.from_json(
                        group_data["trader_trades"], SGXTradeSource.TRADER
                    )
                    group_exchange_trades = sgx_factory.from_json(
                        group_data["exchange_trades"], SGXTradeSource.EXCHANGE
                    )

                elif system_name == "cme_match":
                    # Use CME trade factory for sophisticated field handling
                    cme_config_manager = CMEConfigManager()
                    cme_normalizer = CMETradeNormalizer(cme_config_manager)
                    cme_factory = CMETradeFactory(cme_normalizer)

                    group_trader_trades = cme_factory.from_json(
                        group_data["trader_trades"], CMETradeSource.TRADER
                    )
                    group_exchange_trades = cme_factory.from_json(
                        group_data["exchange_trades"], CMETradeSource.EXCHANGE
                    )

                elif system_name == "eex_match":
                    # Use EEX trade factory for sophisticated field handling
                    eex_config_manager = EEXConfigManager()
                    eex_normalizer = EEXTradeNormalizer(eex_config_manager)
                    eex_factory = EEXTradeFactory(eex_normalizer)

                    group_trader_trades = eex_factory.from_json(
                        group_data["trader_trades"], EEXTradeSource.TRADER
                    )
                    group_exchange_trades = eex_factory.from_json(
                        group_data["exchange_trades"], EEXTradeSource.EXCHANGE
                    )

                else:
                    logger.warning(
                        f"Skipping group {group_id}: System '{system_name}' not supported. Available systems: ICE, SGX, CME, EEX"
                    )
                    continue

                all_trader_trades.extend(group_trader_trades)
                all_exchange_trades.extend(group_exchange_trades)

            # Convert Trade objects back to DataFrames for existing routing infrastructure
            trader_df = self._trades_to_dataframe(all_trader_trades)
            exchange_df = self._trades_to_dataframe(all_exchange_trades)

            # Normalize column names to lowercase for consistency
            trader_df.columns = trader_df.columns.str.lower()
            exchange_df.columns = exchange_df.columns.str.lower()

            logger.info(
                f"Successfully processed JSON data: {len(trader_df)} trader trades, {len(exchange_df)} exchange trades"
            )
            logger.debug(f"Trader DF columns: {trader_df.columns.tolist()}")
            logger.debug(f"Exchange DF columns: {exchange_df.columns.tolist()}")
            if len(trader_df) > 0:
                logger.debug(f"Sample trader row: {trader_df.iloc[0].to_dict()}")
            if len(exchange_df) > 0:
                logger.debug(f"Sample exchange row: {exchange_df.iloc[0].to_dict()}")
            return trader_df, exchange_df

        except Exception as e:
            logger.exception("Error processing JSON data")
            raise DataValidationError(f"Failed to process JSON data: {e}") from e

    def group_trades_by_exchange_group(
        self, trader_df: pd.DataFrame, exchange_df: pd.DataFrame
    ) -> Dict[int, Dict[str, Any]]:
        """Group trades by exchange group and prepare for routing.

        Args:
            trader_df: Trader trades DataFrame
            exchange_df: Exchange trades DataFrame

        Returns:
            Dict mapping group_id to group info with DataFrames and system info
        """
        # Get all unique exchange groups from both datasets
        trader_groups = set(trader_df["exchangegroupid"].dropna().astype(int))
        exchange_groups = set(exchange_df["exchangegroupid"].dropna().astype(int))
        all_groups = trader_groups | exchange_groups

        grouped_trades = {}

        for group_id in sorted(all_groups):
            # Filter data for this group
            group_trader_df = trader_df[trader_df["exchangegroupid"] == group_id].copy()
            group_exchange_df = exchange_df[
                exchange_df["exchangegroupid"] == group_id
            ].copy()

            # Determine matching system for this group
            system_name = self._get_system_for_group(group_id)
            system_config = self.config["system_configs"].get(system_name, {})

            # Validate group data quality
            trader_stats = (
                self.validator.validate_group_data_quality(
                    group_trader_df, group_id, "trader"
                )
                if not group_trader_df.empty
                else None
            )
            exchange_stats = (
                self.validator.validate_group_data_quality(
                    group_exchange_df, group_id, "exchange"
                )
                if not group_exchange_df.empty
                else None
            )

            grouped_trades[group_id] = {
                "group_id": group_id,
                "system": system_name,
                "system_config": system_config,
                "trader_data": group_trader_df,
                "exchange_data": group_exchange_df,
                "trader_count": len(group_trader_df),
                "exchange_count": len(group_exchange_df),
                "trader_stats": trader_stats,
                "exchange_stats": exchange_stats,
                "has_data": len(group_trader_df) > 0 and len(group_exchange_df) > 0,
            }

            logger.info(
                f"Group {group_id}: {len(group_trader_df)} trader trades, {len(group_exchange_df)} exchange trades → {system_name}"
            )

        return grouped_trades

    def _get_system_for_group(self, group_id: int) -> str:
        """Determine which matching system to use for an exchange group.

        Args:
            group_id: Exchange group ID

        Returns:
            System name ('ice_match', 'sgx_match', etc.)
        """
        group_str = str(group_id)
        system_name = self.config["exchange_group_mappings"].get(group_str, "unknown")

        if system_name == "unknown":
            logger.warning(
                f"No system mapping found for exchange group {group_id}, skipping"
            )

        return system_name

    def get_processable_groups(
        self, grouped_trades: Dict[int, Dict[str, Any]]
    ) -> List[int]:
        """Get list of exchange groups that can be processed.

        Args:
            grouped_trades: Grouped trade data from group_trades_by_exchange_group

        Returns:
            List of group IDs that have data and known system mappings
        """
        processable = []

        for group_id, group_info in grouped_trades.items():
            if (
                group_info["has_data"]
                and group_info["system"] != "unknown"
                and group_info["system"] in self.config["system_configs"]
            ):
                processable.append(group_id)
            else:
                reasons = []
                if not group_info["has_data"]:
                    reasons.append("no data")
                if group_info["system"] == "unknown":
                    reasons.append("no system mapping")
                if group_info["system"] not in self.config["system_configs"]:
                    reasons.append("unknown system")

                logger.warning(
                    f"Group {group_id} not processable: {', '.join(reasons)}"
                )

        logger.info(f"Found {len(processable)} processable groups: {processable}")
        return processable

    def prepare_data_for_system(
        self, group_info: Dict[str, Any], system_name: str
    ) -> Dict[str, Any]:
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
            "group_id": group_info["group_id"],
            "system": system_name,
            "trader_data": group_info["trader_data"],
            "exchange_data": group_info["exchange_data"],
            "trader_count": group_info["trader_count"],
            "exchange_count": group_info["exchange_count"],
            "system_config": resolved_config,
        }

        logger.debug(
            f"Prepared data for group {group_info['group_id']} → {system_name}: "
            f"{group_info['trader_count']} trader, {group_info['exchange_count']} exchange trades"
        )

        return prepared_data

    def _group_json_by_exchange_group(
        self, data: Dict[str, Any], trader_key: str, exchange_key: str
    ) -> Dict[int, Dict[str, List]]:
        """Group JSON data by exchangeGroupId.

        Args:
            data: Raw JSON data dictionary
            trader_key: Key for trader trades array
            exchange_key: Key for exchange trades array

        Returns:
            Dictionary mapping group_id to grouped trade data
        """
        grouped_data: Dict[int, Dict[str, List]] = {}

        # Group trader trades by exchangeGroupId
        for trade in data.get(trader_key, []):
            group_id = trade.get("exchangeGroupId")
            if group_id is not None:
                if group_id not in grouped_data:
                    grouped_data[group_id] = {
                        "trader_trades": [],
                        "exchange_trades": [],
                    }
                grouped_data[group_id]["trader_trades"].append(trade)

        # Group exchange trades by exchangeGroupId
        for trade in data.get(exchange_key, []):
            group_id = trade.get("exchangeGroupId")
            if group_id is not None:
                if group_id not in grouped_data:
                    grouped_data[group_id] = {
                        "trader_trades": [],
                        "exchange_trades": [],
                    }
                grouped_data[group_id]["exchange_trades"].append(trade)

        logger.info(
            f"Grouped JSON data into {len(grouped_data)} exchange groups: {list(grouped_data.keys())}"
        )
        return grouped_data

    def _trades_to_dataframe(self, trades: List[Any]) -> pd.DataFrame:
        """Convert Trade objects back to DataFrame format.

        Args:
            trades: List of Trade objects (ICE or SGX)

        Returns:
            DataFrame with trade data
        """
        if not trades:
            return pd.DataFrame()

        # Extract raw_data from each trade object (stored during creation)
        records = []
        for trade in trades:
            if hasattr(trade, "raw_data") and trade.raw_data:
                records.append(trade.raw_data)
            else:
                # Fallback: convert trade object to dict without any mutations
                # Extract ALL fields from the trade object to ensure nothing is lost
                record = {
                    "internaltradeid": trade.internal_trade_id,
                    "exchangegroupid": getattr(trade, "exchange_group_id", None),
                    "brokergroupid": getattr(trade, "broker_group_id", None),
                    "exchclearingacctid": getattr(trade, "exch_clearing_acct_id", None),
                    "productname": trade.product_name,
                    "price": float(trade.price),
                    "contractmonth": trade.contract_month,
                    "b_s": trade.buy_sell,
                    "unit": getattr(trade, "unit", None),
                    "tradedate": getattr(trade, "trade_date", None),
                    "tradetime": getattr(trade, "trade_time", None),
                    # Additional fields that might exist
                    "traderid": getattr(trade, "trader_id", None),
                    "productid": getattr(trade, "product_id", None),
                    "productgroupid": getattr(trade, "product_group_id", None),
                    "specialcomms": getattr(trade, "special_comms", None),
                    "dealid": getattr(trade, "deal_id", None),
                    "clearingstatus": getattr(trade, "clearing_status", None),
                    "tradingsession": getattr(trade, "trading_session", None),
                    "cleareddate": getattr(trade, "cleared_date", None),
                    "strike": float(trade.strike)
                    if hasattr(trade, "strike") and trade.strike
                    else None,
                    "put_call": getattr(trade, "put_call", None),
                    "spread": getattr(trade, "spread", None),
                }

                # Add quantityunit if present (SGX, ICE, EEX trades)
                if hasattr(trade, "quantityunit") and trade.quantityunit is not None:
                    record["quantityunit"] = float(trade.quantityunit)

                # Add quantitylot if present (CME trades, SGX optional)
                if hasattr(trade, "quantitylot") and trade.quantitylot is not None:
                    record["quantitylot"] = float(trade.quantitylot)

                # Add quantitylots if present (ICE trades use plural)
                if hasattr(trade, "quantitylots") and trade.quantitylots is not None:
                    record["quantitylots"] = float(trade.quantitylots)

                records.append(record)

        df = pd.DataFrame(records)
        logger.debug(
            f"Converted {len(trades)} Trade objects to DataFrame with {len(df)} rows"
        )
        return df
