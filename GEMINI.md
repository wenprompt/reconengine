# GEMINI.md

This file provides comprehensive guidance to Gemini when working with this **Energy Trade Matching System** project.

## 🎯 Project Overview

This is an **Energy Trade Matching System** that matches trades between trader and exchange data sources using a sequential, rule-based approach. The system is designed to be robust, extensible, and maintainable, with a focus on clear data processing pipelines and strong data integrity. It now supports a growing set of matching rules, including complex scenarios like multi-leg crack spreads.

### Key Principles

- **Separation of Concerns**: Each module has a single, clear responsibility.
- **Configuration Driven**: Key business logic parameters (conversion ratios, tolerances, rule confidence levels) are managed in a central `ConfigManager`.
- **Externalized Normalization**: Normalization rules are loaded from external JSON files, allowing for easy updates without code changes.
- **Immutable Data Models**: Pydantic v2 models are used for strict, validated, and immutable trade data, ensuring thread safety and data integrity.
- **Testable by Design**: The system is tested using real data scenarios, crucial for a domain-heavy application like trade matching.

## 🌊 Data Processing Flow

The system follows a clear, sequential data processing pipeline:

1.  **Load**: Raw data is loaded from CSV files (e.g., `sourceTraders.csv` and `sourceExchange.csv`) by the `CSVTradeLoader`.
2.  **Normalize**: The `TradeNormalizer` cleans and standardizes critical fields (`product_name`, `contract_month`, `buy_sell`, etc.) from the raw data using rules loaded from `normalizer_config.json`. This is a crucial step to ensure consistent comparisons.
3.  **Instantiate**: Validated and normalized data is used to create immutable `Trade` objects.
4.  **Pool**: All `Trade` objects are placed into the `UnmatchedPoolManager`, which tracks the state of all matched and unmatched trades, preventing duplicate matches.
5.  **Match**: A sequence of `Matcher` modules are run in order of confidence (as defined in `rules.md` and configured in `ConfigManager`). Each matcher operates on the trades remaining in the pool.
    -   **Rule 1 (ExactMatcher)**: Finds exact matches based on 6 fields.
    -   **Rule 2 (SpreadMatcher)**: Finds 2-leg calendar spread matches.
    -   **Rule 3 (CrackMatcher)**: Finds 1-to-1 crack spread matches with unit conversion.
    -   **Rule 4 (ComplexCrackMatcher)**: Finds 2-leg complex crack matches (trader crack vs. exchange base product + Brent swap).
    -   *(Future matchers will follow this sequence)*
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
│   └── complex_crack_matcher.py # Implements Rule 4: Complex Crack Matching.
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

## 🛠️ Development Environment

### UV Package Management

This project uses `uv` for Python package and environment management.

-   **Create virtual environment**: `uv venv`
-   **Activate environment**: `source .venv/bin/activate`
-   **Sync dependencies**: `uv sync`
-   **Add a package**: `uv add <package>`
-   **Run a command**: `uv run <command>`

### Key Development Commands

-   **Format code**: `uv run ruff format .`
-   **Lint and fix**: `uv run ruff check --fix .`
-   **Type checking**: `uv run mypy src/energy_match`
-   **Run with default data**: `uv run python -m src.energy_match.main`
-   **Run with custom data**: `uv run python -m src.energy_match.main path/to/traders.csv path/to/exchange.csv`
-   **See all options**: `uv run python -m src.energy_match.main --help`
-   **Display matching rules info**: `uv run python -m src.energy_match.main --show-rules`

## ✅ Matching Rules Summary

The system uses a sequential, confidence-based rule system defined in `docs/rules.md`.

