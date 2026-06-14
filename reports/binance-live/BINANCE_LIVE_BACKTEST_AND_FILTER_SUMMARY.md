# Binance live-recorder - backtest + filter summary

**Build:** 2026-05-21T18:55:18+00:00
**Dates:** ['2026-05-17', '2026-05-18', '2026-05-19', '2026-05-20']

## 1. Baseline vs filtered (aggregate)

- triggered: 41 -> 14
- reached_raw: 0 -> 0
- primary_unique_reached: 0 -> 0
- duplicate_reached: 0 -> 0
- failed_triggered: 41 -> 14
- baseline precision: 0.0 %  ->  filtered precision: 0.0 %
- primary recall: **None %**
- duplicate removal: **None %**
- failed reduction: **65.85 %**
- actionable signals/day: **3.5**

## 2. Compare to OKX Tardis 24-day best

| pool | scope | recall % | dup_rem % | fail_red % | actionable/day |
|---|---|---:|---:|---:|---:|
| OKX Tardis 24d (held-out) | 24 days, 21 primaries | 95.24 | 72.81 | 66.47 | 6.79 |
| Binance live | 4 days, 0 primaries | None | None | 65.85 | 3.5 |

## 3. Pre-cost sanity (fixed-stop 1 %, 24h, filtered subset)

- trades: 14  (wins=0, losses=6, timeouts=8)
- winrate: 0.0
- avg win %: None
- avg loss %: -1.0
- expectancy %/trade: **-0.4286**
- profit factor: **0.0**

## 4. Final flag matrix

```
BINANCE_LIVE_ARCHIVES_FOUND = YES
BINANCE_LIVE_DATES_DETECTED = ['2026-05-17', '2026-05-18', '2026-05-19', '2026-05-20']
BINANCE_LIVE_DAYS_PROCESSED = 4
BINANCE_LIVE_DATA_AUDIT_PASS = PARTIAL
BINANCE_LIVE_BACKTEST_RAN = YES
BINANCE_LIVE_BASELINE_UNIQUE_MOVES = 0
BINANCE_FILTER_VALIDATION_DONE = YES
FILTER_DECISION_USED_UNIQUEMOVEID = NO
FILTER_INVALID_FUTURE_LEAK = NO
BINANCE_PRIMARY_RECALL_PCT = None
BINANCE_DUPLICATE_REMOVAL_PCT = None
BINANCE_FAILED_REDUCTION_PCT = 65.85
BINANCE_ACTIONABLE_SIGNALS_PER_DAY = 3.5
BINANCE_BASELINE_PRECISION_PCT = 0.0
BINANCE_FILTERED_PRECISION_PCT = 0.0
BINANCE_FILTER_LOOKS_STABLE = NO
PRE_COST_PROFITABILITY_SANITY_DONE = YES
PRE_COST_EXPECTANCY_POSITIVE = NO
PRE_COST_PROFIT_FACTOR = 0.0
PROFITABILITY_CLAIM = NO
READY_FOR_PASSIVE_LIVE_OBSERVER = NO
READY_TO_INTEGRATE_FILTER_IN_STRATEGY = NO
MORE_VALIDATION_REQUIRED = YES
```

## 5. Hard rules honored

- strategy / thresholds / `zoneDetector`: UNCHANGED
- no engine code modified; live data fed via Tardis-style CSV.gz converter only
- post-trigger outcomes used only as evaluation labels
- no API keys; no live trading endpoints touched
- raw archives preserved