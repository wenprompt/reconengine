# CLAUDE.md

This file provides comprehensive guidance to Claude Code when working with this **Energy Trade Matching System** project.

## 🎯 Project Overview

This is a **Reconciliation Engine** that contains multiple specialized matching systems. The **Energy Trade Matching System** (`src/energy_match/`) is the current module under development, with future plans for additional matching systems like `ffa_match` and others, each with their own specialized rules and matching logic.

### Energy Match Module Summary

The energy matching system processes trades between trader and exchange data sources using a sequential rule-based approach with 9 implemented rules:

- **Rules 1-3**: Basic matching (exact, spread, crack)
- **Rules 4-6**: Complex matching (complex crack, product spread, aggregation)
- **Rules 7-9**: Advanced aggregated matching (aggregated complex crack, aggregated spread, aggregated crack)

Each matching system will have its own `docs/rules.md` file for detailed rule specifications.

### Key Features

- **Universal Data Normalization**: TradeNormalizer standardizes product names, contract months, buy/sell indicators, and unit conversions
- **Configuration Management**: Centralized settings with rule confidence levels, tolerances, and conversion ratios
- **Sequential Rule Processing**: Implements rules in priority order (exact matches first) with non-duplication
- **Rich CLI Interface**: Beautiful terminal output with progress indicators and detailed results
- **Product-Specific Unit Conversion**: MT→BBL conversion with product-specific ratios (6.35, 8.9, 7.0 default)
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
├── matchers/            # Matching rule implementations (9 rules)
│   ├── exact_matcher.py # Rule 1: Exact matching
│   ├── spread_matcher.py # Rule 2: Spread matching
│   ├── crack_matcher.py # Rule 3: Crack matching
│   ├── complex_crack_matcher.py # Rule 4: Complex crack matching
│   ├── product_spread_matcher.py # Rule 5: Product spread matching
│   ├── aggregation_matcher.py # Rule 6: Aggregation matching
│   ├── aggregated_complex_crack_matcher.py # Rule 7: Aggregated complex crack
│   ├── aggregated_spread_matcher.py # Rule 8: Aggregated spread matching
│   └── aggregated_crack_matcher.py # Rule 9: Aggregated crack matching
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
    └── rules.md        # Complete rule specifications for this module
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
- **Rule Management**: Confidence levels and processing order for all implemented rules
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

- **Rules 1-3**: Basic matching (exact, spread, crack with unit conversion)
- **Rules 4-6**: Complex matching (2-leg crack, product spread, aggregation)
- **Rules 7-9**: Advanced aggregated matching (complex crack + aggregation, spread + aggregation, crack + aggregation)
- **BaseMatcher**: Universal field validation and shared matcher functionality
- **Extensible Design**: Easy to add new rules following established patterns

**`core/`** - **System Infrastructure**

- **unmatched_pool.py**: Non-duplication manager ensuring trades only match once
- **Thread Safety**: Prevents race conditions in concurrent processing
- **Audit Trail**: Complete history of all matching decisions

**`cli/`** - **User Interface**

- **display.py**: Rich terminal output with progress indicators and statistics
- **User Experience**: Beautiful formatting for complex matching results
- **Debugging Support**: Detailed logging and error reporting

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
# Type checking
uv run python -m mypy src/energy_match

# Run energy match system (example - adapt path for other modules)
uv run python -m src.energy_match.main
uv run python -m src.energy_match.main --help  # See all options
uv run python -m src.energy_match.main --show-rules  # Display detailed rule information

###  logging and debugging
uv run python -m src.energy_match.main --show-logs  # Show detailed logging output
uv run python -m src.energy_match.main --show-logs --log-level DEBUG  # Enable debug logging
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

---

# 📊 Energy Match Module Implementation Progress

_The following sections document the specific implementation progress and updates for the `src/energy_match/` module._

## ✅ Current Implementation Status

**Energy Match Module Completed**:

- **9 Sequential Rules**: Implemented with 90.5% match rate on sample data
- **Universal Field Validation**: JSON-driven configuration system
- **Pydantic v2 Models**: Complete type safety and validation
- **Performance Optimized**: O(N+M) algorithms with intelligent indexing
- **Rich CLI Interface**: Beautiful terminal output with detailed statistics

