# OKX zone_score_v1 — out-of-sample validation

**Venue:** OKX `okex-swap` BTC-USDT-SWAP
**Score:** `zone_score_v1` with **FROZEN weights** and **FROZEN pooled stats** from the 6 calibration dates.
**OOS dates:** 2025-04-01, 2025-05-01, 2024-05-01, 2024-09-01, 2024-06-01, 2025-11-01
**Replay window:** full UTC day on every date.
**Calibration dates EXCLUDED from OOS:** 2024-01-01, 2024-07-01, 2024-10-01, 2025-10-01, 2025-12-01, 2026-04-01
**Build time:** 2026-05-17T12:30:53Z

## HARD DISCLAIMER

  • Out-of-sample = these 6 dates were NOT used to choose the 12 features, the 12 weights, or to fit the z-normalisation mean/std.
  • zone_score_v1 is OBSERVATIONAL only — it does NOT filter zones, NOT gate triggers, NOT change strategy thresholds.
  • Weights are HYPOTHESIS-ONLY from the calibration step. NOT calibrated for trading.
  • Numbers below are not a winrate claim. OKX is NOT Binance.

## A. OOS dates (regime + replay)

| date | bucket | day Δ % | range % | 2% feasibility | trades | zones | triggered | reached_raw | unique moves | dup credits | failed | no_trig | invalid/exp |
|------|--------|--------:|--------:|:--------------:|-------:|------:|----------:|------------:|-------------:|------------:|-------:|--------:|------------:|
| 2025-04-01 | bullish |  +3.16 |   3.82 |      yes      | 2,321,152 |    41 |        26 |          10 |            2 |           8 |     16 |       3 |          12 |
| 2025-05-01 | bullish |  +2.48 |   3.54 |      yes      | 2,334,321 |    44 |        28 |           8 |            1 |           7 |     20 |       1 |          15 |
| 2024-05-01 | bearish |  -3.88 |   7.13 |      yes      | 2,958,790 |    42 |        25 |          14 |            3 |          11 |     11 |       2 |          15 |
| 2024-09-01 | bearish |  -2.86 |   3.28 |      yes      | 1,331,285 |    42 |        20 |           7 |            1 |           6 |     13 |       3 |          19 |
| 2024-06-01 | choppy  |  +0.31 |   0.70 |       no      | 311,304 |     9 |         8 |           0 |            0 |           0 |      8 |       1 |           0 |
| 2025-11-01 | choppy  |  +0.46 |   1.07 |       no      | 1,022,504 |    13 |         9 |           0 |            0 |           0 |      9 |       2 |           2 |

## B. Mean z per class (OOS)

Hypothesis: if the score generalises, `primary_unique_reached_move` zones should have higher mean z than `failed_triggered`.

| class | n | mean z | median z | stdev z | min z | max z |
|---|---:|---:|---:|---:|---:|---:|
| primary_unique_reached_move | 7 |   -1.544 |   -1.460 |    1.615 |   -3.872 |    1.303 |
| duplicate_reached_move | 32 |   -0.242 |   -0.226 |    1.782 |   -3.989 |    3.687 |
| failed_triggered | 77 |   -0.632 |   -0.408 |    1.882 |   -5.536 |    3.093 |
| no_trigger | 12 |    0.506 |    0.170 |    1.900 |   -2.036 |    4.827 |
| invalidated_or_expired | 63 |    0.276 |    0.345 |    1.551 |   -2.812 |    3.827 |

## C. Bucket × class crosstab (OOS)

Bucket cuts on z: `low` < -0.5, `mid` in [-0.5, +0.5], `high` > +0.5.

| bucket | primary unique | duplicate | failed | no_trig | invalid/exp | total |
|---|---:|---:|---:|---:|---:|---:|
| high | 1 | 10 | 27 | 5 | 27 | 70 |
| mid | 1 | 9 | 14 | 2 | 16 | 42 |
| low | 5 | 13 | 36 | 5 | 20 | 79 |
| no_z | 0 | 0 | 0 | 0 | 0 | 0 |

## D. Bucket-level outcome accounting (OOS)

| bucket | n | triggered | reached_raw | unique moves | failed | no_trig | invalid/exp | raw hit | uniq-move hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| high | 70 | 38 | 11 | 1 | 27 | 5 | 27 | 28.95% | 2.63% |
| mid | 42 | 24 | 10 | 1 | 14 | 2 | 16 | 41.67% | 4.17% |
| low | 79 | 54 | 18 | 5 | 36 | 5 | 20 | 33.33% | 9.26% |
| no_z | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — |

## E. Headline (precision / recall of the `high` bucket)

| metric | value |
|--------|-------|
| OOS unique moves total | **7** |
| OOS unique moves in `high` bucket | **1** |
| precision = unique / triggered in `high` | **2.63%** (1/38) |
| recall = unique in `high` / all unique | **14.29%** (1/7) |
| primary mean z − failed mean z | **-0.9118522404346125** |

## F. In-sample vs OOS comparison

| metric | in-sample (calibration) | OOS |
|--------|-------------------------|-----|
| total unique moves | 5 | 7 |
| unique moves in `high` | 5 | 1 |
| recall in `high` | 100.00% | 14.29% |
| precision in `high` | 10.64% | 2.63% |
| primary mean z |    2.513 |   -1.544 |
| failed mean z |   -0.530 |   -0.632 |

## G. Lookahead audit

Features read (pre-trigger only):
  - `zone.reasons[stage in {candidate, confirmed, trigger}].conditions`
  - `zone.scores.absorptionScore` (frozen at trigger transition)
  - `zone.startTs / confirmedTs / triggerTs` (timing only)

Forbidden fields explicitly NOT read by the scorer:
  - `zone.targets.*` (mfePct, maePct, outcome, reachedAt, timeToTargetMin, maxDrawdownBeforeTargetPct, endPrice, endTs)
  - `zone.resolvedTs`, `zone.status` (terminal), `zone.qualityFlags[*]`
  - `zone.uniqueMoveId`, `zone.moveClusterSize`, `zone.isPrimaryMoveZone`, `zone.duplicateMoveCredit`
  - `zone.reasons[stage=expire | invalidate]`
  - day_return / regime label / future max move (regime label appears in Section A only, NOT inside the score)

Enforced by `tests/zoneScoreV1.test.ts` (lookahead-invariance test passes — 87/87).

## H. Verdict

| flag | value |
|------|------|
| `ZONE_SCORE_V1_OOS_DONE` | **YES** |
| `OOS_DATES_COUNT` | **6** |
| `OOS_UNIQUE_MOVES_TOTAL` | **7** |
| `OOS_UNIQUE_MOVES_HIGH_BUCKET` | **1** |
| `OOS_HIGH_BUCKET_RECALL` | **14.29%** (1/7) |
| `OOS_HIGH_BUCKET_PRECISION` | **2.63%** (1/38) |
| `ZONE_SCORE_V1_GENERALIZES` | **WEAK** |
| `READY_FOR_ZONE_SCORE_V2` | **NO** |

## I. Notes

- If `OOS_UNIQUE_MOVES_TOTAL == 0`, the score cannot be validated on the positive class on this sample — verdict is `WEAK` (insufficient signal), not `YES` or `NO`.
- 2 of the 6 chosen choppy dates have 2 %-target infeasibility (max 24h move below 2 %). Those days mechanically cannot produce reaches regardless of strategy or score quality — flagged in Section A.
- `v1` weights remain hypothesis-only. Even with a successful OOS validation here, integrating the score as a filter on Binance requires Binance-specific re-derivation.
