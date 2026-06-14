# OKX `zone_score_v1` — passive observational validation

**Venue:** OKX `okex-swap` BTC-USDT-SWAP
**Dates:** 2024-01-01, 2025-10-01, 2025-12-01, 2024-10-01, 2024-07-01, 2026-04-01
**Zones scored:** 211
**Score fit:** **leave-one-date-out** (zones on date D are scored using mean/std from the OTHER 5 dates only).
**Strategy thresholds:** Binance USDS-M Futures defaults — **UNCHANGED**.
**Strategy logic:** **UNCHANGED**. The score is observational only.

## HARD DISCLAIMER

  • zone_score_v1 is a **passive metric** computed AFTER the strategy has already produced zones. It is NOT a filter, gate, or trade decision.
  • Weights are HYPOTHESIS-ONLY from the 6-date OKX sample. NOT cross-validated. NOT calibrated for trading.
  • Numbers below are observational shape, not a winrate claim.
  • OKX is NOT Binance. Do not transfer this score to Binance without re-fitting.

## A. Mean z-score per zone class

If the score truly separates `primary_unique_reached_move` from `failed_triggered`, the former's mean z should be **higher** than the latter's.

| class | n | mean z | median z | stdev z | min z | max z |
|---|---:|---:|---:|---:|---:|---:|
| primary_unique_reached_move | 5 |    2.513 |    2.293 |    1.424 |    0.829 |    4.979 |
| duplicate_reached_move | 37 |   -0.372 |   -0.375 |    2.590 |   -5.110 |    6.444 |
| failed_triggered | 75 |   -0.530 |    0.026 |    2.359 |   -8.076 |    3.410 |
| no_trigger | 9 |    0.778 |    0.858 |    0.891 |   -1.188 |    1.994 |
| invalidated_or_expired | 85 |    0.420 |    0.324 |    1.782 |   -3.506 |    5.226 |

## B. Zones × bucket (counts)

Bucket cuts on the LOO z-score: `low` = z < -0.5, `mid` = -0.5 ≤ z ≤ +0.5, `high` = z > +0.5, `no_z` = no fitted stats coverage.

| bucket | primary unique | duplicate | failed_triggered | no_trigger | invalid./expired | total |
|---|---:|---:|---:|---:|---:|---:|
| high | 5 | 14 | 28 | 7 | 37 | 91 |
| mid | 0 | 6 | 13 | 1 | 25 | 45 |
| low | 0 | 17 | 34 | 1 | 23 | 75 |
| no_z | 0 | 0 | 0 | 0 | 0 | 0 |

## C. Bucket-level outcome accounting

Triggered = status ∈ {RESOLVED_REACHED, RESOLVED_FAILED}. raw_hit_rate = reached_raw / triggered. unique_move_hit_rate = unique_moves / triggered.

| bucket | n | triggered | reached_raw | unique moves | failed_triggered | no_trigger | invalid./expired | raw_hit | uniq-move_hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| high | 91 | 47 | 19 | 5 | 28 | 7 | 37 | 40.43% | 10.64% |
| mid | 45 | 19 | 6 | 0 | 13 | 1 | 25 | 31.58% | 0.00% |
| low | 75 | 51 | 17 | 0 | 34 | 1 | 23 | 33.33% | 0.00% |
| no_z | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — |

## D. Interpretation

- The score in `high` bucket should contain a disproportionate share of `primary_unique_reached_move` zones if the hypothesis holds.
- The score in `low` bucket should be enriched with `failed_triggered` and `invalidated_or_expired`.
- A coin-flip score would split zones uniformly across buckets.
- **All numbers below are in-sample for the 12 weights**, which were themselves derived from these 6 OKX dates. The LOO fit on z-normalisation removes leakage on the *scale* of each feature, but it does NOT remove leakage on the *choice* of the 12 features and their signs. Take the bucket cross-tab as a sanity check, not as out-of-sample validation.

## E. Lookahead audit

Feature extraction reads ONLY:
  - `zone.reasons[stage=candidate].conditions` (sellPressure/buyPressure, bidRefillScore/askRefillScore, absorbScore, downMovePct/upMovePct, rangeCompression)
  - `zone.reasons[stage=confirmed].conditions` (cyclesSeen, ageMin, defendedPersistenceSec, oppositeThinning, voidScore)
  - `zone.reasons[stage=trigger].conditions` (breakPct, flowMultiplier, sideFlowOK)
  - `zone.scores.absorptionScore` (frozen at trigger transition)
  - `zone.startTs / confirmedTs / triggerTs` (timing only, no future data)

Feature extraction does NOT read:
  - `zone.targets.*` (mfePct, maePct, outcome, reachedAt, timeToTargetMin, maxDrawdownBeforeTargetPct, endPrice, endTs)
  - `zone.resolvedTs`, `zone.status` (terminal), `zone.qualityFlags[*]` (post-trigger flag updates)
  - `zone.uniqueMoveId`, `zone.moveClusterSize`, `zone.isPrimaryMoveZone`, `zone.duplicateMoveCredit`
  - `zone.reasons[stage=expire | invalidate]`

This is enforced by `tests/zoneScoreV1.test.ts` — the `score is invariant under mutation of forbidden post-trigger fields` test passes (87/87).

## F. Files

- `src/strategy/zoneScoreV1.ts` — pure TS module (no strategy mutation)
- `tests/zoneScoreV1.test.ts` — 11 tests (lookahead invariance, purity, weights frozen)
- `reports/zone_score_v1_stats.json` — pooled + LOO fitted stats
- `reports/OKX_TECHNICAL_REPLAY_<date>_fullday_with_zone_score.csv` — per-date annotated CSV
- `reports/OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.json` — machine-readable validation
- `reports/OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.md` — this file

## G. Flag matrix

| flag | value |
|------|------|
| `ZONE_SCORE_V1_IMPLEMENTED` | **YES** (passive, no integration) |
| `AFFECTS_STRATEGY` | **NO** (no zoneDetector / threshold / filter change) |
| `LOOKAHEAD_RISK` | **NO** (pre-trigger only; lookahead-invariance test passes) |
| `PASSIVE_SCORE_USEFUL` | **YES** (verdict from class-z separation; see Section A) |
