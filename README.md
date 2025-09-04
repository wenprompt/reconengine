# Trade Matching & Reconciliation Engine

A comprehensive reconciliation engine for matching trades across multiple exchanges with specialized rule-based matching systems. Now featuring a high-performance REST API for seamless integration.

## 🎯 Overview

This reconciliation engine provides both CLI and REST API interfaces for trade matching across multiple exchanges:

### Matching Systems

- **Unified Reconciliation System** (`src/unified_recon/`) - Centralized data routing system that groups trades by exchange and routes to appropriate matching systems
- **ICE Trade Matching System** (`src/ice_match/`) - Energy derivatives matching with 13 sequential rules
- **SGX Trade Matching System** (`src/sgx_match/`) - Singapore Exchange iron ore futures matching with 3 sequential rules
- **CME Trade Matching System** (`src/cme_match/`) - Chicago Mercantile Exchange futures matching with 1 exact matching rule
- **EEX Trade Matching System** (`src/eex_match/`) - European Energy Exchange matching with 1 exact matching rule

### Key Features

- **🚀 REST API**: FastAPI web service for programmatic access
- **⚡ Optimized Performance**: Direct in-memory processing without filesystem I/O
- **📊 Multiple Interfaces**: CLI for batch processing, API for real-time integration
- **🔄 Automatic Routing**: Trades automatically routed to correct matching system based on exchange group
- **📈 Comprehensive Reporting**: Rich terminal output and JSON response formats

## 🚀 Quick Start

### REST API Server

```bash
# Install dependencies
uv sync

# Start the FastAPI server
uv run python -m src.unified_recon.server

# The API will be available at:
# - http://localhost:7777 (local)
# - http://YOUR_IP:7777 (network)
# - http://localhost:7777/docs (OpenAPI documentation)
```

### API Usage

```bash
# Send reconciliation request
curl -X POST http://localhost:7777/reconcile \
  -H "Content-Type: application/json" \
  -d @src/json_input/ice_sample.json

# Check server health
curl http://localhost:7777/health
```

### CLI Usage

```bash
# Run unified reconciliation (processes all exchanges)
uv run python -m src.unified_recon.main

# Process JSON payload
uv run python -m src.unified_recon.main --json-file src/json_input/ice_sample.json

# Run individual matching systems
uv run python -m src.ice_match.main
uv run python -m src.sgx_match.main
uv run python -m src.cme_match.main
uv run python -m src.eex_match.main

# Development commands
uv run ruff check .                    # Linting
uv run ruff check --fix .              # Auto-fix linting
uv run python -m mypy src/             # Type checking
```

## 🏗️ Architecture

### System Flow

```ascii
┌─────────────────────────────────────────────────────────────────────────┐
│                    UNIFIED RECONCILIATION ARCHITECTURE                   │
└─────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────┐
                        │    REST API         │
                        │  (FastAPI Server)   │
                        │   Port 7777         │
                        └──────────┬──────────┘
                                   │
                          ┌────────▼────────┐
                          │   POST /reconcile│
                          │   JSON Payload   │
                          └────────┬────────┘
                                   │
                       ┌───────────▼───────────┐
                       │  ReconciliationService│
                       │  (api/service.py)     │
                       └───────────┬───────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │ load_and_validate_json_dict │
                    │ (Direct in-memory processing)│
                    └──────────────┬──────────────┘
                                   │
   ┌───────────────────────────────┼───────────────────────────────┐
   │                               │                               │
   │                    ┌──────────▼──────────┐                   │
   │                    │  UnifiedTradeRouter │                   │
   │                    │  (group_router.py)  │                   │
   │                    └──────────┬──────────┘                   │
   │                               │                               │
   │                               │ CLI Path                      │
   │      API Path                 │                               │
   │   (No filesystem I/O)         │                               │
   │                               ▼                               │
   │                        ┌─────────────┐                       │
   │                        │   main.py   │                       │
   │                        └──────┬──────┘                       │
   │                               │                               │
   │                  ┌────────────┴────────────┐                 │
   │                  │  --json-file or CSV     │                 │
   │                  └────────────┬────────────┘                 │
   └───────────────────────────────┼───────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Group JSON by exchangeGroupId│
                    │  Process via Trade Factories  │
                    │  - Group 1,4: ICETradeFactory│
                    │  - Group 2: SGXTradeFactory  │
                    │  - Group 3: CMETradeFactory  │
                    │  - Group 5: EEXTradeFactory  │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Convert Trade Objects      │
                    │  to DataFrames              │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Route to Matching Systems  │
                    │  Based on exchangeGroupId   │
                    └──────────────┬──────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
   ┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
   │ICE Matching │         │SGX Matching │         │CME/EEX Match│
   │ (13 rules)  │         │ (3 rules)   │         │ (1 rule)    │
   └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   ResultAggregator          │
                    │   Combine all results       │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
     ┌────────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐
     │ API Response    │  │ CLI Display    │  │ JSON Output    │
     │ (Array format)  │  │ (Rich terminal)│  │ (--json-output)│
     └─────────────────┘  └────────────────┘  └────────────────┘
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
┌──────────────────────────────┬───────────────────────┬──────────────────┐
│   JSON Field                 │  Intermediate         │  Trade Field     │
├──────────────────────────────┼───────────────────────┼──────────────────┤
│ internalTradeId              │ internaltradeid       │ internal_trade_id│
│ productName                  │ productname           │ product_name     │
│ quantityUnit                 │ quantityunit          │ quantity         │
│ contractMonth                │ contractmonth         │ contract_month   │
│ b/s                          │ b_s                   │ buy_sell         │
│ brokerGroupId                │ brokergroupid         │ broker_group_id  │
│ exchangeClearingAccountId    │ exchclearingacctid    │ exch_clearing_   │
│                              │                       │ acct_id          │
└──────────────────────────────┴───────────────────────┴──────────────────┘
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

## Matching Process

### Sequential Rule Processing

```ascii
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           SEQUENTIAL RULE PROCESSING FLOW                            │
└─────────────────────────────────────────────────────────────────────────────────────┘

Start: 100 Trader Trades, 100 Exchange Trades
                    │
                    ▼
        ┌──────────────────────┐
        │   Rule 1: Exact      │
        │   Confidence: 100%   │
        │   Matches: 30        │
        └──────────┬───────────┘
                   │ Remaining: 70T, 70E
                   ▼
        ┌──────────────────────┐
        │   Rule 2: Spread     │
        │   Confidence: 95%    │
        │   Matches: 10        │
        └──────────┬───────────┘
                   │ Remaining: 60T, 60E
                   ▼
        ┌──────────────────────┐
        │   Rule 3: Crack      │
        │   Confidence: 88%    │
        │   Matches: 5         │
        └──────────┬───────────┘
                   │ Remaining: 55T, 55E
                   ▼
        ┌──────────────────────┐
        │  Rules 4-13: Complex │
        │  (Spreads, Aggregated│
        │   Multileg patterns) │
        │  Matches: 16         │
        └──────────┬───────────┘
                   │
                   ▼
        Final: 61 Total Matches
        Unmatched: 37T, 37E
        Match Rate: 61%
```
