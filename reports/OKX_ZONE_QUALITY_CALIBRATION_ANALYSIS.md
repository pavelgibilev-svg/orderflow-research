# OKX zone quality calibration analysis — 6 full-day dates

**Venue:** OKX `okex-swap` BTC-USDT-SWAP (perpetual)
**Dates:** 2024-01-01, 2025-10-01, 2025-12-01, 2024-10-01, 2024-07-01, 2026-04-01
**Zones analyzed:** 211
**Strategy thresholds:** Binance USDS-M Futures defaults — **UNCHANGED**
**This is analysis only.** No code changes, no threshold changes, no tuning, no winrate claim.

## HARD DISCLAIMER

  • The honest headline of OKX 6-date full-day is **5 unique reached moves** across 6 days (one per non-choppy day). 211 total zones.
  • This analysis is about **which pre-trigger features separate primary-unique-reached zones from failed-triggered zones**.
  • Weights proposed for `zone_score_v1` are **hypotheses**, NOT a calibrated model. Do not trade them.
  • Cross-venue: weights derived here are an OKX-specific signal-of-shape, not a Binance result.

## A. Classification

| class                          | count |
|--------------------------------|------:|
| primary_unique_reached_move    |     5 |
| duplicate_reached_move         |    37 |
| failed_triggered               |    75 |
| no_trigger                     |     9 |
| invalidated_or_expired         |    85 |
| **TOTAL**                      | **211** |

Definitions:
- `primary_unique_reached_move`: status=RESOLVED_REACHED AND isPrimaryMoveZone=true
- `duplicate_reached_move`: status=RESOLVED_REACHED AND isPrimaryMoveZone=false (move-clustering absorbed)
- `failed_triggered`: status=RESOLVED_FAILED (triggered, never reached target on any horizon)
- `no_trigger`: status=NO_TRIGGER (confirmed, never broke past the trigger band)
- `invalidated_or_expired`: status=INVALIDATED or status=EXPIRED before trigger

## B. Per-feature stats by class (mean ± std)

Each feature is observable at-or-before `triggerTs`. See Section E for the lookahead audit.