## 🔧 Energy Match Core Components

### Energy Shared Unit Conversion System

The energy module implements a shared, product-specific unit conversion architecture:

- **Product-Specific Ratios**: Marine 0.5%/380cst crack use 6.35, naphtha japan/nwe crack use 8.9, default 7.0
- **One-Way Conversion**: Always MT→BBL (trader MT data converts to compare with exchange BBL)
- **Unit Logic**: Trader data defaults to MT, exchange data uses unit column
- **Exact Matching**: Product names are pre-normalized, allowing exact ratio lookup instead of "contains" matching
- **Shared Methods**: `convert_mt_to_bbl_with_product_ratio()` and `validate_mt_to_bbl_quantity_match()`
- **Rules 3 & 4 Integration**: Both CrackMatcher and ComplexCrackMatcher use identical conversion logic
- **JSON Configuration**: Conversion ratios stored in `normalizer_config.json` for maintainability

### Energy CSV Integration

The energy CSV loader uses the normalizer for consistent data processing:

- **Automatic Normalization**: All fields normalized during loading
- **Type Safety**: Proper pandas DataFrame type handling
- **Error Handling**: Graceful handling of malformed data
- **Spread Detection**: Identifies spread trades based on tradeid presence

---

_End of Energy Match Module specific documentation_

## 🏗️ Pydantic v2 Data Validation Architecture

### Core Data Models Pattern

```python
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from typing import Optional, List

class Trade(BaseModel):
    """Immutable trade model with strict validation."""

    model_config = ConfigDict(
        frozen=True,  # Immutable for thread safety
        validate_assignment=True,  # Validate on field updates
        str_strip_whitespace=True  # Auto-clean string inputs
    )

    trade_id: str = Field(..., min_length=1, max_length=50)
    product_name: str = Field(..., min_length=1)
    quantity_mt: Decimal = Field(..., gt=0, decimal_places=2)
    price: Decimal = Field(..., decimal_places=2)
    buy_sell: str = Field(..., pattern=r'^[BS]$')

    # Universal fields - must match across all rules
    broker_group_id: Optional[int] = None
    exch_clearing_acct_id: Optional[str] = None

    @property
    def quantity_bbl(self) -> Decimal:
        """Dynamic conversion property."""
        return self.quantity_mt * Decimal("6.35")  # Default ratio
```

### Configuration Management Pattern

```python
class MatchingConfig(BaseModel):
    """Centralized configuration with validation."""

    model_config = ConfigDict(frozen=True, validate_assignment=True)

    rule_confidence_levels: Dict[int, Decimal] = Field(
        default_factory=lambda: {1: Decimal("100"), 2: Decimal("95")}
    )
    quantity_tolerance_bbl: Decimal = Field(default=Decimal("100"), gt=0)
    processing_order: List[int] = Field(default=[1, 2, 3, 4, 5, 6, 7, 8, 9])

    @field_validator('rule_confidence_levels')
    def validate_confidence_levels(cls, v):
        for rule, confidence in v.items():
            if not (0 <= confidence <= 100):
                raise ValueError(f'Confidence must be 0-100, got {confidence}')
        return v
```

### Match Result Pattern

```python
class MatchResult(BaseModel):
    """Structured match output with metadata."""

    match_id: str
    match_type: MatchType  # Enum for type safety
    confidence: Decimal = Field(..., ge=0, le=100)
    trader_trade: Trade
    exchange_trade: Trade
    additional_trader_trades: List[Trade] = []
    additional_exchange_trades: List[Trade] = []
    matched_fields: List[str] = []  # What fields actually matched
    tolerances_applied: Dict[str, str] = {}  # Audit trail
    rule_order: int = Field(..., ge=1)
```

## 🌐 Universal Fields Architecture

### JSON-Driven Universal Field Configuration

Universal fields ensure consistency across ALL matching rules. They are configured in `normalizer_config.json`:

