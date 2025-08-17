# Trade Matching Rules

## Universal Data Normalization Rules

**IMPORTANT**: The following normalization rules must be applied to ALL data from BOTH sources before any matching operations. These normalization rules ensure consistent data format across all matching types (exact, spread, and crack matches).

### Field Name Mapping

- `sourceTraders.B/S` ↔ `sourceExchange.b/s`
- `sourceTraders.contractmonth` ↔ `sourceExchange.contractmonth`
- `sourceTraders.quantityunits` ↔ `sourceExchange.quantityunits`
- `sourceTraders.brokergroupid` ↔ `sourceExchange.brokergroupid`
- `sourceTraders.productname` ↔ `sourceExchange.productname`
- `sourceTraders.price` ↔ `sourceExchange.price`

### Universal Value Normalization

**Apply to ALL records from BOTH data sources:**

- **Buy/Sell Values** (Standardized to full words):

  - `"S"` → `"Sold"`
  - `"B"` → `"Bought"`
  - `"Sell"` → `"Sold"`
  - `"Buy"` → `"Bought"`
  - Case-insensitive input, standardized output

- **Contract Month Format** (Standardized to "MMM-YY"):

  - `"Aug 25"` → `"Aug-25"`
  - `"aug25"` → `"Aug-25"`
  - `"August-25"` → `"Aug-25"`
  - `"Balmo"` → `"Balmo"` (special case preserved)

- **Quantity Units** (Cleaned numeric values):

  - `"2,000"` → `2000` (integer)
  - `'"5,000"'` → `5000` (remove quotes and commas)
  - All quantities converted to numeric for arithmetic operations

- **Product Name** (Lowercase with preserved punctuation):

  - `"Marine 0.5%"` → `"marine 0.5%"`
  - `"380CST CRACK"` → `"380cst crack"`
  - `"marine 0.5%-380cst"` → `"marine 0.5%-380cst"` (hyphenated products preserved)

- **Price** (Precise decimal values):

  - Convert to Decimal type for exact arithmetic
  - No rounding applied during conversion
  - Maintains full precision for exact matching

- **Broker Group ID** (Numeric standardization):
  - Convert to integer for consistent comparison
  - Handles string representations of numbers

**Note**: These normalizations are applied to the actual data columns, not just for comparison. All subsequent matching operations work with the normalized data.

## Processing Order by Confidence Level

The matching engine processes trades in order of confidence level to ensure the most certain matches are identified first, leaving more complex scenarios for later processing:

1. **Exact Matches** (Confidence: 100%) - Highest certainty, processed first
2. **Spread Matches** (Confidence: 95%) - Calendar spreads between contract months
3. **Crack Matches** (Confidence: 90%) - Crack spread trades with unit conversion
4. **Complex Crack Matches** (Confidence: 80%) - 2-leg crack trades (base product + brent swap)
5. **Product Spread Matches** (Confidence: 75%) - Product combination spreads (e.g., "marine 0.5%-380cst")
6. **Aggregation Matches** (Confidence: 72%) - Split/combined trade scenarios
7. **Aggregated Complex Crack Matches** (Confidence: 65%) - 2-leg crack trades with aggregated base products
8. **Crack Roll Matches** (Confidence: 65%) - Calendar spreads of crack positions with enhanced tolerance
9. **Cross-Month Decomposition Matches** (Confidence: 60%) - Cross-month decomposed positions using crack-like calculations
10. **Complex Product Spread Decomposition and Netting Matches** (Confidence: 60%) - Most complex scenario

### Complex Scenario Handling

**Processing Hierarchy**: The system processes matches in a structured hierarchy to handle complex trading scenarios:

- **Exact matches** remove the clearest matches first
- **Spreads and cracks** handle trades with clear indicators and unit conversion needs
- **Aggregation** resolves quantity mismatches between sources
- **Product spreads** handle different product combination representations
- **Complex cracks** handle sophisticated 2-leg crack trading strategies
- **Advanced scenarios** handle the most complex decomposition and netting cases

## 1. Exact Match Rules

### Definition

An **exact match** occurs when trades from both data sources have identical values across all required matching fields after normalization. This is the highest confidence match type (100%) and is processed first to establish the clearest trade relationships.

### Required Matching Fields

For a trade to qualify as an exact match, the following 6 fields must match exactly after normalization:

1. **productname** - Product identifier/name (case-insensitive after normalization)
2. **contractmonth** - Contract delivery month (standardized to "MMM-YY" format)
3. **quantityunits** - Trade quantity in units (numeric values only, commas removed)
4. **b/s** - Buy/Sell indicator (normalized to "Bought" or "Sold")
5. **price** - Trade execution price (exact numeric match)
6. **brokergroupid** - Broker group identifier (exact numeric match)

### Processing Logic

- **No tolerances applied**: All fields must match exactly after normalization
- **One-to-one matching**: Each exact match removes exactly 1 trader trade and 1 exchange trade
- **Highest priority**: Processed before all other matching rules to capture obvious matches first

### RULE 1: Exact Match

#### Example: Exact Match

**sourceTraders.csv:**

```
| productname | contractmonth | quantityunits | B/S | price  | brokergroupid |
|-------------|---------------|---------------|-----|--------|---------------|
| marine 0.5% | Aug 25        | 2000          | S   | 476.75 | 3             |
```

**sourceExchange.csv:**

```
| productname | contractmonth | quantityunits | b/s  | price  | brokergroupid |
|-------------|---------------|---------------|------|--------|---------------|
| marine 0.5% | Aug25         | "2,000"       | Sold | 476.75 | 3             |
```

**After Normalization (both records become):**

```
| productname | contractmonth | quantityunits | b/s  | price  | brokergroupid |
|-------------|---------------|---------------|------|--------|---------------|
| marine 0.5% | Aug-25        | 2000          | Sold | 476.75 | 3             |
```

**Result:** ✅ **EXACT MATCH** - All 6 required fields match exactly after normalization

## 2. Spread Match Rules

### Definition

A **spread match** occurs when a trader executes a spread trade (buying one contract and selling another related contract simultaneously) that appears as two separate trades in the exchange data but as a calculated spread in the trader data. This is a high-confidence match type (95%) that handles complex trading strategies.

**Processing Order**: Spread matching is performed AFTER exact matching has been completed and those trades have been removed from the matching pool. This makes spread identification easier by reducing the dataset to unmatched trades only.

**Key Insight**: Spreads represent **single trading strategies** that appear differently in each data source:

- **Trader data**: Shows the spread as 2 related trades (one with calculated spread price, one with price = 0)
- **Exchange data**: Shows the spread as 2 separate individual trades with actual market prices

### Spread Trade Identification

#### Exchange Data Indicators:

- **tradeid**: Both legs have identical `dealId` values and non-identical `tradeId` values that are not empty - _check the csv first if it can read the `dealId` and `tradeId` properly as they should be integers_ - - **tradeid**: if `dealId` and `tradeId` cannot be read accurately, then use the rule if `tradeid` is not empty, the tradeid is part of a spread - _tradeId preferred but may be missing_
- **Same brokergroupid**: Both legs have identical broker group identifier
- **Opposite B/S**: One leg is "Bought", the other is "Sold"
- **Same product group**: Both legs have the same base product (e.g., "380cst")
- **Same quantity**: Both legs have identical `quantityunits`
- **Different contract months**: Each leg has different `contractmonth`

#### Trader Data Indicators:

- **Spread flag**: `spread` column contains "S" (may be missing in some cases)
- **Price calculation**: One leg has calculated spread price, other leg has price = 0
- **Opposite B/S after normalization**: One "S" (Sold), one "B" (Bought)

**IMPORTANT**: Timestamp matching is NOT required for spread matching. Traders may enter spread legs at different times due to manual entry delays, system processing differences, or operational reasons.

### Required Matching Fields for Spreads

