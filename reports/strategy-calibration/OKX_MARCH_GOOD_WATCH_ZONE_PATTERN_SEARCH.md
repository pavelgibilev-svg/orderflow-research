# Good-watch-zone pattern search (29-day full March)

**Build:** 2026-05-25T15:31:41+00:00
**Target:** alerts/day <= 2.5, precision >> baseline (11.79%), recall > 0.

| pattern | n | per day | GOOD | BAD | wrong | precision % | recall % | wrong rate % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline_all_confirmed` | 1043 | 35.966 | 123 | 774 | 139 | 11.79 | 100.0 | 13.33 |
| `filter_kept` | 224 | 7.724 | 32 | 155 | 28 | 14.29 | 26.02 | 12.5 |
| `not_filter_kept` | 819 | 28.241 | 91 | 619 | 111 | 11.11 | 73.98 | 13.55 |
| `opp_dir_zones_60m_eq_0` | 433 | 14.931 | 55 | 331 | 41 | 12.7 | 44.72 | 9.47 |
| `opp_dir_zones_60m_le_1` | 726 | 25.034 | 90 | 542 | 79 | 12.4 | 73.17 | 10.88 |
| `same_dir_zones_60m_eq_0` | 447 | 15.414 | 59 | 341 | 61 | 13.2 | 47.97 | 13.65 |
| `prior_move_60m_pct_le_0_5` | 634 | 21.862 | 86 | 469 | 72 | 13.56 | 69.92 | 11.36 |
| `prior_move_60m_pct_le_1_0` | 917 | 31.621 | 112 | 679 | 124 | 12.21 | 91.06 | 13.52 |
| `prior_move_180m_pct_le_1_0` | 717 | 24.724 | 98 | 532 | 93 | 13.67 | 79.67 | 12.97 |
| `local_range_60m_pct_ge_0_5` | 879 | 30.31 | 98 | 647 | 120 | 11.15 | 79.67 | 13.65 |
| `ofi_score_aligned_strong` | 493 | 17.0 | 48 | 375 | 55 | 9.74 | 39.02 | 11.16 |
| `flow_mult_ge_2` | 157 | 5.414 | 18 | 110 | 13 | 11.46 | 14.63 | 8.28 |
| `flow_mult_le_2` | 886 | 30.552 | 105 | 664 | 126 | 11.85 | 85.37 | 14.22 |
| `defended_persistence_ge_900` | 290 | 10.0 | 37 | 212 | 47 | 12.76 | 30.08 | 16.21 |
| `zone_width_pct_le_0_4` | 710 | 24.483 | 87 | 523 | 93 | 12.25 | 70.73 | 13.1 |
| `zone_width_pct_le_0_3` | 553 | 19.069 | 67 | 417 | 69 | 12.12 | 54.47 | 12.48 |
| `confirm_to_trigger_le_60` | 443 | 15.276 | 52 | 309 | 46 | 11.74 | 42.28 | 10.38 |
| `confirm_to_trigger_le_30` | 317 | 10.931 | 37 | 221 | 39 | 11.67 | 30.08 | 12.3 |
| `filter_kept_AND_opp_dir_60m_eq_0` | 93 | 3.207 | 18 | 62 | 4 | 19.35 | 14.63 | 4.3 |
| `filter_kept_AND_prior_60m_le_1` | 200 | 6.897 | 29 | 140 | 27 | 14.5 | 23.58 | 13.5 |
| `opp_dir_60m_eq_0_AND_prior_60m_le_1` | 382 | 13.172 | 49 | 293 | 39 | 12.83 | 39.84 | 10.21 |
| `opp_dir_60m_eq_0_AND_local_range_60m_ge_0_5` | 353 | 12.172 | 40 | 270 | 33 | 11.33 | 32.52 | 9.35 |
| `filter_kept_AND_opp_eq_0_AND_prior_60m_le_1` | 83 | 2.862 | 16 | 55 | 4 | 19.28 | 13.01 | 4.82 |
| `filter_kept_AND_zone_width_le_0_4` | 178 | 6.138 | 28 | 123 | 24 | 15.73 | 22.76 | 13.48 |

**Best pattern (alerts/day <= 3, precision > baseline 11.79%, recall >= 5%, wrong <= 25%, max F1):** `filter_kept_AND_opp_eq_0_AND_prior_60m_le_1`