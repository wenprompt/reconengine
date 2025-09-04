# EEX Match Module Rules

## Rule 1: Exact Matching (100% Confidence)

The EEX matching system uses a single exact matching rule that requires all fields to match exactly:

### Required Fields:
- `product_name` - Product identifier (e.g., CAPE)
- `contract_month` - Contract month (e.g., Oct25)
- `quantityunit` - Trade quantity in units
- `price` - Trade price
- `buy_sell` - Buy/Sell indicator (opposite for matching)
- `broker_group_id` - Universal field
- `exch_clearing_acct_id` - Universal field

### Matching Logic:
1. All fields must match exactly
2. Buy/Sell indicators must be opposite (trader Buy matches exchange Sell)
3. Universal fields must match

### Example Match:
- Trader: CAPE, Oct25, 5 units, 28125 price, Sell
- Exchange: CAPE, Oct25, 5 units, 28125 price, Buy
- Result: 100% confidence exact match