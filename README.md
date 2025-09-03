# Trade Matching & Reconciliation Engine

A comprehensive reconciliation engine for matching trades across multiple exchanges with specialized rule-based matching systems.

## 🎯 Overview

This reconciliation engine contains multiple specialized matching systems:

- **Unified Reconciliation System** (`src/unified_recon/`) - Centralized data routing system that groups trades by exchange and routes to appropriate matching systems
- **ICE Trade Matching System** (`src/ice_match/`) - Energy derivatives matching with 13 sequential rules
- **SGX Trade Matching System** (`src/sgx_match/`) - Singapore Exchange iron ore futures matching with 3 sequential rules
- **CME Trade Matching System** (`src/cme_match/`) - Chicago Mercantile Exchange futures matching with 1 exact matching rule

## 🚀 Quick Start

```bash
# Install dependencies
uv sync

# Run unified reconciliation (processes all exchanges)
uv run python -m src.unified_recon.main

# Process JSON payload (API simulation)
uv run python -m src.unified_recon.main --json-file src/test_json/sample_full.json

# Run individual matching systems
uv run python -m src.ice_match.main
uv run python -m src.sgx_match.main
uv run python -m src.cme_match.main

# Development commands
uv run ruff check .                    # Linting
uv run ruff check --fix .              # Auto-fix linting
uv run python -m mypy src/             # Type checking
```

## 🏗️ Architecture

### Unified Reconciliation Flow

```ascii
┌─────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED RECONCILIATION FLOW                      │
└─────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │   main.py   │
                              └──────┬──────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │  Parse CLI Arguments            │
                    │  --json-file or CSV path        │
                    └────────────────┬────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  UnifiedTradeRouter │
                          │  (group_router.py)  │
                          └──────────┬──────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              │                                             │
     ┌────────▼────────┐                       ┌───────────▼──────────┐
     │ JSON Input Path │                       │   CSV Input Path     │
     └────────┬────────┘                       └───────────┬──────────┘
              │                                             │
     ┌────────▼─────────────────┐            ┌─────────────▼──────────┐
     │load_and_validate_json_data│            │load_and_validate_data │
     └────────┬─────────────────┘            └─────────────┬──────────┘
              │                                             │
     ┌────────▼─────────────────┐            ┌─────────────▼──────────┐
     │ Group by exchangeGroupId │            │  DataValidator checks  │
     │ {1: [...], 2: [...], 4:..}│            │  exchangegroupid exists│
     └────────┬─────────────────┘            └─────────────┬──────────┘
              │                                             │
     ┌────────▼─────────────────┐            ┌─────────────▼──────────┐
     │  For each group:         │            │   Load CSV files       │
     │  - ICE: ICETradeFactory  │            │   trader_df, exchange_df│
     │  - SGX: SGXTradeFactory  │            └─────────────┬──────────┘
     └────────┬─────────────────┘                          │
              │                                             │
     ┌────────▼─────────────────┐            ┌─────────────▼──────────┐
     │ factory.from_json()      │            │ Group by exchangeGroupId│
     │ Creates Trade objects    │            │ using pandas operations │
     └────────┬─────────────────┘            └─────────────┬──────────┘
              │                                             │
     ┌────────▼─────────────────┐                          │
     │ _trades_to_dataframe()   │                          │
     │ Convert Trade→DataFrame  │                          │
     └────────┬─────────────────┘                          │
              └──────────────────┬──────────────────────────┘
                                 │
                    ┌────────────▼────────────────┐
                    │  Route to Matching Systems  │
                    │  Group 1,4 → ICE            │
                    │  Group 2 → SGX              │
                    └────────────┬────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
     ┌────────▼────────┐   ┌────▼──────┐   ┌───────▼──────┐
     │ ICEMatchingEngine│   │SGXMatching│   │CMEMatching  │
     │run_matching_from_│   │Engine.run_│   │Engine...    │
     │dataframes()      │   │matching() │   │             │
     └────────┬────────┘   └────┬──────┘   └───────┬──────┘
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 │
                    ┌────────────▼────────────────┐
                    │   ResultAggregator          │
                    │   Combine all results       │
                    └────────────┬────────────────┘
                                 │
                    ┌────────────▼────────────────┐
                    │   UnifiedDisplay            │
                    │   Rich terminal output      │
                    └─────────────────────────────┘
```

