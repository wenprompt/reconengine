"""Data validation utilities for unified reconciliation system."""

import pandas as pd
from pathlib import Path
from typing import Any
import logging

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Raised when data validation fails."""

    pass


class DataValidator:
    """Validates CSV data for unified reconciliation processing."""

    def __init__(self) -> None:
        """Initialize validator."""
        pass

    def validate_file_exists(self, file_path: Path) -> bool:
        """Validate that file exists and is readable.

        Args:
            file_path: Path to file to validate

        Returns:
            True if file exists and is readable

        Raises:
            DataValidationError: If file doesn't exist or isn't readable
        """
        if not file_path.exists():
            raise DataValidationError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise DataValidationError(f"Path is not a file: {file_path}")

        # Try to read the file
        try:
            with open(file_path, "r") as f:
                f.read(1)  # Try to read first character
        except Exception as e:
            raise DataValidationError(f"Cannot read file {file_path}: {e}") from e

        return True

    def validate_csv_structure(
        self, df: pd.DataFrame, data_type: str, file_path: Path
    ) -> bool:
        """Validate CSV structure and required exchangegroupid column.

        Args:
            df: DataFrame to validate
            data_type: Type of data ('exchange' or 'trader')
            file_path: Path to original file (for error messages)

        Returns:
            True if structure is valid

        Raises:
            DataValidationError: If validation fails
        """
        if df.empty:
            raise DataValidationError(f"CSV file is empty: {file_path}")

        # Check for exchangegroupid - the only critical column for routing
        if "exchangegroupid" not in df.columns:
            raise DataValidationError(
                f"Missing 'exchangegroupid' column in {file_path} - required for routing"
            )

        logger.info(
            f"Validated {data_type} CSV structure: {len(df)} rows, {len(df.columns)} columns"
        )
        return True

    def validate_exchange_groups(
        self, df: pd.DataFrame, file_path: Path
    ) -> tuple[list[int], dict[int, int]]:
        """Validate and analyze exchange groups in data.

        Args:
            df: DataFrame with exchangegroupid column
            file_path: Path to original file (for error messages)

        Returns:
            Tuple of (unique_groups, group_counts)

        Raises:
            DataValidationError: If validation fails
        """
        if "exchangegroupid" not in df.columns:
            raise DataValidationError(f"Missing exchangegroupid column in {file_path}")

        # Check for null/empty exchange groups
        null_groups = df["exchangegroupid"].isnull().sum()
        if null_groups > 0:
            logger.warning(
                f"Found {null_groups} rows with null exchangegroupid in {file_path}"
            )

        # Get unique exchange groups
        unique_groups_raw = df["exchangegroupid"].dropna().unique()
        unique_groups = [int(g) for g in unique_groups_raw if pd.notna(g)]

        if not unique_groups:
            raise DataValidationError(f"No valid exchange groups found in {file_path}")

        # Count trades per group
        group_counts = df.groupby("exchangegroupid").size().to_dict()
        group_counts = {int(k): int(v) for k, v in group_counts.items() if pd.notna(k)}

        logger.info(f"Found exchange groups in {file_path}: {dict(group_counts)}")
        return sorted(unique_groups), group_counts

    def validate_data_consistency(
        self, trader_groups: list[int], exchange_groups: list[int]
    ) -> bool:
        """Validate that trader and exchange data have consistent exchange groups.

        Args:
            trader_groups: List of exchange groups from trader data
            exchange_groups: List of exchange groups from exchange data

        Returns:
            True if consistent

        Raises:
            DataValidationError: If inconsistent
        """
        trader_set = set(trader_groups)
        exchange_set = set(exchange_groups)

        # Check for groups in trader data but not in exchange data
        trader_only = trader_set - exchange_set
        if trader_only:
            logger.warning(
                f"Exchange groups found in trader data but not exchange data: {trader_only}"
            )

        # Check for groups in exchange data but not in trader data
        exchange_only = exchange_set - trader_set
        if exchange_only:
            logger.warning(
                f"Exchange groups found in exchange data but not trader data: {exchange_only}"
            )

        # Find common groups
        common_groups = trader_set & exchange_set
        if not common_groups:
            raise DataValidationError(
                "No common exchange groups found between trader and exchange data"
            )

        logger.info(f"Common exchange groups for processing: {sorted(common_groups)}")
        return True

    def validate_group_data_quality(
        self, df: pd.DataFrame, group_id: int, data_type: str
    ) -> dict[str, Any]:
        """Validate data quality for a specific exchange group.

        Args:
            df: DataFrame containing the group data
            group_id: Exchange group ID to validate
            data_type: Type of data ('exchange' or 'trader')

        Returns:
            dict with validation results and statistics
        """
        group_data = df[df["exchangegroupid"] == group_id]

        stats = {
            "group_id": group_id,
            "data_type": data_type,
            "total_rows": len(group_data),
            "null_prices": group_data["price"].isnull().sum()
            if "price" in group_data.columns
            else 0,
            "zero_prices": (group_data["price"] == 0).sum()
            if "price" in group_data.columns
            else 0,
            "unique_products": group_data["productname"].nunique()
            if "productname" in group_data.columns
            else 0,
            "date_range": None,
        }

        # Check date range if tradedate column exists
        if "tradedate" in group_data.columns:
            try:
                dates = pd.to_datetime(group_data["tradedate"], errors="coerce")
                valid_dates = dates.dropna()
                if not valid_dates.empty:
                    stats["date_range"] = {
                        "start": valid_dates.min().strftime("%Y-%m-%d"),
                        "end": valid_dates.max().strftime("%Y-%m-%d"),
                    }
            except (AttributeError, TypeError, ValueError, KeyError):
                # Date parsing failed, skip date range statistics
                pass

        logger.debug(f"Group {group_id} {data_type} data quality: {stats}")
        return stats
