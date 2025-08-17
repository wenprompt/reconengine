# CLAUDE.md

This file provides comprehensive guidance to Claude Code when working with this **Energy Trade Matching System** project.

## 🎯 Project Overview

This is an **Energy Trade Matching System** that matches trades between trader and exchange data sources using a sequential rule-based approach. The system implements exact matching (Rule 1) and spread matching (Rule 2) with plans for 8 additional sophisticated matching rules including cracks, aggregations, product spreads, and complex scenarios.

### Key Features

- **Universal Data Normalization**: TradeNormalizer standardizes product names, contract months, buy/sell indicators, and unit conversions
- **Configuration Management**: Centralized settings with rule confidence levels, tolerances, and conversion ratios
- **Sequential Rule Processing**: Implements rules in priority order (exact matches first) with non-duplication
- **Rich CLI Interface**: Beautiful terminal output with progress indicators and detailed results
- **Unit Conversion**: Automatic BBL ↔ MT conversion with configurable ratios (default 6.35)
- **Pydantic v2 Data Models**: Strict validation and type safety for all trade data
- **Complete Type Safety**: Full mypy compliance with pandas-stubs integration

## 🏗️ Project Architecture

### Core Structure

```
src/energy_match/
├── main.py                 # Main application entry point with CLI
├── models/                 # Pydantic v2 data models
│   ├── trade.py           # Core Trade model with validation and unit conversion
│   └── match_result.py    # MatchResult model for output
├── loaders/               # CSV data loading with normalization integration
│   └── csv_loader.py     # Handles both trader and exchange CSV files
├── normalizers/          # Data normalization and standardization
│   └── trade_normalizer.py # Product names, contract months, buy/sell, units
├── matchers/            # Matching rule implementations
│   ├── exact_matcher.py # Rule 1: Exact matching (6-field comparison)
│   └── spread_matcher.py # Rule 2: Spread matching (contract month spreads)
├── core/               # Core system components
│   └── unmatched_pool.py # Non-duplication pool management
├── config/            # Configuration management
│   └── config_manager.py # Settings, tolerances, rule confidence levels
├── cli/              # Rich CLI interface
│   └── display.py   # Beautiful terminal output and progress
├── data/            # Sample data sets
│   ├── sourceTraders.csv    # Default trader data
│   ├── sourceExchange.csv   # Default exchange data
│   └── [additional datasets] # Various test scenarios
└── docs/
    └── rules.md        # Complete 10-rule specification
```

### Architecture Principles

- **Separation of Concerns**: Each module has a single, clear responsibility
- **Data Validation**: Pydantic v2 models ensure type safety and validation
- **Immutable Models**: Trade objects are frozen for thread safety
- **Universal Normalization**: Standardized field mapping and data cleaning via TradeNormalizer
- **Configuration-Driven**: Centralized settings with validation and rule confidence management
- **Rule-Based Design**: Sequential rule processing with priority ordering and non-duplication
- **Type Safety**: Complete mypy compliance with pandas-stubs integration

## 🔧 Core Components

### TradeNormalizer

The TradeNormalizer ensures consistent data formatting across all trade sources:

- **Product Name Standardization**: Maps variations to canonical forms (e.g., "marine 0.5%", "380cst crack", "marine 0.5%-380cst")
- **Contract Month Normalization**: Standardizes formats to "MMM-YY" pattern (e.g., "Jan-25", "Feb-25")
- **Buy/Sell Indicator Mapping**: Converts all variations to "B" or "S"
- **Unit Conversion**: Handles BBL ↔ MT conversions with configurable ratios
- **Adjacent Month Detection**: Identifies consecutive contract months for Rule 6

### SpreadMatcher (Rule 2)

The SpreadMatcher implements sophisticated contract month spread matching with high efficiency:

- **Intelligent Grouping**: Pre-groups trades by (product, quantity, broker) to minimize search space
- **Spread Detection**: Identifies spread indicators (`spread="S"` or `price=0`) in trader data
- **Price Validation**: Calculates and validates spread price differentials between exchange legs
- **Contract Month Matching**: Ensures trader and exchange contract months align exactly
- **Direction Validation**: Verifies B/S directions match per contract month
- **Non-Duplication**: Triple validation prevents any trade from being matched multiple times
- **Performance**: O(n+m) grouping plus small combination checks vs. O(n²×m²) brute force

