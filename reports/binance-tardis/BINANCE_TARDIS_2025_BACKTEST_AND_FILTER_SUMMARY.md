# Binance Tardis 2025 - backtest + filter master summary

**Build:** 2026-05-22T15:28:57+00:00

## 1. PART 1 - Binance live diagnostic (2026-05-17..20)

- 2 % feasible days: 2 / 4
- baseline triggered: 41   reached: 0
- filtered kept: 14   reached: 0
- filtered reached 0.5 %: 78.57 %   reached 1.0 %: 28.57 %   reached 1.5 %: 14.29 %   reached 2 %: 0.0 %
- median MFE 24h (filtered): 0.71 %   median MAE 24h (filtered): 0.87 %
- Verdict: TARGET_2PCT_TOO_HIGH_FOR_LIVE_SAMPLE = YES; ZONES_SHOW_SUB_2PCT_EDGE = YES; n_primary = 0 so primary recall undefined.

## 2. PART 2 - Binance Tardis 2025 baseline

| date | regime | zones | trig | reached | primary | dup | failed |
|---|---|---:|---:|---:|---:|---:|---:|
| 2025-01-01 | bullish | 28 | 16 | 0 | 0 | 0 | 16 |
| 2025-02-01 | bearish | 33 | 16 | 1 | 1 | 0 | 15 |
| 2025-03-01 | bullish | 28 | 16 | 2 | 1 | 1 | 14 |
| 2025-04-01 | bullish | 40 | 23 | 9 | 1 | 8 | 14 |
| 2025-05-01 | bullish | 41 | 22 | 9 | 1 | 8 | 13 |
| 2025-06-01 | choppy | 36 | 19 | 0 | 0 | 0 | 19 |
| 2025-07-01 | bearish | 24 | 14 | 0 | 0 | 0 | 14 |
| 2025-08-01 | bearish | 32 | 19 | 4 | 1 | 3 | 15 |
| 2025-09-01 | choppy | 22 | 17 | 0 | 0 | 0 | 17 |
| 2025-10-01 | bullish | 44 | 21 | 6 | 1 | 5 | 15 |
| 2025-11-01 | choppy | 18 | 8 | 0 | 0 | 0 | 8 |
| 2025-12-01 | bearish | 38 | 18 | 6 | 1 | 5 | 12 |

**Total (12 days):** zones = 384, triggered = 209, reached_raw = 37, primary_unique = 7, duplicate = 30, failed = 172

## 3. PART 2 - filter validation

| metric | value |
|---|---:|
| primary recall | 71.43 % |
| duplicate removal | 90.0 % |
| failed reduction | 70.93 % |
| actionable signals / day | 4.833 |
| baseline precision | 17.7 % |
| filtered precision | 13.79 % |
| precision delta | -3.91 pp |

## 4. Cross-venue comparison

| pool | n_days | n_primary | recall % | dup_rem % | fail_red % | actionable/day |
|---|---:|---:|---:|---:|---:|---:|
| OKX Tardis 24d (held-out) | 24 | 21 | 95.24 | 72.81 | 66.47 | 6.79 |
| Binance live 2026-05-17..20 | 4 | 0 | undefined | undefined | 65.85 | 3.5 |
| **Binance Tardis 2025** | **12** | **7** | **71.43** | **90.0** | **70.93** | **4.833** |

## 5. Final flag matrix

```
BINANCE_LIVE_FEASIBILITY_DIAGNOSTIC_DONE = YES
BINANCE_LIVE_2PCT_FEASIBLE_DAYS = 2
TARGET_2PCT_TOO_HIGH_FOR_LIVE_SAMPLE = YES
ZONES_SHOW_SUB_2PCT_EDGE = YES
LIVE_SAMPLE_INFORMATIVE_FOR_PRIMARY_RECALL = NO
BINANCE_TARDIS_2025_INVENTORY_DONE = YES
BINANCE_TARDIS_DATES_AVAILABLE = ['2025-01-01', '2025-02-01', '2025-03-01', '2025-04-01', '2025-05-01', '2025-06-01', '2025-07-01', '2025-08-01', '2025-09-01', '2025-10-01', '2025-11-01', '2025-12-01']
BINANCE_TARDIS_DATES_SELECTED = ['2025-01-01', '2025-02-01', '2025-03-01', '2025-04-01', '2025-05-01', '2025-06-01', '2025-07-01', '2025-08-01', '2025-09-01', '2025-10-01', '2025-11-01', '2025-12-01']
BINANCE_TARDIS_DAYS_PROCESSED = 12
BINANCE_TARDIS_DATA_QUALITY_PASS = YES
BINANCE_TARDIS_BACKTEST_RAN = YES
BINANCE_TARDIS_BASELINE_ZONES = 384
BINANCE_TARDIS_BASELINE_TRIGGERED = 209
BINANCE_TARDIS_BASELINE_REACHED_RAW = 37
BINANCE_TARDIS_BASELINE_PRIMARY_UNIQUE = 7
BINANCE_TARDIS_FILTER_VALIDATION_DONE = YES
FILTER_DECISION_USED_UNIQUEMOVEID = NO
FILTER_INVALID_FUTURE_LEAK = NO
BINANCE_TARDIS_FILTER_PRIMARY_RECALL_PCT = 71.43
BINANCE_TARDIS_FILTER_DUPLICATE_REMOVAL_PCT = 90.0
BINANCE_TARDIS_FILTER_FAILED_REDUCTION_PCT = 70.93
BINANCE_TARDIS_FILTER_ACTIONABLE_PER_DAY = 4.833
BINANCE_TARDIS_FILTER_PRECISION_DELTA_PP = -3.91
BINANCE_TARDIS_TARGET_2PCT_FEASIBLE_DAYS = 11
BINANCE_TARDIS_FILTER_LOOKS_TRANSFERABLE = YES
READY_FOR_PASSIVE_LIVE_OBSERVER = YES
READY_TO_INTEGRATE_FILTER_IN_STRATEGY = NO
MORE_VALIDATION_REQUIRED = YES
```

## 6. Hard rules honored

- strategy / thresholds / `zoneDetector`: UNCHANGED
- filter is post-hoc passive; not integrated into engine
- NO `uniqueMoveId` in suppress decision (FILTER_DECISION_USED_UNIQUEMOVEID = NO)
- NO future-leak (FILTER_INVALID_FUTURE_LEAK = NO); strict-past prior comparisons
- post-trigger outcomes used only as evaluation labels (recall/precision denominators)
- no profitability claim; no production integration
- raw archives untouched