### Trade Factory Flow (JSON → Trade Objects)

```ascii
┌─────────────────────────────────────────────────────────────────────────┐
│                           TRADE FACTORY FLOW                             │
└─────────────────────────────────────────────────────────────────────────┘

                        ┌───────────────────┐
                        │   JSON Input      │
                        │ {'internalTradeId'│
                        │  'productName'... │
                        └─────────┬─────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   ICETradeFactory or       │
                    │   SGXTradeFactory          │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   from_json() method       │
                    │   - Iterate through list   │
                    │   - Process each record    │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  _process_json_record()    │
                    │  - Map camelCase→snake_case│
                    │  - Apply field mappings    │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  TradeNormalizer           │
                    │  - normalize_product_name  │
                    │  - normalize_contract_month│
                    │  - normalize_buy_sell      │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Handle Optional Fields    │
                    │  - Set None for missing   │
                    │  - Apply defaults         │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Create Trade Object       │
                    │  - Pydantic validation    │
                    │  - Type conversion        │
                    │  - Store raw_data         │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Return List[Trade]        │
                    └─────────────────────────────┘

Field Mapping Example:
┌────────────────────┬────────────────────┬──────────────────┐
│   JSON Field       │  Intermediate      │  Trade Field     │
├────────────────────┼────────────────────┼──────────────────┤
│ internalTradeId    │ internal_trade_id  │ internal_trade_id│
│ productName        │ product_name       │ product_name     │
│ quantityUnit       │ quantity_unit      │ quantity         │
│ contractMonth      │ contract_month     │ contract_month   │
│ b_s                │ b_s                │ buy_sell         │
│ brokerGroupId      │ broker_group_id    │ broker_group_id  │
│ exchClearingAcctId │ exch_clearing_acct │ exch_clearing_   │
│                    │ _id                │ acct_id          │
└────────────────────┴────────────────────┴──────────────────┘
```

### Trade Model Flow

```ascii
┌─────────────────────────────────────────────────────────────────────────┐
│                            TRADE MODEL FLOW                              │
└─────────────────────────────────────────────────────────────────────────┘

                        ┌───────────────────┐
                        │   Raw Input Data  │
                        │  (JSON/CSV/Dict)  │
                        └─────────┬─────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   Trade Constructor        │
                    │   Pydantic BaseModel        │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   Field Validation         │
                    │   - Required fields check  │
                    │   - Type conversion        │
                    │   - Range validation       │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   Model Configuration      │
                    │   - frozen=True (immutable)│
                    │   - validate_assignment    │
                    │   - str_strip_whitespace   │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   Trade Object Created     │
                    │   Fields:                  │
                    │   - internal_trade_id      │
                    │   - product_name           │
                    │   - quantity (Decimal)     │
                    │   - price (Decimal)        │
                    │   - buy_sell ('B'/'S')     │
                    │   - broker_group_id        │
                    │   - exch_clearing_acct_id  │
                    │   - raw_data (original)    │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   Computed Properties      │
                    │   @property methods:       │
                    │   - is_buy()               │
                    │   - is_sell()              │
                    │   - quantity_mt()          │
                    │   - quantity_bbl()         │
                    │   - matching_signature()   │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   Usage in Matchers        │
                    │   - Signature generation   │
                    │   - Field comparison       │
                    │   - Unit conversion        │
                    └─────────────────────────────┘
```

## 📊 Matching Systems

### ICE Match Module (13 Rules)

Energy derivatives matching with sequential rule processing:

- **Rules 1-3**: Basic matching (exact, spread, crack)
- **Rules 4-6**: Complex matching (complex crack, product spread, fly)
- **Rules 7-9**: Advanced aggregated matching
- **Rules 10-13**: Advanced matching (multileg spread, aggregated crack, complex crack roll, aggregated product spread)

### SGX Match Module (3 Rules)

Singapore Exchange iron ore futures matching:

- **Rule 1**: Exact matching on 7 fields (100% confidence)
- **Rule 2**: Spread matching for calendar spreads (95% confidence)
- **Rule 3**: Product spread matching with 3-tier confidence system (90-95% confidence)

