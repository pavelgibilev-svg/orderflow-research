# OKX zone_score_v2 — simple rule candidates (research only)

All rules use ONLY pre-trigger features. Lookahead audit identical to `zone_score_v1`'s.

**HARD RULE:** None of these rules are wired into the strategy. None replace `zoneDetector` or change thresholds. They are exploratory shapes for a future v2 score.

## A. Single-feature quartile rules (over stable features)

For each stable feature: pick the top 25 % (if d>0) or bottom 25 % (if d<0) of TRIGGERED zones by that feature. Measure precision/recall against `primary_unique_reached_move`.

| feature | direction | cut | n bucket | primary in bucket | precision | recall |
|---|---|---:|---:|---:|---:|---:|
| `confirm_to_trigger_min` | low | 9.433 | 117 | 6/21 | 5.13% | 28.57% |
| `total_pre_trigger_min` | low | 17.483 | 117 | 6/21 | 5.13% | 28.57% |
| `score_ofi` | low | -0.074 | 117 | 10/21 | 8.55% | 47.62% |
| `cand_prior_move_pct` | high | 0.000 | 74 | 7/21 | 9.46% | 33.33% |
| `score_trigger` | low | 0.972 | 117 | 9/21 | 7.69% | 42.86% |
| `score_absorption` | low | 0.612 | 117 | 7/21 | 5.98% | 33.33% |
| `cand_pressure_against` | high | 0.631 | 117 | 6/21 | 5.13% | 28.57% |
| `trig_break_pct` | low | 0.062 | 117 | 3/21 | 2.56% | 14.29% |

## B. Two-feature AND-rules (top-6 stable, median cut)

Each combination uses the sign of each feature's full-pool Cohen d to choose `> median` or `< median`.

| rule | n bucket | primary in bucket | precision | recall |
|---|---:|---:|---:|---:|
| `(total_pre_trigger_min < median) AND (score_ofi < median)` | 118 | 13/21 | 11.02% | 61.90% |
| `(confirm_to_trigger_min < median) AND (total_pre_trigger_min < median)` | 218 | 12/21 | 5.50% | 57.14% |
| `(confirm_to_trigger_min < median) AND (score_ofi < median)` | 119 | 12/21 | 10.08% | 57.14% |
| `(score_ofi < median) AND (score_trigger < median)` | 124 | 12/21 | 9.68% | 57.14% |
| `(confirm_to_trigger_min < median) AND (score_trigger < median)` | 108 | 10/21 | 9.26% | 47.62% |
| `(total_pre_trigger_min < median) AND (score_trigger < median)` | 112 | 10/21 | 8.93% | 47.62% |
| `(score_ofi < median) AND (score_absorption < median)` | 124 | 9/21 | 7.26% | 42.86% |
| `(total_pre_trigger_min < median) AND (score_absorption < median)` | 126 | 8/21 | 6.35% | 38.10% |
| `(score_trigger < median) AND (score_absorption < median)` | 111 | 8/21 | 7.21% | 38.10% |
| `(confirm_to_trigger_min < median) AND (score_absorption < median)` | 127 | 7/21 | 5.51% | 33.33% |
| `(score_ofi < median) AND (cand_prior_move_pct > median)` | 43 | 4/21 | 9.30% | 19.05% |
| `(cand_prior_move_pct > median) AND (score_trigger < median)` | 33 | 4/21 | 12.12% | 19.05% |
| `(cand_prior_move_pct > median) AND (score_absorption < median)` | 39 | 4/21 | 10.26% | 19.05% |
| `(confirm_to_trigger_min < median) AND (cand_prior_move_pct > median)` | 29 | 3/21 | 10.34% | 14.29% |
| `(total_pre_trigger_min < median) AND (cand_prior_move_pct > median)` | 29 | 3/21 | 10.34% | 14.29% |

## C. Caveats

- Cuts are computed in-sample for the entire 24-day pool. Out-of-sample evaluation would require leave-one-date-out cuts.
- 21 primary unique reaches is too thin for serious rule mining; these numbers are *suggestive* only.
- A 'precision' of e.g. 10 % over n=20 bucket includes (2/20) = (1/10) — confidence interval is wide; do NOT read these as winrates.
- These are decision-stub research shapes. No production filter, no entry change.

Companion JSON: `reports/OKX_ZONE_SCORE_V2_RULE_CANDIDATES.json`