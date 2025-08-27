# SGX Match Module - Matching Rules

This document provides comprehensive documentation for the **SGX Match Module** matching rules. Unlike the complex energy matching system, SGX matching focuses on iron ore (FE) futures and options traded on the Singapore Exchange.

## 🎯 Overview

The SGX matching system processes trades between trader and exchange data sources using a simplified rule-based approach focused on exact matching with universal field validation.

### Key Features

- **Simple Exact Matching**: Direct trade-to-trade matching based on key fields
- **Universal Field Validation**: Consistent brokergroupid and exchclearingacctid matching across all rules
- **Options Support**: Handles both futures and options (puts/calls) with strike prices
- **Non-Duplication**: Ensures each trade matches only once using pool management

## 📊 Data Structure

### Trader Data Fields (`sourceTraders.csv`)

```
traderid,tradedate,tradetime,productid,productname,productgroupid,exchangegroupid,
brokergroupid,exchclearingacctid,quantitylots,quantityunits,unit,price,contractmonth,
strike,specialComms,spread,b/s,RMKS,BKR
```

### Exchange Data Fields (`sourceExchange.csv`)

```
tradedate,tradedatetime,dealid,tradeid,productname,contractmonth,quantitylots,
quantityunits,price,clearingstatus,exchclearingacctid,trader,brokergroupid,
exchangegroupid,tradingsession,cleareddate,strike,unit,put/call,b/s
```

## 🔧 Universal Matching Fields

**ALL** matching rules must validate these universal fields:

- **brokergroupid**: Must match exactly between trader and exchange data
- **exchclearingacctid**: Must match exactly between trader and exchange data

## 📋 Rule 1: Exact Match

### Rule Description

Matches trades based on exact field matching with universal field validation.

### Matching Criteria

1. **productname**: Exact match (e.g., "FE")
2. **contractmonth**: Exact match (e.g., "Oct25")
3. **quantityunits**: Exact match (e.g., 15000.0)
4. **price**: Exact match (e.g., 101.65)
5. **b/s**: Exact match ("B" or "S")
6. **brokergroupid**: Universal field - exact match (e.g., "3")
7. **exchclearingacctid**: Universal field - exact match (e.g., "2")

### Real Data Example

**Trader Data (sourceTraders.csv):**

| traderid | tradedate | tradetime | productid | productname | productgroupid | exchangegroupid | brokergroupid | exchclearingacctid | quantitylots | quantityunits | unit    | price  | contractmonth | strike  | specialComms | spread  | b/s | RMKS | BKR     |
| -------- | --------- | --------- | --------- | ----------- | -------------- | --------------- | ------------- | ------------------ | ------------ | ------------- | ------- | ------ | ------------- | ------- | ------------ | ------- | --- | ---- | ------- |
| (empty)  | (empty)   | 21:11:21  | (empty)   | FE          | (empty)        | 1               | 3             | 2                  | 150.0        | 15000.0       | (empty) | 101.65 | Oct25         | (empty) | (empty)      | (empty) | B   | fis  | (empty) |

**Exchange Data (sourceExchange.csv):**

| tradedate  | tradedatetime       | dealid  | tradeid | productname | contractmonth | quantitylots | quantityunits | price  | clearingstatus | exchclearingacctid | trader     | brokergroupid | exchangegroupid | tradingsession | cleareddate | strike  | unit | put/call | b/s |
| ---------- | ------------------- | ------- | ------- | ----------- | ------------- | ------------ | ------------- | ------ | -------------- | ------------------ | ---------- | ------------- | --------------- | -------------- | ----------- | ------- | ---- | -------- | --- |
| 2025-07-25 | 25/07/2025 09:14 pm | 1714332 | 3127095 | FE          | Oct25         | 150          | 15000         | 101.65 | Cleared        | 2                  | Wenjie Fan | 3             | 1               | T+1            | 28/07/2025  | (empty) | MT   | (empty)  | B   |

### Match Validation

✅ **productname**: FE ↔ FE  
✅ **contractmonth**: Oct25 ↔ Oct25  
✅ **quantityunits**: 15000.0 ↔ 15000  
✅ **price**: 101.65 ↔ 101.65  
✅ **b/s**: B ↔ B  
✅ **brokergroupid**: 3 ↔ 3 (Universal Field)  
✅ **exchclearingacctid**: 2 ↔ 2 (Universal Field)

**Result**: ✅ MATCH - All criteria satisfied

## 📋 Rule 2: Spread Match

### Rule Description

A **spread match** identifies a calendar spread, where a trader's spread position (represented as two trades with a spread price) corresponds to two separate trades on the exchange. This is a 2-to-2 match.

### Matching Criteria

1.  **Universal Fields**: `brokergroupid` and `exchclearingacctid` must match across all four trades.
2.  **Product**: `productname` must be the same for all four trades.
3.  **Quantity**: `quantityunits` must be the same for all four trades.
4.  **Opposite Directions**:
    - The two trader trades must have opposite `b/s` values (one "B", one "S").
    - The two exchange trades must have opposite `b/s` values.
5.  **Legs Correspondence**: The `contractmonth` and `b/s` direction of each trader leg must match a corresponding exchange leg.
6.  **Price Calculation**: The difference between the exchange prices must equal the trader's spread price. The formula is: `(Price of Earlier Month Leg) - (Price of Later Month Leg) = Trader Spread Price`.

