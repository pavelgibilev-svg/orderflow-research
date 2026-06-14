# OKX Tardis 24-date pool - true held-out passive-filter validation

**Build:** 2026-05-21T14:21:20+00:00
**Scope:** OKX Tardis 24-date pool (6 calibration + 6 OOS_v1 + 12 v2)
**Zones:** 784  **Dates:** 24
**Filter under test:** `duplicate_60m_PRICE_BAND_ONLY AND fast_trigger<=X`  (LIVE-VALID: NO `uniqueMoveId` in suppress decision)

## HARD DISCLAIMER

  - This is a TRUE held-out sample for the OKX-direct-March-derived filter rule,
    but the duplicate cut is PURELY price-band-based here (no uniqueMoveId),
    so the rule shape differs slightly from the OKX-direct mini-OOS version.
  - No engine / threshold change. No new backtest. Passive, post-hoc.
  - No profitability claim. No production integration.

## A. Future-leak audit (static, before any number is reported)

- `FILTER_DECISION_USED_UNIQUEMOVEID` = **NO**
- `FILTER_INVALID_FUTURE_LEAK` = **NO**
- allowed fields used in decision: `['direction', 'triggerTs', 'confirmedTs', 'zoneLow', 'zoneHigh']`
- forbidden fields referenced in decision: `[]`

Notes:
  - evaluate_combination's suppress branch reads only triggerTs / direction / confirmedTs and zone midpoints. uniqueMoveId / isPrimaryMoveZone / duplicateMoveCredit / moveClusterSize / status / reached / target_*.* / resolvedTs / mfePct / maePct are referenced ONLY in evaluation metric denominators (precision/recall) and per-class breakdowns AFTER the kept/suppressed split.
  - All prior-zone comparisons are strict-past (prior.triggerTs < current.triggerTs).
  - No future zones are visible: prior pool is sliced by triggered[:i] where i is the chronological index of the current zone within its date.

## B. Baseline (no filter, all 24 days)

- zones = 784
- triggered = 469
- reached_raw = 135
- primary_unique_reached_move = 21
- duplicate_reached_move = 114
- failed_triggered = 334

## C. 12 filter combinations (aggregate over the 24 days)

| X (min) | price % | primary recall % | dup removal % | failed reduce % | prec delta pp | actionable/day |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | 0.25 | 61.9 | 75.44 | 60.18 | -5.22 | 7.25 |
| 30 | 0.5 | 61.9 | 79.82 | 71.86 | -1.09 | 5.417 |
| 30 | 0.75 | 61.9 | 82.46 | 75.15 | -0.34 | 4.833 |
| 30 | 1.0 | 61.9 | 82.46 | 75.45 | -0.09 | 4.792 |
| 60 | 0.25 | 95.24 | 65.79 | 50.3 | -2.56 | 9.375 |
| 60 | 0.5 | 95.24 | 70.18 | 62.87 | 1.55 | 7.417 |
| 60 | 0.75 | 95.24 | 72.81 | 66.17 | 2.31 | 6.833 |
| 60 | 1.0 | 95.24 | 72.81 | 66.47 | 2.5 | 6.792 |
| 90 | 0.25 | 100.0 | 59.65 | 42.51 | -2.92 | 10.792 |
| 90 | 0.5 | 100.0 | 64.91 | 56.59 | 0.83 | 8.583 |
| 90 | 0.75 | 100.0 | 67.54 | 59.88 | 1.42 | 8.0 |
| 90 | 1.0 | 100.0 | 67.54 | 60.18 | 1.58 | 7.958 |

## D. Best combination (recall >= 70 % gate, then max dup_remove + failed_reduce)

- `X = 60 min`, `price_threshold = 1.0 %`
- primary recall: **95.24 %**
- duplicate removal: **72.81 %**
- failed reduction: **66.47 %**
- baseline precision: **28.785 %**
- filtered precision: **31.288 %**
- precision delta: **2.5 pp**
- actionable signals/day: **6.792**

### Per-round (calibration / OOS_v1 / v2)

| round | trig | prim | dup | fail | recall % | dup_rem % | fail_red % |
|---|---:|---:|---:|---:|---:|---:|---:|
| calibration | 117 | 5 | 37 | 75 | 100.0 | 67.57 | 66.67 |
| OOS_v1 | 116 | 7 | 32 | 77 | 100.0 | 81.25 | 68.83 |
| v2 | 236 | 9 | 45 | 182 | 88.89 | 71.11 | 65.38 |