```json
{
  "universal_matching_fields": {
    "description": "Fields that must match across ALL matching rules",
    "required_fields": ["brokergroupid", "exchclearingacctid"],
    "field_mappings": {
      "brokergroupid": "broker_group_id",
      "exchclearingacctid": "exch_clearing_acct_id"
    },
    "notes": {
      "field_mappings": "Maps CSV column names to Trade model attributes"
    }
  }
}
```

### BaseMatcher Pattern for Universal Rule Inheritance

```python
class BaseMatcher:
    """Base matcher providing universal field validation to all matchers."""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.universal_fields = config_manager.get_universal_matching_fields()
        self.field_mappings = config_manager.get_universal_field_mappings()

    def validate_universal_fields(self, trade1: Trade, trade2: Trade) -> bool:
        """Validate universal fields match between trades."""
        for config_field in self.universal_fields:
            trade_attribute = self.field_mappings[config_field]
            value1 = getattr(trade1, trade_attribute)
            value2 = getattr(trade2, trade_attribute)
            if value1 != value2:
                return False
        return True

    def create_universal_signature(self, trade: Trade, rule_specific_fields: List) -> Tuple:
        """Create matching signature including universal fields."""
        signature_parts = rule_specific_fields.copy()
        for config_field in self.universal_fields:
            trade_attribute = self.field_mappings[config_field]
            signature_parts.append(getattr(trade, trade_attribute))
        return tuple(signature_parts)

    def get_universal_matched_fields(self, rule_fields: List[str]) -> List[str]:
        """Combine rule-specific fields with universal fields for match results."""
        return rule_fields + [self.field_mappings[f] for f in self.universal_fields]
```

### Adding New Universal Fields

To add universal fields that apply to ALL matching rules:

1. **Update JSON Configuration**:

```json
"required_fields": ["brokergroupid", "exchclearingacctid", "traderid"],
"field_mappings": {
  "brokergroupid": "broker_group_id",
  "exchclearingacctid": "exch_clearing_acct_id",
  "traderid": "trader_id"
}
```

2. **Update Trade Model**:

```python
class Trade(BaseModel):
    # Existing fields...
    trader_id: Optional[str] = None  # Add new universal field
```

3. **Zero Code Changes Required**: All matchers inherit universal validation automatically!

## 📁 File Organization Patterns

### Modular Architecture Template

For `ffa_match` or other future modules, follow this structure:

```
src/ffa_match/                     # New matching module
├── main.py                        # Module entry point
├── models/                        # Pydantic models specific to FFA
│   ├── ffa_trade.py              # FFA-specific trade model
│   └── ffa_match_result.py       # FFA match result extensions
├── matchers/                      # FFA-specific matching rules
│   ├── base_matcher.py           # Inherit universal patterns
│   ├── ffa_exact_matcher.py      # FFA Rule 1
│   └── ffa_complex_matcher.py    # FFA Rule 2, etc.
├── normalizers/                   # FFA data normalization
│   └── ffa_normalizer.py         # FFA-specific normalization
├── config/                        # FFA configuration
│   ├── config_manager.py         # FFA-specific config
│   └── ffa_config.json           # FFA normalization/universal fields
├── core/                          # Shared core components
│   └── ffa_pool.py               # FFA-specific pool management
├── cli/                           # FFA CLI interface
│   └── ffa_display.py            # FFA-specific display logic
├── data/                          # FFA sample data
└── docs/
    └── rules.md                   # FFA-specific rules documentation
```

### Inheritance and Code Reuse Pattern

```python
# In ffa_match/matchers/base_matcher.py
from ...energy_match.matchers.base_matcher import BaseMatcher as EnergyBaseMatcher

class FFABaseMatcher(EnergyBaseMatcher):
    """FFA-specific base matcher inheriting universal field validation."""

    def __init__(self, config_manager: FFAConfigManager):
        super().__init__(config_manager)
        # FFA-specific initialization

# In ffa_match/matchers/ffa_exact_matcher.py
class FFAExactMatcher(FFABaseMatcher):
    """FFA exact matching with inherited universal field validation."""

    def find_matches(self, pool_manager) -> List[FFAMatchResult]:
        # FFA-specific matching logic
        # Universal fields automatically validated via parent class
```

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
