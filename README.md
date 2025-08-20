considerations

```
to get today's trade on sgx including T+1 need sgx titan export file trades from T and T+1 date bcos T+1 trades is on T+1 date even though its the previous day technically
iron ore and freight 710am-8pm T, 8pm-5.15 T+1
duplication can be handled by unique tradeID

traders have to give a non-duplicated copy each time

blotter files can be repeated but will be auto skipped with unique tradeIDs

traders internal tradefile MUST be reconciled

logs for changes made i.e. edit internal record

if quarter or cal on trader file > split to multiple columns
```

-if quarter or cal on trader file > split to multiple columns
-traders have to give a non-duplicated copy each time
-blotter files can be repeated but will be auto skipped with unique tradeIDs

- require = traders to give a list of the countarparty
- T+1 session and today's cleared date = T-1 days trades

SGX File:
-if quarter or cal on trader file > split to multiple columns
internal trade file has Q or Cal >

- trader file ignore internal

EEX file:

contract have quarters and strips to split
only take completed trades

Traders > trades table > filter by exchange and match with

---

MOPJ:
MOPJ_CRACK
92R
92R_CRACK
380cst
0.5: GNU micro, MFZ mini, MF4 normal, FDK balmo
380cst Crack
0.5 Crack

edge cases:

if some trades take forever to clear, that unmatched trade will have to roll over

every team will upload their netpos together instead of each trader by each trader

- iron ore: each table is 1 acct and each acct to 1 trader
- ffa: under Clearer column will be SGX1 for example for A1 and 1 clearing acct to 1 trader
- energy: 1 netpos file for 1 trading acct

all sgx traders file to match by product name first instead of ID for standardisation because petchem has BZF BZN and BZ

**NOTES FOR ENERGY MATCHING**
looks like debugging still not debugging well tier1-3 > try for 270625 file mainly tier1 issue
update claude
