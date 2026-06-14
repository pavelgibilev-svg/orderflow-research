# Train/test validation (first half vs second half)

**Build:** 2026-05-25T15:31:41+00:00
**First-half baseline precision:** 13.24%   |   **Second-half baseline:** 10.43%

| pattern | H1 alerts | H1 precision | H1 recall | H2 alerts | H2 precision | H2 recall | stable both halves |
|---|---:|---:|---:|---:|---:|---:|:---:|
| `baseline_all_confirmed` | 506 | 13.24 | 100.0 | 537 | 10.43 | 100.0 | NO |
| `filter_kept` | 103 | 15.53 | 23.88 | 121 | 13.22 | 28.57 | YES |
| `not_filter_kept` | 403 | 12.66 | 76.12 | 416 | 9.62 | 71.43 | NO |
| `opp_dir_zones_60m_eq_0` | 209 | 15.31 | 47.76 | 224 | 10.27 | 41.07 | NO |
| `opp_dir_zones_60m_le_1` | 346 | 13.29 | 68.66 | 380 | 11.58 | 78.57 | YES |
| `same_dir_zones_60m_eq_0` | 215 | 14.88 | 47.76 | 232 | 11.64 | 48.21 | YES |
| `prior_move_60m_pct_le_0_5` | 281 | 14.23 | 59.7 | 353 | 13.03 | 82.14 | YES |
| `prior_move_60m_pct_le_1_0` | 430 | 13.72 | 88.06 | 487 | 10.88 | 94.64 | YES |
| `prior_move_180m_pct_le_1_0` | 319 | 15.36 | 73.13 | 398 | 12.31 | 87.5 | YES |
| `local_range_60m_pct_ge_0_5` | 439 | 13.67 | 89.55 | 440 | 8.64 | 67.86 | NO |
| `ofi_score_aligned_strong` | 238 | 11.34 | 40.3 | 255 | 8.24 | 37.5 | NO |
| `flow_mult_ge_2` | 77 | 15.58 | 17.91 | 80 | 7.5 | 10.71 | NO |
| `flow_mult_le_2` | 429 | 12.82 | 82.09 | 457 | 10.94 | 89.29 | NO |
| `defended_persistence_ge_900` | 143 | 14.69 | 31.34 | 147 | 10.88 | 28.57 | YES |
| `zone_width_pct_le_0_4` | 310 | 14.19 | 65.67 | 400 | 10.75 | 76.79 | YES |
| `zone_width_pct_le_0_3` | 231 | 11.69 | 40.3 | 322 | 12.42 | 71.43 | NO |
| `confirm_to_trigger_le_60` | 210 | 14.76 | 46.27 | 233 | 9.01 | 37.5 | NO |
| `confirm_to_trigger_le_30` | 154 | 14.29 | 32.84 | 163 | 9.2 | 26.79 | NO |
| `filter_kept_AND_opp_dir_60m_eq_0` | 41 | 19.51 | 11.94 | 52 | 19.23 | 17.86 | YES |
| `filter_kept_AND_prior_60m_le_1` | 84 | 15.48 | 19.4 | 116 | 13.79 | 28.57 | YES |
| `opp_dir_60m_eq_0_AND_prior_60m_le_1` | 177 | 15.82 | 41.79 | 205 | 10.24 | 37.5 | NO |
| `opp_dir_60m_eq_0_AND_local_range_60m_ge_0_5` | 178 | 15.17 | 40.3 | 175 | 7.43 | 23.21 | NO |
| `filter_kept_AND_opp_eq_0_AND_prior_60m_le_1` | 34 | 17.65 | 8.96 | 49 | 20.41 | 17.86 | YES |
| `filter_kept_AND_zone_width_le_0_4` | 75 | 16.0 | 17.91 | 103 | 15.53 | 28.57 | YES |