# CLAUDE.md

This file provides comprehensive guidance to Claude Code when working with this **Reconciliation Engine** project.

## 🎯 Project Overview

This is a **Reconciliation Engine** that contains multiple specialized matching systems:

- **Unified Reconciliation System** (`src/unified_recon/`) - Centralized data routing system that groups trades by exchange and routes to appropriate matching systems
- **ICE Trade Matching System** (`src/ice_match/`) - Energy derivatives matching with 13 sequential rules
- **SGX Trade Matching System** (`src/sgx_match/`) - Singapore Exchange iron ore futures matching with 3 sequential rules
- **Future Modules**: Plans for additional matching systems like `ffa_match` and others

Each matching system has its own specialized rules and matching logic tailored to specific exchanges and products.

### ICE Match Module Summary

The ice matching system processes trades between trader and exchange data sources using a sequential rule-based approach with 13 implemented rules:

- **Rules 1-3**: Basic matching (exact, spread, crack)
- **Rules 4-6**: Complex matching (complex crack, product spread, fly)
- **Rules 7-9**: Advanced aggregated matching (aggregation, aggregated complex crack, aggregated spread)
- **Rules 10-13**: Advanced matching (multileg spread, aggregated crack, complex crack roll, aggregated product spread)

### SGX Match Module Summary

The SGX matching system processes Singapore Exchange iron ore futures trades using a 3-rule sequential matching approach:

- **Rule 1**: Exact matching on 7 fields (product, contract month, quantity, price, buy/sell, + universal fields)
- **Rule 2**: Spread matching for calendar spreads with price validation
- **Rule 3**: Product spread matching with 3-tier confidence system (PS required 95%, no PS required 92%, hyphenated exchange 90%)
- **Iron Ore Focus**: Specialized for FE (Iron Ore) futures and options with M65 product spread support
- **Options Support**: Handles puts/calls with strike prices
- **Case-Insensitive Architecture**: Consistent normalization with intelligent fallback logic

### Unified Reconciliation System Summary

The unified reconciliation system acts as a centralized data router and aggregator:

- **Data Routing**: Groups trades by `exchangegroupid` and routes to appropriate systems (Group 1 → ICE, Group 2 → SGX)
- **System Integration**: Calls individual matching systems with filtered data while maintaining system isolation
- **Result Aggregation**: Combines results from multiple systems with unified reporting
- **Phase 1 Architecture**: Pure data routing without centralizing normalizers/configs
- **Rich Display**: Beautiful terminal output with detailed breakdowns and DataFrame tables

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

**Unified Reconciliation System Structure:**

```text
src/unified_recon/
├── main.py                 # Main entry point for unified reconciliation
├── config/                 # Configuration management
│   ├── unified_config.json # System mappings and routing configuration
│   └── __init__.py
├── core/                   # Core routing and aggregation logic
│   ├── group_router.py    # Data loading, validation, and routing by exchangegroupid
│   ├── result_aggregator.py # Cross-system result aggregation and statistics
│   └── __init__.py
├── utils/                  # Validation and helper utilities
│   ├── data_validator.py  # CSV validation and exchange group detection
│   └── __init__.py
├── cli/                    # Rich terminal interface
│   ├── unified_display.py # Unified reporting and DataFrame display
│   └── __init__.py
└── data/                   # Centralized master data (moved from individual systems)
    ├── sourceTraders.csv   # Master trader data (104 records)
    └── sourceExchange.csv  # Master exchange data (101 records)
```

**ICE Match Module Structure:**

