# CLAUDE.md

This file provides comprehensive guidance to Claude Code when working with this **Energy Trade Matching System** project.

## 🎯 Project Overview

This is an **Energy Trade Matching System** that matches trades between trader and exchange data sources using a sequential rule-based approach. The system implements exact matching (Rule 1), spread matching (Rule 2), crack matching (Rule 3), complex crack matching (Rule 4), product spread matching (Rule 5), aggregation matching (Rule 6), aggregated complex crack matching (Rule 7), and aggregated spread matching (Rule 8) with plans for 3 additional sophisticated matching rules including time-based scenarios.

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
├── matchers/            # Matching rule implementations
│   ├── exact_matcher.py # Rule 1: Exact matching (6-field comparison)
│   ├── spread_matcher.py # Rule 2: Spread matching (contract month spreads)
│   ├── crack_matcher.py # Rule 3: Crack matching with unit conversion (optimized)
│   ├── complex_crack_matcher.py # Rule 4: Complex crack matching (2-leg: base + brent swap)
│   ├── product_spread_matcher.py # Rule 5: Product spread matching (hyphenated products)
│   ├── aggregation_matcher.py # Rule 6: Aggregation matching (many↔one trade grouping)
│   ├── aggregated_complex_crack_matcher.py # Rule 7: Aggregated complex crack matching (2-leg + aggregation)
│   └── aggregated_spread_matcher.py # Rule 8: Aggregated spread matching (2-phase: aggregation + spread)
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
    └── rules.md        # Complete 11-rule specification
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
- **Rule Management**: Confidence levels and processing order for all 8 implemented rules
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
- **product_spread_matcher.py**: Rule 5 - Product spread matching with hyphenated product parsing
- **aggregation_matcher.py**: Rule 6 - Bidirectional aggregation matching with exact quantity sum validation
- **aggregated_complex_crack_matcher.py**: Rule 7 - Aggregated complex crack matching with inherited ComplexCrackMatcher logic and enhanced tolerances
- **aggregated_spread_matcher.py**: Rule 8 - Two-phase aggregated spread matching with exchange trade aggregation and spread logic
- **Extensible Design**: Easy to add Rules 9-11 following established patterns

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
- **Product-Specific Unit Conversion**: Handles MT→BBL conversions with product-specific ratios from JSON configuration
- **Adjacent Month Detection**: Identifies consecutive contract months for Rule 6
- **Shared Conversion Methods**: Provides reusable MT→BBL conversion logic for Rules 3 and 4

### SpreadMatcher (Rule 2)

The SpreadMatcher implements sophisticated contract month spread matching with high efficiency:

- **Intelligent Grouping**: Pre-groups trades by (product, quantity, broker) to minimize search space
- **Unit-Aware Grouping**: Uses product-specific unit defaults for quantity comparison (BBL for brent swap, MT for others)
- **Spread Detection**: Identifies spread indicators (`spread="S"` or `price=0`) in trader data
- **Price Validation**: Calculates and validates spread price differentials between exchange legs
- **Contract Month Matching**: Ensures trader and exchange contract months align exactly
- **Direction Validation**: Verifies B/S directions match per contract month
- **Non-Duplication**: Triple validation prevents any trade from being matched multiple times
- **Performance**: O(n+m) grouping plus small combination checks vs. O(n²×m²) brute force

### CrackMatcher (Rule 3) - **MT→BBL Conversion Optimized**

The CrackMatcher implements crack spread matching with product-specific unit conversion and advanced optimization:

- **Indexing Strategy**: Optimized from O(N\*M) to O(N+M) using dictionary-based lookups
- **Product-Specific Conversion**: Uses configurable ratios (6.35 for marine 0.5%/380cst, 8.9 for naphtha, 7.0 default)
- **One-Way Conversion**: Pure MT→BBL conversion scenarios with BBL tolerance only (±100 BBL)
- **Unit Logic**: Trader data defaults to MT, exchange data uses unit column for determination
- **Shared Conversion Methods**: Uses reusable conversion logic from TradeNormalizer
- **Match Key Optimization**: Groups by (product, contract, price, broker, buy/sell) for O(1) lookups
- **Duplicate Prevention**: Triple validation with pool manager integration prevents any duplicate matches
- **Performance**: Scales linearly instead of quadratically with large datasets
- **Real-World Testing**: Successfully processes trades with accurate product-specific conversion