1. **productname** - Base product must match between all legs (after normalization)
2. **quantityunits** - Quantity must be identical for all legs (2 trader + 2 exchange)
3. **brokergroupid** - Broker group must match across all trades
4. **contractmonth** - Contract months must correspond between trader and exchange legs
5. **b/s directions** - Each leg's direction must match between sources (opposite directions within each source)
6. **spread price calculation** - Exchange price differential must equal trader spread price

### Spread Matching Logic

- **Multi-trade matching**: Each spread match removes 2 trader trades and 2 exchange trades
- **Price validation**: |Earlier_Contract_Price - Later_Contract_Price| = |Trader_Spread_Price|
- **Direction validation**: Opposite B/S directions within each source, matching directions between sources
- **Contract month validation**: Different months for legs, but corresponding months must match between sources

### Spread-Specific Normalization Rules

#### Price Calculation Logic:

- **Calculate exchange spread**: `earlier_contract_price - later_contract_price` (e.g., Jun-25 price - Jul-25 price)
- **Match validation**: Exchange spread must equal trader spread price

### Example: Spread Match

#### Before Normalization:

**sourceTraders.csv (Spread Entry):**

```
| teamid | tradedate | tradetime | productname | quantityunits | price | contractmonth | spread | B/S |
|--------|-----------|-----------|-------------|---------------|-------|---------------|--------|-----|
| 1      | 15/5/2025 | 11:14     | 380cst      | 20000         | 16.50 | Jun-25        | S      | S   |
| 1      | 15/5/2025 | 11:14     | 380cst      | 20000         | 0.00  | Jul-25        | S      | B   |
```

**sourceExchange.csv (Two Separate Trades):**

```
| tradeid    | productname | contractmonth | quantityunits | b/s    | price  | brokergroupid |
|------------|-------------|---------------|---------------|--------|--------|---------------|
| 1.9E+13    | 380cst Sing | Jun25         | 20,000        | Sold   | 425.50 | 3             |
| 1.9E+13    | 380cst Sing | Jul25         | 20,000        | Bought | 409.00 | 3             |
```

#### After Normalization & Calculation:

**Spread Price Calculation:** `425.50 - 409.00 = 16.50` ✅ (Jun-25 price - Jul-25 price)

**Normalized Match:**

```
| productname | quantityunits | spread_price | leg1_month | leg1_bs | leg2_month | leg2_bs | brokergroupid |
|-------------|---------------|--------------|------------|---------|------------|---------|---------------|
| 380cst      | 20000         | 16.50        | Jun25      | Sold    | Jul25      | Bought  | 3             |
```

**Result:** ✅ **SPREAD MATCH**

### Edge Cases for Spread Matching

#### Missing Data Handling:

- **Missing tradeid in exchange**: If `tradeid` is empty, match using brokergroupid + product + quantity criteria
- **Missing spread flag in trader**: If `spread` column is empty or missing "S", identify spreads by:
  - Entries with one leg having price > 0 and other leg having price = 0
  - **In sourceTraders.csv**, they will **usually** be placed consecutive one after another e.g. index X and index X+1 instead of apart.
  - **Spreads are identified as**: Opposite B/S directions for same product&quantityunits&brokergroupid and different contractmonth
  - **No timestamp requirement** for spread identification

#### Matching Tolerances:

- **Price tolerance**: Price calculation validation must be exact
- **No time window requirement**: Spread legs do NOT need to match by timestamp

#### Processing Notes:

- Process spread matching only on remaining unmatched trades after exact matching
- Prioritize spreads with tradeid and spread flags first, then handle missing data cases
- Each spread match removes 2 exchange trades and 2 trader trades from the unmatched pool

## 3. Crack Match Rules

### Definition

A **crack match** occurs when a trader executes a crack spread trade (price differential between refined products and crude oil) that appears in both data sources but may require unit conversion between metric tons (MT) and barrels (BBL). This is a high-confidence match type (90%) that handles specialized energy trading products.

**Processing Order**: Crack matching is performed AFTER exact matching and spread matching have been completed. This handles remaining unmatched crack spread trades that require unit normalization.

**Key Characteristics**:

- **Product identification**: Only trades with "crack" in the product name are eligible
- **Unit conversion**: Automatic handling of MT ↔ BBL conversions using 6.35 ratio
- **Conversion tolerances**: ±100 BBL or ±50 MT difference allowed for rounding
- **One-to-one matching**: Each crack match removes 1 trader trade and 1 exchange trade

### Crack Trade Identification

#### Key Characteristics:

- **Product type**: Contains "crack" in productname (e.g., "marine 0.5% crack")
- **Unit mismatch**: One source in MT, other in BBL requiring conversion
- **Price matching**: Same price after normalization
- **Same contract month**: Identical delivery period
- **Same brokergroupid**: Same broker handling the trade

### Required Matching Fields for Cracks

All 6 fields must match exactly (with unit conversion applied where needed):

1. **productname** - Must contain "crack" and match exactly after normalization
2. **contractmonth** - Contract delivery month must match exactly
3. **price** - Trade execution price must be identical (no price tolerance for crack matches)
4. **brokergroupid** - Broker group must match exactly
5. **quantityunits** - Quantity must match after unit conversion within tolerance (±100 BBL or ±50 MT)
6. **b/s** - Buy/Sell indicator must match exactly after normalization

### Crack Matching Logic

- **Product filter**: Only processes trades containing "crack" in product name
- **Unit-aware comparison**: Automatically converts between MT and BBL using 6.35 ratio
- **Dual tolerance validation**: Checks both BBL and MT tolerances for maximum flexibility
- **Exact field matching**: All non-quantity fields must match exactly (no tolerances except for unit conversion)

### Unit Conversion Rules

#### MT to BBL Conversion:

- **Conversion Factor**: `1 MT = 6.35 BBL` (approximately)
- **Formula**: `MT_quantity × 6.35 = BBL_quantity`
- **Reverse Formula**: `BBL_quantity ÷ 6.35 = MT_quantity`

#### Conversion Scenarios:

- **sourceTraders in MT, sourceExchange in BBL**: Convert MT to BBL for comparison
- **sourceTraders in BBL, sourceExchange in MT**: Convert BBL to MT for comparison
- **Both in same units**: No conversion needed, direct comparison

#### Conversion Tolerance:

- Allow ±100 BBL or ±50 MT difference due to rounding in conversions

### Crack-Specific Normalization Rules

#### Unit Normalization:

- Standardize unit abbreviations: `"mt"` ↔ `"MT"`, `"bbl"` ↔ `"BBL"`
- Apply conversion factor when units differ

### Example: Crack Match

#### Before Normalization:

**sourceTraders.csv:**

```
| tradedate | tradetime | productname       | quantityunits | unit | price | contractmonth | B/S | brokergroupid |
|-----------|-----------|-------------------|---------------|------|-------|---------------|-----|---------------|
| 15/5/2025 | 10:49     | marine 0.5% crack | 2520          | mt   | 11.95 | Jul-25        | S   | 3             |
```

**sourceExchange.csv:**

```
| tradedate      | tradetime     | productname       | quantityunits | unit | price | contractmonth | b/s  | brokergroupid |
|----------------|---------------|-------------------|---------------|------|-------|---------------|------|---------------|
| May 15, 2025   | 02:49:09 AM   | marine 0.5% crack | 16,000        | bbl  | 11.95 | Jul-25        | Sold | 3             |
```

#### After Normalization & Conversion:

**Unit Conversion**: `2520 MT × 6.35 = 16,002 BBL` ≈ `16,000 BBL` ✅ (within tolerance)

**Normalized Match:**

```
| productname  | quantityunits | unit | price | contractmonth | b/s  | brokergroupid |
|--------------|---------------|------|-------|---------------|------|---------------|
| marine 0.5% crack | 16000         | bbl  | 11.95 | Jul-25        | Sold | 3             |
```

**Result:** ✅ **CRACK MATCH**

