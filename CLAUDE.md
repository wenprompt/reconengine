# CLAUDE.md

This file provides comprehensive guidance to Claude Code when working with this **Energy Trade Matching System** project.

## 🎯 Project Overview

This is an **Energy Trade Matching System** that matches trades between trader and exchange data sources using a sequential rule-based approach. The system implements exact matching (Rule 1), spread matching (Rule 2), crack matching (Rule 3), and complex crack matching (Rule 4) with plans for 6 additional sophisticated matching rules including aggregations, product spreads, and time-based scenarios.

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
│   ├── spread_matcher.py # Rule 2: Spread matching (contract month spreads)
│   ├── crack_matcher.py # Rule 3: Crack matching with unit conversion (optimized)
│   └── complex_crack_matcher.py # Rule 4: Complex crack matching (2-leg: base + brent swap)
├── core/               # Core system components
│   └── unmatched_pool.py # Non-duplication pool management
├── config/            # Configuration management
│   └── config_manager.py # Settings, tolerances, rule confidence levels
├── cli/              # Rich CLI interface
│   └── display.py   # Beautiful terminal output and progress
├── data/            # Sample data sets
│   ├── sourceTraders.csv    # Default trader data
│   ├── sourceExchange.csv   # Default exchange data
│   └── [additional datasets] # Various test scenarios (150525, 160525, etc.)
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
- **Performance Optimization**: Intelligent algorithms with indexing strategies for scalability

### File Organization & Purpose

#### Why Separate Config and Normalizer Files?

**`config/config_manager.py`** - **Centralized Configuration Hub**

- **Single Source of Truth**: All system settings, tolerances, and thresholds in one place
- **Environment Flexibility**: Easy to adjust parameters without code changes
- **Type Safety**: Pydantic validation ensures configuration integrity
- **Rule Management**: Confidence levels and processing order for all 10 rules
- **Business Logic Separation**: Keeps matching algorithms clean from configuration details

**`normalizers/trade_normalizer.py`** - **Data Standardization Engine**

- **Data Quality**: Ensures consistent formatting across different CSV sources
- **Business Rule Encoding**: Product name mappings, contract month patterns
- **Preprocessing Pipeline**: Cleans data before it reaches matching algorithms
- **Extensibility**: Easy to add new normalization rules for additional data sources
- **Separation of Concerns**: Keeps data cleaning separate from business logic

#### Core System Components

**`models/`** - **Data Contracts**

- **trade.py**: Immutable trade objects with validation and unit conversion
- **match_result.py**: Structured output format for all match types
- **Type Safety**: Pydantic v2 ensures data integrity throughout the system

**`loaders/`** - **Data Input Layer**

- **csv_loader.py**: Handles CSV parsing with automatic normalization integration
- **Error Handling**: Graceful handling of malformed data and missing fields
- **Format Flexibility**: Supports different CSV schemas from various exchanges

**`matchers/`** - **Business Logic Engine**

- **exact_matcher.py**: Rule 1 - Perfect field matching with 100% confidence
- **spread_matcher.py**: Rule 2 - Complex spread detection with price validation
- **crack_matcher.py**: Rule 3 - Unit conversion matching with performance optimization
- **complex_crack_matcher.py**: Rule 4 - Complex 2-leg crack matching (base product + brent swap)
- **Extensible Design**: Easy to add Rules 5-10 following established patterns

**`core/`** - **System Infrastructure**

- **unmatched_pool.py**: Non-duplication manager ensuring trades only match once
- **Thread Safety**: Prevents race conditions in concurrent processing
- **Audit Trail**: Complete history of all matching decisions

**`cli/`** - **User Interface**

- **display.py**: Rich terminal output with progress indicators and statistics
- **User Experience**: Beautiful formatting for complex matching results
- **Debugging Support**: Detailed logging and error reporting

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

### CrackMatcher (Rule 3) - **Performance Optimized**

The CrackMatcher implements crack spread matching with unit conversion and advanced optimization:

