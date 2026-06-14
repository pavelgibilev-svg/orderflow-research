# Binance Tardis 2025 — strategy profitability sanity summary (pre-cost)

**Build:** 2026-05-22T16:56:43+00:00
**`PRE_COST_ONLY=YES`, `FEES_SLIPPAGE_INCLUDED=NO`, `PROFITABILITY_CLAIM=NO`. Target 2 % strict.**

## Answers

1. Telegram alerts for 12 days: **58** (~4.83/day)
2. Reached 2 % strict: **8** (= 13.79 %)
3. Correct-direction days (any feasible direction has matching signal): **11** / 12
4. Wrong-direction alerts total: **10**
5. Missed 2 % opportunity days (feasible but no matching signal): **0**
6. Filter vs baseline MODE-2 expectancy delta: **0.2468 pp**
7. Pre-cost positive expectancy (MODE 2): **YES**
8. STRATEGY_PROBABLY_PROFITABLE = **YES**

## Blockers (if any)

- 10 wrong-direction alerts on no-2%-feasible days

## Caveats

- Sample = 12 first-of-month days only; not a representative full year.
- 1-second price buckets (high/low/last). Sub-second target-vs-stop tiebreak ⇒ conservative stop-first.
- NO fees, NO slippage, NO funding. Real trading costs would reduce pnl materially.
- Engine triggers might not be the actual user-Telegram entry point in production.

## Final flag matrix

```
BINANCE_PROFITABILITY_SANITY_DONE = YES
TARGET_USED_FOR_PROFITABILITY = 2.0%
TELEGRAM_ALERTS_TOTAL = 58
TELEGRAM_ALERTS_PER_DAY = 4.833
TELEGRAM_ALERTS_REACHED_2PCT = 8
TELEGRAM_ALERT_REACHED_2PCT_RATE_PCT = 13.79
DAYS_WITH_2PCT_OPPORTUNITY = 11
DAYS_WITH_CORRECT_DIRECTION_SIGNAL = 11
DAYS_WITH_MISSED_2PCT_OPPORTUNITY = 0
WRONG_DIRECTION_ALERTS_TOTAL = 10
FILTERED_PRIMARY_UNIQUE_KEPT = 5
FILTERED_PRIMARY_UNIQUE_TOTAL = 7
FILTERED_PRIMARY_RECALL_PCT = 71.43
STRICT_LEDGER_TRADES = 19
STRICT_LEDGER_WINS = 5
STRICT_LEDGER_LOSSES = 3
STRICT_LEDGER_TIMEOUTS = 11
STRICT_LEDGER_WINRATE_PCT = 26.32
STRICT_LEDGER_EXPECTANCY_PRE_COST_PCT = 0.6423
STRICT_LEDGER_PROFIT_FACTOR_PRE_COST = 3.68
FILTER_IMPROVES_EXPECTANCY = UNCLEAR
PRE_COST_EXPECTANCY_POSITIVE = YES
STRATEGY_PROBABLY_PROFITABLE = YES
READY_FOR_PASSIVE_LIVE_OBSERVER = YES
READY_TO_INTEGRATE_FILTER_IN_STRATEGY = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- strategy / thresholds / `zoneDetector`: UNCHANGED
- NO new backtest spawned; pure post-hoc simulation over existing zones + price path
- NO `uniqueMoveId` in filter decision; NO future-leak in suppress
- target STRICT 2 % (no 0.5/1/1.5 considered as 'win')
- no production integration; no profitability claim