### Edge Cases for Crack Matching

#### Unit Conversion Edge Cases:

- **Rounding differences**: Allow small quantity differences due to conversion rounding
- **Mixed units in same source**: Some exchanges may use both MT and BBL - normalize accordingly
- **Missing unit field**: Infer unit from quantity magnitude (large numbers typically BBL, smaller typically MT)

#### Processing Notes:

- Process crack matching only on remaining unmatched trades after exact and spread matching
- Apply unit conversion before all other matching criteria
- Each crack match removes 1 exchange trade and 1 trader trade from the unmatched pool
- Prioritize exact unit matches first, then apply conversion matching

## 4. Complex Crack Match Rules (2-Leg with Brent Swap)

### Definition

A **complex crack match** occurs when a trader executes a crack spread trade that corresponds to a combination of two separate exchange trades: the base product trade and a Brent swap trade. This represents a more sophisticated crack trading strategy where the crack spread is calculated from the differential between the refined product and crude oil (Brent) prices.

**Processing Order**: Complex crack matching is performed AFTER other simplier matching types have been completed. This handles more complex scenarios where crack products need to be matched against combinations of base product + Brent swap trades.

### Complex Crack Trade Identification

#### Key Relationship:

- **Crack Product Formula**: `Crack Product = Base Product - Brent Swap`
- **Universal Application**: This relationship holds for any crack product (e.g., "380cst crack" = "380cst" - "brent swap")
- **2-Leg Exchange Structure**: Exchange shows two separate trades (base product + brent swap), trader shows single crack trade

#### Required Exchange Components:

1. **Base Product Trade**: Trade in the base product (e.g., "380cst")
2. **Brent Swap Trade**: Trade in "brent swap" or "Brent Swap"
3. **Opposite B/S Directions**: Base product and Brent swap must have opposite buy/sell directions
4. **Quantity Relationship**: After unit conversion, quantities must match the trader crack quantity

#### Required Trader Components:

1. **Crack Product**: Product name contains "crack" (e.g., "380cst crack")
2. **Single Trade Entry**: Shows as one consolidated crack trade
3. **Price Calculation**: Crack price derived from base product and Brent swap price differential

### Required Matching Fields for Complex Cracks

1. **Product Relationship**: Trader crack product base name must match exchange base product

   - `"380cst crack"` matches with `"380cst"` + `"brent swap"`
   - `"marine 0.5% crack"` matches with `"marine 0.5%"` + `"brent swap"`

2. **Contract Month**: All three trades (base product, brent swap, crack) must have identical contract months

3. **Quantity Matching**: After unit conversion, quantities must align:

   - Exchange base product quantity = trader crack quantity
   - Exchange brent swap quantity (converted from BBL to MT) ≈ trader crack quantity

4. **B/S Direction Logic**:

   - **Sell Crack** = **Sell Base Product** + **Buy Brent Swap**
   - **Buy Crack** = **Buy Base Product** + **Sell Brent Swap**

5. **Price Calculation**: `(Base Product Price ÷ 6.35) - Brent Swap Price = Crack Price`

6. **Broker Group**: All trades must have matching brokergroupid

### Unit Conversion for Complex Cracks

#### Critical Conversion Rules:

- **Brent Swap Units**: Always in BBL (barrels)
- **Base Product Units**: Typically in MT (metric tons)
- **Crack Product Units**: Typically in MT (metric tons)
- **Conversion Formula**: `BBL ÷ 6.35 = MT`
- **Price Adjustment**: Base product price must be divided by 6.35 when comparing to Brent price

#### Conversion Process:

1. Convert Brent swap quantity from BBL to MT: `13,000 BBL ÷ 6.35 ≈ 2,047 MT ≈ 2,000 MT`
2. Verify base product and crack quantities match (both in MT)
3. Apply price formula with unit conversion factor

### Example: Complex Crack Match

#### Exact Source Data:

**sourceExchange.csv (Two Separate Trades):**

```
| Row | productname | contractmonth | quantityunits | unit | price  | b/s    | brokergroupid |
|-----|-------------|---------------|---------------|------|--------|--------|---------------|
| 45  | Brent Swap  | Jun-25        | 13,000        | bbl  | 64.05  | Bought | 3             |
| 46  | 380cst      | Jun-25        | 2,000         | mt   | 427.99 | Sold   | 3             |
```

**sourceTraders.csv (Single Crack Trade):**

```
| Row | productname  | contractmonth | quantityunits | unit | price | b/s  | brokergroupid |
|-----|--------------|---------------|---------------|------|-------|------|---------------|
| 47  | 380cst crack | Jun-25        | 2,000         | mt   | 3.35  | Sold | 3             |
```

#### Matching Validation Process:

1. **Product Relationship**: ✅

   - Trader: "380cst crack" → Base product: "380cst"
   - Exchange has: "380cst" + "Brent Swap"

2. **Contract Month**: ✅

   - All trades: Jun-25

3. **Quantity Conversion & Matching**: ✅

   - Brent Swap: 13,000 BBL ÷ 6.35 ≈ 2,047 MT ≈ 2,000 MT
   - Base product: 2,000 MT
   - Crack: 2,000 MT
   - All quantities align after conversion

4. **B/S Direction Logic**: ✅

   - Trader: **Sell** 380cst crack
   - Exchange: **Sell** 380cst + **Buy** Brent Swap
   - Pattern matches: Sell Crack = Sell Base + Buy Brent

5. **Price Calculation**: ✅

   - Formula: (427.99 ÷ 6.35) - 64.05 = 67.40 - 64.05 = 3.35
   - Trader crack price: 3.35
   - **Perfect match**: 3.35 = 3.35

6. **Broker Group**: ✅
   - All trades: brokergroupid = 3

**Result:** ✅ **COMPLEX CRACK MATCH**

### Implementation Strategy

#### Processing Approach:

1. **Process After Other Matches**: Handle complex cracks only after exact, spread, simple crack matches are complete
2. **CHECK** units of the row to know if it is BBL or MT so you know a conversion is required
3. **Unit Normalization First**: Convert all BBL quantities to MT using ÷6.35 conversion
4. **Pattern Identification**: Look for unmatched crack products in trader data
5. **Combination Search**: For each crack, search for matching base product + brent swap pairs in exchange data
6. **Validation Cascade**: Apply all matching criteria in sequence
7. **Price Formula Verification**: Apply complex price calculation as final validation

#### Matching Tolerance:

- **Quantity Tolerance**: ±100 MT difference allowed for unit conversion rounding
- **Price Tolerance**: ±0.01 difference allowed for calculation precision
- **Product Name Matching**: Case-insensitive, normalized comparison

### Processing Notes

- Each complex crack match removes 2 exchange trades (base product + brent swap) and 1 trader trade from unmatched pool
- Maintains detailed mapping of which exchange trades combine to form the crack match
- Apply same universal normalization rules as other matching types
- Handles sophisticated 2-leg crack trading scenarios

## 5. Product Spread Match Rules

### Definition

A **product spread match** occurs when a trader executes a spread trade between two different products that appears as separate individual product trades in the exchange data but as a combined product spread notation in the trader data. This handles cases where product combinations are represented differently between data sources.

**Processing Order**: Product spread matching is performed AFTER exact matching, spread matching, crack matching, and aggregation matching have been completed. This handles remaining unmatched trades that represent product combinations rather than contract month spreads.

### Product Spread Trade Identification

#### Key Characteristics:

- **Product combination notation**: Exchange uses hyphenated product names (e.g., "marine 0.5%-380cst")
- **Separate product trades**: Trader data shows individual trades for each component product
- **Price relationship**: Spread price calculation matches the price differential between products. **Usually** 1 leg of the price is the spread price and the other leg is 0
- **Opposite B/S directions**: Component products have opposite buy/sell directions
- **Same fundamental details**: Contract month, quantity, and broker group must match

#### Exchange Data Indicators:

