# CLAUDE.md

This file provides comprehensive guidance to Claude Code when working with this **Reconciliation Engine** project.

## 🎯 Project Overview

This is a **Reconciliation Engine** that contains multiple specialized matching systems:

- **Unified Reconciliation System** (`src/unified_recon/`) - Centralized data routing system that groups trades by exchange and routes to appropriate matching systems
- **ICE Trade Matching System** (`src/ice_match/`) - Energy derivatives matching with 13 sequential rules
- **SGX Trade Matching System** (`src/sgx_match/`) - Singapore Exchange iron ore futures matching with 3 sequential rules
- **CME Trade Matching System** (`src/cme_match/`) - Chicago Mercantile Exchange futures matching with 1 exact matching rule
- **EEX Trade Matching System** (`src/eex_match/`) - European Energy Exchange matching with 1 exact matching rule
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

### CME Match Module Summary

The CME matching system processes Chicago Mercantile Exchange futures trades using a single-rule exact matching approach:

- **Rule 1**: Exact matching on 7 fields (product, contract month, quantity lots, price, buy/sell, + universal fields)
- **Quantity Lots Focus**: Designed specifically around `quantitylots` - the standard unit for CME futures contracts
- **Futures Focus**: Specialized for commodity futures (corn, soybeans, wheat, LTH, etc.) and index futures (ES, NQ, YM)
- **Single Rule Architecture**: Only exact matching implemented, focusing on high-confidence matches (100%)
- **Universal Field Validation**: Inherits broker group and clearing account validation from base architecture
- **Lot-Based Trading**: CME-specific design around lot-based contract specifications

### EEX Match Module Summary

The EEX matching system processes European Energy Exchange trades using a single-rule exact matching approach:

- **Rule 1**: Exact matching on 7 fields (product, contract month, quantity unit, price, buy/sell, + universal fields)
- **CAPE Focus**: Specialized for Capesize freight derivatives and related products
- **Trade Factory Pattern**: Uses SGX-style trade factory for CSV, DataFrame, and JSON data ingestion
- **Single Rule Architecture**: Only exact matching implemented, focusing on high-confidence matches (100%)
- **Universal Field Validation**: Inherits broker group and clearing account validation from base architecture
- **Clean Implementation**: Follows SGX pattern with no unnecessary loaders folder

### Unified Reconciliation System Summary

The unified reconciliation system acts as a centralized data router and aggregator:

- **Data Routing**: Groups trades by `exchangegroupid` and routes to appropriate systems (Group 1 → ICE, Group 2 → SGX, Group 3 → CME, Group 4 → ICE, Group 5 → EEX)
- **System Integration**: Calls individual matching systems with filtered data while maintaining system isolation
- **Result Aggregation**: Combines results from multiple systems with unified reporting
- **JSON API Support**: Processes JSON payloads using trade factories with `--json-file` flag
- **DataFrame Output**: Creates standardized output with matchId, traderTradeIds, exchangeTradeIds, status, remarks, confidence columns
- **Rich Display**: Beautiful terminal output with detailed breakdowns and DataFrame tables

### Key Features

- **Universal Data Normalization**: TradeNormalizer standardizes product names, contract months, buy/sell indicators, and unit conversions
- **Configuration Management**: Centralized settings with rule confidence levels, tolerances, and conversion ratios
- **Sequential Rule Processing**: Implements rules in priority order (exact matches first) with non-duplication
- **Rich CLI Interface**: Beautiful terminal output with progress indicators and detailed results
- **Product-Specific Unit Conversion**: MT→BBL conversion with product-specific ratios (6.35, 8.9, 7.0 default)
- **Pydantic v2 Data Models**: Strict validation and type safety for all trade data
- **Complete Type Safety**: Full mypy compliance with pandas-stubs integration

## 🏗️ Project Architecture

### Standard Module Structure

All matching modules follow this consistent architecture:

```text
src/{exchange}_match/
├── main.py                 # Entry point with CLI
├── models/                 # Pydantic v2 data models
│   ├── trade.py           # Trade model with validation
│   └── match_result.py    # MatchResult model
├── normalizers/           # Data standardization
├── matchers/              # Rule implementations
│   ├── base_matcher.py   # Universal field validation
│   └── [rule_matchers]   # Exchange-specific rules
├── core/                  # System infrastructure
│   ├── trade_factory.py  # CSV/DataFrame/JSON ingestion (SGX/CME/EEX)
│   └── pool.py           # Non-duplication management
├── config/               # Configuration
├── cli/                  # Rich terminal interface
├── data/                 # Sample data sets
└── docs/rules.md         # Rule specifications
```

**Module-Specific Differences:**
- **ICE**: Has 13 matchers, `utils/` folder with conversion helpers, uses csv_loader
- **SGX**: Has 3 matchers, includes options support in trade model
- **CME**: Single matcher, focuses on quantity_lots field
- **EEX**: Single matcher, CAPE freight derivatives focus
- **Unified**: No matchers, has `group_router.py` and `result_aggregator.py` for routing

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

