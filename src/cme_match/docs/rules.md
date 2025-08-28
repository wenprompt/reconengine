# CME Trade Matching Rules

## Universal Data Normalization Rules

**IMPORTANT**: The following normalization rules must be applied to ALL data from BOTH sources before any matching operations.

### Field Name Mapping

- `sourceTraders.b/s` ↔ `sourceExchange.b/s`
- `sourceTraders.contractmonth` ↔ `sourceExchange.contractmonth`
- `sourceTraders.quantitylots` ↔ `sourceExchange.quantitylots`
- `sourceTraders.brokergroupid` ↔ `sourceExchange.brokergroupid`
- `sourceTraders.exchclearingacctid` ↔ `sourceExchange.exchclearingacctid`
- `sourceTraders.productname` ↔ `sourceExchange.productname`
- `sourceTraders.price` ↔ `sourceExchange.price`

### Universal Value Normalization

**Apply to ALL records from BOTH data sources:**

- **Buy/Sell Values** (Standardized to B/S):

  - `"Buy"` → `"B"`
  - `"Sell"` → `"S"`
  - Case-insensitive input

- **Contract Month Format** (Standardized to "MMMYY"):

  - `"Oct-25"` → `"Oct25"`
  - `"April-26"` → `"Apr26"`

- **Product Name** (Case standardization):

  - `"lth"` → `"LTH"`
  - `"corn"` → `"CORN"`
  - Standardized to uppercase

- **Quantity Lots** (Cleaned numeric values):

  - Remove quotes, convert to numeric

- **Price** (Precise decimal values):
  - Convert to Decimal type for exact arithmetic

## 1. Exact Match Rules

### Required Matching Fields

All fields must match exactly after normalization:

1. **productname** - Product identifier
2. **contractmonth** - Contract delivery month
3. **quantitylots** - Trade quantity in lots
4. **b/s** - Buy/Sell indicator
5. **price** - Trade execution price
6. **brokergroupid** - Broker group identifier (universal field)
7. **exchclearingacctid** - Exchange clearing account (universal field)

### Example: LTH Futures Exact Match

**sourceTraders.csv:**

```
| productname | contractmonth | quantitylots | b/s | price | brokergroupid | exchclearingacctid |
|-------------|---------------|--------------|-----|-------|---------------|---------------------|
| LTH         | Oct-25        | 5            | S   | 10.5  | 3             | 2                   |
| LTH         | Nov-25        | 5            | S   | 10.5  | 3             | 2                   |
```

**sourceExchange.csv:**

```
| productname | contractmonth | quantitylots | b/s | price | brokergroupid | exchclearingacctid |
|-------------|---------------|--------------|-----|-------|---------------|---------------------|
| LTH         | Oct-25        | 5            | S   | 10.5  | 3             | 2                   |
| LTH         | Nov-25        | 5            | S   | 10.5  | 3             | 2                   |
```

**Match Results:**

- 2 exact matches found (100% confidence)
- All trader trades matched (100% trader match rate)
- All exchange trades matched (100% exchange match rate)
- Total match rate: 100%

```

```
