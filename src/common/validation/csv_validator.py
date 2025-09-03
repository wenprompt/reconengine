"""CSV input validator implementation."""

import logging
from pathlib import Path
from typing import Any, Dict, Hashable, List, Optional, Union
import pandas as pd
from pydantic import ValidationError as PydanticValidationError

from ..schemas.input_schemas import TraderInputSchema, ExchangeInputSchema
from .base import BaseInputValidator, ValidatedData
from .exceptions import CSVValidationError

logger = logging.getLogger(__name__)


class CSVInputValidator(BaseInputValidator):
    """
    Validator for CSV input files.
    
    Handles CSV-specific concerns like:
    - Encoding detection (UTF-8, UTF-8-sig)
    - Forcing string dtype for ID columns to prevent scientific notation
    - Row-by-row validation with error collection
    - Field mapping from CSV column names to standard names
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize CSV validator with optional configuration.
        
        Args:
            config: Optional configuration dictionary containing:
                - field_mappings: Column name mappings
                - encoding: Default encoding (default: 'utf-8')
                - error_handling: 'fail_fast' or 'collect_all' (default: 'collect_all')
        """
        super().__init__(config)
        self.encoding = self.config.get('encoding', 'utf-8')
        self.error_handling = self.config.get('error_handling', 'collect_all')
    
    def validate(
        self,
        trader_input: Union[str, Path, pd.DataFrame],
        exchange_input: Union[str, Path, pd.DataFrame]
    ) -> ValidatedData:
        """
        Validate CSV input data and return ValidatedData object.
        
        Args:
            trader_input: Path to trader CSV file or DataFrame
            exchange_input: Path to exchange CSV file or DataFrame
            
        Returns:
            ValidatedData object with validated and normalized data
            
        Raises:
            CSVValidationError: If validation fails
        """
        # Load CSV files if paths provided
        trader_df = self._load_csv(trader_input, "trader") if not isinstance(trader_input, pd.DataFrame) else trader_input
        exchange_df = self._load_csv(exchange_input, "exchange") if not isinstance(exchange_input, pd.DataFrame) else exchange_input
        
        # Validate data
        trader_data = self._validate_trader_data(trader_df)
        exchange_data = self._validate_exchange_data(exchange_df)
        
        # Create metadata
        metadata = {
            "source": "csv",
            "trader_count": len(trader_data),
            "exchange_count": len(exchange_data),
            "encoding": self.encoding
        }
        
        return ValidatedData(
            trader_data=trader_data,
            exchange_data=exchange_data,
            metadata=metadata
        )
    
    def _load_csv(self, file_path: Union[str, Path], data_type: str) -> pd.DataFrame:
        """
        Load CSV file with proper encoding and dtype handling.
        
        Args:
            file_path: Path to CSV file
            data_type: Type of data ("trader" or "exchange")
            
        Returns:
            Loaded DataFrame
            
        Raises:
            CSVValidationError: If file cannot be loaded
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise CSVValidationError(
                f"CSV file not found: {file_path}",
                file_path=str(file_path),
                data_type=data_type
            )
        
        # Force string dtype for ID columns to prevent scientific notation
        dtype_spec: Dict[Hashable, Any] = {
            'dealid': 'str',
            'tradeid': 'str',
            'traderid': 'str',
            'exchclearingacctid': 'str'
        }
        
        try:
            # Try to read with specified encoding
            df = pd.read_csv(
                file_path,
                dtype=dtype_spec,
                encoding=self.encoding,
                keep_default_na=False,  # Treat empty strings as empty, not NaN
                na_values=['']  # Only treat actual empty strings as missing
            )
            logger.info(f"Loaded {data_type} CSV from {file_path}: {len(df)} rows")
            return df
            
        except UnicodeDecodeError:
            # Try with UTF-8-sig if UTF-8 fails (handles BOM)
            if self.encoding == 'utf-8':
                try:
                    df = pd.read_csv(
                        file_path,
                        dtype=dtype_spec,
                        encoding='utf-8-sig',
                        keep_default_na=False,
                        na_values=['']
                    )
                    logger.info(f"Loaded {data_type} CSV with UTF-8-sig from {file_path}")
                    return df
                except Exception:
                    pass
            
            raise CSVValidationError(
                f"Failed to decode CSV file with encoding {self.encoding}",
                file_path=str(file_path),
                data_type=data_type
            )
        except Exception as e:
            raise CSVValidationError(
                f"Failed to load CSV file: {e}",
                file_path=str(file_path),
                data_type=data_type
            ) from e
    
    def _validate_trader_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Validate trader-specific data.
        
        Args:
            df: Raw trader DataFrame from CSV
            
        Returns:
            List of validated trader records as dictionaries
            
        Raises:
            CSVValidationError: If validation fails
        """
        validated_records = []
        errors = []
        
        for idx, row in df.iterrows():
            assert isinstance(idx, int)  # Type hint for mypy
            try:
                # Convert row to dict and handle NaN values
                row_dict = self._prepare_row_dict(row, "trader")
                
                # Add internal trade ID (using the dataframe index)
                row_dict['internaltradeid'] = idx
                
                # Apply field mappings if configured
                mapped_dict = self.apply_field_mappings(row_dict, "trader")
                
                # Validate with Pydantic schema
                validated = TraderInputSchema(**mapped_dict)
                
                # Convert to dict, excluding None values
                validated_dict = validated.model_dump(exclude_none=True, by_alias=False)
                validated_records.append(validated_dict)
                
            except PydanticValidationError as e:
                if self.error_handling == 'fail_fast':
                    raise CSVValidationError(
                        f"Validation failed for trader row {idx + 2}",  # +2 for 1-based row number + header
                        row_number=idx + 2,
                        data_type="trader",
                        errors=[{"row": idx + 2, "errors": e.errors()}]
                    ) from e
                else:
                    errors.append({
                        "row": idx + 2,
                        "errors": e.errors()
                    })
        
        # If collecting all errors and some were found, raise with all details
        if errors:
            raise CSVValidationError(
                f"Validation failed for {len(errors)} trader rows",
                data_type="trader",
                errors=errors
            )
        
        logger.info(f"Validated {len(validated_records)} trader records")
        return validated_records
    
    def _validate_exchange_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Validate exchange-specific data.
        
        Args:
            df: Raw exchange DataFrame from CSV
            
        Returns:
            List of validated exchange records as dictionaries
            
        Raises:
            CSVValidationError: If validation fails
        """
        validated_records = []
        errors = []
        
        for idx, row in df.iterrows():
            assert isinstance(idx, int)  # Type hint for mypy
            try:
                # Convert row to dict and handle NaN values
                row_dict = self._prepare_row_dict(row, "exchange")
                
                # Add internal trade ID (using the dataframe index)
                row_dict['internaltradeid'] = idx
                
                # Apply field mappings if configured
                mapped_dict = self.apply_field_mappings(row_dict, "exchange")
                
                # Validate with Pydantic schema
                validated = ExchangeInputSchema(**mapped_dict)
                
                # Convert to dict, excluding None values
                validated_dict = validated.model_dump(exclude_none=True, by_alias=False)
                validated_records.append(validated_dict)
                
            except PydanticValidationError as e:
                if self.error_handling == 'fail_fast':
                    raise CSVValidationError(
                        f"Validation failed for exchange row {idx + 2}",
                        row_number=idx + 2,
                        data_type="exchange",
                        errors=[{"row": idx + 2, "errors": e.errors()}]
                    ) from e
                else:
                    errors.append({
                        "row": idx + 2,
                        "errors": e.errors()
                    })
        
        # If collecting all errors and some were found, raise with all details
        if errors:
            raise CSVValidationError(
                f"Validation failed for {len(errors)} exchange rows",
                data_type="exchange",
                errors=errors
            )
        
        logger.info(f"Validated {len(validated_records)} exchange records")
        return validated_records
    
    def _prepare_row_dict(self, row: pd.Series, data_type: str) -> Dict[str, Any]:
        """
        Convert DataFrame row to dictionary, handling NaN and empty values.
        
        Args:
            row: Pandas Series representing a row
            data_type: Type of data for context
            
        Returns:
            Dictionary with cleaned values
        """
        row_dict = {}
        
        for col, value in row.items():
            # Skip completely empty columns
            if pd.isna(value) or value == '':
                continue
            
            # Ensure col is string (for mypy)
            col = str(col)
            
            # Clean column names (lowercase, remove spaces)
            clean_col = col.lower().strip()
            
            # Handle 'b/s' column specially (keep as is - Pydantic alias will handle it)
            if clean_col == 'b/s':
                row_dict['b/s'] = value
            # Handle 'put/call' column specially (keep as is - Pydantic alias will handle it)
            elif clean_col == 'put/call':
                row_dict['put/call'] = value
            else:
                # For other columns, replace spaces with underscores
                clean_col = clean_col.replace(' ', '_')
                row_dict[clean_col] = value
        
        return row_dict