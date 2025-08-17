# GEMINI.md

This file provides comprehensive guidance to Gemini when working with this **Energy Trade Matching System** project.

## 🎯 Project Overview

This is an **Energy Trade Matching System** that matches trades between trader and exchange data sources using a sequential, rule-based approach. The system is designed to be robust, extensible, and maintainable, with a focus on clear data processing pipelines and strong data integrity.

### Key Principles

- **Separation of Concerns**: Each module (`loader`, `normalizer`, `matcher`, `pool_manager`) has a single, clear responsibility.
- **Configuration Driven**: Key business logic parameters (conversion ratios, tolerances) are managed in a central `ConfigManager`.
- **Immutable Data Models**: Pydantic v2 models are used for strict, validated, and immutable trade data, ensuring thread safety and data integrity.
- **Testable by Design**: The system is tested using real data scenarios, which is crucial for a domain-heavy application like trade matching.

## 🌊 Data Processing Flow

The system follows a clear, sequential data processing pipeline:

1.  **Load**: Raw data is loaded from `sourceTraders.csv` and `sourceExchange.csv` by the `CSVTradeLoader`.
2.  **Normalize**: The `TradeNormalizer` cleans and standardizes critical fields (`product_name`, `contract_month`, `buy_sell`, etc.) from the raw data. This is a crucial step to ensure consistent comparisons.
3.  **Instantiate**: Validated and normalized data is used to create immutable `Trade` objects.
4.  **Pool**: All `Trade` objects are placed into the `UnmatchedPoolManager`, which tracks the state of all matched and unmatched trades.
5.  **Match**: A sequence of `Matcher` modules are run in order of confidence (as defined in `rules.md`). Each matcher operates on the trades remaining in the pool.
    - **Rule 1 (ExactMatcher)**: Finds exact matches.
    - **Rule 2 (SpreadMatcher)**: Operates on remaining trades to find spread matches.
    - *(Future matchers will follow this sequence)*
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
│   └── trade_normalizer.py # Handles universal cleaning of product names, dates, etc.
├── matchers/
│   ├── exact_matcher.py   # Implements Rule 1: Exact Matching.
│   ├── spread_matcher.py  # Implements Rule 2: Spread Matching.
│   └── crack_matcher.py   # Implements Rule 3: Crack Matching.
├── core/
│   └── unmatched_pool.py # State manager for all trades, preventing duplicate matches.
├── config/
│   └── config_manager.py # Centralized settings (tolerances, conversion ratios).
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

- **Create virtual environment**: `uv venv`
- **Activate environment**: `source .venv/bin/activate`
- **Sync dependencies**: `uv sync`
- **Add a package**: `uv add <package>`
- **Run a command**: `uv run <command>`

### Key Development Commands

- **Format code**: `uv run ruff format .`
- **Lint and fix**: `uv run ruff check --fix .`
- **Type checking**: `uv run mypy src/energy_match`
- **Run with default data**: `python -m src.energy_match.main`
- **Run with custom data**: `python -m src.energy_match.main path/to/traders.csv path/to/exchange.csv`
- **See all options**: `python -m src.energy_match.main --help`

## ✅ Matching Rules Summary

The system uses a sequential, confidence-based rule system defined in `docs/rules.md`.

1.  **Exact Match (Implemented)**: 6 fields (`product_name`, `quantity_mt`, `price`, `contract_month`, `buy_sell`, `broker_group_id`) must match exactly after normalization.
2.  **Spread Match (Implemented)**: Matches a 2-leg trader spread (where one leg's price is the spread differential and the other is zero) against two separate exchange trades. The logic groups potential legs by `(product, quantity, broker)` for efficiency.
3.  **Crack Match (Implemented)**: Matches crack spread trades, handling unit conversions.
4.  **Aggregation Match (Future)**: Matches trades that are split or combined across sources.
5.  ... and so on for more complex scenarios.

---
*This document was last updated by Gemini based on a comprehensive code review.*
