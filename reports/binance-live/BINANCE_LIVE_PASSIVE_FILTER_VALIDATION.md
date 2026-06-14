# Binance live-recorder - passive filter validation

**Filter:** `fast_trigger <= 60 min AND duplicate_60m (price band <= 1.0 %)`  (live-valid; no uniqueMoveId in decision).
**Dates:** ['2026-05-17', '2026-05-18', '2026-05-19', '2026-05-20']

## Baseline vs filtered

| metric | baseline | filtered |
|---|---:|---:|
| zones | 71 | (only-triggered subset) |
| triggered | 41 | 14 |
| reached_raw | 0 | 0 |
| primary_unique | 0 | 0 |
| duplicate_reached | 0 | 0 |
| failed_triggered | 41 | 14 |

## Per-day breakdown

| date | trig (b/f) | reached (b/f) | primary (b/f) |
|---|---|---|---|
| 2026-05-17 | 12/3 | 0/0 | 0/0 |
| 2026-05-18 | 13/6 | 0/0 | 0/0 |
| 2026-05-19 | 10/4 | 0/0 | 0/0 |
| 2026-05-20 | 6/1 | 0/0 | 0/0 |

## Flags

- `BINANCE_FILTER_VALIDATION_DONE` = **YES**
- `FILTER_DECISION_USED_UNIQUEMOVEID` = **NO**
- `FILTER_INVALID_FUTURE_LEAK` = **NO**
- `BINANCE_PRIMARY_RECALL_PCT` = **None**
- `BINANCE_DUPLICATE_REMOVAL_PCT` = **None**
- `BINANCE_FAILED_REDUCTION_PCT` = **65.85**
- `BINANCE_ACTIONABLE_SIGNALS_PER_DAY` = **3.5**
- `BINANCE_BASELINE_PRECISION_PCT` = **0.0**
- `BINANCE_FILTERED_PRECISION_PCT` = **0.0**
- `BINANCE_FILTER_LOOKS_STABLE` = **NO**

## Hard rules honored

- engine / thresholds NOT changed
- post-trigger outcome fields used ONLY as evaluation labels (recall/precision),
  NEVER inside suppress decision
- raw archives preserved; no API keys touched