```text
src/ice_match/
├── main.py                 # Main application entry point with CLI
├── models/                 # Pydantic v2 data models
│   ├── trade.py           # Core Trade model with validation and unit conversion
│   └── match_result.py    # MatchResult model for output
├── loaders/               # CSV data loading with normalization integration
│   └── csv_loader.py     # Handles both trader and exchange CSV files
├── normalizers/          # Data normalization and standardization
│   └── trade_normalizer.py # Product names, contract months, buy/sell, units
├── utils/               # Utility functions separated by dependency type
│   ├── __init__.py     # Module exports and documentation
│   ├── trade_helpers.py # Pure utility functions (no config dependencies)
│   └── conversion_helpers.py # Config-dependent utility functions
├── matchers/            # Matching rule implementations (13 rules)
│   ├── exact_matcher.py # Rule 1: Exact matching
│   ├── spread_matcher.py # Rule 2: Spread matching
│   ├── crack_matcher.py # Rule 3: Crack matching
│   ├── complex_crack_matcher.py # Rule 4: Complex crack matching
│   ├── product_spread_matcher.py # Rule 5: Product spread matching
│   ├── fly_matcher.py # Rule 6: Fly matching (butterfly spread)
│   ├── aggregation_matcher.py # Rule 7: Aggregation matching
│   ├── aggregated_complex_crack_matcher.py # Rule 8: Aggregated complex crack
│   ├── aggregated_spread_matcher.py # Rule 9: Aggregated spread matching
│   ├── multileg_spread_matcher.py # Rule 10: Multileg spread matching
│   ├── aggregated_crack_matcher.py # Rule 11: Aggregated crack matching
│   ├── complex_crack_roll_matcher.py # Rule 12: Complex crack roll matching
│   └── aggregated_product_spread_matcher.py # Rule 13: Aggregated product spread matching
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

**SGX Match Module Structure:**

```text
src/sgx_match/
├── main.py                 # Main application entry point with CLI
├── models/                 # Pydantic v2 data models
│   ├── trade.py           # SGXTrade model with options support
│   └── match_result.py    # SGXMatchResult model for output
├── loaders/               # CSV data loading with normalization integration
│   └── sgx_csv_loader.py  # Handles SGX trader and exchange CSV files
├── normalizers/          # Data normalization and standardization
│   └── sgx_trade_normalizer.py # SGX-specific product names, contract months
├── matchers/            # Matching rule implementations (3 rules)
│   ├── base_matcher.py   # Base matcher with universal field validation
│   ├── exact_matcher.py # Rule 1: Exact matching for SGX
│   ├── spread_matcher.py # Rule 2: Spread matching for SGX
│   └── product_spread_matcher.py # Rule 3: Product spread matching (3-tier system)
├── core/               # Core system components
│   └── sgx_pool.py    # Non-duplication pool management for SGX
├── config/            # Configuration management
│   ├── sgx_config_manager.py # SGX-specific settings and configuration
│   └── normalizer_config.json # SGX product mappings and field configuration
├── cli/              # Rich CLI interface
│   └── sgx_display.py # Beautiful terminal output for SGX results
├── data/            # SGX sample data sets
│   ├── sourceTraders.csv    # SGX trader data (46 records)
│   └── sourceExchange.csv   # SGX exchange data (367 records)
└── docs/
    └── rules.md        # SGX rule specifications
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

**`utils/`** - **Utility Functions Layer**

- **trade_helpers.py**: Pure utility functions with no configuration dependencies
  - `extract_base_product()` - Extract base product from crack products
  - `extract_month_year()` - Parse contract month components
  - `get_month_order_tuple()` - Convert months to sortable tuples
- **conversion_helpers.py**: Configuration-dependent utility functions
  - `get_product_conversion_ratio()` - Product-specific MT↔BBL ratios
  - `convert_mt_to_bbl_with_product_ratio()` - MT to BBL conversion
  - `validate_mt_to_bbl_quantity_match()` - Quantity validation with conversion
- **Architectural Benefits**: Separates helper functions from business logic, improves testability and reusability

**`matchers/`** - **Business Logic Engine**

- **Rules 1-3**: Basic matching (exact, spread, crack with unit conversion)
- **Rules 4-6**: Complex matching (complex crack, product spread, fly)
- **Rules 7-9**: Advanced aggregated matching (aggregation, aggregated complex crack, aggregated spread)
- **Rules 10-13**: Advanced matching (multileg spread, aggregated crack, complex crack roll, aggregated product spread)
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
uv run python -m mypy src/ice_match
uv run python -m mypy src/sgx_match
uv run python -m mypy src/unified_recon

# Centralized data routing with master data processing
uv run python -m src.unified_recon.main                    # Shows all matches+unmatches
uv run python -m src.unified_recon.main --log-level DEBUG # Enable debug logging

# Run ICE match system directly
uv run python -m src.ice_match.main
uv run python -m src.ice_match.main --show-rules  # Display detailed rule information
uv run python -m src.ice_match.main --log-level DEBUG  # Enable debug logging

