# GEMINI.md

This file provides comprehensive guidance to Gemini when working with this **Energy Trade Matching System** project.

## 🎯 Project Overview

This is an **Energy Trade Matching System** that matches trades between trader and exchange data sources using a sequential, rule-based approach. The system is designed to be robust, extensible, and maintainable, with a focus on clear data processing pipelines and strong data integrity. It now supports a growing set of matching rules, including complex scenarios like multi-leg crack spreads, product spreads, aggregation, and advanced decomposition and netting. All 10 rules defined in `docs/rules.md` are now implemented.

### Key Features

- **Universal Data Normalization**: `TradeNormalizer` standardizes product names, contract months, buy/sell indicators, and unit conversions.
- **Configuration Management**: Centralized settings with rule confidence levels, tolerances, and conversion ratios.
- **Sequential Rule Processing**: Implements rules in priority order (exact matches first) with non-duplication.
- **Rich CLI Interface**: Beautiful terminal output with progress indicators and detailed results.
- **Product-Specific Unit Conversion**: MT→BBL conversion with product-specific ratios (6.35, 8.9, 7.0 default).
- **Pydantic v2 Data Models**: Strict validation and type safety for all trade data.
- **Complete Type Safety**: Full mypy compliance with pandas-stubs integration.

## 🌊 Data Processing Flow

The system follows a clear, sequential data processing pipeline:

1.  **Load**: Raw data is loaded from CSV files (e.g., `sourceTraders.csv` and `sourceExchange.csv`) by the `CSVTradeLoader`.
2.  **Normalize**: The `TradeNormalizer` cleans and standardizes critical fields (`product_name`, `contract_month`, `buy_sell`, etc.) from the raw data using rules loaded from `normalizer_config.json`. It also provides product-specific unit conversion ratios and shared conversion/validation methods. This is a crucial step to ensure consistent comparisons.
3.  **Instantiate**: Validated and normalized data is used to create immutable `Trade` objects.
4.  **Pool**: All `Trade` objects are placed into the `UnmatchedPoolManager`, which tracks the state of all matched and unmatched trades, preventing duplicate matches.
5.  **Match**: A sequence of `Matcher` modules are run in order of confidence (as defined in `rules.md` and configured in `ConfigManager`). Each matcher operates on the trades remaining in the pool.
    -   **Rule 1 (ExactMatcher)**: Finds exact matches based on 6 fields.
    -   **Rule 2 (SpreadMatcher)**: Finds 2-leg calendar spread matches.
    -   **Rule 3 (CrackMatcher)**: Finds 1-to-1 crack spread matches with unit conversion.
    -   **Rule 4 (ComplexCrackMatcher)**: Finds 2-leg complex crack matches (trader crack vs. exchange base product + Brent swap).
    -   **Rule 5 (ProductSpreadMatcher)**: Matches product combination spreads.
    -   **Rule 6 (AggregationMatcher)**: Matches trades that are split or combined across sources.
    -   **Rule 7 (AggregatedComplexCrackMatcher)**: Finds 2-leg complex crack matches with aggregated base products.
    -   **Rule 8 (CrackRollMatcher)**: Finds calendar spreads of crack positions.
    -   **Rule 9 (CrossMonthDecompositionMatcher)**: Finds cross-month decomposed positions.
    -   **Rule 10 (ComplexProductSpreadDecompositionMatcher)**: Finds complex product spread decomposition and netting matches.
6.  **Display**: The `MatchDisplayer` presents the results, including matches, unmatched trades, and statistics, in a clear, user-friendly format.

## 🏗️ Project Architecture

```
src/energy_match/
├── main.py                 # Main application entry point and CLI. Orchestrates the data flow.
├── models/
│   ├── trade.py           # Core `Trade` model. The single source of truth for a trade.
│   └── match_result.py    # `MatchResult` model for storing match details.
├── loaders/
│   └── csv_loader.py     # Handles loading raw data from CSV files.
├── normalizers/
│   └── trade_normalizer.py # Cleans and standardizes trade data using external configurations.
├── matchers/
│   ├── exact_matcher.py   # Implements Rule 1: Exact Matching.
│   ├── spread_matcher.py  # Implements Rule 2: Spread Matching.
│   ├── crack_matcher.py   # Implements Rule 3: Crack Matching.
│   ├── complex_crack_matcher.py # Implements Rule 4: Complex Crack Matching.
│   ├── product_spread_matcher.py # Implements Rule 5: Product Spread Matching.
│   ├── aggregation_matcher.py # Implements Rule 6: Aggregation Matching.
│   ├── aggregated_complex_crack_matcher.py # Implements Rule 7: Aggregated Complex Crack Matching.
│   ├── crack_roll_matcher.py # Implements Rule 8: Crack Roll Matching.
│   ├── cross_month_decomposition_matcher.py # Implements Rule 9: Cross-Month Decomposition Matching.
│   └── complex_product_spread_decomposition_matcher.py # Implements Rule 10: Complex Product Spread Decomposition and Netting Matching.
├── core/
│   └── unmatched_pool.py # State manager for all trades, preventing duplicate matches.
├── config/
│   ├── config_manager.py # Centralized system settings (tolerances, conversion ratios, rule confidences).
│   └── normalizer_config.json # External JSON file for normalization mappings (products, months).
├── cli/
│   └── display.py   # Rich terminal output and progress display.
├── data/
│   ├── sourceTraders.csv    # Default trader data.
│   └── sourceExchange.csv   # Default exchange data.
│   └── ...                  # Additional data directories for specific dates or test cases.
└── docs/
    └── rules.md        # The complete 10-rule specification. The primary source for business logic.
```