- **Indexing Strategy**: Optimized from O(N\*M) to O(N+M) using dictionary-based lookups
- **Unit Conversion**: Handles BBL ↔ MT conversions with configurable tolerances (±100 BBL, ±50 MT)
- **Match Key Optimization**: Groups by (product, contract, price, broker, buy/sell) for O(1) lookups
- **Configurable Tolerances**: Moved from hardcoded values to centralized configuration management
- **Duplicate Prevention**: Triple validation with pool manager integration prevents any duplicate matches
- **Performance**: Scales linearly instead of quadratically with large datasets
- **Real-World Testing**: Successfully processes 97 trades in 0.05 seconds with 3 crack matches found

### ComplexCrackMatcher (Rule 4) - **2-Leg Crack Matching**

The ComplexCrackMatcher implements sophisticated 2-leg crack trade matching where a single crack trade in trader data corresponds to a base product + brent swap combination in exchange data:

- **Base Product Extraction**: Intelligently extracts base product from crack names (e.g., "marine 0.5% crack" → "marine 0.5%")
- **2-Leg Validation**: Matches single crack trade against base product + brent swap pairs in exchange data
- **B/S Direction Logic**: Enforces direction rules: Sell Crack = Sell Base + Buy Brent; Buy Crack = Buy Base + Sell Brent
- **Unit Conversion**: Handles BBL ↔ MT conversions with configurable tolerances (±100 MT default)
- **Price Formula Validation**: Verifies (base_price ÷ 6.35) - brent_price = crack_price within tolerance
- **Pool Integration**: Uses UnmatchedPoolManager for proper trade removal and non-duplication
- **Encapsulated Architecture**: Clean integration using `pool_manager.record_match()` method
- **Configuration-Driven**: Leverages ConfigManager for tolerances and confidence levels (80% default)
- **Real-World Validation**: Successfully matches T_0016 crack with E_0016 (base) + E_0015 (brent swap)

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
uv run python -m mypy src/energy_match

# Type checking (fallback if stubs missing)
uv run python -m mypy src/energy_match --ignore-missing-imports

# Energy Trade Matching System Commands

# Run with default sample data (recommended for testing)
uv run python -m src.energy_match.main

# Run with debug logging visible
uv run python -m src.energy_match.main --show-logs --log-level DEBUG

# Run with custom data files
uv run python -m src.energy_match.main path/to/traders.csv path/to/exchange.csv

# Run with output options
uv run python -m src.energy_match.main --no-unmatched  # Hide unmatched trades
uv run python -m src.energy_match.main --no-stats      # Hide statistics
uv run python -m src.energy_match.main --show-logs     # Show detailed logs

# Show help for all available options
uv run python -m src.energy_match.main --help

# Show rules and configurations of each rule
uv run python -m src.energy_match.main --show-rules
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

- **Rule 1 (Exact Matching)**: 28 exact matches found in sample data with proper product spread preservation
- **Rule 2 (Spread Matching)**: 18 spread matches found using intelligent grouped approach with 95% confidence
- **Rule 3 (Crack Matching)**: 3 crack matches found with optimized indexing strategy and unit conversion
- **Rule 4 (Complex Crack Matching)**: 1 complex crack match found using 2-leg base product + brent swap validation
- **CSV Data Loading**: Integrated with TradeNormalizer for consistent data processing
- **Universal Normalization**: Product names, contract months, buy/sell indicators standardized
- **Product Spread Preservation**: Hyphenated product names (e.g., "marine 0.5%-380cst") correctly preserved for Rule 5
- **Configuration Management**: Centralized settings with rule confidence levels and configurable tolerances
- **Performance Optimization**: CrackMatcher optimized from O(N\*M) to O(N+M) using indexing strategy
- **Pydantic v2 Validation**: Type safety and data validation for all models
- **Non-Duplication Architecture**: Triple validation ensures no trade matched more than once across rules
- **Encapsulated Pool Management**: Proper `record_match()` method usage for multi-leg matches
- **Rich CLI Output**: Shows matches by type, unmatched trades, and comprehensive statistics with multi-leg display
- **Type Safety**: Complete mypy compliance with pandas-stubs integration

🔄 **Planned for Implementation**:

- **Rules 5-10**: Aggregation, product spreads, time-based matching, and complex scenarios
- **Additional Data Sets**: More diverse trading scenarios for comprehensive rule testing
- **Scaling Optimization**: Further performance improvements for enterprise-scale datasets

## 🏆 Rule 4 Implementation Summary