# Run SGX match system directly
uv run python -m src.sgx_match.main  # Shows all matches+unmatches
uv run python -m src.sgx_match.main --log-level DEBUG  # Enable debug logging

# options
--help
--log-level DEBUG
--no-unmatched
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

This project uses **real CSV data** for testing and validation instead of traditional unit tests. The ice trade matching system processes actual trader and exchange data files, making this approach more practical and reliable.

**Why Real Data Testing?**

- **Realistic scenarios**: Actual CSV variations and edge cases
- **End-to-end validation**: Complete workflows with real data patterns
- **Immediate feedback**: See actual matches and unmatched trades
- **Rule verification**: Test matching rules against real trading scenarios

---

# 📊 ICE Match Module Implementation Progress

_The following sections document the specific implementation progress and updates for the `src/ice_match/` module._

## ✅ Current Implementation Status

**ICE Match Module Completed**:

- **13 Sequential Rules**: Implemented with enhanced match rate on sample data, including new Rule 6 (Fly Matcher)
- **Fly Matching**: Rule 6 for butterfly spread trades (3-leg buy-sell-buy pattern) with dealid-based grouping ⭐ **NEW**
- **Complex Crack Roll Matching**: Rule 12 for calendar spreads of crack positions
- **Aggregated Product Spread Matching**: Rule 13 with comprehensive 4-tier architecture for product spread matching with aggregation logic ⭐ **ENHANCED**
- **Refactored Utils Architecture**: Separated pure utilities from config-dependent functions
- **3-Tier Spread Matching**: Enhanced spread detection with DealID/TradeID, time-based, and product/quantity tiers
- **Universal Field Validation**: JSON-driven configuration system
- **Pydantic v2 Models**: Complete type safety and validation
- **Performance Optimized**: O(N+M) algorithms with intelligent indexing
- **Rich CLI Interface**: Beautiful terminal output with detailed statistics and tier-specific breakdowns
- **Zero-Price Spread Support**: Allows spreads where both legs have price = 0

## 🔧 ICE Match Core Components

### ICE Shared Unit Conversion System

The ice module implements a shared, product-specific unit conversion architecture:

- **Product-Specific Ratios**: Marine 0.5%/380cst crack use 6.35, naphtha japan/nwe crack use 8.9, default 7.0
- **One-Way Conversion**: Always MT→BBL (trader MT data converts to compare with exchange BBL)
- **Unit Logic**: Trader data defaults to MT, exchange data uses unit column
- **Exact Matching**: Product names are pre-normalized, allowing exact ratio lookup instead of "contains" matching
- **Shared Methods**: `convert_mt_to_bbl_with_product_ratio()` and `validate_mt_to_bbl_quantity_match()` in `utils/conversion_helpers.py`
- **Rules 3, 4 & 12 Integration**: CrackMatcher, ComplexCrackMatcher, and ComplexCrackRollMatcher use identical conversion logic
- **JSON Configuration**: Conversion ratios stored in `normalizer_config.json` for maintainability
- **Modular Architecture**: Utility functions separated from TradeNormalizer for better code organization

### ICE CSV Integration

The ice CSV loader uses the normalizer for consistent data processing:

- **Automatic Normalization**: All fields normalized during loading
- **Type Safety**: Proper pandas DataFrame type handling
- **Error Handling**: Graceful handling of malformed data
- **Spread Detection**: Identifies spread trades based on tradeid presence

---

## 🚀 Recent Enhancement: Rule 13 Tier 4 Implementation

### New Tier 4: Hyphenated Exchange Aggregation → Trader Spread Pair ⭐

**Problem Solved**: Previously, Rule 13 couldn't handle cases where multiple identical hyphenated exchange spreads needed to aggregate to match a single trader spread pair.

**Example Case Fixed**:

- **Exchange**: E_0044 + E_0045 (both "naphtha japan-naphtha nwe", 5000 MT each, 22.25, S)
- **Trader**: T_0078 (naphtha japan, 10000 MT, S) + T_0079 (naphtha nwe, 10000 MT, B)
- **Before**: ❌ No match found
- **After**: ✅ Successfully matched with Tier 4 logic

### Complete Four-Tier Architecture