- **Hyphenated product name**: Contains "-" separator indicating product spread (e.g., "marine 0.5%-380cst")
- **Single trade entry**: Shows as one consolidated spread trade
- **Spread price**: Price represents the differential between the two products

#### Trader Data Indicators:

- **Separate product trades**: Two individual trades for each component product
- **Opposite B/S directions**: One product "Bought", the other "Sold"
- **Same quantity**: Both component trades have identical quantity
- **Price calculation**: Price differential matches exchange price

**IMPORTANT**: Timestamp matching is NOT required for product spread matching. Traders may enter component trades at different times due to manual entry processes or operational workflows.

### Required Matching Fields for Product Spreads

1. **Product relationship**: Exchange hyphenated name must match trader component products

   - "marine 0.5%-380cst" matches "marine 0.5%" + "380cst"

2. **Contract month**: All trades must have identical contract months

3. **Quantity**: All trades must have identical quantities

4. **Broker group**: All trades must have matching brokergroupid

5. **B/S direction logic**: Component trades must have opposite directions

6. **Price calculation**: Exchange price must equal trader price differential

### Product Spread Direction Logic

#### Sell Product Spread:

- **Exchange**: Sell "Product1-Product2" spread
- **Trader**: Sell Product1 + Buy Product2
- **Price calculation**: Product1_price - Product2_price = Spread_price

#### Buy Product Spread:

- **Exchange**: Buy "Product1-Product2" spread
- **Trader**: Buy Product1 + Sell Product2
- **Price calculation**: Product1_price - Product2_price = Spread_price

### Example: Product Spread Match

#### Source Data from Current System:

**sourceTraders.csv (Separate Product Trades):**

```
| Index | productname | contractmonth | quantityunits | price | B/S    | brokergroupid |
|-------|-------------|---------------|---------------|-------|--------|---------------|
| 23    | marine 0.5% | Aug-25        | 3000          | 68.0  | Sold   | 3             |
| 24    | 380cst      | Aug-25        | 3000          | 0.0   | Bought | 3             |
```

**sourceExchange.csv (Combined Product Spread):**

```
| Index | productname       | contractmonth | quantityunits | price | b/s  | brokergroupid |
|-------|-------------------|---------------|---------------|-------|------|---------------|
| 27    | marine 0.5%-380cst| Aug-25        | 3000          | 68.0  | Sold | 3             |
```

#### Matching Validation Process:

1. **Product Relationship**: ✅

   - Exchange: "marine 0.5%-380cst" → Components: "marine 0.5%" + "380cst"
   - Trader has: "marine 0.5%" + "380cst"

2. **Contract Month**: ✅

   - All trades: Aug-25

3. **Quantity**: ✅

   - All trades: 3000

4. **Broker Group**: ✅

   - All trades: brokergroupid = 3

5. **B/S Direction Logic**: ✅

   - Exchange: **Sell** marine 0.5%-380cst spread
   - Trader: **Sell** marine 0.5% + **Buy** 380cst
   - Pattern matches: Sell spread = Sell first product + Buy second product

6. **Price Calculation**: ✅
   - Formula: 68.0 - 0.0 = 68.0
   - Exchange spread price: 68.0
   - **Perfect match**: 68.0 = 68.0

**Result:** ✅ **PRODUCT SPREAD MATCH**

### Product Spread Processing Logic

#### Product Name Parsing:

- **Split on hyphen**: "marine 0.5%-380cst" → ["marine 0.5%", "380cst"]
- **Case normalization**: Apply universal product name normalization rules

#### Price Calculation Logic:

- **Identify component prices**: Extract prices from trader component trades
- **Calculate differential**: First_product_price - Second_product_price
- **Validate against exchange**: Calculated differential must match exchange spread price

#### Matching Algorithm:

1. **Parse exchange product spreads**: Identify hyphenated product names in unmatched exchange data
2. **Extract component products**: Split hyphenated names into individual product components
3. **Search trader components**: Look for matching individual product trades in unmatched trader data
4. **Validate trade details**: Ensure contract month, quantity, and broker group match
5. **Validate B/S logic**: Confirm opposite directions match spread direction
6. **Validate price calculation**: Verify price differential calculation

### Implementation Strategy

#### Processing Approach:

1. **Process After Aggregation**: Handle product spreads only after simpler matching types are complete
2. **Pattern Recognition**: Identify hyphenated product names in exchange data
3. **Component Matching**: Search for individual component trades in trader data
4. **Direction Validation**: Apply B/S logic rules for spread direction
5. **Price Formula Verification**: Apply price calculation as final validation
6. **Broker group validation**: All trades must share the same broker

### Processing Notes

- Each product spread match removes 1 exchange trade and 2 trader trades from unmatched pool
- Maintains detailed mapping of which trader trades combine to form the spread match
- Apply same universal normalization rules as other matching types
- Handles sophisticated product combination trading scenarios
- Processed before low-confidence matches to catch clear product spread patterns

## 6. Aggregation Match Rules

### Definition

An **aggregation match** occurs when the same trade is represented differently between sources - either split into multiple smaller entries in one source and combined in the other, or vice versa. This handles cases where trade quantities are disaggregated or aggregated between the two data sources.

**Processing Order**: Aggregation matching is performed AFTER exact matching, spread matching, and crack matching have been completed. This handles remaining unmatched trades that may be split or combined representations of the same underlying trade.

### Aggregation Trade Identification

#### Key Characteristics:

- **Same fundamental trade details**: Product, contract month, price, broker group, and B/S direction must match
- **Quantity relationship**: Sum of smaller trades equals the larger single trade
- **Same brokergroupid**: All trades must be from the same broker group

**IMPORTANT**: Timestamp matching is NOT strictly required for aggregation matching. Traders may enter aggregated trades at different times due to manual entry processes, system delays, or operational workflows.

### Types of Aggregation Scenarios

#### Scenario A: Multiple Trader Entries → Single Exchange Entry

- **sourceTraders**: Multiple entries with identical details except smaller quantities
- **sourceExchange**: Single entry with quantity equal to sum of trader entries

#### Scenario B: Single Trader Entry → Multiple Exchange Entries

- **sourceTraders**: Single entry with larger quantity
- **sourceExchange**: Multiple entries with quantities that sum to trader quantity

### Required Matching Fields for Aggregation

1. **productname** - Must match exactly (after normalization)
2. **contractmonth** - Contract delivery month must be identical
3. **price** - Trade execution price must be identical across all entries
4. **brokergroupid** - Broker group must match for all entries
5. **b/s** - Buy/Sell indicator must match (after normalization)
6. **Quantity sum validation** - Sum of split trades must equal aggregated trade

### Example: Aggregation Match (Multiple Traders → Single Exchange)

#### Before Normalization:

**sourceTraders.csv (Split Entries):**

```
| teamid | tradedate | tradetime | productname | quantityunits | price | contractmonth | B/S | brokergroupid |
|--------|-----------|-----------|-------------|---------------|-------|---------------|-----|---------------|
| 1      | 15/5/2025 | 14:00     | marine 0.5% | 2000          | 473   | Aug-25        | S   | 3             |
| 1      | 15/5/2025 | 14:00     | marine 0.5% | 2000          | 473   | Aug-25        | S   | 3             |
```

**sourceExchange.csv (Aggregated Entry):**

```
| tradetime        | productname | contractmonth | quantityunits | price | b/s  | brokergroupid |
|------------------|-------------|---------------|---------------|-------|------|---------------|
| 06:03:43 AM GMT  | marine 0.5% | Aug-25        | 4,000         | 473   | Sold | 3             |
```

#### After Normalization & Aggregation:

**Quantity Validation**: `2000 + 2000 = 4000` ✅

**Normalized Match:**