| feature | primary unique (n) | duplicate (n) | failed_triggered (n) | no_trigger (n) | invalid./expired (n) | Cohen d (primary vs failed) |
|---------|-------------------|---------------|---------------------|----------------|---------------------|----------------------------:|
| cand_pressure_against | 0.566 ± 0.024 (n=5) | 0.596 ± 0.052 (n=37) | 0.601 ± 0.051 (n=75) | 0.577 ± 0.020 (n=9) | 0.595 ± 0.042 (n=85) | -0.857 |
| cand_absorb_score | 0.623 ± 0.026 (n=5) | 0.641 ± 0.039 (n=37) | 0.653 ± 0.043 (n=75) | 0.635 ± 0.022 (n=9) | 0.648 ± 0.041 (n=85) | -0.841 |
| conf_cycles_seen | 27.600 ± 37.345 (n=5) | 85.649 ± 62.041 (n=37) | 63.947 ± 51.743 (n=75) | 18.167 ± 12.240 (n=6) | 59.118 ± 47.327 (n=85) | -0.806 |
| cand_refill_with | 0.501 ± 0.000 (n=5) | 0.500 ± 0.001 (n=37) | 0.500 ± 0.001 (n=75) | 0.500 ± 0.001 (n=9) | 0.500 ± 0.001 (n=85) | +0.646 |
| confirm_to_trigger_min | 19.733 ± 15.683 (n=5) | 49.629 ± 41.503 (n=37) | 74.236 ± 119.234 (n=75) | — (n=0) | — (n=0) | -0.641 |
| trig_flow_multiplier | 3.323 ± 2.961 (n=5) | 2.101 ± 1.457 (n=37) | 2.015 ± 1.067 (n=75) | — (n=0) | — (n=0) | +0.588 |
| total_pre_trigger_min | 34.933 ± 17.057 (n=5) | 59.104 ± 42.101 (n=37) | 84.621 ± 122.021 (n=75) | — (n=0) | — (n=0) | -0.570 |
| conf_age_min | 15.200 ± 9.669 (n=5) | 9.474 ± 11.561 (n=37) | 10.386 ± 9.324 (n=75) | 11.667 ± 4.874 (n=6) | 16.105 ± 13.445 (n=85) | +0.507 |
| conf_defended_persistence_sec | 912.000 ± 580.114 (n=5) | 568.459 ± 693.669 (n=37) | 623.147 ± 559.467 (n=75) | 700.000 ± 292.436 (n=6) | 966.294 ± 806.696 (n=85) | +0.507 |
| candidate_to_confirm_min | 15.200 ± 9.669 (n=5) | 9.474 ± 11.561 (n=37) | 10.386 ± 9.324 (n=75) | 11.667 ± 4.874 (n=6) | 16.105 ± 13.445 (n=85) | +0.507 |
| score_absorption | 0.629 ± 0.028 (n=5) | 0.659 ± 0.060 (n=37) | 0.647 ± 0.046 (n=75) | 0.644 ± 0.027 (n=9) | 0.640 ± 0.045 (n=85) | -0.483 |
| trig_break_pct | 0.134 ± 0.144 (n=5) | 0.217 ± 0.162 (n=37) | 0.220 ± 0.219 (n=75) | — (n=0) | — (n=0) | -0.465 |
| zone_width_pct | 0.448 ± 0.315 (n=5) | 0.305 ± 0.284 (n=37) | 0.334 ± 0.341 (n=75) | 0.758 ± 0.659 (n=9) | 0.471 ± 0.507 (n=85) | +0.346 |
| cand_move_pct | 0.000 ± 0.000 (n=5) | 0.000 ± 0.002 (n=37) | 0.000 ± 0.001 (n=75) | 0.000 ± 0.000 (n=9) | 0.000 ± 0.001 (n=85) | -0.326 |
| target_distance_pct | 2.000 ± 0.000 (n=5) | 2.000 ± 0.000 (n=37) | 2.000 ± 0.000 (n=75) | — (n=0) | — (n=0) | +0.178 |
| score_ofi | -0.003 ± 0.134 (n=5) | 0.029 ± 0.150 (n=37) | 0.018 ± 0.160 (n=75) | 0.024 ± 0.115 (n=9) | 0.007 ± 0.165 (n=85) | -0.137 |
| score_refill | 0.500 ± 0.001 (n=5) | 0.500 ± 0.001 (n=37) | 0.500 ± 0.001 (n=75) | 0.501 ± 0.001 (n=9) | 0.500 ± 0.001 (n=85) | +0.101 |
| conf_opposite_thinning | 0.500 ± 0.001 (n=5) | 0.500 ± 0.001 (n=37) | 0.500 ± 0.001 (n=75) | 0.500 ± 0.000 (n=6) | 0.500 ± 0.001 (n=85) | -0.037 |
| score_trigger | 0.988 ± 0.015 (n=5) | 0.985 ± 0.014 (n=37) | 0.988 ± 0.014 (n=75) | — (n=0) | — (n=0) | -0.012 |
| cand_range_compression | 1.000 ± 0.000 (n=5) | 1.000 ± 0.000 (n=37) | 1.000 ± 0.000 (n=75) | 1.000 ± 0.000 (n=9) | 1.000 ± 0.000 (n=85) | +0.000 |
| conf_void_score | 1.000 ± 0.000 (n=5) | 1.000 ± 0.000 (n=37) | 1.000 ± 0.000 (n=75) | 1.000 ± 0.000 (n=6) | 1.000 ± 0.000 (n=85) | +0.000 |
| trig_side_flow_ok | 1.000 ± 0.000 (n=5) | 1.000 ± 0.000 (n=37) | 1.000 ± 0.000 (n=75) | 0.000 ± 0.000 (n=9) | 0.000 ± 0.000 (n=85) | +0.000 |
| score_liquidity_void | 1.000 ± 0.000 (n=5) | 1.000 ± 0.000 (n=37) | 1.000 ± 0.000 (n=75) | 1.000 ± 0.000 (n=9) | 1.000 ± 0.000 (n=85) | +0.000 |
| n_quality_flags | 0.000 ± 0.000 (n=5) | 0.000 ± 0.000 (n=37) | 0.000 ± 0.000 (n=75) | 0.000 ± 0.000 (n=9) | 0.000 ± 0.000 (n=85) | +0.000 |

## C. Top features by separation power (primary vs failed_triggered)

Cohen's d magnitude |d|: 0.2 small, 0.5 medium, 0.8 large.
Positive d ⇒ feature is higher for primary-unique reached than for failed-triggered.
Negative d ⇒ feature is higher for failed-triggered than for primary-unique reached.

| rank | feature | Cohen d | primary mean | failed mean | sample size (primary / failed) |
|-----:|---------|--------:|-------------:|------------:|-------------------------------|
| 1 | `cand_pressure_against` |  -0.857 |       0.5664 |      0.6005 | 5 / 75 |
| 2 | `cand_absorb_score` |  -0.841 |       0.6230 |      0.6529 | 5 / 75 |
| 3 | `conf_cycles_seen` |  -0.806 |      27.6000 |     63.9467 | 5 / 75 |
| 4 | `cand_refill_with` |   0.646 |       0.5009 |      0.5001 | 5 / 75 |
| 5 | `confirm_to_trigger_min` |  -0.641 |      19.7333 |     74.2356 | 5 / 75 |
| 6 | `trig_flow_multiplier` |   0.588 |       3.3235 |      2.0155 | 5 / 75 |
| 7 | `total_pre_trigger_min` |  -0.570 |      34.9333 |     84.6213 | 5 / 75 |
| 8 | `conf_age_min` |   0.507 |      15.2000 |     10.3858 | 5 / 75 |
| 9 | `conf_defended_persistence_sec` |   0.507 |     912.0000 |    623.1467 | 5 / 75 |
| 10 | `candidate_to_confirm_min` |   0.507 |      15.2000 |     10.3858 | 5 / 75 |
| 11 | `score_absorption` |  -0.483 |       0.6289 |      0.6473 | 5 / 75 |
| 12 | `trig_break_pct` |  -0.465 |       0.1336 |      0.2200 | 5 / 75 |
| 13 | `zone_width_pct` |   0.346 |       0.4478 |      0.3342 | 5 / 75 |
| 14 | `cand_move_pct` |  -0.326 |       0.0000 |      0.0002 | 5 / 75 |
| 15 | `target_distance_pct` |   0.178 |       2.0000 |      2.0000 | 5 / 75 |