1.  **Exact Match (Implemented)**: 6 fields (`product_name`, `quantity_mt`, `price`, `contract_month`, `buy_sell`, `broker_group_id`) must match exactly after normalization.
2.  **Spread Match (Implemented)**: Matches a 2-leg trader spread (where one leg's price is the spread differential and the other is zero) against two separate exchange trades. The logic groups potential legs by `(product, quantity, broker)` for efficiency.
3.  **Crack Match (Implemented)**: Matches crack spread trades, handling unit conversions.
4.  **Complex Crack Match (Implemented)**: Matches a trader's crack trade against a combination of an exchange base product trade and a Brent swap trade, involving price calculation and unit conversion.
5.  **Product Spread Match (Future)**: Matches product combination spreads.
6.  **Aggregation Match (Future)**: Matches trades that are split or combined across sources.
7.  **Aggregated Complex Crack Match (Future)**: 2-leg crack trades with aggregated base products.
8.  **Crack Roll Match (Future)**: Calendar spreads of crack positions.
9.  **Cross-Month Decomposition Match (Future)**: Cross-month decomposed positions.
10. **Complex Product Spread Decomposition and Netting Match (Future)**: Most complex scenario.

---

## 📚 Detailed Module Responsibilities

This section provides a deeper dive into the role of each module within the `src/energy_match/` directory.

*   **`src/energy_match/main.py`**:
    *   **Role**: The central orchestrator and application entry point.
    *   **Responsibilities**: Initializes the `ConfigManager`, `TradeNormalizer`, `CSVTradeLoader`, `UnmatchedPoolManager`, and all `Matcher` instances. It defines the sequence of matching rule application, manages the overall data flow, and handles command-line arguments.

*   **`src/energy_match/models/`**:
    *   **Role**: Defines the core data structures used throughout the system.
    *   **Responsibilities**:
        *   `trade.py`: Defines the `Trade` Pydantic model, which is the immutable, normalized representation of a single trade. It includes properties for quantity conversion (MT/BBL) and basic matching signatures.
        *   `match_result.py`: Defines the `MatchResult` Pydantic model, which captures details of a successful match, including the matched trades, rule used, confidence, and any additional trades involved in multi-leg matches.

*   **`src/energy_match/loaders/`**:
    *   **Role**: Handles the ingestion of raw trade data from external files.
    *   **Responsibilities**:
        *   `csv_loader.py`: Implements `CSVTradeLoader` to read trade data from CSV files (e.g., `sourceTraders.csv`, `sourceExchange.csv`). It performs initial parsing and leverages the `TradeNormalizer` to clean and standardize data before creating `Trade` objects.

*   **`src/energy_match/normalizers/`**:
    *   **Role**: Ensures data consistency and standardization across different sources and formats.
    *   **Responsibilities**:
        *   `trade_normalizer.py`: Implements `TradeNormalizer`, which provides methods to clean and standardize various trade fields (e.g., product names, contract months, buy/sell indicators). It loads its specific normalization rules from an external JSON file.
        *   **`src/energy_match/config/normalizer_config.json`**: This JSON file externalizes the normalization mappings. It contains:
            *   `product_mappings`: Direct mapping for specific product name strings.
            *   `month_patterns`: Regular expressions and replacements for standardizing contract month formats.
            *   `product_variation_map`: Keywords used to identify and normalize product name variations (e.g., "marine 0.5% crack" from keywords "marine", "0.5", "crack").
            *   **Benefit**: Allows business users or configuration managers to update and extend normalization rules without requiring changes to the Python code, improving flexibility and maintainability.

*   **`src/energy_match/matchers/`**:
    *   **Role**: Contains the core business logic for identifying and validating trade matches based on specific rules.
    *   **Responsibilities**: Each file in this directory implements a distinct matching rule (e.g., `exact_matcher.py`, `spread_matcher.py`, `crack_matcher.py`, `complex_crack_matcher.py`). Matchers are designed to operate on the `UnmatchedPoolManager` to ensure trades are not duplicated across matches. They also provide a `get_rule_info()` method to describe their specific rule.

*   **`src/energy_match/core/`**:
    *   **Role**: Manages the state of trades throughout the matching process.
    *   **Responsibilities**:
        *   `unmatched_pool.py`: Implements `UnmatchedPoolManager`, which maintains pools of trades that are still available for matching. It provides methods to retrieve unmatched trades, and crucially, to `record_match()` (for multi-leg matches) or `remove_matched_trades()` (for 1-to-1 matches), ensuring that once trades are matched, they are removed from further consideration.

*   **`src/energy_match/config/`**:
    *   **Role**: Centralizes system-wide configuration parameters.
    *   **Responsibilities**:
        *   `config_manager.py`: Implements `ConfigManager`, which loads and provides access to various system settings, including conversion ratios, general tolerances, and confidence levels for each matching rule. It uses Pydantic for robust configuration management.

*   **`src/energy_match/cli/`**:
    *   **Role**: Handles the command-line interface and presentation of results.
    *   **Responsibilities**:
        *   `display.py`: Implements `MatchDisplayer`, which uses the `rich` library to provide visually appealing and informative output to the terminal, including summaries, detailed match tables, unmatched trade lists, and statistics.

---
*This document was last updated by Gemini based on a comprehensive code review.*