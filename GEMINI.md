# GEMINI.md

This file provides comprehensive guidance to Gemini when working with this **Energy Trade Matching System** project.

## 🎯 Project Overview

This is an **Energy Trade Matching System** that matches trades between trader and exchange data sources using a sequential rule-based approach. The system implements exact matching (Rule 1) with plans for 9 additional sophisticated matching rules including spreads, cracks, aggregations, and complex scenarios.

### Key Features

- **Universal Data Normalization**: Handles CSV data from different sources with unified field mapping
- **Sequential Rule Processing**: Implements rules in priority order (exact matches first)
- **Non-Duplication Architecture**: Manages unmatched trade pools to prevent duplicate matching
- **Rich CLI Interface**: Beautiful terminal output with progress indicators and detailed results
- **Unit Conversion**: Automatic BBL ↔ MT conversion with configurable ratios
- **Pydantic v2 Data Models**: Strict validation and type safety for all trade data

## 🏗️ Project Architecture

### Core Structure

```
src/energy_match/
├── main.py                 # Main application entry point with CLI
├── models/                 # Pydantic v2 data models
│   ├── trade.py           # Core Trade model with validation
│   └── match_result.py    # MatchResult model for output
├── loaders/               # CSV data loading
│   └── csv_loader.py     # Handles both trader and exchange CSV files
├── normalizers/          # Data normalization
│   └── trade_normalizer.py # Universal field mapping and cleaning
├── matchers/            # Matching rule implementations
│   └── exact_matcher.py # Rule 1: Exact matching (6-field comparison)
├── core/               # Core system components
│   └── unmatched_pool.py # Non-duplication pool management
├── config/            # Configuration management
│   └── config_manager.py # Centralized settings with validation
├── cli/              # Rich CLI interface
│   └── display.py   # Beautiful terminal output and progress
├── data/            # Sample data sets
│   ├── sourceTraders.csv    # Default trader data
│   ├── sourceExchange.csv   # Default exchange data
│   └── [additional datasets] # Various test scenarios
└── docs/
    └── rules.md        # Complete 10-rule specification
```

## 🛠️ Development Environment

### UV Package Management

This project uses UV for package and environment management.

- Create virtual environment: `uv venv`
- Sync dependencies: `uv sync`
- Add a package: `uv add <package>`
- Run commands: `uv run <command>`

### Development Commands

- Format code: `uv run ruff format .`
- Linting: `uv run ruff check .`
- Type checking: `python -m mypy src/energy_match`
- Run application: `python -m src.energy_match.main`

## 📋 Style & Conventions

- **PEP8** with 100-character line length.
- **Google-style docstrings**.
- **`snake_case`** for variables and functions, **`PascalCase`** for classes.

## ✅ Quality Assurance

- Testing is done using **real CSV data** instead of traditional unit tests.
- **Rule 1 (Exact Matching)** is complete and tested.
- Rules 2-10 are planned.

## Matching Rules Summary

The system uses a sequential, confidence-based rule system.

1.  **Exact Match**: 6 fields must match exactly after normalization.
2.  **Spread Match**: A spread trade in trader data matches two separate trades in exchange data.
3.  **Crack Match**: Matches crack spread trades, handling MT/BBL unit conversion.
4.  **Aggregation Match**: Matches trades that are split in one source and combined in the other.
5.  **Product Spread Match**: Matches spread trades between two different products.
6.  **Complex Crack Match**: A crack trade matches a base product trade and a Brent swap trade.
7.  **Aggregated Complex Crack Match**: A crack trade matches multiple split base product trades and a Brent swap trade.
8.  **Crack Roll Match**: A calendar spread of crack positions.
9.  **Cross-Month Decomposition Match**: A complex position across different contract months.
10. **Complex Product Spread Decomposition and Netting Match**: The most complex scenario, involving decomposition and netting of multiple trades.

**Data Normalization is key**: All data from both sources must be normalized *before* any matching operations. This includes field name mapping and value normalization (e.g., "S" to "Sold", date formats, number formats).