## D. `zone_score_v1` — HYPOTHESIS ONLY

**Do not trade this.** Weights are derived from observed separation on a 6-day OKX sample with Binance-tuned thresholds. They are NOT calibrated, NOT cross-validated, and the cross-venue transferability has NOT been checked.

Formula (skeleton):

```
zone_score_v1(zone) = Σ w_i * value_i
```

where each `value_i` is the raw feature value (no normalisation in v1; a real
implementation must add per-feature z-score normalisation first).

Tentative weights (sign+magnitude derived from Cohen's d, clamped to [-1, +1]):

| feature | weight | rationale |
|---------|-------:|-----------|
| `cand_pressure_against` | -0.572 | @candidate, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `cand_absorb_score` | -0.561 | @candidate, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `conf_cycles_seen` | -0.537 | @confirmed, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `cand_refill_with` | +0.431 | @candidate, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `confirm_to_trigger_min` | -0.427 | derived, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `trig_flow_multiplier` | +0.392 | @trigger, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `total_pre_trigger_min` | -0.380 | derived, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `conf_age_min` | +0.338 | @confirmed, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `conf_defended_persistence_sec` | +0.338 | @confirmed, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `candidate_to_confirm_min` | +0.338 | derived, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `score_absorption` | -0.322 | @score, top-12 by |Cohen d| with |d| ≥ 0.20 |
| `trig_break_pct` | -0.310 | @trigger, top-12 by |Cohen d| with |d| ≥ 0.20 |

**Caveats:**

- Sample is **6 days, 211 zones** with class imbalance (primary unique ≈ 5, failed ≈ 75). Cohen's d on n=5 vs n=75 is suggestive at best.
- Weights here are derived from |d| magnitude, not from a regression. There is no held-out validation set, no significance testing, no bias correction.
- Several features (e.g. `score_trigger`, `trig_side_flow_ok`) are nearly constant because they're gating conditions for getting to TRIGGERED at all — their Cohen's d will be tiny by construction.
- Cross-venue: this calibration tells us about OKX with Binance-tuned thresholds; transferring weights to Binance without re-derivation would itself be a strategy change.
- Strategy code remains unchanged: this v1 score is a *passive* score that could be computed alongside the existing engine and **then** evaluated on a held-out sample. Threshold integration is out of scope.

## E. Lookahead audit

All features in `pretrigger_features()` are pulled from the zone's `reasons[stage in {candidate, confirmed, trigger}].conditions` blocks or from `zone.scores` (populated by the state machine by the trigger transition). The following fields were deliberately **excluded** to avoid lookahead bias:

- `targets.* (mfePct, maePct, reachedAt, timeToTargetMin, outcome, maxDrawdownBeforeTargetPct, endPrice, endTs)`
- `resolvedTs`
- `status (final)`
- `isPrimaryMoveZone (assigned post-resolve by clustering)`
- `duplicateMoveCredit (post-resolve)`
- `uniqueMoveId (post-resolve)`
- `moveClusterSize (post-resolve)`
- `reasons[stage='expire']`

`zone.scores` is a tiny grey area: it is the running state-machine score at the moment of transition. Code path inspection (`src/strategy/zoneDetector.ts`) confirms these are set during state-machine progression and are FROZEN once the zone is TRIGGERED, so they are pre-trigger by construction. This audit treats them as pre-trigger but flags them as a near-boundary surface area to keep an eye on if a future v2 score is wired into the live path.

## F. Final flag matrix

| flag | value | rationale |
|------|-------|-----------|
| `OKX_ZONE_SCORE_READY` | **YES (v1 hypothesis)** | a skeleton score with 12 non-zero weights is proposed; integration into the engine is explicitly NOT done here |
| `USEFUL_FEATURES_FOUND` | **YES** | 12 features show |Cohen d| ≥ 0.20 between primary-unique-reached and failed-triggered |
| `LOOKAHEAD_RISK` | **NO (pre-trigger only)** | features come from candidate/confirmed/trigger stages or zone.scores frozen at trigger; targets / move-clustering excluded |

Companion JSON: `reports/OKX_ZONE_QUALITY_CALIBRATION_ANALYSIS.json` (full per-feature stats + raw zone classifications).