### Real Data Example

**Trader Data (sourceTraders.csv):**

| tradetime | productname | quantityunits | price | contractmonth | spread | b/s | brokergroupid | exchclearingacctid |
| --------- | ----------- | ------------- | ----- | ------------- | ------ | --- | ------------- | ------------------ |
| 13:47:08  | FE          | 155000        | -0.85 | Dec-25        | S      | S   | 3             | 2                  |
| 13:47:09  | FE          | 155000        | -0.85 | Aug-25        | S      | B   | 3             | 2                  |

**Exchange Data (sourceExchange.csv):**

| dealid  | productname | contractmonth | quantityunits | price  | b/s | brokergroupid | exchclearingacctid |
| ------- | ----------- | ------------- | ------------- | ------ | --- | ------------- | ------------------ |
| 1733680 | FE          | Aug-25        | 155000        | 101.80 | B   | 3             | 2                  |
| 1733680 | FE          | Dec-25        | 155000        | 102.65 | S   | 3             | 2                  |

### Match Validation

✅ **Universal Fields**: `brokergroupid` (3) and `exchclearingacctid` (2) match across all trades.  
✅ **Product**: All trades are for product "FE".  
✅ **Quantity**: All trades have `quantityunits` of 155000.  
✅ **Legs Correspondence**:

- Trader (Buy Aug-25) ↔ Exchange (Buy Aug-25)
- Trader (Sell Dec-25) ↔ Exchange (Sell Dec-25)  
  ✅ **Price Calculation**:
- Earlier Month (Aug-25) Price: 101.80
- Later Month (Dec-25) Price: 102.65
- Exchange Spread: `101.80 - 102.65 = -0.85`
- Trader Spread Price: `-0.85`
- The prices match.

**Result**: ✅ MATCH - All criteria satisfied

## 📋 Rule 3: Product Spread Match

### Rule Description

A **product spread match** identifies a product spread, where a trader's spread position (represented as two trades with the same spread price but different products) corresponds to two separate trades with different products on the exchange. This is a 2-to-2 match between different product types.

### Matching Criteria

1. **Universal Fields**: `brokergroupid` and `exchclearingacctid` must match across all four trades.
2. **Different Products**: The two trader trades must have different `productname` values (e.g., M65 and FE).
3. **Same Contract Month**: `contractmonth` must be the same for all four trades.
4. **Same Quantity**: `quantityunits` must be the same for all four trades.
5. **Opposite Directions**:
   - The two trader trades must have opposite `b/s` values (one "B", one "S").
   - The two exchange trades must have opposite `b/s` values.
6. **Product Correspondence**: The `productname` and `b/s` direction of each trader leg must match a corresponding exchange leg.
7. **Price Calculation**: The difference between the exchange prices must equal the trader's spread price. The formula is: `(M65 Price) - (FE Price) = Trader Spread Price`.
8. **Spread Indicator**: Trader trades must have spread indicator "PS" (Product Spread).

### Real Data Example

**Trader Data (sourceTraders.csv):**

| tradetime | productname | brokergroupid | exchclearingacctid | quantitylots | quantityunits | price | contractmonth | spread | b/s |
| --------- | ----------- | ------------- | ------------------ | ------------ | ------------- | ----- | ------------- | ------ | --- | --- |
| 14:37:32  | M65         | 3             | 2                  | 100          | 10000         | 15.65 | Sept-25       | PS     | S   | gfi |
| 14:37:32  | FE          | 3             | 2                  | 100          | 10000         | 15.65 | Sept-25       | PS     | B   | gfi |

**Exchange Data (sourceExchange.csv):**

| tradedate | tradedatetime   | dealid  | tradeid | productname | contractmonth | quantitylots | quantityunits | price  | brokergroupid | exchclearingacctid | b/s |
| --------- | --------------- | ------- | ------- | ----------- | ------------- | ------------ | ------------- | ------ | ------------- | ------------------ | --- |
| 25/8/2025 | 25/8/2025 15:11 | 1733632 | 3160166 | FE          | Sept-25       | 100          | 10000         | 103.10 | 3             | 2                  | B   |
| 25/8/2025 | 25/8/2025 15:11 | 1733632 | 3160167 | M65         | Sept-25       | 100          | 10000         | 118.75 | 3             | 2                  | S   |

### Match Validation

✅ **Universal Fields**: `brokergroupid` (3) and `exchclearingacctid` (2) match across all trades.  
✅ **Different Products**: Trader trades have M65 and FE products.  
✅ **Same Contract Month**: All trades are for "Sept-25".  
✅ **Same Quantity**: All trades have `quantityunits` of 10000.  
✅ **Product Correspondence**:

- Trader (Buy M65) ↔ Exchange (Sell M65)
- Trader (Sell FE) ↔ Exchange (Buy FE)

✅ **Price Calculation**:

- M65 Price: 118.75
- FE Price: 103.10
- Exchange Product Spread: `118.75 - 103.10 = 15.65`
- Trader Spread Price: `15.65`
- The prices match.

✅ **Spread Indicator**: Trader trades marked with "PS" (Product Spread).

**Result**: ✅ MATCH - All criteria satisfied