### ConfigManager

Centralized configuration management with Pydantic validation:

- **Rule Confidence Levels**: Predefined confidence percentages for Rules 1-10
- **Tolerance Settings**: Price and quantity tolerances for fuzzy matching
- **Conversion Ratios**: BBL to MT conversion factor (default 6.35)
- **Processing Order**: Sequential rule execution order
- **Output Settings**: Display options and logging configuration

### CSV Integration

The CSV loader now uses the normalizer for consistent data processing:

- **Automatic Normalization**: All fields normalized during loading
- **Type Safety**: Proper pandas DataFrame type handling
- **Error Handling**: Graceful handling of malformed data
- **Spread Detection**: Identifies spread trades based on tradeid presence

## 🧱 Code Quality Standards

### File and Function Limits

- **Functions under 50 lines** with single responsibility
- **Classes under 100 lines** representing single concepts
- **Files under 500 lines** - refactor by splitting modules if needed
- **Line length: 100 characters max** (enforced by Ruff)

### Design Principles

- **Single Responsibility**: Each function/class has one clear purpose
- **Open/Closed**: Extensible for new rules without modifying existing code
- **Fail Fast**: Validate input early, raise exceptions immediately
- **Type Safety**: Use type hints for all function signatures

## 🛠️ Development Environment

### UV Package Management

This project uses UV for blazing-fast Python package and environment management.

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv

# Sync dependencies
uv sync

# Add a package ***NEVER UPDATE A DEPENDENCY DIRECTLY IN PYPROJECT.toml***
# ALWAYS USE UV ADD
uv add requests

# Add development dependency
uv add --dev pytest ruff mypy

# Remove a package
uv remove requests

# Install specific Python version
uv python install 3.12
```

### Development Commands

```bash
# Type checking (with pandas type stubs installed)
python -m mypy src/energy_match

# Type checking (fallback if stubs missing)
python -m mypy src/energy_match --ignore-missing-imports

# Energy Trade Matching System Commands

# Run with default sample data (recommended for testing)
python -m src.energy_match.main

# Run with debug logging visible
python -m src.energy_match.main --show-logs --log-level DEBUG

# Run with custom data files
python -m src.energy_match.main path/to/traders.csv path/to/exchange.csv

# Run with output options
python -m src.energy_match.main --no-unmatched  # Hide unmatched trades
python -m src.energy_match.main --no-stats      # Hide statistics
python -m src.energy_match.main --show-logs     # Show detailed logs

# Show help for all available options
python -m src.energy_match.main --help
```

## 📋 Style & Conventions

### Python Style Guide

- **Follow PEP8** with these specific choices:
  - Line length: 100 characters (set by Ruff in pyproject.toml)
  - Use double quotes for strings
  - Use trailing commas in multi-line structures
- **Always use type hints** for function signatures and class attributes
- **Format with `ruff format`** (faster alternative to Black)
- **Use `pydantic` v2** for data validation and settings management

### Docstring Standards

Use Google-style docstrings for all public functions, classes, and modules:

```python
def calculate_discount(
    price: Decimal,
    discount_percent: float,
    min_amount: Decimal = Decimal("0.01")
) -> Decimal:
    """
    Calculate the discounted price for a product.

    Args:
        price: Original price of the product
        discount_percent: Discount percentage (0-100)
        min_amount: Minimum allowed final price

    Returns:
        Final price after applying discount

    Raises:
        ValueError: If discount_percent is not between 0 and 100
        ValueError: If final price would be below min_amount

    Example:
        >>> calculate_discount(Decimal("100"), 20)
        Decimal('80.00')
    """
