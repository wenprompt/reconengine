# GEMINI.md

This file provides comprehensive guidance to Gemini when working with this **Reconciliation Engine** project.

## 🎯 Project Overview

This is a **Reconciliation Engine** that contains multiple specialized matching systems, orchestrated by a central routing system.

- **Unified Reconciliation System** (`src/unified_recon/`): The main entry point. It acts as a centralized data router that groups trades by `exchangegroupid` and routes them to the appropriate matching system (e.g., Group 1 → ICE, Group 2 → SGX). It then aggregates the results from all systems for unified reporting.

- **ICE Trade Matching System** (`src/ice_match/`): A specialized subsystem for matching energy derivatives. It uses a sequential, 12-rule engine to find complex matches.

- **SGX Trade Matching System** (`src/sgx_match/`): A specialized subsystem for matching Singapore Exchange iron ore futures using a simple exact matching rule.

### Key Features

- **Centralized Routing**: The `UnifiedTradeRouter` loads master data files, validates them, and routes trades to the correct subsystem based on exchange group.
- **Modular Matching Systems**: Each matching system (ICE, SGX) is self-contained with its own rules, models, and configuration, allowing for independent operation and maintenance.
- **Sequential Rule Processing**: The ICE system implements 12 rules in priority order (exact matches first) with non-duplication to handle complex trade scenarios.
- **Universal Data Normalization**: Each subsystem's `TradeNormalizer` standardizes product names, contract months, buy/sell indicators, and unit conversions.
- **Universal Matching Fields**: A data-driven system ensures specified fields (e.g., `brokergroupid`) must match across ALL matching rules within a subsystem.
- **Rich CLI Interface**: Beautiful terminal output with progress indicators and detailed, aggregated results.
- **Pydantic v2 Data Models**: Strict validation and type safety for all trade data.
- **Complete Type Safety**: Full mypy compliance with pandas-stubs integration.

## 🌊 Data Processing Flow

The system follows a clear, sequential data processing pipeline orchestrated by the **Unified Reconciliation System**:

1.  **Load & Validate**: The `UnifiedTradeRouter` loads the master `sourceTraders.csv` and `sourceExchange.csv` files from `src/unified_recon/data/`. It performs initial validation to ensure data integrity and the presence of `exchangegroupid`.
2.  **Group & Route**: Trades are grouped by their `exchangegroupid`. Each group of trades is routed to its designated matching system as defined in `unified_config.json`.
3.  **Subsystem Processing**: Each matching system (e.g., `ice_match`) executes its own internal pipeline:
    a.  **Load**: The subsystem-specific loader (e.g., `CSVTradeLoader` for ICE) loads the filtered data.
    b.  **Normalize**: The subsystem's `TradeNormalizer` cleans and standardizes critical fields.
    c.  **Instantiate**: Validated and normalized data is used to create immutable `Trade` objects.
    d.  **Pool**: All `Trade` objects are placed into a `UnmatchedPoolManager` to track state.
    e.  **Match**: A sequence of `Matcher` modules are run in order of confidence. For the ICE system, this includes 12 rules.
4.  **Aggregate Results**: The `ResultAggregator` collects the results (matches, statistics) from each subsystem that was run.
5.  **Display**: The `UnifiedDisplay` presents the aggregated results, including a system-wide summary and detailed breakdowns for each exchange group.

### ICE Matcher Rule Sequence

The `ice_match` subsystem processes trades with the following 12 rules in order:
- **Rule 1 (ExactMatcher)**: Finds exact matches.
- **Rule 2 (SpreadMatcher)**: Finds 2-leg calendar spread matches.
- **Rule 3 (CrackMatcher)**: Finds 1-to-1 crack spread matches with unit conversion.
- **Rule 4 (ComplexCrackMatcher)**: Finds 2-leg complex crack matches.
- **Rule 5 (ProductSpreadMatcher)**: Matches product combination spreads.
- **Rule 6 (AggregationMatcher)**: Matches trades that are split or combined.
- **Rule 7 (AggregatedComplexCrackMatcher)**: Finds complex crack matches with aggregated legs.
- **Rule 8 (AggregatedSpreadMatcher)**: Finds spread matches with aggregated legs.
- **Rule 9 (MultilegSpreadMatcher)**: Finds complex multi-leg spreads with internal netting.
- **Rule 10 (AggregatedCrackMatcher)**: Finds crack matches with aggregation.
- **Rule 11 (ComplexCrackRollMatcher)**: Finds calendar spreads of complex crack positions.
- **Rule 12 (AggregatedProductSpreadMatcher)**: Finds product spreads with aggregation.

