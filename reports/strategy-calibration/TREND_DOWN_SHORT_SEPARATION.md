# B. TREND_DOWN SHORT — winner vs loser separation

**Build:** 2026-06-04T15:57:14+00:00
Cohorts: win 62 · noise 48 · strong(>=2.5) 61 · weak(2-2.5) 5 · timeout 31

### WIN vs NOISE (Cohen d, |d|>=0.3 = signal)
| feature | win med | noise med | d |
|---|--:|--:|--:|
| book_entropy_top25 | 0.4219 | 0.2962 | 1.575 |
| supportive_taker_imb_15m | -0.0541 | -0.0249 | -0.368 |
| taker_imbalance_15m | 0.0541 | 0.0249 | 0.368 |
| eng_ofi | -0.0612 | -0.1056 | 0.28 |
| reclaim_zoneMid_preconfirm | 1.0 | 0.0 | 0.243 |
| dist_to_recent_swing_high_pct | 1.1091 | 1.0897 | 0.22 |
| eng_void | 1.0 | 1.0 | 0.206 |
| uniq_score_pctile_vs_prior | 49.95 | 64.4 | -0.174 |
| ms_thin_path_score | 0.0958 | 0.0944 | -0.123 |
| dl2_microprice_aligned_delta_5m_bps | 1.101 | 1.4485 | 0.12 |
| eng_refill | 0.5003 | 0.5 | 0.116 |
| prior_move_60m_pct | -0.4284 | -0.4022 | -0.064 |

### STRONG(2.5) vs WEAK(2-2.5)
| feature | strong med | weak med | d |
|---|--:|--:|--:|
| prior_move_60m_pct | -0.5478 | 0.2764 | -1.742 |
| dist_to_recent_swing_high_pct | 1.2728 | 0.7232 | 1.008 |
| supportive_taker_imb_15m | -0.0358 | -0.1524 | 0.686 |
| taker_imbalance_15m | 0.0358 | 0.1524 | -0.686 |
| eng_refill | 0.5002 | 0.5007 | -0.567 |
| uniq_score_pctile_vs_prior | 50.8 | 44.0 | 0.366 |
| reclaim_zoneMid_preconfirm | 1 | 0 | 0.285 |
| eng_ofi | -0.0649 | -0.0255 | -0.133 |
| dl2_microprice_aligned_delta_5m_bps | 1.462 | 0.344 | -0.113 |
| eng_void | 1 | 1 | 0.0 |
| ms_thin_path_score | 0.0958 | None | None |
| book_entropy_top25 | 0.4219 | None | None |