**Rule 13** now implements a comprehensive four-tier system:

1. **Tier 1 (Scenario A)**: Exchange Component Aggregation → Trader Spread Pair
   - Multiple individual exchange component trades → Single trader spread pair
2. **Tier 2 (Scenario B)**: Exchange Hyphenated Spread → Trader Component Aggregation
   - Single exchange hyphenated spread → Multiple trader trades per component
3. **Tier 3 (Scenario C)**: Cross-Spread Aggregation (Trader Spread Pairs → Exchange Components)
   - Multiple trader spread pairs aggregate by component → Individual exchange component trades
4. **Tier 4 (Scenario D)**: Hyphenated Exchange Aggregation → Trader Spread Pair ⭐ **NEW**
   - Multiple identical hyphenated exchange spreads → Single trader spread pair

### Implementation Quality

**Architecture Excellence**:

- **Clear Tier Organization**: Section headers and comprehensive documentation
- **Zero Technical Debt**: No unused imports, hardcoded values, or magic numbers
- **Type Safety**: 100% mypy compliant with comprehensive type annotations
- **Performance**: O(N+M) algorithms with intelligent indexing
- **Maintainability**: Well-structured code following established patterns

**Test Results**:

- **Successfully matches**: `AGG_PROD_SPREAD_13_ce811aca`
- **Confidence Level**: 62%
- **Aggregation Type**: Many-to-Many (N:N)
- **DataFrame Integration**: Displays correctly in standardized output

---

## 🆕 New Rule 6: Fly Matcher Implementation

### Butterfly Spread (Fly) Matching ⭐ **NEWLY IMPLEMENTED**

**Rule 6** implements sophisticated butterfly spread matching with dealid-based grouping inspired by SGX spread matcher Tier 1 approach:

**Key Features:**
- **3-Leg Pattern Validation**: X+Z=Y quantity relationship where outer legs sum equals middle leg
- **Direction Pattern**: Outer legs (X,Z) same direction, middle leg (Y) opposite direction  
- **Contract Month Sorting**: Chronological ordering (earliest → middle → latest)
- **DealID-Based Grouping**: Exchange trades must share same dealid for fly identification
- **Universal Field Validation**: Inherits broker group and clearing account validation
- **Non-Duplication Protection**: Proper pool manager integration prevents trade reuse

**Example Pattern:**
- **Trader**: 3 trades with spread indicator 'S' (e.g., Buy 1000 Sep, Sell 2000 Oct, Buy 1000 Nov)
- **Exchange**: 3 trades sharing same dealid (corresponding to the butterfly structure)
- **Validation**: 1000 + 1000 = 2000 ✅, Buy/Sell/Buy pattern ✅

**Technical Implementation:**
- **74% Confidence Level**: Positioned between Product Spread (75%) and Aggregation (72%)
- **Fly Price Calculation**: Validates (X_price - Y_price) + (Z_price - Y_price) = trader_fly_price
- **Pool Integration**: `pool_manager.record_match()` ensures proper trade removal
- **Type Safety**: 100% mypy compliant with comprehensive type annotations

---

_End of ICE Match Module specific documentation_

# 📊 SGX Match Module Implementation

_The following sections document the specific implementation for the `src/sgx_match/` module._

## ✅ SGX Implementation Status

**SGX Match Module Completed**:

- **3 Sequential Rules**: Exact matching (Rule 1), Spread matching (Rule 2), and Product Spread matching (Rule 3) with 100% match rate on sample data
- **3-Tier Product Spread System**: Enhanced product spread matching with PS required (95%), no PS required (92%), and hyphenated exchange spread (90%) confidence tiers
- **Universal Field Validation**: JSON-driven configuration system inherited from ICE architecture with consistent case-insensitive normalization
- **Options Support**: Handles iron ore futures and options with puts/calls and strike prices
- **Pydantic v2 Models**: Complete type safety and validation for SGXTrade and SGXMatchResult
- **Performance Optimized**: O(N+M) algorithms with signature-based indexing for efficient matching
- **Rich CLI Interface**: Beautiful terminal output with detailed statistics, match tables, and tier-specific breakdowns
- **Iron Ore Focus**: Specialized for Singapore Exchange FE (Iron Ore) futures and options
- **Case-Insensitive Normalization**: Standardized buy/sell mapping with intelligent fallback logic matching ICE system architecture