**`utils/`** - **Utility Functions Layer** (ICE only)

- **trade_helpers.py**: Pure utility functions (extract products, parse months)
- **conversion_helpers.py**: MT↔BBL conversion with product-specific ratios
- **fly_helpers.py**: Butterfly spread pattern matching utilities

**`matchers/`** - **Business Logic Engine**

- **BaseMatcher**: Universal field validation shared by all matchers
- **Rule Implementations**: Exchange-specific matching rules (1-13 for ICE, 1-3 for SGX, 1 for CME/EEX)
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

### Development Commands

```bash
# Check linting
uv run ruff check .

# Fix linting issues automatically
uv run ruff check --fix .

# Type checking
uv run python -m mypy src/

# Centralized data routing with master data processing
uv run python -m src.unified_recon.main  # Shows all matches+unmatches
uv run python -m src.unified_recon.main --log-level DEBUG # Enable debug logging

# JSON payload routing (API simulation)
uv run python -m src.unified_recon.main --json-file src/json_input/ice_sample.json
uv run python -m src.unified_recon.main --json-file src/json_input/ice_sample.json --json-output

# Run individual match systems
uv run python -m src.ice_match.main
uv run python -m src.sgx_match.main
uv run python -m src.cme_match.main
uv run python -m src.eex_match.main

# Common options
--help
--log-level DEBUG
--no-unmatched
--show-rules
--json-file path/to/file.json
--json-output
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

## 📊 Module-Specific Features

### ICE Match Module Features

- **13 Sequential Rules**: From exact matching to aggregated product spread matching
- **Unit Conversion System**: Product-specific MT→BBL conversion ratios (Marine 6.35, naphtha 8.9, default 7.0)
- **Shared Methods**: `convert_mt_to_bbl_with_product_ratio()` and `validate_mt_to_bbl_quantity_match()` in `utils/conversion_helpers.py`
- **Fly Matching**: Butterfly spread trades with 3-leg validation
- **Zero-Price Spread Support**: Allows spreads where both legs have price = 0

_See `src/ice_match/docs/rules.md` for detailed rule specifications._

### SGX Match Module Features

- **3 Sequential Rules**: Exact, Spread, and Product Spread matching
- **3-Tier Product Spread System**: PS required (95%), no PS required (92%), hyphenated exchange spread (90%)
- **Iron Ore Focus**: Specialized for FE futures and options with strike prices and put/call support
- **Product Mappings**: FE, PMX, CAPE, SMX, M65 products

_See `src/sgx_match/docs/rules.md` for detailed rule specifications._

### CME Match Module Features

- **Single Rule**: Exact matching with 100% confidence
- **Quantity Lots Focus**: Designed around `quantitylots` - standard CME futures unit
- **Futures Products**: LTH, CORN, WHEAT, SOYBEANS, ES, NQ, YM
- **Uses Unified Data**: References `src/unified_recon/data/` folder

_See `src/cme_match/docs/rules.md` for detailed rule specifications._

### EEX Match Module Features

- **Single Rule**: Exact matching with 100% confidence
- **CAPE Specialization**: Capesize freight derivatives focus
- **Product Mappings**: CAPE, CAPE5TC, PMX4TC, SMX10TC
- **Contract Month Formats**: Handles both 25-Oct and Oct25 formats

_See `src/eex_match/docs/rules.md` for detailed rule specifications._

---

## 🏗️ Pydantic v2 Data Validation

All modules use Pydantic v2 models with:
- **Immutable Models**: `frozen=True` for thread safety
- **Type Validation**: Strict field validation with type hints
- **Universal Fields**: `broker_group_id` and `exch_clearing_acct_id` validated across all rules
- **Configuration Models**: Centralized settings with validation

## 🌐 Universal Fields Architecture

Universal fields (`brokergroupid` and `exchclearingacctid`) are validated across ALL matching rules via:
- **JSON Configuration**: Field mappings in `normalizer_config.json`
- **BaseMatcher Class**: Provides universal field validation to all matchers
- **Automatic Inheritance**: All matchers inherit universal validation without code changes

To add new universal fields, update the JSON configuration and Trade model - all matchers will automatically validate the new fields.

## 📁 File Organization Patterns

### Modular Architecture Template

All matching modules (ICE, SGX, CME) demonstrate the established architectural patterns for building matching systems. Future matching modules should follow the same modular structure:

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

## 🚨 Error Handling & Configuration

- **Custom Exceptions**: Domain-specific error classes with meaningful messages
- **Structured Logging**: Consistent logging with debug/info/warning/error levels
- **Configuration Management**: Pydantic settings with environment variable support
- **Context Managers**: Resource management for database transactions and file operations

---

