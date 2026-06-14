# `zone_score_v1` — final verdict (archived as FAILED OOS hypothesis)

**Build time:** 2026-05-17 UTC
**Venue:** OKX `okex-swap` BTC-USDT-SWAP (perpetual)
**Status:** **ARCHIVED — DO NOT USE FOR ENTRY, DO NOT USE AS FILTER**

---

## 1. Headline flags

| flag | value |
|------|-------|
| `ZONE_SCORE_V1_ARCHIVED` | **YES** |
| `DO_NOT_USE_AS_FILTER` | **TRUE** |
| `DO_NOT_USE_FOR_ENTRY` | **TRUE** |
| `IS_OBSERVATIONAL_ONLY` | TRUE (and even that is misleading on OOS) |
| `IS_OOS_GENERALIZING` | **NO** (high-bucket recall 14.29 %, direction inverts) |

The TS module `src/strategy/zoneScoreV1.ts` is left on disk for archival/audit, but no production code path consumes it. The score is not wired to `ZoneDetector`, `TargetChecker`, or any backtest CLI. Tests (`tests/zoneScoreV1.test.ts`) remain to guard against accidental lookahead if the file is ever revived.

---

## 2. Why v1 failed (summary)

| metric | in-sample (6 calibration dates) | OOS (6 held-out dates) |
|---|---:|---:|
| total unique reached moves | 5 | 7 |
| **unique moves in `high` bucket** | **5 (100 % recall)** | **1 (14.29 % recall)** |
| precision of `high` bucket | 10.64 % | 2.63 % |
| primary mean z | **+2.513** | **-1.544** |
| failed mean z | -0.530 | -0.632 |
| `primary − failed` z separation | **+3.04** | **-0.91** (direction inverts) |

Five of seven OOS unique reached moves landed in the **low** bucket — the score was anti-predictive on OOS. The `high` bucket's unique-move hit rate was 2.63 % vs the `low` bucket's 9.26 % — a 3.5× anti-signal.

This is a textbook small-sample feature-selection artefact: the 12 features and the signs of their weights were chosen on n=5 positives, so 100 % in-sample recall and inverted OOS behaviour are both consistent with overfitting to noise.

Full numbers in `reports/OKX_ZONE_SCORE_V1_OOS_VALIDATION.md`. In-sample report at `reports/OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.md`.

---

## 3. What was right about the v1 pipeline (kept)

These pieces of v1 infrastructure remain valid and are reused going forward:

- **`src/strategy/zoneScoreV1.ts`** — pure-function scorer with formal lookahead-invariance test. The *mechanism* is sound; only the *weights* and the *features-selected* are an artefact of small-sample fitting.
- **Per-feature extractor mirror** in `scripts/okx/zone_score_v1_*.py` — keeps Python and TS in lockstep so reports never disagree with code.
- **Bucket × class crosstab + per-class mean-z** as the OOS validation harness — this is the right shape for evaluating v2 if/when it exists.
- **Leave-one-date-out z-normalisation** — correct way to score within the in-sample period without leaking each date's scale.
- **Strict-sequential subprocess chain runner** for full-day backtests — proven to avoid the orphan-parallel bugs from earlier iterations.

---

## 4. What was wrong (will not be repeated in v2)

- **n=5 positive class is statistical noise.** Picking 12 features by Cohen's d on n=5 is fitting to noise by definition. v2 requires substantially more unique reached moves (target: ≥30 positives) before any weight selection happens.
- **No held-out validation set during weight selection.** Weights and feature list were chosen *and* evaluated on the same 6 dates. The OOS test was the FIRST honest validation, and it failed. v2 must split selection/validation samples up front.
- **No significance testing.** Cohen's d was reported but no p-value, no bootstrap, no confidence interval. v2 must report uncertainty per weight.
- **No regularisation, no cross-validation.** v1 weights are `sign(Cohen_d) * |d|/1.5`. That's an effect-size rescaling, not a fitted model. v2 should use proper regression with regularisation and k-fold CV.

---

## 5. v1 status — what to do with the code and reports

- `src/strategy/zoneScoreV1.ts`: **keep**, with a header comment noting the OOS failure (already documented in code via the "HYPOTHESIS-ONLY" caveat). Do not import it into the live engine.
- `tests/zoneScoreV1.test.ts`: **keep** (11 tests, lookahead-invariance test useful even for v2's separate scorer).
- `reports/OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.*`: **keep** as the in-sample baseline. It is honest about being in-sample.
- `reports/OKX_ZONE_SCORE_V1_OOS_VALIDATION.*`: **keep** as the OOS evidence-of-failure. This is the file to point to when explaining the verdict.
- `reports/zone_score_v1_stats.json`: **keep** but **do not refit** with OOS data. The file's `features_pooled` block is a snapshot of the calibration sample only.
- `reports/zone_score_v1_*_with_zone_score.csv`: **keep** as audit traces. Do not use as production input.
- `scripts/okx/zone_score_v1_*.py`: **keep** as the analytical pipeline; the v2 pipeline will follow the same shape.

No file is deleted. The verdict is encoded by this report and by the absence of any production wiring.

---

## 6. Next step — dataset expansion (v2 prep)

Before any v2 weights are fitted, the OKX dataset must be expanded:

1. Inventory current on-disk OKX data — see `reports/OKX_DATASET_INVENTORY_FOR_SCORE_V2.md`.
2. Download missing free first-of-month L2 samples via Tardis.
3. Recompute the regime table across all available dates — see `reports/OKX_EXPANDED_REGIME_TABLE_FOR_SCORE_V2.md`.
4. Select ≥12 new candidate dates for full-day replay — see `reports/OKX_SCORE_V2_CANDIDATE_DATES.json`.
5. Run full-day replays only after the operator confirms (the runtime estimate is published in step 6 of the task).

Until v2 is built and OOS-validated on independent dates, **no entry filter, no zone weighting, no live integration** is permitted.