```
| productname | contractmonth | total_quantity | price | b/s  | brokergroupid | trader_entries | exchange_entries |
|-------------|---------------|----------------|-------|------|---------------|----------------|------------------|
| marine 0.5% | Aug-25        | 4000           | 473   | Sold | 3             | [idx1, idx2]   | [idx3]          |
```

**Result:** ✅ **AGGREGATION MATCH**

### Aggregation-Specific Rules

#### Quantity Aggregation Logic:

- **Sum validation**: Total quantity of split entries must exactly equal aggregated entry quantity
- **No partial matches**: All split entries must be included in the aggregation match
- **Bidirectional matching**: Algorithm must handle both scenarios (many→one and one→many)

#### Aggregation Processing Logic:

- **Group by trade characteristics**: Group trades by product, contract, price, brokergroup, and B/S
- **Validate trade details**: Ensure all fundamental trade characteristics match exactly
- **Calculate quantity sums**: Verify quantity relationships before confirming match

#### Processing Priority:

- **Fundamental match validation**: All non-quantity fields must match exactly after normalization
- **Quantity conservation**: Total quantities must balance exactly between sources
- **No time dependency**: Processing does not depend on timestamp matching

#### Processing Notes:

- Process aggregation matching only on remaining unmatched trades after all other matching types
- Each aggregation match removes multiple entries from one source and single/multiple entries from the other
- Maintain detailed mapping of which specific entries were aggregated together
- **No overlapping matches**: Aggregated trades cannot be part of other match types
- Apply same universal normalization rules as other matching types

## 7. Aggregated Complex Crack Match Rules (2-Leg with Split Base Products)

### Definition

An **aggregated complex crack match** occurs when a trader executes a crack spread trade that corresponds to a combination of multiple exchange trades: multiple split base product trades and a Brent swap trade. This represents the most complex trading scenario where base products are aggregated before applying complex crack matching logic.

**Processing Order**: Aggregated complex crack matching is performed AFTER all other matching types have been completed, including simple complex crack matching. This ensures we only attempt this complex scenario when simpler matches have failed.

### Aggregated Complex Crack Trade Identification

#### Key Relationship:

- **Crack Product Formula**: `Crack Product = Aggregated Base Product - Brent Swap`
- **Base Product Aggregation**: Multiple base product trades with identical characteristics (price, B/S, contract, broker) are summed
- **3+ Leg Exchange Structure**: Exchange shows multiple base product trades + one brent swap trade, trader shows single crack trade

#### Required Exchange Components:

1. **Multiple Base Product Trades**: 2 or more trades in the same base product with identical price and B/S
2. **Brent Swap Trade**: Single trade in "brent swap" or "Brent Swap"
3. **Opposite B/S Directions**: Aggregated base product and Brent swap must have opposite buy/sell directions
4. **Quantity Relationship**: Sum of base product quantities must match trader crack quantity after unit conversion

#### Required Trader Components:

1. **Crack Product**: Product name contains "crack" (e.g., "marine 0.5% crack")
2. **Single Trade Entry**: Shows as one consolidated crack trade
3. **Price Calculation**: Crack price derived from aggregated base product and Brent swap price differential

### Required Matching Fields for Aggregated Complex Cracks

1. **Product Relationship**: Trader crack product base name must match exchange base product
2. **Contract Month**: All trades (multiple base products, brent swap, crack) must have identical contract months
3. **Base Product Aggregation**: Multiple base product trades must have:
   - Identical product names
   - Identical prices
   - Identical B/S directions
   - Identical contract months
   - Identical broker group IDs
4. **Quantity Matching**: After aggregation and unit conversion, quantities must align
5. **B/S Direction Logic**: Same as simple complex crack matching
6. **Price Calculation**: `(Aggregated Base Product Price ÷ 6.35) - Brent Swap Price = Crack Price`
7. **Broker Group**: All trades must have matching brokergroupid

### Example: Aggregated Complex Crack Match

#### Source Data:

**sourceExchange.csv (Split Base Product + Brent Swap):**

```
| Row | productname | contractmonth | quantityunits | unit | price  | b/s    | brokergroupid |
|-----|-------------|---------------|---------------|------|--------|--------|---------------|
| 0   | marine 0.5% | Aug-25        | 500           | mt   | 474.98 | Bought | 3             |
| 1   | marine 0.5% | Aug-25        | 1000          | mt   | 474.98 | Bought | 3             |
| 2   | brent swap  | Aug-25        | 10000         | bbl  | 63.75  | Sold   | 3             |
```

**sourceTraders.csv (Single Crack Trade):**

```
| Row | productname       | contractmonth | quantityunits | unit | price | b/s    | brokergroupid |
|-----|-------------------|---------------|---------------|------|-------|--------|---------------|
| 0   | marine 0.5% crack | Aug-25        | 1500          | mt   | 11.05 | Bought | 3             |
```

#### Matching Validation Process:

1. **Base Product Aggregation**: ✅

   - marine 0.5%: 500 MT + 1000 MT = 1500 MT (Bought)
   - Same price (474.98), same B/S (Bought), same contract (Aug-25), same broker (3)

2. **Quantity Conversion & Matching**: ✅

   - Brent Swap: 10,000 BBL ÷ 6.35 ≈ 1,575 MT ≈ 1,500 MT (within tolerance)
   - Aggregated base product: 1,500 MT
   - Crack: 1,500 MT

3. **B/S Direction Logic**: ✅

   - Trader: **Buy** marine 0.5% crack
   - Exchange: **Buy** marine 0.5% (aggregated) + **Sell** Brent Swap
   - Pattern matches: Buy Crack = Buy Base + Sell Brent

4. **Price Calculation**: ✅

   - Formula: (474.98 ÷ 6.35) - 63.75 = 74.80 - 63.75 = 11.05
   - Trader crack price: 11.05
   - **Perfect match**: 11.05 = 11.05

5. **Contract Month & Broker Group**: ✅
   - All trades: Aug-25, brokergroupid = 3

**Result:** ✅ **AGGREGATED COMPLEX CRACK MATCH**

### Implementation Strategy

#### Processing Approach:

1. **Process Last**: Handle aggregated complex cracks only after other simplier matching types have been completed
2. **Preserve Simple Logic**: Never interfere with standard complex crack matching
3. **Aggregation First**: Group potential base product trades by characteristics before attempting crack matching
4. **Higher Tolerances**: Apply increased tolerances for quantity (±100 MT) and price (±0.01) due to complexity
5. **Lower Confidence**: Apply reduced confidence score (65%) due to multiple complexity factors

#### Matching Tolerance:

- **Quantity Tolerance**: ±100 MT difference allowed for aggregation + unit conversion precision
- **Price Tolerance**: ±0.01 difference allowed for aggregated calculation complexity
- **Product Name Matching**: Case-insensitive, normalized comparison

#### Edge Case Priority:

- **Fallback Only**: Only attempt when simpler complex crack matching fails
- **No Interference**: Ensure this doesn't break any existing matching logic
- **Clear Separation**: Treat as completely separate match type with own processing

### Processing Notes

- Each aggregated complex crack match removes 3+ exchange trades (multiple base products + brent swap) and 1 trader trade from unmatched pool
- Maintains detailed mapping of which exchange trades are aggregated and combined
- Apply same universal normalization rules as other matching types
- Handles the most complex trading scenarios in the entire matching hierarchy
- Processed with lowest priority to ensure it doesn't interfere with simpler matches

## 8. Crack Roll Match Rules (Calendar Spread of Crack Positions)

### Definition

A **crack roll match** occurs when a trader executes a calendar spread of crack positions (rolling from one contract month to another) that appears as consecutive crack trades in trader data but corresponds to two complete crack positions (base product + brent swap) in exchange data for each contract month.

**Processing Order**: Crack roll matching is performed as the second-to-last step, after all other matching types except the complex decomposition netting rule. This handles sophisticated crack calendar spread scenarios.

### Crack Roll Trade Identification

#### Key Characteristics:

- **Adjacent Trading**: Crack trades are typically keyed consecutively (index X and X+1)
- **Calendar Spread Pattern**: Two crack products with different contract months
- **Price Pattern**: One leg has actual spread price, other leg has price = 0.0
- **Opposite B/S Directions**: One crack Sold, other crack Bought
- **Same Underlying Product**: Both cracks reference the same base product
- **Unit Conversion Tolerance**: BBL to MT conversions require ±145 MT tolerance minimum

#### Required Trader Components:

1. **Consecutive Crack Trades**: Two crack trades with adjacent or near-adjacent indices
2. **Different Contract Months**: Each crack references different delivery periods
3. **Price Spread Pattern**: One trade has calculated spread price, other has price = 0.0
4. **Opposite B/S**: One trade Sold, other Bought
5. **Same Broker and Quantity**: Identical brokergroupid and quantity (with conversion tolerance)

#### Required Exchange Components:

1. **Complete Crack Positions**: For each contract month, both base product and brent swap trades
2. **Quantity Alignment**: Brent swap quantities (in BBL) convert to match crack quantities (in MT)
3. **B/S Direction Logic**: Each exchange crack position follows standard crack logic
4. **Price Calculation**: Each crack price = (base product price ÷ 6.35) - brent swap price

### Required Matching Fields for Crack Rolls

1. **Product Relationship**: Both trader cracks must reference same base product

   - `"380cst crack"` matches with `"380cst"` + `"brent swap"` for each contract month

2. **Contract Month Matching**: Each trader crack contract must match corresponding exchange trades

3. **Quantity Matching with Tolerance**: After unit conversion, quantities must align within ±145 MT

   - Trader crack quantity ≈ Exchange base product quantity
   - Trader crack quantity ≈ Exchange brent swap quantity (converted from BBL to MT)

4. **B/S Direction Logic**: Each crack position must follow proper crack trading logic

   - **Sell Crack** = **Sell Base Product** + **Buy Brent Swap**
   - **Buy Crack** = **Buy Base Product** + **Sell Brent Swap**

5. **Price Calculation Validation**: Calculated exchange crack prices must match trader pattern

   - One calculated crack price matches trader non-zero price
   - Price difference between calculated cracks matches trader spread

6. **Broker Group**: All trades must have matching brokergroupid

### Unit Conversion with Enhanced Tolerance

#### Critical Conversion Rules:

- **Conversion Factor**: `1 MT = 6.35 BBL` (approximately)
- **Enhanced Tolerance**: ±145 MT minimum for crack roll matching
- **Real Example**: 39,000 BBL ÷ 6.35 = 6,141 MT ≈ 6,000 MT (within ±145 MT tolerance)
- **Bidirectional Tolerance**: Apply tolerance for both BBL→MT and MT→BBL conversions

### Example: Crack Roll Match

#### Source Data from Unmatched Trades:

**sourceTraders.csv (Crack Roll):**

```
| Index | productname  | contractmonth | quantityunits | price | B/S    | brokergroupid |
|-------|--------------|---------------|---------------|-------|--------|---------------|
| 47    | 380cst crack | Jul-25        | 6000          | -0.5  | Sold   | 3             |
| 48    | 380cst crack | Sep-25        | 6000          | 0.0   | Bought | 3             |
```

**sourceExchange.csv (Two Complete Crack Positions):**

```
| Index | productname | contractmonth | quantityunits | price  | b/s    | brokergroupid |
|-------|-------------|---------------|---------------|--------|--------|---------------|
| 57    | Brent Swap  | Jul-25        | 39000         | 75.35  | Bought | 3             |
| 58    | 380cst      | Jul-25        | 6000          | 472.44 | Sold   | 3             |
| 59    | 380cst      | Sep-25        | 6000          | 459.74 | Bought | 3             |
| 60    | Brent Swap  | Sep-25        | 39000         | 72.85  | Sold   | 3             |
```

#### Matching Validation Process:

**Step 1: Crack Position Calculation (Jul-25)**

- Base Product: 380cst Jul-25, 6000 MT, 472.44, Sold
- Brent Swap: Jul-25, 39000 BBL ÷ 6.35 = 6141 MT ≈ 6000 MT (within ±145 MT tolerance), 75.35, Bought
- Crack Price: (472.44 ÷ 6.35) - 75.35 = 74.40 - 75.35 = -0.95
- B/S Logic: Sell Crack = Sell Base + Buy Brent ✅

**Step 2: Crack Position Calculation (Sep-25)**

- Base Product: 380cst Sep-25, 6000 MT, 459.74, Bought
- Brent Swap: Sep-25, 39000 BBL ÷ 6.35 = 6141 MT ≈ 6000 MT (within ±145 MT tolerance), 72.85, Sold
- Crack Price: (459.74 ÷ 6.35) - 72.85 = 72.40 - 72.85 = -0.45
- B/S Logic: Buy Crack = Buy Base + Sell Brent ✅

**Step 3: Roll Pattern Matching**

- Calculated Jul-25 crack: -0.95
- Calculated Sep-25 crack: -0.45
- Roll spread: -0.95 - (-0.45) = -0.5 (Jul-25 crack - Sep-25 crack, earlier minus later)
- Trader pattern: Jul-25 = -0.5, Sep-25 = 0.0
- **Match validation**: Roll spread (-0.5) equals trader non-zero price (-0.5) ✅

**Step 4: Final Validations**

1. **Product Relationship**: Both trader cracks are "380cst crack" ✅
2. **Contract Months**: Jul-25 and Sep-25 match ✅
3. **Quantities**: All 6000 MT (with conversion tolerance) ✅
4. **B/S Pattern**: Opposite directions (Sold/Bought) ✅
5. **Broker Group**: All trades brokergroupid = 3 ✅
6. **Price Calculation**: Roll spread matches trader pattern ✅

**Result:** ✅ **CRACK ROLL MATCH**

### Implementation Strategy

#### Processing Approach:

1. **Sequential Search**: Look for consecutive or near-consecutive crack trades in trader data
2. **Pattern Recognition**: Identify price pattern (one non-zero, one zero) with opposite B/S
3. **Exchange Position Building**: For each contract month, find matching base product + brent swap pairs
4. **Crack Price Calculation**: Calculate crack prices for each position using standard formula
5. **Roll Spread Validation**: Verify calculated roll spread matches trader price pattern

#### Matching Tolerance:

- **Quantity Tolerance**: ±145 MT minimum for unit conversion differences
- **Price Tolerance**: ±0.01 difference allowed for calculation precision
- **Index Proximity**: Allow some flexibility in consecutive indexing (±2 indices)

#### Critical Implementation Notes:

- **Enhanced Unit Tolerance**: Use larger tolerance for crack roll scenarios
- **Complex Price Logic**: Validate both crack calculations and roll spread mathematics
- **Adjacent Trade Detection**: Identify consecutive trading patterns in trader data
- **Complete Position Matching**: Ensure each crack corresponds to complete exchange position

### Processing Notes

- **Confidence Level**: 65% (complex scenario with multiple calculations)
- **Processing Priority**: Second-to-last (before complex decomposition netting only)
- **Match Removal**: Removes 4 exchange trades and 2 trader trades from unmatched pool
- **Calculation Audit**: Maintains detailed record of crack price calculations and roll spread validation
- **Enhanced Tolerance**: Uses increased unit conversion tolerance for realistic matching

## 9. Cross-Month Decomposition Match Rules

### Definition

A **cross-month decomposition match** occurs when a trader executes a complex position across different contract months that appears as consecutive trades with a price pattern (one actual price, one 0.0 price) in trader data, but corresponds to separate component trades in exchange data that need to be pieced together using crack-like calculation logic.

**Processing Order**: Cross-month decomposition matching is performed as one of the final steps, after crack roll matching but before the complex decomposition netting rule. This handles sophisticated cross-month trading scenarios that use similar calculation patterns to crack spreads but are not necessarily crack products.