### ComplexCrackMatcher (Rule 4) - **2-Leg Crack Matching with Shared Conversion**

The ComplexCrackMatcher implements sophisticated 2-leg crack trade matching where a single crack trade in trader data corresponds to a base product + brent swap combination in exchange data:

- **Base Product Extraction**: Intelligently extracts base product from crack names (e.g., "marine 0.5% crack" → "marine 0.5%")
- **2-Leg Validation**: Matches single crack trade against base product + brent swap pairs in exchange data
- **B/S Direction Logic**: Enforces direction rules: Sell Crack = Sell Base + Buy Brent; Buy Crack = Buy Base + Sell Brent
- **Shared Conversion Logic**: Uses same MT→BBL conversion methods as Rule 3 for consistency
- **Unit-Specific Tolerances**: ±50 MT for crack vs base, ±100 BBL for crack vs brent swap
- **Product-Specific Price Formula**: Verifies (base_price ÷ product_ratio) - brent_price = crack_price
- **Pool Integration**: Uses UnmatchedPoolManager for proper trade removal and non-duplication
- **Encapsulated Architecture**: Clean integration using `pool_manager.record_match()` method
- **Configuration-Driven**: Leverages ConfigManager for tolerances and confidence levels (80% default)
- **Real-World Validation**: Successfully matches complex crack scenarios with accurate conversions

### ProductSpreadMatcher (Rule 5) - **Hyphenated Product Matching**

The ProductSpreadMatcher implements sophisticated product spread matching where exchange data shows hyphenated products and trader data shows separate component trades:

- **Hyphenated Product Parsing**: Intelligently splits hyphenated products (e.g., "marine 0.5%-380cst" → "marine 0.5%" + "380cst")
- **Price=0 Pattern Detection**: Identifies multi-leg trader trades using the price=0 pattern similar to spread matching
- **Component Trade Matching**: Matches separate trader trades for each component product against exchange hyphenated product
- **Direction Logic Validation**: Enforces B/S direction rules: Sell spread = Sell first + Buy second component
- **Exact Price Matching**: Validates first_component_price - second_component_price = exchange_spread_price (no tolerance)
- **Pool Integration**: Uses UnmatchedPoolManager for proper trade removal and non-duplication
- **Configuration-Driven**: Leverages ConfigManager for confidence levels (75% default)
- **Real-World Validation**: Successfully matches T_0025 + T_0026 with E_0026 (marine 0.5%-380cst)

### AggregatedSpreadMatcher (Rule 8) - **Two-Phase Spread Matching with Exchange Aggregation**

The AggregatedSpreadMatcher implements sophisticated two-phase spread matching where trader spread patterns correspond to multiple disaggregated exchange trades that must first be aggregated:

- **Two-Phase Algorithm**: Phase 1 aggregates exchange trades by matching characteristics, Phase 2 applies standard spread matching logic
- **Spread Pattern Recognition**: Identifies trader spread patterns using price/0.00 indicators with opposite B/S directions and different contract months
- **Exchange Trade Aggregation**: Groups exchange trades by (product, contract_month, price, buy_sell, broker) for precise aggregation
- **Universal Field Integration**: Uses `validate_universal_fields()`, `get_universal_matched_fields()`, and dynamic field access for consistency
- **Perfect Matching Requirements**: Exact quantity sum validation and precise price differential calculation with no tolerances
- **Bidirectional Processing**: Handles complex scenarios where exchange data is disaggregated but trader data shows consolidated spread positions
- **Pool Integration**: Uses UnmatchedPoolManager for proper trade removal and non-duplication across all component trades
- **Configuration-Driven**: Leverages ConfigManager for confidence levels (70%) and universal field mappings
- **Real-World Testing**: Successfully matches complex scenarios like T_0032 + T_0033 spread against aggregated E_0055 + E_0056 + additional trades

### ConfigManager

Centralized configuration management with Pydantic validation:

- **Rule Confidence Levels**: Predefined confidence percentages for Rules 1-8
- **Enhanced Tolerance Settings**: Realistic tolerances for complex scenarios (±500 BBL, ±150 MT)
- **Product-Specific Ratios**: JSON-configured conversion ratios for different products
- **Unit Default Configuration**: Product-specific unit defaults (brent swap = BBL, others = MT)
- **Processing Order**: Sequential rule execution order
- **Output Settings**: Display options and logging configuration

### Shared Unit Conversion System

The system implements a shared, product-specific unit conversion architecture:

- **Product-Specific Ratios**: Marine 0.5%/380cst crack use 6.35, naphtha japan/nwe crack use 8.9, default 7.0
- **One-Way Conversion**: Always MT→BBL (trader MT data converts to compare with exchange BBL)
- **Unit Logic**: Trader data defaults to MT, exchange data uses unit column
- **Exact Matching**: Product names are pre-normalized, allowing exact ratio lookup instead of "contains" matching
- **Shared Methods**: `convert_mt_to_bbl_with_product_ratio()` and `validate_mt_to_bbl_quantity_match()`
- **Rules 3 & 4 Integration**: Both CrackMatcher and ComplexCrackMatcher use identical conversion logic
- **JSON Configuration**: Conversion ratios stored in `normalizer_config.json` for maintainability

### CSV Integration

The CSV loader now uses the normalizer for consistent data processing:

- **Automatic Normalization**: All fields normalized during loading
- **Type Safety**: Proper pandas DataFrame type handling
- **Error Handling**: Graceful handling of malformed data
- **Spread Detection**: Identifies spread trades based on tradeid presence

### Universal Matching Fields System

The system implements a sophisticated universal field matching architecture that ensures consistency across all matching rules:

#### Architecture Overview

- **JSON-Driven Configuration**: All universal fields are defined in `normalizer_config.json` under `universal_matching_fields`
- **BaseMatcher Inheritance**: All matchers inherit from `BaseMatcher` class providing universal field capabilities
- **Dynamic Field Access**: Uses `getattr()` with configurable field mappings for flexible field access
- **Single Source of Truth**: ConfigManager provides centralized access to universal field configuration
- **Type-Safe Implementation**: Full mypy compliance with proper type annotations

#### Current Universal Fields

```json
"universal_matching_fields": {
  "required_fields": ["brokergroupid", "exchclearingacctid"],
  "field_mappings": {
    "brokergroupid": "broker_group_id",
    "exchclearingacctid": "exch_clearing_acct_id"
  }
}
```

**Universal Field Requirements**:
- **brokergroupid** → `broker_group_id`: Broker group identifier that must match exactly
- **exchclearingacctid** → `exch_clearing_acct_id`: Exchange clearing account identifier that must match exactly

#### Adding New Universal Fields

To add new universal fields that apply to ALL matching rules:

1. **Update JSON Configuration**: Add field to `required_fields` array in `normalizer_config.json`
2. **Add Field Mapping**: Map config field name to Trade model attribute in `field_mappings`
3. **Ensure Trade Model**: Verify the Trade model has the corresponding attribute
4. **Zero Code Changes**: No matcher code changes required - all matchers inherit universal capabilities

Example adding `traderid` field:
```json
"required_fields": ["brokergroupid", "exchclearingacctid", "traderid"],
"field_mappings": {
  "brokergroupid": "broker_group_id", 
  "exchclearingacctid": "exch_clearing_acct_id",
  "traderid": "trader_id"
}
```

#### Implementation Architecture

**BaseMatcher Class**:
- `create_universal_signature()`: Creates matching signatures with universal fields
- `validate_universal_fields()`: Validates universal field matches
- `get_universal_matched_fields()`: Returns complete field lists for match results
- `_get_trade_field_value()`: Dynamic field value extraction using mappings

**ConfigManager Integration**:
- `get_universal_matching_fields()`: Returns required universal field list
- `get_universal_field_mappings()`: Returns config-to-attribute field mappings
- Cached JSON loading for performance optimization

**Benefits**:
- **Maintainability**: Single point to add/modify universal requirements
- **Consistency**: Guaranteed application across all matching rules
- **Performance**: Cached configuration loading prevents disk I/O on each request
- **Extensibility**: Easy to add new universal fields without code changes
- **Type Safety**: Full compile-time validation with mypy

