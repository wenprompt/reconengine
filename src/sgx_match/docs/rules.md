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

## 🎯 Options Trading Examples

### Put Option Example

**Trader Data:**

| traderid | tradedate | tradetime | productid | productname | productgroupid | exchangegroupid | brokergroupid | exchclearingacctid | quantitylots | quantityunits | unit    | price  | contractmonth | strike  | specialComms | spread | b/s | RMKS | BKR     |
| -------- | --------- | --------- | --------- | ----------- | -------------- | --------------- | ------------- | ------------------ | ------------ | ------------- | ------- | ------ | ------------- | ------- | ------------ | ------ | --- | ---- | ------- |
| (empty)  | (empty)   | 14:39:35  | (empty)   | FE          | (empty)        | 1               | 3             | 2                  | 1000.0       | 100000.0      | (empty) | 100.05 | Dec25         | (empty) | (empty)      | S      | S   | icap | (empty) |

**Exchange Data:**

| tradedate  | tradedatetime       | dealid  | tradeid | productname | contractmonth | quantitylots | quantityunits | price  | clearingstatus | exchclearingacctid | trader  | brokergroupid | exchangegroupid | tradingsession | cleareddate | strike  | unit | put/call | b/s |
| ---------- | ------------------- | ------- | ------- | ----------- | ------------- | ------------ | ------------- | ------ | -------------- | ------------------ | ------- | ------------- | --------------- | -------------- | ----------- | ------- | ---- | -------- | --- |
| 2025-07-28 | 28/07/2025 02:43 pm | 1715113 | 3128301 | FE          | Dec25         | 1000         | 100000        | 100.05 | Cleared        | 2                  | (empty) | 3             | 1               | T              | 28/07/2025  | (empty) | MT   | (empty)  | S   |