**Successfully Completed**: Rule 4 - Complex Crack Matching (2-Leg with Brent Swap)

### Implementation Highlights

- **✅ Complete Integration**: Fully integrated into the matching pipeline following Rules 1-3
- **✅ Configuration Management**: Uses ConfigManager for tolerances and confidence levels (80%)
- **✅ Pool Management**: Proper encapsulation using `pool_manager.record_match()` method
- **✅ Multi-Leg Display**: CLI shows both exchange trades (base product + brent swap) correctly
- **✅ Type Safety**: Full MyPy compliance with proper type annotations
- **✅ Real-World Testing**: Successfully matches T_0016 crack with E_0016 (base) + E_0015 (brent swap)

### Architecture Improvements Made

- **Refactored Trade Removal**: Replaced manual trade pool manipulation with encapsulated `record_match()` calls
- **Enhanced CLI Display**: Added special handling for complex crack matches showing both exchange trades
- **Configuration Integration**: Added complex crack tolerances and confidence to ConfigManager
- **Import Organization**: Updated `__init__.py` and `main.py` with proper imports and integration

### Key Technical Features

- **Base Product Extraction**: Intelligent parsing of crack product names (e.g., "marine 0.5% crack" → "marine 0.5%")
- **2-Leg Validation**: Matches single crack trade against base product + brent swap pairs
- **B/S Direction Logic**: Enforces "Sell Crack = Sell Base + Buy Brent; Buy Crack = Buy Base + Sell Brent"
- **Unit Conversion**: BBL ↔ MT conversion with ±100 MT tolerance
- **Price Formula**: Validates (base_price ÷ 6.35) - brent_price = crack_price within ±0.01 tolerance
- **Non-Duplication**: Triple validation ensures trades only match once across all rules

## 📋 Rule 5 Implementation Guidelines

**Next Development Target**: Rule 5 - Product Spread Matching

### Context for Rule 5 Implementation

Based on the established patterns and architecture, Rule 5 should follow these implementation guidelines:

#### Architecture Consistency
- **File Location**: Create `src/energy_match/matchers/product_spread_matcher.py`
- **Class Pattern**: Follow `ProductSpreadMatcher` naming convention
- **Integration**: Add to `__init__.py` and `main.py` following Rules 1-4 pattern
- **Pool Management**: Use `pool_manager.record_match(match)` for proper trade removal

#### Configuration Integration
- **Config Manager**: Add Rule 5 confidence level and tolerances to `ConfigManager`
- **Tolerance Settings**: Define product spread specific tolerances in configuration
- **Rule Order**: Ensure Rule 5 processes after Rules 1-4 using `pool_manager.get_unmatched_*_trades()`

#### Implementation Pattern
- **Constructor**: Accept `config_manager` and `normalizer` parameters
- **Main Method**: `find_matches(pool_manager: UnmatchedPoolManager) -> List[MatchResult]`
- **Rule Info**: Implement `get_rule_info()` method for `--show-rules` functionality
- **Validation**: Include comprehensive validation methods for spread logic
- **Logging**: Follow established logging patterns with appropriate debug/info levels

#### Product Spread Detection
- **Hyphenated Products**: Look for products containing "-" (e.g., "marine 0.5%-380cst")
- **Component Extraction**: Split hyphenated names into component products
- **Match Validation**: Ensure component products exist in exchange data with proper relationships
- **Price Relationship**: Implement spread price calculation and validation logic

#### Data Model Integration
- **MatchType**: Add `PRODUCT_SPREAD = "product_spread"` to `MatchType` enum
- **MatchResult**: Use `additional_exchange_trades` for multi-leg product spread matches
- **Trade Fields**: Leverage existing normalized fields and unit conversion capabilities

#### Testing and Validation
- **Sample Data**: Verify existing CSV data contains product spread examples
- **Unit Tests**: Test component extraction, price validation, and match logic
- **Integration Test**: Ensure Rule 5 doesn't interfere with Rules 1-4 results
- **Performance**: Maintain O(N+M) complexity using indexing strategies like Rule 3

#### Display Integration
- **CLI Output**: Update `display.py` to handle product spread matches properly
- **Multi-Leg Display**: Show all component trades in match results
- **Statistics**: Include Rule 5 matches in summary statistics and rule breakdown

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