#### Rule Integration

All implemented matchers automatically include universal field validation:
- **Rule 1 (ExactMatcher)**: Exact universal field matching
- **Rule 2 (SpreadMatcher)**: Universal fields in spread grouping
- **Rule 3 (CrackMatcher)**: Universal fields in crack matching
- **Rule 4 (ComplexCrackMatcher)**: Universal fields in 2-leg matching  
- **Rule 5 (ProductSpreadMatcher)**: Universal fields in component matching
- **Rule 6 (AggregationMatcher)**: Universal fields in aggregation grouping
- **Rule 7 (AggregatedComplexCrackMatcher)**: Universal fields in complex aggregation
- **Rule 8 (AggregatedSpreadMatcher)**: Universal fields in aggregated spread matching

Universal fields are automatically included in:
- Matching signatures for trade grouping
- Validation logic for match verification  
- Match result metadata for audit trails
- Rule information for documentation

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

- **Rule 1 (Exact Matching)**: 20 exact matches found in sample data with proper product spread preservation
- **Rule 2 (Spread Matching)**: 4 spread matches found using intelligent grouped approach with 95% confidence
- **Rule 3 (Crack Matching)**: 0 crack matches in current sample data (functionality verified with unit conversion)
- **Rule 4 (Complex Crack Matching)**: 1 complex crack match found with enhanced BBL tolerance (±500 BBL) for real-world unit conversion scenarios
- **Rule 5 (Product Spread Matching)**: 2 product spread matches found using hyphenated product parsing with 75% confidence
- **Rule 6 (Aggregation Matching)**: 3 aggregation matches found using bidirectional many↔one trade grouping with 72% confidence
- **Rule 7 (Aggregated Complex Crack Matching)**: 1 aggregated complex crack match found with enhanced tolerances (±150 MT, ±500 BBL) for sophisticated aggregation scenarios
- **Rule 8 (Aggregated Spread Matching)**: 1 aggregated spread match found using two-phase matching (aggregation + spread logic) with 70% confidence
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

- **Rules 9-11**: Crack roll matching, cross-month decomposition, and complex product spread decomposition scenarios
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

## 🏆 Rule 5 Implementation Summary

**Successfully Completed**: Rule 5 - Product Spread Matching (Hyphenated Products)

### Implementation Highlights

- **✅ Complete Integration**: Fully integrated into the matching pipeline following Rules 1-4
- **✅ Configuration Management**: Uses ConfigManager for confidence levels (75%)
- **✅ Pool Management**: Proper encapsulation using `pool_manager.record_match()` method
- **✅ Multi-Leg Display**: CLI shows both trader trades (component products) correctly
- **✅ Type Safety**: Full MyPy compliance with proper type annotations
- **✅ Real-World Testing**: Successfully matches T_0025 + T_0026 with E_0026 (marine 0.5%-380cst)

### Architecture Improvements Made

- **Enhanced Pattern Detection**: Implemented price=0 pattern detection for multi-leg trader trades
- **Hyphenated Product Parsing**: Intelligent splitting of exchange products into components
- **Direction Logic Validation**: Enforced proper B/S direction rules for product spreads
- **Exact Price Matching**: Removed price tolerance requirement for precise matching
- **Import Organization**: Updated `__init__.py` and `main.py` with proper imports and integration

### Key Technical Features

- **Hyphenated Product Parsing**: Intelligent parsing of exchange product names (e.g., "marine 0.5%-380cst" → ("marine 0.5%", "380cst"))
- **Price=0 Pattern Detection**: Identifies multi-leg trader trades using the same pattern as spread matching
- **Component Trade Matching**: Matches separate trader trades for each component product
- **B/S Direction Logic**: Enforces "Sell Product Spread = Sell First Component + Buy Second Component"
- **Exact Price Validation**: Validates first_component_price - second_component_price = exchange_spread_price (no tolerance)
- **Non-Duplication**: Triple validation ensures trades only match once across all rules

### Performance Results

- **2 Product Spread Matches Found**: Successfully identified and matched hyphenated products
- **Improved Match Rate**: Overall system match rate increased from 65.1% to 69.9%
- **Trader Match Rate**: Improved from 77.5% to 87.5%
- **Processing Time**: Maintains sub-100ms performance for 83 trades
- **Zero False Positives**: All matches validated through multiple criteria

