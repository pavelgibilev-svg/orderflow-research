# OKX direct partial March 2026 — strategy profitability sanity summary

**Build:** 2026-05-23T02:06:31+00:00
**Main metric: `PRE_COST_ONLY = YES`. Cost diagnostic separate. `PROFITABILITY_CLAIM = NO`.**
**Target 2 % strict.**

## Answers

1. Telegram alerts for 14 days: **103** (~7.36/day)
2. Reached 2 % strict: **21** (= 20.39 %)
3. Correct-direction days: **12** / 14
4. Wrong-direction alerts total: **15**
5. Missed 2 % opportunity days: **1**
6. Filter vs baseline MODE-2 expectancy delta: **0.1095 pp**
7. Pre-cost positive expectancy (MODE 2): **NO**
8. After-basic-cost positive expectancy (MODE 2, fees+slip~0.14 %): **NO**
9. STRATEGY_PROBABLY_PROFITABLE_ON_THIS_SAMPLE = **NO**

## Cross-venue compare (vs Binance Tardis 2025)

| metric | Binance Tardis 2025 (12d, 19 trades) | OKX direct March 2026 (14d) |
|---|---:|---:|
| strict ledger trades | 19 | 41 |
| winrate % | 26.32 | 26.83 |
| expectancy %/trade | +0.6423 | -0.0497 |
| profit factor | 3.68 | 0.92 |
| primary recall % | 71.43 | 100.0 |
| wrong-direction alerts | 10 | 15 |

## Final flag matrix

```
OKX_DIRECT_PROFITABILITY_SANITY_DONE = YES
TARGET_USED_FOR_PROFITABILITY = 2.0%
OKX_TELEGRAM_ALERTS_TOTAL = 103
OKX_TELEGRAM_ALERTS_PER_DAY = 7.357
OKX_TELEGRAM_ALERTS_REACHED_2PCT = 21
OKX_TELEGRAM_ALERT_REACHED_2PCT_RATE_PCT = 20.39
OKX_DAYS_WITH_2PCT_OPPORTUNITY = 13
OKX_DAYS_WITH_CORRECT_DIRECTION_SIGNAL = 12
OKX_DAYS_WITH_MISSED_2PCT_OPPORTUNITY = 1
OKX_WRONG_DIRECTION_ALERTS_TOTAL = 15
OKX_FILTERED_PRIMARY_UNIQUE_KEPT = 15
OKX_FILTERED_PRIMARY_UNIQUE_TOTAL = 15
OKX_FILTERED_PRIMARY_RECALL_PCT = 100.0
OKX_STRICT_LEDGER_TRADES = 41
OKX_STRICT_LEDGER_WINS = 11
OKX_STRICT_LEDGER_LOSSES = 24
OKX_STRICT_LEDGER_TIMEOUTS = 6
OKX_STRICT_LEDGER_WINRATE_PCT = 26.83
OKX_STRICT_LEDGER_EXPECTANCY_PRE_COST_PCT = -0.0497
OKX_STRICT_LEDGER_PROFIT_FACTOR_PRE_COST = 0.92
OKX_STRICT_LEDGER_EXPECTANCY_AFTER_BASIC_COST_PCT = -0.1897
OKX_STRICT_LEDGER_PROFIT_FACTOR_AFTER_BASIC_COST = 0.734
OKX_FILTER_IMPROVES_EXPECTANCY = YES
OKX_PRE_COST_EXPECTANCY_POSITIVE = NO
OKX_AFTER_COST_EXPECTANCY_POSITIVE = NO
OKX_STRATEGY_PROBABLY_PROFITABLE_ON_THIS_SAMPLE = NO
COMPARES_WELL_WITH_BINANCE_TARDIS_2025 = NO
READY_FOR_PASSIVE_LIVE_OBSERVER = YES
READY_TO_INTEGRATE_FILTER_IN_STRATEGY = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- strategy / thresholds / `zoneDetector`: UNCHANGED
- NO new backtest; pure post-hoc simulation over existing zones + price path
- NO `uniqueMoveId` in filter decision; NO future-leak in suppress
- target STRICT 2 % (no 0.5/1/1.5 considered as 'win')
- no production integration; no profitability claim