### CME Match Module (1 Rule)

Chicago Mercantile Exchange futures matching:

- **Rule 1**: Exact matching on 7 fields with quantity lots focus (100% confidence)

## 🔧 Key Components

### run_matching vs run_matching_minimal

```ascii
┌──────────────────────────┬────────────────────────────────────────┐
│     run_matching()       │        run_matching_minimal()          │
├──────────────────────────┼────────────────────────────────────────┤
│ Purpose:                 │ Purpose:                               │
│ - Direct CLI execution   │ - Called by unified reconciliation     │
│ - Human-readable output  │ - Machine-readable output              │
│                          │                                        │
│ Display:                 │ Display:                               │
│ - Rich terminal UI       │ - No display output                    │
│ - Progress bars          │ - Silent execution                     │
│ - Colored tables         │ - Returns data structures              │
│                          │                                        │
│ Returns:                 │ Returns:                               │
│ - None (prints to screen)│ - tuple[List[MatchResult], Dict]      │
│                          │ - Matches + statistics                 │
│                          │                                        │
│ Use Case:                │ Use Case:                              │
│ - Standalone execution   │ - Integration with unified system      │
│ - Testing single system  │ - Programmatic access                  │
│ - Debugging              │ - API/service integration              │
└──────────────────────────┴────────────────────────────────────────┘
```

### Core Module Responsibilities

#### UnifiedTradeRouter (`group_router.py`)
- Handles both CSV and JSON loading paths
- Groups trades by `exchangegroupid` field
- Routes to appropriate matching systems (ICE, SGX, CME)
- Integrates trade factories for sophisticated field handling
- Converts between Trade objects and DataFrames

#### Trade Factory
- Processes JSON payloads with camelCase→snake_case conversion
- Applies field mappings and normalization
- Handles optional fields with None values
- Creates immutable Trade objects with validation

#### Trade Model
- Immutable (frozen=True) for thread safety
- Pydantic v2 validation and type conversion
- Computed properties for unit conversion (MT↔BBL)
- Raw data preservation for audit trail

## 📁 Project Structure

```
matching/
├── src/
│   ├── unified_recon/      # Centralized routing system
│   │   ├── main.py         # Entry point
│   │   ├── core/           # Routing and aggregation
│   │   ├── config/         # System mappings
│   │   └── data/           # Master CSV files
│   ├── ice_match/          # ICE matching system (13 rules)
│   │   ├── main.py
│   │   ├── models/         # Trade and MatchResult models
│   │   ├── matchers/       # Rule implementations
│   │   ├── normalizers/    # Data standardization
│   │   └── core/           # Trade factory and pool management
│   ├── sgx_match/          # SGX matching system (3 rules)
│   │   └── [similar structure]
│   └── cme_match/          # CME matching system (1 rule)
│       └── [similar structure]
├── tests/                  # Test files
├── pyproject.toml         # Project configuration
└── README.md             # This file
```

## 🛠️ Development

### Code Quality Standards

- **Functions under 50 lines** with single responsibility
- **Classes under 100 lines** representing single concepts
- **Files under 500 lines** - refactor by splitting modules if needed
- **Line length: 100 characters max** (enforced by Ruff)
- **Type hints** for all function signatures
- **Pydantic v2** for data validation

### Testing

This project uses real CSV data for testing instead of traditional unit tests:

```bash
# Test with sample data
uv run python -m src.unified_recon.main

# Test with custom data
uv run python -m src.unified_recon.main --data-dir path/to/data

# Test JSON routing
uv run python -m src.unified_recon.main --json-file src/test_json/sample_full.json
```

## 📋 Configuration

### Exchange Group Mappings

Edit `src/unified_recon/config/unified_config.json`:

```json
{
  "exchange_group_mappings": {
    "1": "ice_match", # CSV testing
    "2": "sgx_match", # CSV testing
    "4": "ice_match" # for JSON
  }
}
```

### Adding New Matching Systems

1. Create new module under `src/` following existing patterns
2. Implement Trade model with required fields
3. Create matchers extending BaseMatcher
4. Add trade factory for JSON support
5. Update unified_config.json with group mapping

## 📝 License

Proprietary - All rights reserved

