# OKX direct partial-March 2026 - zone calibration report

**Build:** 2026-05-21T13:08:16+00:00
**Scope:** OKX direct Historical Market Data, BTC-USDT-SWAP, UTC days 2026-03-02..2026-03-15 (14 days)
**Strategy / thresholds / engine:** UNCHANGED. Post-hoc analysis of already-produced backtest output.

## HARD DISCLAIMER

  - 15 primary unique reached moves across 14 days = thin sample. All metrics here are SUGGESTIVE.
  - No filter is integrated into the engine. No threshold is changed. No production model fitted.
  - No profitability claim is made.
  - OKX != Binance; do NOT port these filter rules to Binance without independent cross-venue validation.

## 1. Dataset summary (Phase A)

- rows = **510** zones
- triggered = **295**
- reached_raw = **98**
- primary_unique = **15**
- duplicate_reached = **83**
- failed_triggered = **197**
- no_trigger = **33**
- invalidated_or_expired = **182**

Companion: `OKX_DIRECT_MARCH_PARTIAL_ZONE_DATASET.{csv,json}`

## 2. Timing findings (Phase B)

(see `OKX_DIRECT_MARCH_ZONE_TIMING_ANALYSIS.md`).

Headlines: 
- Primaries trigger noticeably faster after confirmation than failed triggers do (negative d on
  `confirm_to_trigger_min` for primary vs failed).
- Duplicates tend to trigger LATER than primaries within the same cluster (positive delta-t in dedup table),
  consistent with the duplicate filter hypothesis.

## 3. Duplicate / cluster findings (Phase C)

(see `OKX_DIRECT_MARCH_DUPLICATE_CLUSTER_ANALYSIS.md`).

- 15 unique moves; 83 duplicate zones distributed across them.
- 82 duplicates trigger AFTER the first
  trigger of their cluster - candidate to suppress.
- 49 duplicates trigger AFTER the move
  is already half-completed - clear late-entry to suppress.

## 4. Failed-zone findings (Phase D)

(see `OKX_DIRECT_MARCH_FAILED_ZONE_ANALYSIS.md`).

- failed_triggered total = 197
- failed with active same-dir triggered zone in prior 60 min = 106
- failed with opposite direction reaching the move later same day = 0
  (this is informative context, not a usable strategy feature.)

## 5. Local anomaly findings (Phase E)

(see `OKX_DIRECT_MARCH_LOCAL_ANOMALY_ANALYSIS.md`).

Per-day percentile-rank used as a proxy for `local baseline` since the existing artefacts do not include
minute-windowed orderflow series; mean per-day rank by class is the headline metric.

## 6. Passive filter v0 candidates (Phase F+G)

(see `OKX_DIRECT_MARCH_PASSIVE_FILTER_V0_ANALYSIS.md`).

Best research-only filter: `duplicate_60m_AND_fast<=60m`
  - primary recall: **1.0**
  - duplicate remove rate: **0.735**
  - failed reduce rate: **0.706**
  - actionable signals / day: **6.786**

## 7. Filters that look stable

- `duplicate_60m` consistently the strongest single filter for duplicate removal.
- Combination of `duplicate_60m AND flow_confirmation_>=2x` removes a meaningful share of failed zones
  while keeping most primaries.

## 8. Filters that should NOT be used yet

- Anything tuned against the same 14-day window without OOS validation - including the best filter above.
- `counter_direction_ofi`: OFI sign post-hoc; using it as an entry filter risks lookahead-style overfit.
- Anything based on `target_24h_*` (mfePct/maePct/reachedAt/outcome) - these are post-trigger outcomes.

## 9. What to check on another period

- Same filter rules on the 24-date Tardis pool already in this repo (calibration + OOS_v1 + v2 dates).
  Sample of 21 primaries across 24 days; check sign preservation of best-rule metrics.
- A second OKX direct partial month (e.g. 03-16..03-31 once data is downloaded), for true held-out OOS.

## 10. What can later transfer to Binance live / backtest

- Only filters that survive Section 9 cross-venue and OOS checks.
- Until then: passive-only, observational on Binance backtest outputs; NEVER as an entry filter on live.

## 11. Final flag matrix

```
OKX_DIRECT_MARCH_CALIBRATION_DONE = YES
PRIMARY_UNIQUE_MOVES_TOTAL = 15
STABLE_FILTER_CANDIDATES_FOUND = YES
BEST_FILTER_UNIQUE_RECALL_PCT = 100.0
BEST_FILTER_DUPLICATE_REMOVAL_PCT = 73.5
BEST_FILTER_FAILED_REDUCTION_PCT = 70.6
BEST_FILTER_ACTIONABLE_SIGNALS_PER_DAY = 6.786
READY_FOR_PASSIVE_FILTER_BACKTEST = YES
READY_TO_INTEGRATE_FILTER_IN_STRATEGY = NO
MORE_VALIDATION_REQUIRED = YES
```

## 12. Hard rules honored

- strategy / thresholds / `zoneDetector`: UNCHANGED
- `zone_score_v1` / `zone_score_v2`: not used as entry filter
- production model: NOT built
- profitability claim: NOT made
- raw archives untouched
- no new backtest invoked; this is post-hoc analysis only