# Centralized Input Validation System Implementation Tasks

## Overview
Implement dual-mode architecture where X_match systems can:
1. Run standalone with CSV files (backward compatible)
2. Receive ValidatedData objects from unified_recon (no temp CSV files)

Normalization stays in X_match modules to preserve module-specific business logic.

## Phase 1: Core Infrastructure Setup

### 1. [X] Create Common Module Structure
   - 1.1. [X] Create `src/common/` directory
   - 1.2. [X] Create `src/common/validation/` subdirectory
   - 1.3. [X] Create `src/common/schemas/` subdirectory
   - 1.4. [X] Create `src/common/loaders/` subdirectory
   - 1.5. [X] Create `src/common/utils/` subdirectory
   - 1.6. [X] Add `__init__.py` files to all directories

### 2. [X] Design Base Validation Architecture
   - 2.1. [X] Create `src/common/validation/base.py`
      - 2.1.1. [X] Define abstract `BaseInputValidator` class
      - 2.1.2. [X] Define `validate()` abstract method
      - 2.1.3. [X] Define `_validate_trader_data()` and `_validate_exchange_data()` abstract methods
      - 2.1.4. [X] Define common error handling methods via exceptions.py
   - 2.2. [X] Create `src/common/validation/base.py` with `ValidatedData`
      - 2.2.1. [X] Define `ValidatedData` dataclass
      - 2.2.2. [X] Include trader_data, exchange_data, metadata fields
      - 2.2.3. [X] Add to_dataframe() method for conversion

### 3. [X] Implement Pydantic Input Schemas with Type Strategy
   - 3.1. [X] Create `src/common/schemas/input_schemas.py`
   - 3.2. [X] Define `TraderInputSchema` and `ExchangeInputSchema` with Union types
      - 3.2.1. [X] String fields: productname, contractmonth, buysell (no conversion)
      - 3.2.2. [X] ID fields as strings: dealid, tradeid (prevent scientific notation)
      - 3.2.3. [X] Integer fields with Union[str, int]: brokergroupid, exchclearingacctid, exchangegroupid
      - 3.2.4. [X] Decimal fields with Union[str, float, Decimal]: price, quantityunits, quantitylots
      - 3.2.5. [X] Configure field aliases via ConfigDict
   - 3.3. [X] Add field validators for type coercion
      - 3.3.1. [X] ID validator: ensure dealid/tradeid always strings
      - 3.3.2. [X] Integer validator: convert string numbers to int, handle empty
      - 3.3.3. [X] Decimal validator: convert to Decimal
      - 3.3.4. [X] String validator: strip whitespace via ConfigDict
   - 3.4. [X] Define `TraderInputSchema` model
      - 3.4.1. [X] Includes all trader fields
      - 3.4.2. [X] Add trader-specific fields with proper types
      - 3.4.3. [X] Has all validators
   - 3.5. [X] Define `ExchangeInputSchema` model
      - 3.5.1. [X] Includes all exchange fields
      - 3.5.2. [X] Add exchange-specific fields (exchangeorderid, exchangetradeid)
      - 3.5.3. [X] Has all validators

## Phase 2: Format-Specific Validators

### 4. [X] Implement CSV Validator
   - 4.1. [X] Create `src/common/validation/csv_validator.py`
   - 4.2. [X] Implement `CSVInputValidator` class
      - 4.2.1. [X] Inherit from BaseInputValidator
      - 4.2.2. [X] Implement `load_csv()` method with pandas
      - 4.2.3. [X] Handle encoding issues (UTF-8, UTF-8-sig)
      - 4.2.4. [X] Force string dtype for ID columns: {'dealid': 'str', 'tradeid': 'str'}
      - 4.2.5. [X] Let other fields load naturally (all will be strings from CSV)
   - 4.3. [X] Implement row-by-row validation
      - 4.3.1. [X] Convert DataFrame rows to dictionaries
      - 4.3.2. [X] Apply Pydantic validation per row (handles str→int/Decimal conversion)
      - 4.3.3. [X] Collect validation errors with row numbers
   - 4.4. [X] Add field mapping support
      - 4.4.1. [X] Load field mappings from config
      - 4.4.2. [X] Apply mappings before validation