### Per-direction

| direction | trig | prim | dup | fail | recall % | dup_rem % | fail_red % |
|---|---:|---:|---:|---:|---:|---:|---:|
| LONG | 248 | 10 | 52 | 186 | 100.0 | 71.15 | 73.12 |
| SHORT | 221 | 11 | 62 | 148 | 90.91 | 74.19 | 58.11 |

### Per-regime

| regime | trig | prim | dup | fail | recall % | dup_rem % | fail_red % |
|---|---:|---:|---:|---:|---:|---:|---:|
| bullish | 194 | 9 | 46 | 139 | 100.0 | 73.91 | 72.66 |
| choppy | 109 | 2 | 12 | 95 | 100.0 | 58.33 | 67.37 |
| bearish | 221 | 12 | 80 | 129 | 91.67 | 70.0 | 60.47 |

## E. Stability of best combination

- per-round primary recalls: [100.0, 100.0, 88.89]  (range = 11.11 pp)
- per-direction primary recalls: [100.0, 90.91]  (range = 9.09 pp)
- per-regime primary recalls: [100.0, 100.0, 91.67]  (range = 8.33 pp)
- `FILTER_STABLE_ACROSS_ROUNDS` = **YES**
- `FILTER_STABLE_ACROSS_DIRECTION` = **YES**

## F. Late-entry hypothesis on suppressed zones (best combo)

- n suppressed total: 306
- by class label (LABEL-ONLY evaluation): {'duplicate_reached_move': 83, 'failed_triggered': 222, 'primary_unique_reached_move': 1}
- median delta_t from KEPT prior trigger (live-valid, not uniqueMoveId-based): **24.442 min**
- p25 / p75 delta_t: 2.475 / 43.154 min

## G. Compare to OKX direct March mini-OOS

- OKX direct mini-OOS used uniqueMoveId OR price-band <= 2 %. This Tardis validation is LIVE-VALID: NO uniqueMoveId in suppress decision; duplicate match is purely price-band.

| variant | scope | X (min) | recall % | dup_rem % | fail_red % | prec delta pp | actionable/day |
|---|---|---:|---:|---:|---:|---:|---:|
| OKX direct mini-OOS | 03-11..03-13 (3 days, 3 prim) | 30 | 100.0 | 66.67 | 87.23 | 29.66 | 4.0 |
| OKX direct mini-OOS | 03-11..03-13 (3 days, 3 prim) | 60 | 100.0 | 55.56 | 80.85 | 23.41 | 5.333 |
| OKX direct mini-OOS | 03-11..03-13 (3 days, 3 prim) | 90 | 100.0 | 55.56 | 78.72 | 20.84 | 5.667 |
| Tardis 24d held-out (live-valid) | 24 days, 21 prim | 60 (price<=1.0%) | 95.24 | 72.81 | 66.47 | 2.5 | 6.792 |

## H. Final flag matrix

```
TARDIS_FILTER_VALIDATION_DONE = YES
FILTER_DECISION_USED_UNIQUEMOVEID = NO
FILTER_INVALID_FUTURE_LEAK = NO
BEST_FAST_X_MIN = 60
BEST_PRICE_DISTANCE_PCT = 1.0
TARDIS_PRIMARY_RECALL_PCT = 95.24
TARDIS_DUPLICATE_REMOVAL_PCT = 72.81
TARDIS_FAILED_REDUCTION_PCT = 66.47
TARDIS_ACTIONABLE_SIGNALS_PER_DAY = 6.792
TARDIS_PRECISION_DELTA_PP = 2.5
FILTER_STABLE_ACROSS_ROUNDS = YES
FILTER_STABLE_ACROSS_DIRECTION = YES
FILTER_LOOKS_TRANSFERABLE_TO_LIVE = YES
READY_FOR_PASSIVE_LIVE_OBSERVER = YES
READY_TO_INTEGRATE_FILTER_IN_STRATEGY = NO
MORE_VALIDATION_REQUIRED = YES
```

## I. Hard rules honored

- strategy / thresholds / `zoneDetector`: UNCHANGED
- no new backtest spawned; no conversion re-run
- post-trigger outcomes used only as labels (recall/precision denominators),
  NEVER inside the suppress decision
- `zone_score_v1` / `v2`: not used as filter
- raw archives untouched
- no production integration; no profitability claim