## 🏆 Rule 6 Implementation Summary

**Successfully Completed**: Rule 6 - Aggregation Matching (Bidirectional Many↔One Trade Grouping)

### Implementation Highlights

- **✅ Complete Integration**: Fully integrated into the matching pipeline following Rules 1-5
- **✅ Configuration Management**: Uses ConfigManager for confidence levels (72%)
- **✅ Pool Management**: Proper encapsulation using `pool_manager.record_match()` method
- **✅ Multi-Leg Display**: CLI shows all aggregated trades (primary + additional) correctly
- **✅ Type Safety**: Full MyPy compliance with proper type annotations
- **✅ Real-World Testing**: Successfully matches 3 aggregation scenarios (AGG_B1BF5E8F, AGG_A8194C30, AGG_D5C1C579)

### Architecture Improvements Made

- **Bidirectional Matching**: Implements both trader→exchange and exchange→trader aggregation scenarios
- **Intelligent Grouping**: Groups trades by all fields except quantity for O(N+M) performance
- **Exact Sum Validation**: Enforces perfect quantity sum matching with no tolerance
- **Enhanced CLI Display**: Added special handling for aggregation matches showing all component trades
- **Import Organization**: Updated `__init__.py` and `main.py` with proper imports and integration

### Key Technical Features

- **Aggregation Key Grouping**: Groups trades by (product, contract, price, broker, B/S) excluding quantity
- **Bidirectional Scenarios**: Handles both many→one and one→many aggregation patterns
- **Perfect Sum Validation**: Validates sum(many_trades.quantity) == one_trade.quantity exactly
- **Direction Logic**: Maintains proper B/S direction consistency across all component trades
- **Non-Duplication**: Triple validation ensures trades only match once across all rules
- **Performance Optimization**: O(N+M) indexing strategy for scalable aggregation detection

### Performance Results

- **3 Aggregation Matches Found**: Successfully identified and matched aggregated trade scenarios
- **Improved Match Rate**: Overall system match rate increased from 69.9% to 77.1%
- **Trader Match Rate**: Improved from 87.5% to 95.0%
- **Exchange Match Rate**: Improved from 76.7% to 90.7%
- **Processing Time**: Maintains excellent performance (~0.05 seconds for 83 trades)
- **Zero False Positives**: All matches validated through exact sum and field matching criteria

## 🏆 Rule 7 Implementation Summary

**Successfully Completed**: Rule 7 - Aggregated Complex Crack Matching (2-Leg with Split Base Products)

### Implementation Highlights

- **✅ Complete Integration**: Fully integrated into the matching pipeline following Rules 1-6
- **✅ Inheritance Architecture**: Inherits from ComplexCrackMatcher for code reusability and consistency
- **✅ Enhanced Tolerances**: Uses ±150 MT and ±500 BBL tolerances for complex aggregation scenarios
- **✅ Configuration Management**: Uses ConfigManager for confidence levels (65%) and shared BBL tolerance
- **✅ Pool Management**: Proper encapsulation using `pool_manager.record_match()` method
- **✅ Multi-Leg Display**: CLI shows aggregated base products + brent swap correctly
- **✅ Type Safety**: Full MyPy compliance with proper type annotations
- **✅ Real-World Testing**: Successfully matches T_0000 with aggregated E_0000 + E_0001 + E_0002

### Architecture Improvements Made

- **Code Reusability**: Inherits all complex crack logic from Rule 4 while adding aggregation capability
- **Enhanced Tolerances**: Increased MT tolerance to ±150 MT and BBL tolerance to ±500 BBL for real-world scenarios
- **Shared Configuration**: Uses ConfigManager's `get_crack_tolerance_bbl()` for consistent tolerance management
- **Aggregation Logic**: Implements base product aggregation before applying complex crack validation
- **Import Organization**: Updated `__init__.py` and `main.py` with proper imports and integration

### Key Technical Features