### 5. [ ] Implement JSON Validator
   - 5.1. [ ] Create `src/common/validation/json_validator.py`
   - 5.2. [ ] Implement `JSONInputValidator` class
      - 5.2.1. [ ] Inherit from BaseInputValidator
      - 5.2.2. [ ] Implement `load_json()` for file paths
      - 5.2.3. [ ] Implement `parse_json()` for string input
      - 5.2.4. [ ] Handle nested JSON structures
   - 5.3. [ ] Implement JSON-specific validation
      - 5.3.1. [ ] Validate JSON schema structure
      - 5.3.2. [ ] Apply Pydantic validation to each trade
      - 5.3.3. [ ] Handle different JSON field names

### 6. [ ] Implement API Validator (Thin wrapper around JSON Validator)
   - 6.1. [ ] Create `src/common/validation/api_validator.py`
   - 6.2. [ ] Implement `APIInputValidator` class (extends JSONInputValidator)
      - 6.2.1. [ ] Handle API payload structure (if different from plain JSON)
      - 6.2.2. [ ] No authentication needed (per requirements)
      - 6.2.3. [ ] Reuse JSONInputValidator validation logic
   - 6.3. [ ] Add API-specific features (if needed)
      - 6.3.1. [ ] Handle request envelope/wrapper if API uses one
      - 6.3.2. [ ] Format errors for API responses

### 7. [ ] Implement Format Auto-Detection
   - 7.1. [ ] Create `src/common/validation/format_detector.py`
   - 7.2. [ ] Implement detection logic
      - 7.2.1. [ ] Check file extensions (.csv, .json)
      - 7.2.2. [ ] Peek at content for format detection
      - 7.2.3. [ ] Detect API payloads by structure
   - 7.3. [ ] Add fallback mechanisms
      - 7.3.1. [ ] Try multiple formats if detection fails
      - 7.3.2. [ ] Provide clear error messages

## Phase 3: Field Mapping Configuration

### 8. [ ] Create Field Mapping System
   - 8.1. [ ] Create `src/common/config/field_mappings.json`
   - 8.2. [ ] Define mapping structure
      - 8.2.1. [ ] CSV field mappings (current column names)
      - 8.2.2. [ ] JSON field mappings (new standardized names)
      - 8.2.3. [ ] API field mappings (camelCase or other conventions)
   - 8.3. [ ] Create mapping loader
      - 8.3.1. [ ] Create `src/common/config/mapping_manager.py`
      - 8.3.2. [ ] Load mappings based on format type
      - 8.3.3. [ ] Cache loaded mappings

### 9. [ ] Migrate Existing Field Mappings
   - 9.1. [ ] Extract ICE field mappings
      - 9.1.1. [ ] Review ICE csv_loader.py for hardcoded fields
      - 9.1.2. [ ] Add ICE-specific mappings to config
   - 9.2. [ ] Copy SGX field mappings
      - 9.2.1. [ ] Extract from SGX normalizer_config.json
      - 9.2.2. [ ] Merge into centralized config
   - 9.3. [ ] Copy CME field mappings
   - 9.4. [ ] Copy EEX field mappings

## Phase 4: Trade Factory Implementation

### 10. [ ] Create Trade Factory System
   - 10.1. [ ] Create `src/common/factories/trade_factory.py`
   - 10.2. [ ] Implement `BaseTradeFactory` class
      - 10.2.1. [ ] Define `create_trade_from_validated()` abstract method
      - 10.2.2. [ ] Add common field processing
      - 10.2.3. [ ] Add ID generation logic
   - 10.3. [ ] Create module-specific factories
      - 10.3.1. [ ] Create `ICETradeFactory` (uses ICE normalizer internally)
      - 10.3.2. [ ] Create `SGXTradeFactory` (uses SGX normalizer internally)
      - 10.3.3. [ ] Create `CMETradeFactory` (uses CME normalizer internally)
      - 10.3.4. [ ] Create `EEXTradeFactory` (uses EEX normalizer internally)

### 11. [ ] Keep Normalization in X_Match Modules
   - 11.1. [ ] Preserve existing normalizer architecture
      - 11.1.1. [ ] Keep normalizers in X_match modules
      - 11.1.2. [ ] Normalization happens AFTER receiving ValidatedData
      - 11.1.3. [ ] Each factory uses its module's normalizer
   - 11.2. [ ] Preserve module-specific normalization logic
      - 11.2.1. [ ] Keep product name mappings per module
      - 11.2.2. [ ] Keep contract month patterns per module
      - 11.2.3. [ ] Keep buy/sell normalization per module
      - 11.2.4. [ ] Keep unit conversions (ICE MT↔BBL)

## Phase 5: Unified Recon Integration

