# OKX zone_score_v2 — feature class comparisons

**Dataset:** 24 OKX BTC-USDT-SWAP full-day replays, 784 zones.
**Class counts:** primary_unique=21, duplicate=114, failed=334, no_trigger=48, invalid/expired=267.

## HARD DISCLAIMER

  • Sample is **n=21 primary unique reached** moves across 24 dates. Effect sizes and p-values below are **suggestive only**.
  • This is research, not production. NO score is wired into the engine. NO threshold is changed.
  • All features are pre-trigger by construction; lookahead-invariance is enforced upstream (tests/zoneScoreV1.test.ts).

## A. Top-30 features by |Cohen's d| (primary unique vs failed triggered)

Positive d ⇒ feature is higher for primary-unique than for failed. Magnitude scale: 0.2 small, 0.5 medium, 0.8 large.

| rank | feature | Cohen d | MW U | p (two-sided) | primary mean | failed mean | n primary / n failed |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | `confirm_to_trigger_min` | -0.588 | +2886.500 | 0.174 | +26.316 | +74.847 | 21/334 |
| 2 | `total_pre_trigger_min` | -0.579 | +2869.000 | 0.162 | +36.851 | +85.957 | 21/334 |
| 3 | `score_ofi` | -0.491 | +2520.000 | 0.030 | -0.065 | +0.007 | 21/334 |
| 4 | `cand_prior_move_pct` | +0.451 | +4209.000 | 0.015 | +0.001 | +0.000 | 21/334 |
| 5 | `score_trigger` | -0.416 | +2802.000 | 0.095 | +0.982 | +0.988 | 21/334 |
| 6 | `score_absorption` | -0.407 | +2770.000 | 0.106 | +0.632 | +0.649 | 21/334 |
| 7 | `cand_pressure_against` | +0.329 | +3903.000 | 0.385 | +0.623 | +0.602 | 21/334 |
| 8 | `trig_break_pct` | -0.325 | +3334.000 | 0.704 | +0.144 | +0.203 | 21/334 |
| 9 | `conf_cycles_seen` | +0.202 | +3623.500 | 0.798 | +70.762 | +59.174 | 21/334 |
| 10 | `conf_opposite_thinning` | -0.175 | +2866.000 | 0.160 | +0.500 | +0.500 | 21/334 |
| 11 | `cand_refill_with` | +0.117 | +3993.000 | 0.287 | +0.500 | +0.500 | 21/334 |
| 12 | `zone_width_pct` | -0.111 | +3438.000 | 0.880 | +0.292 | +0.320 | 21/334 |
| 13 | `score_refill` | -0.103 | +3390.000 | 0.798 | +0.500 | +0.500 | 21/334 |
| 14 | `target_distance_pct` | -0.096 | +3376.500 | 0.775 | +2.000 | +2.000 | 21/334 |
| 15 | `conf_age_min` | -0.057 | +3174.000 | 0.464 | +10.535 | +11.110 | 21/334 |
| 16 | `candidate_to_confirm_min` | -0.057 | +3174.000 | 0.464 | +10.535 | +11.110 | 21/334 |
| 17 | `conf_defended_persistence_sec` | -0.057 | +3174.000 | 0.464 | +632.095 | +666.608 | 21/334 |
| 18 | `trig_flow_multiplier` | +0.041 | +2805.000 | 0.124 | +2.024 | +1.962 | 21/334 |
| 19 | `cand_absorb_score` | -0.023 | +3131.000 | 0.410 | +0.650 | +0.651 | 21/334 |
| 20 | `cand_range_compression` | +0.000 | +3507.000 | — | +1.000 | +1.000 | 21/334 |
| 21 | `conf_void_score` | +0.000 | +3507.000 | — | +1.000 | +1.000 | 21/334 |
| 22 | `trig_side_flow_ok` | +0.000 | +3507.000 | — | +1.000 | +1.000 | 21/334 |
| 23 | `score_liquidity_void` | +0.000 | +3507.000 | — | +1.000 | +1.000 | 21/334 |
| 24 | `n_quality_flags` | +0.000 | +3507.000 | — | +0.000 | +0.000 | 21/334 |

## B. Primary unique vs duplicate reached

Why this pair matters: duplicates ARE successful reaches, but the engine fires them on the same multi-hour move that the primary already caught. Features that separate them are the 'first-mover' signal.

| rank | feature | Cohen d | n primary / n duplicate |
|---:|---|---:|---|
| 1 | `confirm_to_trigger_min` | -0.527 | 21/114 |
| 2 | `score_absorption` | -0.520 | 21/114 |
| 3 | `total_pre_trigger_min` | -0.508 | 21/114 |
| 4 | `score_ofi` | -0.467 | 21/114 |
| 5 | `trig_break_pct` | -0.385 | 21/114 |
| 6 | `cand_prior_move_pct` | +0.347 | 21/114 |
| 7 | `score_trigger` | -0.337 | 21/114 |
| 8 | `cand_pressure_against` | +0.287 | 21/114 |
| 9 | `cand_refill_with` | +0.165 | 21/114 |
| 10 | `score_refill` | -0.116 | 21/114 |
| 11 | `conf_opposite_thinning` | +0.080 | 21/114 |
| 12 | `conf_cycles_seen` | -0.070 | 21/114 |
| 13 | `conf_age_min` | +0.036 | 21/114 |
| 14 | `candidate_to_confirm_min` | +0.036 | 21/114 |
| 15 | `conf_defended_persistence_sec` | +0.036 | 21/114 |

## C. Primary unique vs non_primary_all (the catch-all)

non_primary_all = duplicate + failed + no_trigger + invalidated/expired (everything that is NOT a primary-unique reached zone).

| rank | feature | Cohen d | n primary / n non-primary |
|---:|---|---:|---|
| 1 | `confirm_to_trigger_min` | -0.572 | 21/448 |
| 2 | `total_pre_trigger_min` | -0.561 | 21/448 |
| 3 | `score_ofi` | -0.463 | 21/763 |
| 4 | `cand_prior_move_pct` | +0.463 | 21/763 |
| 5 | `score_absorption` | -0.417 | 21/763 |
| 6 | `score_trigger` | -0.396 | 21/448 |
| 7 | `cand_pressure_against` | +0.375 | 21/763 |
| 8 | `trig_break_pct` | -0.340 | 21/448 |
| 9 | `zone_width_pct` | -0.270 | 21/763 |
| 10 | `conf_cycles_seen` | +0.215 | 21/751 |
| 11 | `score_refill` | -0.185 | 21/763 |
| 12 | `conf_opposite_thinning` | -0.168 | 21/751 |
| 13 | `conf_age_min` | -0.163 | 21/751 |
| 14 | `candidate_to_confirm_min` | -0.163 | 21/751 |
| 15 | `conf_defended_persistence_sec` | -0.163 | 21/751 |

Companion JSON: `reports/OKX_ZONE_SCORE_V2_FEATURE_ANALYSIS.json`