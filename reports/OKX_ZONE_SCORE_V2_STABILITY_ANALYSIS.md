# OKX zone_score_v2 — stability analysis

**Dataset:** 784 zones across 24 OKX BTC-USDT-SWAP dates.

## A. Leave-one-date-out sign preservation (primary unique vs failed)

For each feature: sign of Cohen's d on the full dataset, vs the sign in each 23-date fold.

| feature | full d | LOO match rate | fold match |
|---|---:|---:|---:|
| `confirm_to_trigger_min` | -0.588 | 100.0% | 24/24 |
| `total_pre_trigger_min` | -0.579 | 100.0% | 24/24 |
| `score_ofi` | -0.491 | 100.0% | 24/24 |
| `cand_prior_move_pct` | +0.451 | 100.0% | 24/24 |
| `score_trigger` | -0.416 | 100.0% | 24/24 |
| `score_absorption` | -0.407 | 100.0% | 24/24 |
| `cand_pressure_against` | +0.329 | 100.0% | 24/24 |
| `trig_break_pct` | -0.325 | 100.0% | 24/24 |
| `conf_cycles_seen` | +0.202 | 100.0% | 24/24 |
| `conf_opposite_thinning` | -0.175 | 100.0% | 24/24 |
| `cand_refill_with` | +0.117 | 100.0% | 24/24 |
| `zone_width_pct` | -0.111 | 100.0% | 24/24 |
| `score_refill` | -0.103 | 100.0% | 24/24 |
| `target_distance_pct` | -0.096 | 70.8% | 17/24 |
| `conf_age_min` | -0.057 | 91.7% | 22/24 |
| `candidate_to_confirm_min` | -0.057 | 91.7% | 22/24 |
| `conf_defended_persistence_sec` | -0.057 | 91.7% | 22/24 |
| `trig_flow_multiplier` | +0.041 | 91.7% | 22/24 |
| `cand_absorb_score` | -0.023 | 70.8% | 17/24 |
| `cand_range_compression` | +0.000 | 0.0% | 0/24 |
| `conf_void_score` | +0.000 | 0.0% | 0/24 |
| `trig_side_flow_ok` | +0.000 | 0.0% | 0/24 |
| `score_liquidity_void` | +0.000 | 0.0% | 0/24 |
| `n_quality_flags` | +0.000 | 0.0% | 0/24 |

## B. Stable features

Definition: `|d| >= 0.3` AND LOO sign match rate `>= 80%`.

**Count:** 8

| feature | full d | LOO match rate |
|---|---:|---:|
| `confirm_to_trigger_min` | -0.588 | 100.0% |
| `total_pre_trigger_min` | -0.579 | 100.0% |
| `score_ofi` | -0.491 | 100.0% |
| `cand_prior_move_pct` | +0.451 | 100.0% |
| `score_trigger` | -0.416 | 100.0% |
| `score_absorption` | -0.407 | 100.0% |
| `cand_pressure_against` | +0.329 | 100.0% |
| `trig_break_pct` | -0.325 | 100.0% |

## C. Unstable features

Definition: `|d| >= 0.2` AND LOO sign match rate `< 50%` — the sign flips frequently when one date is removed.

**Count:** 0

| feature | full d | LOO match rate |
|---|---:|---:|

## D. Direction-specific features (opposite signs LONG vs SHORT)

**Count:** 4

| feature | LONG d | SHORT d |
|---|---:|---:|
| `conf_age_min` | +0.399 | -0.644 |
| `conf_defended_persistence_sec` | +0.399 | -0.644 |
| `candidate_to_confirm_min` | +0.399 | -0.644 |
| `target_distance_pct` | -0.376 | +0.310 |

## E. Regime-specific features (different signs across bullish/bearish/choppy)

**Count:** 5

| feature | bullish d | bearish d | choppy d |
|---|---:|---:|---:|
| `conf_age_min` | +0.409 | -0.687 | — |
| `conf_defended_persistence_sec` | +0.409 | -0.687 | — |
| `candidate_to_confirm_min` | +0.409 | -0.687 | — |
| `score_absorption` | -1.021 | +0.037 | — |
| `target_distance_pct` | -0.600 | +0.200 | — |

Companion JSON: `reports/OKX_ZONE_SCORE_V2_STABILITY_ANALYSIS.json`