## 🏗️ Project Architecture

### Unified Reconciliation System
```
src/unified_recon/
├── main.py                 # Main entry point for unified reconciliation
├── config/
│   └── unified_config.json # System mappings and routing configuration
├── core/
│   ├── group_router.py    # Data loading, validation, and routing by exchangegroupid
│   └── result_aggregator.py # Cross-system result aggregation and statistics
├── utils/
│   └── data_validator.py  # CSV validation and exchange group detection
├── cli/
│   └── unified_display.py # Unified reporting and DataFrame display
└── data/
    ├── sourceTraders.csv   # Master trader data
    └── sourceExchange.csv  # Master exchange data
```

### ICE Match Module
```
src/ice_match/
├── main.py                 # Main application entry point for standalone ICE matching
├── models/
│   ├── trade.py           # Core `Trade` model for ICE.
│   └── match_result.py    # `MatchResult` model for storing match details.
├── loaders/
│   └── csv_loader.py     # Handles loading raw data from CSV files.
├── normalizers/
│   └── trade_normalizer.py # Cleans and standardizes ICE trade data.
├── matchers/
│   ├── exact_matcher.py   # Rule 1: Exact Matching.
│   ├── spread_matcher.py  # Rule 2: Spread Matching.
│   ├── crack_matcher.py   # Rule 3: Crack Matching.
│   ├── complex_crack_matcher.py # Rule 4: Complex Crack Matching.
│   ├── product_spread_matcher.py # Rule 5: Product Spread Matching.
│   ├── aggregation_matcher.py # Rule 6: Aggregation Matching.
│   ├── aggregated_complex_crack_matcher.py # Rule 7: Aggregated Complex Crack Matching.
│   ├── aggregated_spread_matcher.py # Rule 8: Aggregated Spread Matching.
│   ├── multileg_spread_matcher.py # Rule 9: Multileg Spread Matching.
│   ├── aggregated_crack_matcher.py # Rule 10: Aggregated Crack Matching.
│   ├── complex_crack_roll_matcher.py # Rule 11: Complex Crack Roll Matching.
│   └── aggregated_product_spread_matcher.py # Rule 12: Aggregated Product Spread Matching.
├── core/
│   └── unmatched_pool.py # State manager for all trades, preventing duplicate matches.
├── config/
│   └── config_manager.py # Centralized system settings for ICE.
└── cli/
    └── display.py         # Rich terminal output for ICE results.
```

## ⚙️ Universal Matching Fields System

The system implements a sophisticated universal field matching architecture that ensures consistency across all matching rules **within a given subsystem (e.g., ICE or SGX)**. This is a key feature for data integrity.

### Architecture Overview

- **JSON-Driven Configuration**: All universal fields for a subsystem are defined in its `normalizer_config.json`.
- **Centralized Management**: The subsystem's `ConfigManager` is the single source of truth for its configuration.
- **BaseMatcher Inheritance**: All matcher classes inherit from a common `BaseMatcher` which contains the logic to validate trades against the universal fields.
- **Dynamic Field Access**: The system uses `getattr()` to dynamically access the correct attributes on the `Trade` model.

### Current Universal Fields (ICE & SGX)

The following fields are currently configured as universal and must match for any trade reconciliation within their respective subsystems:

- **`brokergroupid`** → `broker_group_id`
- **`exchclearingacctid`** → `exch_clearing_acct_id`