### Cross-Month Decomposition Trade Identification

#### Key Characteristics:

- **Consecutive Trading Pattern**: Typically trades are keyed consecutively (index X and X+1) in trader data
- **Cross-Month Structure**: Two trades with different contract months
- **Price Pattern**: One leg has actual calculated price, other leg has price = 0.0
- **Different Products**: Trades may involve different products (e.g., 380cst + Brent Swap)
- **Decomposition Logic**: Exchange shows separate component trades that need to be combined using calculation formulas
- **Unit Conversion Tolerance**: BBL to MT conversions require enhanced tolerance due to different product units

#### Pattern Recognition:

**Key Insight**: In sourceTrader CSV files, you can identify potential groups when you see consecutive indices with one having a 0.0 price. When this pattern appears, there must be some combination in the exchange source file that can be matched using decomposition logic.

#### Required Trader Components:

1. **Consecutive Index Pattern**: Two trades with adjacent or near-adjacent indices
2. **Price Pattern**: One trade has calculated price, other has price = 0.0
3. **Cross-Month Structure**: Different contract months between the two trades
4. **Quantity Relationship**: Both trades have same quantity (with unit conversion tolerance)
5. **Opposite or Related B/S**: Trading directions that indicate a complex position

#### Required Exchange Components:

1. **Component Trade Matching**: Separate trades that correspond to each trader component
2. **Calculation Relationship**: Trades that when combined using formula create the trader's non-zero price
3. **Unit Conversion**: Handle BBL ↔ MT conversions with enhanced tolerance
4. **Broker Group Matching**: All trades must share the same brokergroupid

### Required Matching Fields for Cross-Month Decomposition

1. **Product Relationship**: Exchange component trades must relate to trader products

   - May involve different products (e.g., 380cst + Brent Swap)
   - Support crack-like calculations: (base_product_price ÷ 6.35) - swap_price

2. **Contract Month Matching**: Each trader trade must correspond to exchange trades for the same contract month

3. **Quantity Matching with Enhanced Tolerance**: After unit conversion, quantities must align

   - Allow ±145 MT tolerance minimum for unit conversion differences
   - Handle BBL to MT conversions: 64,000 BBL ÷ 6.35 ≈ 10,079 MT ≈ 10,000 MT

4. **Price Calculation Validation**: Calculated exchange price must match trader's non-zero price

   - Use formula: (base_product_price ÷ 6.35) - swap_price = trader_price
   - Must match within standard price tolerance

5. **B/S Direction Logic**: Exchange components must have appropriate buy/sell directions

   - For crack-like calculations: opposite directions between base product and swap

6. **Broker Group**: All trades must have matching brokergroupid

### Example: Cross-Month Decomposition Match

#### Source Data from Unmatched Trades:

**sourceTraders.csv (Cross-Month Pattern):**

```
| Index | productname | contractmonth | quantityunits | price | B/S    | brokergroupid |
|-------|-------------|---------------|---------------|-------|--------|---------------|
| 42    | 380cst      | Aug-25        | 10000         | -1.6  | Sold   | 3             |
| 43    | Brent Swap  | Jul-25        | 64000         | 0.0   | Bought | 3             |
```

**sourceExchange.csv (Separate Components):**

```
| Index | productname | contractmonth | quantityunits | price  | b/s    | brokergroupid |
|-------|-------------|---------------|---------------|--------|--------|---------------|
| 47    | Brent Swap  | Jul-25        | 64000         | 75.0   | Bought | 3             |
| 48    | 380cst      | Aug-25        | 10000         | 466.09 | Sold   | 3             |
```

#### Matching Validation Process:

**Step 1: Pattern Recognition**

- Trader: Consecutive indices 42-43 with price pattern (-1.6, 0.0)
- Cross-month: Aug-25 (380cst) and Jul-25 (Brent Swap)
- Price decomposition needed: -1.6 must be calculated from exchange components

**Step 2: Component Identification**

- Exchange Index 47: Brent Swap Jul-25, 64000 BBL, 75.0, Bought
- Exchange Index 48: 380cst Aug-25, 10000 MT, 466.09, Sold
- Products match trader components ✅

**Step 3: Unit Conversion & Quantity Matching**

- Brent Swap: 64,000 BBL ÷ 6.35 = 10,079 MT ≈ 10,000 MT (within ±145 MT tolerance) ✅
- 380cst: 10,000 MT (exact match) ✅
- Quantity alignment confirmed ✅

**Step 4: B/S Direction Validation**

- Trader: 380cst Sold, Brent Swap Bought
- Exchange: 380cst Sold, Brent Swap Bought
- Directions match exactly ✅

**Step 5: Price Calculation**

- Formula: (380cst_price ÷ 6.35) - brent_swap_price
- Calculation: (466.09 ÷ 6.35) - 75.0 = 73.39 - 75.0 = -1.61 ≈ -1.6
- Trader price: -1.6
- **Price match**: -1.61 ≈ -1.6 (within tolerance) ✅

**Step 6: Final Validations**

1. **Product Relationship**: 380cst + Brent Swap components ✅
2. **Contract Months**: Aug-25 and Jul-25 match ✅
3. **Quantities**: 10,000 MT equivalent (with conversion tolerance) ✅
4. **B/S Pattern**: Matching directions ✅
5. **Broker Group**: All trades brokergroupid = 3 ✅
6. **Price Calculation**: Formula result matches trader price ✅

**Result:** ✅ **CROSS-MONTH DECOMPOSITION MATCH**

### Implementation Strategy

#### Processing Approach:

1. **Consecutive Pattern Detection**: Identify trader trade pairs with adjacent indices
2. **Price Pattern Recognition**: Look for one non-zero price and one 0.0 price
3. **Cross-Month Validation**: Confirm different contract months
4. **Exchange Component Search**: Find corresponding separate trades in exchange data
5. **Calculation Application**: Apply appropriate formula (crack-like or other) to validate price
6. **Enhanced Tolerance**: Use larger tolerances for unit conversion differences

#### Matching Tolerance:

- **Quantity Tolerance**: ±145 MT minimum for unit conversion differences
- **Price Tolerance**: ±0.01 difference allowed for calculation precision
- **Index Proximity**: Allow some flexibility in consecutive indexing
- **Unit Conversion**: Enhanced tolerance for BBL ↔ MT conversions

#### Critical Implementation Notes:

- **Pattern Recognition**: The 0.0 price leg is the key indicator of decomposition
- **Formula Flexibility**: Support different calculation patterns, not just crack formulas
- **Cross-Month Logic**: Handle different contract months between components
- **Unit Conversion**: Apply robust BBL ↔ MT conversion with enhanced tolerances

### Processing Notes

- **Confidence Level**: 60% (complex scenario with cross-month calculations)
- **Processing Priority**: Near the end (before complex decomposition netting only)
- **Match Removal**: Removes 2 exchange trades and 2 trader trades from unmatched pool
- **Calculation Audit**: Maintains detailed record of price calculations and formula validation
- **Enhanced Tolerance**: Uses increased unit conversion tolerance for realistic matching
- **Pattern Driven**: Relies on consecutive index patterns with 0.0 price indicators

## 10. Complex Product Spread Decomposition and Netting Match Rules

### Definition

A **complex product spread decomposition and netting match** occurs when exchange data contains both product spread trades (hyphenated products) and individual component product trades, which when mathematically decomposed and netted, reveal residual positions that match trader spread positions. This represents the most sophisticated matching scenario where multiple exchange trades are decomposed, netted against each other, and the residual positions matched to trader data.

**Processing Order**: This matching is performed as the FINAL step after ALL other matching types have been completed. This ensures we only attempt this extremely complex scenario when all simpler matches have failed.

### Complex Decomposition Trade Identification

#### Key Relationship:

- **Product Spread Decomposition**: Hyphenated exchange products are split into component positions
- **Component Netting**: Individual exchange component trades net against decomposed component positions
- **Residual Matching**: Remaining positions after netting must match trader positions exactly

#### Required Exchange Components:

1. **Product Spread Trades**: Exchange trades with hyphenated product names (e.g., "marine 0.5%-380cst")
2. **Component Product Trades**: Separate exchange trades for individual component products (e.g., "marine 0.5%")
3. **Perfect Netting**: Component positions must net to zero after decomposition
4. **Residual Positions**: Remaining positions after netting must form a coherent trader-matchable pattern

#### Required Trader Components:

1. **Residual Pattern Trades**: Trader trades that match the residual positions exactly
2. **Price Validation**: Calculated residual prices must match trader trade prices

### Required Matching Fields for Complex Decomposition

1. **Broker Group**: All involved trades must have identical brokergroupid
2. **Contract Month**: All trades involved must have matching contract months
3. **Quantity**: All trades must have identical quantities
4. **Perfect Component Netting**: Component products must net to exactly zero
5. **Residual Position Matching**: Remaining positions must match trader positions exactly
6. **Price Calculation Validation**: Derived residual prices must equal trader prices

### Decomposition and Netting Logic

#### Step 1: Product Spread Decomposition

- **Hyphenated Product Parsing**: "marine 0.5%-380cst" becomes two virtual positions:
  - If exchange **Buys** the spread: **Buy** marine 0.5% + **Sell** 380cst
  - If exchange **Sells** the spread: **Sell** marine 0.5% + **Buy** 380cst

#### Step 2: Component Netting

- **Perfect Cancellation**: Virtual component positions must exactly cancel with actual exchange component trades
- **Netting Validation**: After netting, component products must have zero net position

#### Step 3: Residual Identification

- **Remaining Positions**: Only residual product positions remain after complete component netting
- **Coherent Pattern**: Residual positions must form a logical trading pattern

#### Step 4: Price Assignment and Calculation

- **Direct Price Assignment**: Assign actual exchange trade prices to component products
- **Residual Price Derivation**: Calculate residual product prices using spread mathematics
- **Validation**: Derived prices must match trader trade prices exactly

### Example: Complex Product Spread Decomposition Match

#### Source Data:

**sourceExchange.csv (Product Spreads + Components):**

```
| Index | productname       | contractmonth | quantityunits | price | b/s    | brokergroupid |
|-------|-------------------|---------------|---------------|-------|--------|---------------|
| 35    | marine 0.5%-380cst| Jul-25        | 5000          | 68.0  | Bought | 3             |
| 36    | marine 0.5%-380cst| Aug-25        | 5000          | 67.5  | Sold   | 3             |
| 39    | marine 0.5%       | Jul-25        | 5000          | 539.0 | Sold   | 3             |
| 40    | marine 0.5%       | Aug-25        | 5000          | 533.5 | Bought | 3             |
```

**sourceTraders.csv (Residual Pattern):**

```
| Index | productname | contractmonth | quantityunits | price | B/S    | brokergroupid |
|-------|-------------|---------------|---------------|-------|--------|---------------|
| 34    | 380cst      | Jul-25        | 5000          | 5.0   | Sold   | 3             |
| 35    | 380cst      | Aug-25        | 5000          | 0.0   | Bought | 3             |
```

#### Matching Validation Process:

**Step 1: Product Spread Decomposition**

- Exchange 35: **Buy** marine 0.5%-380cst Jul-25 → **Buy** marine 0.5% Jul-25 + **Sell** 380cst Jul-25
- Exchange 36: **Sell** marine 0.5%-380cst Aug-25 → **Sell** marine 0.5% Aug-25 + **Buy** 380cst Aug-25

**Virtual Positions After Decomposition:**

```
| Product      | Contract | Quantity | B/S    | Source        | Price Context |
|--------------|----------|----------|--------|---------------|---------------|
| marine 0.5%  | Jul-25   | 5000     | Bought | Ex35 decomp   | (to be calc)  |
| 380cst       | Jul-25   | 5000     | Sold   | Ex35 decomp   | (to be calc)  |
| marine 0.5%  | Aug-25   | 5000     | Sold   | Ex36 decomp   | (to be calc)  |
| 380cst       | Aug-25   | 5000     | Bought | Ex36 decomp   | (to be calc)  |
| marine 0.5%  | Jul-25   | 5000     | Sold   | Ex39 direct   | 539.0         |
| marine 0.5%  | Aug-25   | 5000     | Bought | Ex40 direct   | 533.5         |
```

**Step 2: Component Netting**

- marine 0.5% Jul-25: **Buy** (Ex35 decomp) + **Sell** (Ex39 direct) = **Net Zero** ✅
- marine 0.5% Aug-25: **Sell** (Ex36 decomp) + **Buy** (Ex40 direct) = **Net Zero** ✅

**Step 3: Residual Positions**

```
| Product | Contract | Quantity | B/S    | Source        |
|---------|----------|----------|--------|---------------|
| 380cst  | Jul-25   | 5000     | Sold   | Ex35 decomp   |
| 380cst  | Aug-25   | 5000     | Bought | Ex36 decomp   |
```

**Step 4: Price Assignment and Calculation**

- Assign marine 0.5% Jul-25 = 539.0 (from Ex39)
- Assign marine 0.5% Aug-25 = 533.5 (from Ex40)
- Calculate 380cst Jul-25 = 539.0 - 68.0 = 471.0
- Calculate 380cst Aug-25 = 533.5 - 67.5 = 466.0
- Residual 380cst spread = 471.0 - 466.0 = 5.0

**Step 5: Trader Matching**

- Trader 34: 380cst Jul-25, 5.0, Sold ✅
- Trader 35: 380cst Aug-25, 0.0, Bought ✅
- Trader spread = 5.0 - 0.0 = 5.0 ✅

**All Validations:**

1. **Broker Group**: All trades have brokergroupid = 3 ✅
2. **Contract Months**: Jul-25 and Aug-25 consistently ✅
3. **Quantities**: All trades 5000 units ✅
4. **Perfect Component Netting**: marine 0.5% positions net to zero ✅
5. **Residual Position Matching**: 380cst pattern matches trader exactly ✅
6. **Price Calculation**: Derived spread (5.0) matches trader spread (5.0) ✅

**Result:** ✅ **COMPLEX PRODUCT SPREAD DECOMPOSITION AND NETTING MATCH**

### Implementation Strategy

#### Processing Approach:

1. **Process Absolutely Last**: Only attempt after ALL other matching types have been exhausted
2. **Systematic Decomposition**:
   - Identify all hyphenated products in exchange data
   - Decompose each into virtual component positions
   - Identify matching component trades in exchange data
3. **Perfect Netting Validation**: Verify components net to exactly zero
4. **Residual Pattern Recognition**: Identify coherent residual trading patterns
5. **Price Mathematics**: Apply complex price derivation and validation

#### Matching Tolerance:

- **Price Tolerance**: ±0.01 difference allowed for calculation precision
- **Quantity Matching**: Must be exact (no tolerance for this complex scenario)
- **Netting Requirement**: Component positions must net to exactly zero (no tolerance)

#### Critical Implementation Notes:

- **No Interference**: Must not break any existing simpler matching logic
- **Exhaustive Prerequisites**: Only attempt when all other matches have failed
- **Mathematical Rigor**: Apply precise price calculation and validation
- **Documentation**: Maintain detailed audit trail of decomposition and netting steps

### Processing Notes

- **Confidence Level**: 60% (lowest confidence due to extreme complexity)
- **Processing Priority**: Absolute last (after aggregated complex crack matching)
- **Match Removal**: Removes 4+ exchange trades and 2+ trader trades from unmatched pool
- **Audit Trail**: Maintains detailed record of decomposition, netting, and residual calculations
- **Fallback Nature**: Only processes trades that no other matching rule can handle
- **Mathematical Validation**: All price relationships must validate exactly
