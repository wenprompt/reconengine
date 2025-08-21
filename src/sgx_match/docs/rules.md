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
exchangegroupid,tradingsession,cleareddate,strike,unit,p/c,b/s
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

**Trader Data (sourceTraders.csv - Line 2):**
```
traderid: (empty)
tradedate: (empty) 
tradetime: 21:11:21
productname: FE
exchangegroupid: 1
brokergroupid: 3
exchclearingacctid: 2
quantitylots: 150.0
quantityunits: 15000.0
price: 101.65
contractmonth: Oct25
b/s: B
RMKS: fis
```

**Exchange Data (sourceExchange.csv - Example):**
```
tradedate: 25/7/2025
tradedatetime: 25/7/2025 21:14
dealid: 1714332
tradeid: 3127095
productname: FE
contractmonth: Oct25
quantitylots: 150
quantityunits: 15000
price: 101.65
clearingstatus: Cleared
exchclearingacctid: 2
trader: Wenjie Fan
brokergroupid: 3
exchangegroupid: 1
tradingsession: T+1
cleareddate: 28/7/2025
unit: MT
b/s: B
```

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

**Trader Data (Options with Strike):**
```
productname: FE
contractmonth: Dec25
quantityunits: 100000.0
price: 100.05
strike: (present)
b/s: S
brokergroupid: 3
exchclearingacctid: 2
```

**Exchange Data (Options with P/C):**
```
productname: FE
contractmonth: Dec25
quantityunits: 100000
price: 100.05
strike: 105.0
p/c: P
b/s: S
brokergroupid: 3
exchclearingacctid: 2
```

### Spread Trading Example

**Trader Data (Spread - Line 40-41):**
```
# Leg 1 (Sell)
quantityunits: 100000.0
price: 100.05
contractmonth: Dec25
spread: S
b/s: S

# Leg 2 (Buy)  
quantityunits: 100000.0
price: 101
contractmonth: Sep25
spread: B
b/s: B
```

## 🚫 Non-Duplication Rules

After matching, the system ensures:
1. **No Duplicate Trader IDs**: Each trader trade can only match once
2. **No Duplicate Deal/Trade IDs**: Each exchange trade can only match once
3. **Pool Management**: Matched trades are removed from the available pool
4. **Audit Trail**: Complete record of all matching decisions

## 📈 Product Coverage

### Supported Products
- **FE**: Iron Ore (Primary product in dataset)
- **PMX**: Palm Oil
- **CAPE**: Capesize Freight 
- **SMX**: Steel Making Material
- **M65**: Iron Ore 65%

### Contract Months
- **2025**: Jul25, Aug25, Sep25, Oct25, Nov25, Dec25
- **2026**: Jan26, Feb26, Mar26

## 🏢 Trading Participants

### Trader Remarks (RMKS)
- **fis**: FIS (Multiple trades)
- **ssy**: SSY (Shipbroker)
- **enmore**: Enmore Trading
- **bpi**: BPI Trading
- **icap**: ICAP (Interdealer broker)
- **gfi**: GFI Securities
- **mysteel**: MySteel (Information provider)

### Exchange Traders
- Wenjie Fan
- Various clearing members

## 🔍 Quality Assurance

### Data Validation Checks
1. **Clearing Status**: Only "Cleared" trades are processed
2. **Data Completeness**: Required fields must be present
3. **Price Validation**: Numeric price fields validated
4. **Date Formatting**: Consistent date/time handling
5. **Unit Conversion**: MT (Metric Tons) unit standardization

### Error Handling
- Malformed date/time entries are logged but processing continues
- Missing optional fields are handled gracefully
- Invalid clearing status trades are filtered out

## 📊 Performance Metrics

### Typical Dataset Statistics
- **Exchange Data**: ~368 trades
- **Trader Data**: ~47 trades  
- **Match Rate**: Varies by data quality and trade timing
- **Processing Time**: Sub-second for typical datasets

---

*This documentation is designed to be AI-readable and provides exact examples from the SGX data files for consistent understanding and processing.*
