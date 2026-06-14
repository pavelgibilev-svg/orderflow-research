# OKX zone_score_v2 — research analysis (24 full-day OKX dates)

**Build time:** 2026-05-18T23:49:30Z
**Venue:** OKX `okex-swap` BTC-USDT-SWAP — perpetual
**Strategy thresholds:** Binance USDS-M Futures defaults — UNCHANGED
**zone_score_v1:** ARCHIVED (do not use as filter or for entry)
**zone_score_v2:** NOT BUILT — this is research only

## HARD DISCLAIMER

  • This is research/statistical analysis. No production score is built. No threshold is changed.
  • Sample is **n=21 primary unique reached** across 24 OKX days. Effect sizes are *suggestive only* at this sample size.
  • All features are pre-trigger by construction (lookahead audit inherits from `zone_score_v1`'s lookahead-invariance test).
  • OKX ≠ Binance — nothing here transfers without explicit cross-venue validation.
  • No winrate / profitability claim is made or implied.

## A. Dataset summary

- **24** dates (6 calibration + 6 OOS_v1 + 12 v2)
- **784** zones
- **469** triggered
- **135** reached raw
- **21** primary unique reached moves

## B. Class distribution

| class | count |
|---|---:|
| primary_unique_reached_move | 21 |
| duplicate_reached_move      | 114 |
| failed_triggered            | 334 |
| no_trigger                  | 48 |
| invalidated_or_expired      | 267 |
| **TOTAL**                   | **784** |

## C. Stable / unstable features

- **Stable** (|d| ≥ 0.3 AND LOO sign match ≥ 80 %): **8** features
- **Unstable** (|d| ≥ 0.2 AND LOO sign match < 50 %): **0** features
- **Direction-specific** (LONG and SHORT signs disagree, |d| ≥ 0.3 on each): **4** features
- **Regime-specific** (signs disagree across bullish/bearish/choppy, max |d| ≥ 0.5): **5** features

### Top-5 stable features

- `confirm_to_trigger_min` — full d -0.588, LOO match 100.0%
- `total_pre_trigger_min` — full d -0.579, LOO match 100.0%
- `score_ofi` — full d -0.491, LOO match 100.0%
- `cand_prior_move_pct` — full d +0.451, LOO match 100.0%
- `score_trigger` — full d -0.416, LOO match 100.0%

Full details in `reports/OKX_ZONE_SCORE_V2_STABILITY_ANALYSIS.md`.

## D. v1 retrospective

On the full 24-day pool, of the 12 v1 features:
- **5** inverted sign vs v1's weight
- **4** survived (sign matches AND |d| ≥ 0.2)
- **3** became too flat

v1 features that inverted on 24 days:

- `cand_pressure_against` (v1 expected sign -1, 24-day d +0.329)
- `conf_cycles_seen` (v1 expected sign -1, 24-day d +0.202)
- `conf_age_min` (v1 expected sign +1, 24-day d -0.057)
- `conf_defended_persistence_sec` (v1 expected sign +1, 24-day d -0.057)
- `candidate_to_confirm_min` (v1 expected sign +1, 24-day d -0.057)

Full table in `reports/WHY_ZONE_SCORE_V1_FAILED.md`.

## E. Candidate v2 shape (hypothesis only)

**Do not integrate.** This is a starting shape for future work, not a production design.

Preferred building blocks:

- 5–7 STABLE features as the core (top of section C).
- Direction-specific subscores: combine LONG-specific features and SHORT-specific features separately (section D of stability report).
- Regime-aware modifier: optional adjustment by regime (section E of stability report).
- Features to AVOID: every v1 feature that inverted on 24 days (section D above).

**Architecture caveats:**

- Sample is 21 positives. Rule of thumb for proper linear-regression-with-regularisation + held-out-test is 10+ positives per feature, so 50–70+ positives needed for a 5–7 feature model. We are short.
- Don't fit weights on the same sample that selected features. Use a 70/30 date split.
- A shallow decision stub (depth ≤ 2) may be a better fit at n=21 than a linear model.

## F. Data sufficiency

| question | answer |
|---|---|
| Enough for research? | **YES** |
| Enough for production model? | **NO** |
| How many positives needed for production? | **50–100+** unique moves (we have 21) |

## G. Next steps

- Validate the stable-feature picture on Binance live data (this is the cross-venue check).
- Collect more OKX dates via Tardis paid API key (~$X / month) or OKX VIP/premium tier.
- Do NOT integrate any score until proper held-out OOS validation on n ≥ 50 positives.

## H. Final flag matrix

| flag | value |
|---|---|
| `OKX_ZONE_SCORE_V2_RESEARCH_DONE` | **YES** |
| `TOTAL_DATES` | **24** |
| `TOTAL_ZONES` | **784** |
| `TOTAL_UNIQUE_MOVES` | **21** |
| `STABLE_FEATURES_FOUND` | **YES** |
| `V1_FAILURE_EXPLAINED` | **YES** |
| `V2_RULE_CANDIDATES_FOUND` | **YES** |
| `READY_FOR_PASSIVE_V2_SCORE` | **YES** |
| `READY_FOR_PRODUCTION_FILTER` | **NO** |
| `MORE_DATA_REQUIRED` | **YES** |

## I. Companion files

- `reports/OKX_24D_ZONE_DATASET.csv/.json` — unified dataset (Phase A)
- `reports/OKX_24D_PRETRIGGER_FEATURE_CATALOG.md/.json` — feature catalog (Phase B)
- `reports/OKX_ZONE_SCORE_V2_FEATURE_ANALYSIS.md/.json` — class comparisons (Phase C)
- `reports/OKX_ZONE_SCORE_V2_STABILITY_ANALYSIS.md/.json` — stability (Phase D)
- `reports/WHY_ZONE_SCORE_V1_FAILED.md/.json` — v1 retrospective (Phase E)
- `reports/OKX_ZONE_SCORE_V2_RULE_CANDIDATES.md/.json` — rule shapes (Phase F)
- `reports/OKX_ZONE_SCORE_V2_RESEARCH_ANALYSIS.md/.json` — this master report (Phase G)

## J. Hard rules honored

- Strategy thresholds: UNCHANGED.
- `zoneDetector`: NOT modified.
- `zone_score_v1`: left archived; NOT used as filter or entry signal.
- Pre-trigger features only; post-trigger fields used only as labels / stratifier.
- Regime labels used only for stratified analysis, NEVER as a score feature.
- No production model fitted, no winrate claim.