### 12. [ ] Modify Unified Recon Router
   - 12.1. [ ] Update `src/unified_recon/core/group_router.py`
      - 12.1.1. [ ] Import new validation system
      - 12.1.2. [ ] Replace CSV-only loading with format-agnostic loading
      - 12.1.3. [ ] Keep exchange group validation logic
   - 12.2. [ ] Modify `load_and_validate_data()` method
      - 12.2.1. [ ] Accept format parameter (csv/json/api)
      - 12.2.2. [ ] Use centralized validator
      - 12.2.3. [ ] Return ValidatedData objects
   - 12.3. [ ] Update data grouping
      - 12.3.1. [ ] Work with validated dictionaries instead of DataFrames
      - 12.3.2. [ ] Preserve group_by_exchange_group logic
      - 12.3.3. [ ] Group ValidatedData by exchange_group_id

### 13. [ ] Update Unified Recon Main (No Temp CSV Files)
   - 13.1. [ ] Modify `src/unified_recon/main.py`
      - 13.1.1. [ ] Add --input-format CLI option
      - 13.1.2. [ ] Add --trader-json option
      - 13.1.3. [ ] Add --exchange-json option
   - 13.2. [ ] Update system calling functions (pass objects, not files)
      - 13.2.1. [ ] Modify `call_ice_match_system()` to pass ValidatedData
      - 13.2.2. [ ] Modify `call_sgx_match_system()` to pass ValidatedData
      - 13.2.3. [ ] Modify `call_cme_match_system()` to pass ValidatedData
      - 13.2.4. [ ] Remove temp CSV file creation logic
   - 13.3. [ ] Direct object passing to X_match
      - 13.3.1. [ ] Pass ValidatedData objects directly
      - 13.3.2. [ ] Each X_match normalizes the data it receives
      - 13.3.3. [ ] No filesystem I/O for inter-system communication

## Phase 6: X_Match System Updates (Dual-Mode Support)

### 14. [ ] Update ICE Match System for Dual-Mode
   - 14.1. [ ] Add object-based entry point
      - 14.1.1. [ ] Add `run_matching_from_objects()` method to main.py
      - 14.1.2. [ ] Method receives ValidatedData objects
      - 14.1.3. [ ] Apply ICE normalization to validated data
      - 14.1.4. [ ] Create Trade objects using normalized data
   - 14.2. [ ] Keep existing CSV loader unchanged
      - 14.2.1. [ ] `run_matching_minimal()` continues to work with CSV
      - 14.2.2. [ ] Preserve all existing normalization logic
   - 14.3. [ ] Update ICEMatchingEngine class
      - 14.3.1. [ ] Add dual-mode support
      - 14.3.2. [ ] Keep backward compatibility for standalone mode

### 15. [ ] Update SGX Match System for Dual-Mode
   - 15.1. [ ] Follow same dual-mode pattern as ICE
   - 15.2. [ ] Preserve SGX-specific logic
      - 15.2.1. [ ] Keep options support (strike, put/call)
      - 15.2.2. [ ] Keep spread detection
      - 15.2.3. [ ] Apply SGX normalization after receiving ValidatedData

### 16. [ ] Update CME Match System for Dual-Mode
   - 16.1. [ ] Follow same dual-mode pattern as ICE
   - 16.2. [ ] Preserve CME-specific logic
      - 16.2.1. [ ] Keep quantity_lots focus
      - 16.2.2. [ ] Apply CME normalization after receiving ValidatedData

### 17. [ ] Update EEX Match System for Dual-Mode
   - 17.1. [ ] Follow same dual-mode pattern as ICE
   - 17.2. [ ] Leverage existing good structure
      - 17.2.1. [ ] Apply EEX normalization after receiving ValidatedData

## Phase 7: Testing Implementation

### 18. [ ] Test Dual-Mode Architecture
   - 18.1. [ ] Test standalone X_match with CSV files
      - 18.1.1. [ ] ICE: `python -m src.ice_match.main` with CSV files
      - 18.1.2. [ ] SGX: `python -m src.sgx_match.main` with CSV files
      - 18.1.3. [ ] CME: `python -m src.cme_match.main` with CSV files
      - 18.1.4. [ ] Verify normalization works as before
   - 18.2. [ ] Test unified_recon with object passing
      - 18.2.1. [ ] Test with `src/unified_recon/data/sourceTraders.csv`
      - 18.2.2. [ ] Test with `src/unified_recon/data/sourceExchange.csv`
      - 18.2.3. [ ] Verify no temp CSV files created
      - 18.2.4. [ ] Verify ValidatedData objects passed correctly
   - 18.3. [ ] Verify backward compatibility
      - 18.3.1. [ ] Ensure same Trade objects created in both modes
      - 18.3.2. [ ] Ensure matching results remain unchanged
      - 18.3.3. [ ] Verify exchange_group_id routing still works
      - 18.3.4. [ ] Compare results between old and new flows