- **Base Product Aggregation**: Groups multiple base product trades with identical characteristics (price, B/S, contract, broker)
- **Inherited Validation**: Uses ComplexCrackMatcher's price calculation and B/S direction logic
- **Enhanced Unit Conversion**: Handles MT→BBL conversion with realistic tolerances for aggregated quantities
- **Fallback Processing**: Only processes after simpler complex crack matching fails
- **Enhanced Tolerances**: ±150 MT for aggregation precision, ±500 BBL for unit conversion differences
- **Non-Duplication**: Triple validation ensures trades only match once across all rules

### Performance Results

- **1 Aggregated Complex Crack Match Found**: Successfully identified and matched the most complex trading scenario
- **Perfect Match Rate**: Achieved 100% match rate (all trades matched) in test scenario
- **Processing Time**: Maintains excellent performance with complex aggregation logic
- **Zero False Positives**: All matches validated through multiple aggregation and crack validation criteria
- **Real-World Validation**: Handles realistic unit conversion differences (475 BBL difference within ±500 BBL tolerance)

## 🏆 Rule 8 Implementation Summary

**Successfully Completed**: Rule 8 - Aggregated Spread Matching (Two-Phase: Aggregation + Spread Logic)

### Implementation Highlights

- **✅ Complete Integration**: Fully integrated into the matching pipeline following Rules 1-7
- **✅ Two-Phase Algorithm**: Phase 1 aggregates exchange trades, Phase 2 applies spread matching logic
- **✅ Universal Fields Integration**: Proper use of `validate_universal_fields()` and `get_universal_matched_fields()`
- **✅ Configuration Management**: Uses ConfigManager for confidence levels (70%) and centralized settings
- **✅ Pool Management**: Proper encapsulation using `pool_manager.record_match()` method
- **✅ Multi-Leg Display**: CLI shows both trader spread legs and all aggregated exchange trades correctly
- **✅ Type Safety**: Full MyPy compliance with proper type annotations
- **✅ Real-World Testing**: Successfully matches T_0032 + T_0033 with aggregated E_0055 + E_0056 + additional exchange trades

### Architecture Improvements Made

- **Two-Phase Processing**: Implements aggregation of exchange trades followed by spread matching logic
- **Universal Field Compliance**: Uses BaseMatcher's universal field validation throughout the matching process
- **Exact Matching Logic**: No price tolerances - exact price differential calculation required
- **Enhanced Pattern Recognition**: Identifies price/0.00 spread patterns with opposite B/S directions
- **Aggregation Validation**: Perfect quantity sum matching with no tolerance for precision
- **Import Organization**: Updated `__init__.py` and `main.py` with proper imports and integration

### Key Technical Features

- **Spread Pattern Detection**: Identifies trader spread patterns (price vs 0.00) with opposite B/S directions and different contract months
- **Exchange Trade Aggregation**: Groups exchange trades by (product, contract, price, B/S, broker) for aggregation
- **Two-Phase Validation**: Universal field validation in Phase 1, exact spread calculation validation in Phase 2
- **Perfect Sum Matching**: Validates aggregated exchange quantities match trader spread quantities exactly
- **Price Differential Logic**: Enforces first_contract_price - second_contract_price = spread_price exactly
- **Non-Duplication**: Triple validation ensures trades only match once across all rules
- **Dynamic Field Access**: Uses `getattr()` with configurable field mappings for flexible universal field handling

### Performance Results

- **1 Aggregated Spread Match Found**: Successfully identified and matched complex two-phase spread scenario
- **Excellent Processing Speed**: Maintains sub-100ms performance with complex aggregation logic
- **Zero False Positives**: All matches validated through multiple aggregation and spread validation criteria
- **Real-World Validation**: Handles actual disaggregated exchange data requiring aggregation before spread matching
- **Configuration-Driven**: 70% confidence level appropriate for medium-complexity two-phase matching

### Universal Fields Implementation

- **Trader Grouping**: Uses `get_universal_matching_fields()` and `get_universal_field_mappings()` for consistent grouping
- **Validation Logic**: Uses `validate_universal_fields()` in `_is_valid_spread_pair()` for universal field validation
- **Match Results**: Uses `get_universal_matched_fields()` for comprehensive matched field reporting
- **Dynamic Access**: Uses `getattr()` with field mappings for flexible universal field value extraction
- **Code Quality**: Removed unused imports, maintained type safety, and followed established patterns

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