## 🔧 SGX Match Core Components

### SGX Trade Model Architecture

The SGX module implements specialized models for Singapore Exchange trading:

- **SGXTrade Model**: Immutable trade objects with iron ore-specific fields (strike prices, put/call options)
- **SGXTradeSource Enum**: TRADER and EXCHANGE source identification
- **SGXMatchType Enum**: EXACT match type classification
- **Options Integration**: Native support for option contracts with strike prices and put/call indicators
- **Universal Fields**: Inherits broker_group_id and exch_clearing_acct_id validation from base architecture

### SGX Normalization System

The SGX normalizer focuses on Singapore Exchange data standardization with case-insensitive architecture:

- **Product Mappings**: FE (Iron Ore), PMX (Palm Oil), CAPE (Capesize), SMX (Steel Making), M65 (Iron Ore 65%)
- **Contract Month Patterns**: Aug25, Sep25, Oct25, etc. standardization with regex pattern matching
- **Buy/Sell Normalization**: Case-insensitive B/S indicator standardization with intelligent fallback logic
- **Direct Column Mapping**: Works directly with CSV column names (no field mapping layer)
- **JSON Configuration**: All mappings stored in `normalizer_config.json` with cleaned, meaningful variations only
- **Consistent Architecture**: Matches ICE normalization patterns for unified system behavior

### SGX CSV Integration

The SGX CSV loader processes Singapore Exchange data files:

- **Real Data Processing**: Loads 46 trader trades and 367 exchange trades from sample data
- **Automatic Normalization**: All fields normalized during loading via SGXTradeNormalizer
- **Type Safety**: Proper pandas DataFrame type handling
- **Error Handling**: Graceful handling of malformed data and missing fields
- **Direct CSV Access**: Works with actual CSV column names without field mapping complexity

### SGX Multi-Rule Matching System

The SGX system implements a 3-rule sequential matching approach:

#### Rule 1: Exact Matcher

- **7-Field Matching**: product_name, contract_month, quantity_units, price, buy_sell + universal fields
- **Signature Indexing**: O(1) lookup performance using tuple signatures
- **Universal Validation**: Inherits broker_group_id and exch_clearing_acct_id validation
- **100% Confidence**: High confidence matching for exact field alignment
- **Options Aware**: Handles both futures and options contracts seamlessly

#### Rule 2: Spread Matcher

- **Calendar Spread Detection**: Matches trader spread pairs against exchange spread pairs
- **Price Validation**: Validates spread price calculations between contract months
- **2-to-2 Matching**: Two trader trades match against two exchange trades
- **95% Confidence**: High confidence for spread position matching

#### Rule 3: Product Spread Matcher (3-Tier System)

- **Tier 1 (95%)**: PS required - Trader spread pairs with "PS" indicator vs exchange pairs
- **Tier 2 (92%)**: No PS required - Identical spread price pattern without PS indicator
- **Tier 3 (90%)**: Hyphenated exchange spread - Single hyphenated exchange trade vs trader pair
- **Configuration-Driven**: Uses tier-based confidence adjustment system
- **Product Cross-Matching**: Handles different products (M65, FE) in spread relationships

---

_End of SGX Match Module specific documentation_

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
    processing_order: List[int] = Field(default=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

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

Both ICE and SGX modules demonstrate the established architectural patterns for building matching systems. Future matching modules should follow the same modular structure:

**Required Folders:**

- `models/`: Pydantic data models (trade, match_result)
- `matchers/`: Rule implementations with base_matcher inheritance
- `normalizers/`: Data normalization and standardization
- `loaders/`: CSV data loading with normalization integration
- `config/`: Configuration management and JSON settings
- `core/`: Pool management and system infrastructure
- `cli/`: Rich terminal interface and display
- `data/`: Sample data sets for testing
- `docs/`: Rule specifications and documentation

**Architecture Benefits:**

- **Separation of Concerns**: Each module has a single, clear responsibility
- **Inheritance Patterns**: Base classes provide universal field validation
- **Configuration-Driven**: JSON files for product mappings and field configurations
- **Type Safety**: Pydantic v2 models throughout
- **Performance**: Optimized algorithms with indexing strategies

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