## Phase 8: API Endpoint (Future Enhancement)

### 19. [ ] Create REST API Endpoint
   - 19.1. [ ] Design API specification
   - 19.2. [ ] Implement FastAPI endpoint
   - 19.3. [ ] Add authentication/authorization
   - 19.4. [ ] Add rate limiting
   - 19.5. [ ] Add async processing for large payloads

## Critical Considerations

### 20. [ ] Ensure Dual-Mode Functionality
   - 20.1. [ ] X_match systems work standalone with CSV files
   - 20.2. [ ] X_match systems accept ValidatedData from unified_recon
   - 20.3. [ ] No temp CSV files in object-passing mode
   - 20.4. [ ] Normalization stays in X_match modules

### 21. [ ] Ensure Routing Integrity
   - 21.1. [ ] Preserve exchange_group_id based routing
   - 21.2. [ ] Maintain group filtering before calling X_match
   - 21.3. [ ] Keep result aggregation working
   - 21.4. [ ] ValidatedData grouped correctly by exchange_group_id

### 22. [ ] Performance Optimization
   - 22.1. [ ] No filesystem I/O for inter-system communication
   - 22.2. [ ] Direct object passing reduces overhead
   - 22.3. [ ] Batch validation where possible
   - 22.4. [ ] Profile and optimize bottlenecks

### 23. [ ] Error Handling Strategy
   - 23.1. [ ] Define validation error response format
   - 23.2. [ ] Implement row-level error reporting
   - 23.3. [ ] Add option to skip invalid rows vs fail fast
   - 23.4. [ ] Log validation statistics

## Dependencies and Order

- Phase 1-4 can be done in parallel (core infrastructure)
- Phase 5 depends on Phase 1-4 (unified_recon needs validation system)
- Phase 6 depends on Phase 5 (X_match systems need unified_recon changes)
- Phase 7 (testing) should verify both standalone and object-passing modes
- Phase 8 is optional future enhancement for API support

## Key Architecture Decisions

1. **Normalization stays in X_match**: Each module keeps its business logic
2. **Dual-mode support**: Backward compatible + new object passing
3. **No temp CSV files**: Direct object passing from unified_recon
4. **ValidatedData intermediate format**: Clean separation of concerns
5. **Type handling strategy**: Union types with smart coercion

## Type Handling Strategy

### Field Categories and Type Rules

1. **ID Fields (MUST stay as strings)**:
   - `dealid`, `tradeid` → Always string to prevent scientific notation
   - Validator ensures: `str(value)` for any input

2. **Integer Fields (Union[str, int])**:
   - `brokergroupid`, `exchangegroupid`, `exchclearingacctid`, `productgroupid`
   - CSV provides strings → convert to int
   - JSON provides int → keep as int
   - Empty/None → None

3. **Decimal Fields (Union[str, float, Decimal])**:
   - `price`, `quantityunits`, `quantitylots`, `strike`
   - Handle commas in strings (e.g., "6,000" → Decimal('6000'))
   - Convert to Decimal for precision
   - Empty/None → None

4. **String Fields (no conversion)**:
   - `productname`, `contractmonth`, `buysell` (b/s in CSV)
   - `tradedate`, `tradetime`, `tradedatetime`, `cleareddate`
   - `unit`, `spread`, `specialcomms`, `put/call`
   - Strip whitespace only
   - Normalization happens in X_match modules

**Note**: Field names based on actual CSV columns. No `quantity` field exists (only `quantitylots` and `quantityunits`). No date part fields like `tradeyear`, `trademonth`, `tradeday`.

### Example Type Flow

```python
# CSV input (all strings)
{"dealid": "12345", "broker_group_id": "1", "price": "100.50"}
# After validation
{"dealid": "12345", "broker_group_id": 1, "price": Decimal("100.50")}

# JSON input (mixed types)
{"dealid": 12345, "broker_group_id": 1, "price": 100.5}
# After validation (same result!)
{"dealid": "12345", "broker_group_id": 1, "price": Decimal("100.50")}
```

This ensures consistent types regardless of input format!