```

### Naming Conventions

- **Variables and functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private attributes/methods**: `_leading_underscore`
- **Type aliases**: `PascalCase`
- **Enum values**: `UPPER_SNAKE_CASE`

## ✅ Quality Assurance

### Data-Driven Testing Approach

This project uses **real CSV data** for testing and validation instead of traditional unit tests. The energy trade matching system processes actual trader and exchange data files, making this approach more practical and reliable.

**Why Real Data Testing?**

- **Realistic scenarios**: Actual CSV variations and edge cases
- **End-to-end validation**: Complete workflows with real data patterns
- **Immediate feedback**: See actual matches and unmatched trades
- **Rule verification**: Test matching rules against real trading scenarios

### Current Implementation Status

✅ **Completed & Tested**:

- **Rule 1 (Exact Matching)**: 23 exact matches found in sample data with proper product spread preservation
- **Rule 2 (Spread Matching)**: 4 spread matches found using intelligent grouped approach with 95% confidence
- **CSV Data Loading**: Integrated with TradeNormalizer for consistent data processing
- **Universal Normalization**: Product names, contract months, buy/sell indicators standardized
- **Product Spread Preservation**: Hyphenated product names (e.g., "marine 0.5%-380cst") correctly preserved for Rule 5
- **Configuration Management**: Centralized settings with rule confidence levels and tolerances
- **Pydantic v2 Validation**: Type safety and data validation for all models
- **Non-Duplication Architecture**: Triple validation ensures no trade matched more than once across rules
- **Rich CLI Output**: Shows matches by type, unmatched trades, and comprehensive statistics
- **Type Safety**: Complete mypy compliance with pandas-stubs integration

🔄 **Planned for Implementation**:

- **Rules 3-10**: Crack spreads, aggregation, product spreads, and complex matching scenarios
- **Additional Data Sets**: More diverse trading scenarios for comprehensive rule testing
- **Performance Optimization**: Large-scale data processing capabilities

## 🚨 Error Handling

### Exception Best Practices

```python
# Create custom exceptions for your domain
class PaymentError(Exception):
    """Base exception for payment-related errors."""
    pass

class InsufficientFundsError(PaymentError):
    """Raised when account has insufficient funds."""
    def __init__(self, required: Decimal, available: Decimal):
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient funds: required {required}, available {available}"
        )

# Use specific exception handling
try:
    process_payment(amount)
except InsufficientFundsError as e:
    logger.warning(f"Payment failed: {e}")
    return PaymentResult(success=False, reason="insufficient_funds")
except PaymentError as e:
    logger.error(f"Payment error: {e}")
    return PaymentResult(success=False, reason="payment_error")

# Use context managers for resource management
from contextlib import contextmanager

@contextmanager
def database_transaction():
    """Provide a transactional scope for database operations."""
    conn = get_connection()
    trans = conn.begin_transaction()
    try:
        yield conn
        trans.commit()
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()
```

### Logging Strategy

```python
import logging
from functools import wraps

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Log function entry/exit for debugging
def log_execution(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"Entering {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Exiting {func.__name__} successfully")
            return result
        except Exception as e:
            logger.exception(f"Error in {func.__name__}: {e}")
            raise
    return wrapper
```

## 🔧 Configuration Management

### Environment Variables and Settings

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings with validation."""
    app_name: str = "MyApp"
    debug: bool = False
    database_url: str
    redis_url: str = "redis://localhost:6379"
    api_key: str
    max_connections: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

# Usage
settings = get_settings()
```

## 🏗️ Data Models and Validation

### Example Pydantic Models strict with pydantic v2

```python
from pydantic import BaseModel, Field, validator, EmailStr
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

class ProductBase(BaseModel):
    """Base product model with common fields."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: Decimal = Field(..., gt=0, decimal_places=2)
    category: str
    tags: List[str] = []

    @validator('price')
    def validate_price(cls, v):
        if v > Decimal('1000000'):
            raise ValueError('Price cannot exceed 1,000,000')
        return v

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }

class ProductCreate(ProductBase):
    """Model for creating new products."""
    pass

class ProductUpdate(BaseModel):
    """Model for updating products - all fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    category: Optional[str] = None
    tags: Optional[List[str]] = None

class Product(ProductBase):
    """Complete product model with database fields."""
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

    class Config:
        from_attributes = True  # Enable ORM mode
```
