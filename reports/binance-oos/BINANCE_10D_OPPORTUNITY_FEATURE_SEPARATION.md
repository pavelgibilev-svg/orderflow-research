# B. GOOD vs NOISE feature separation (after guard) — BINANCE_10D

**Build:** 2026-06-02T17:15:24+00:00
Kept (guard-passing) n=102 · GOOD 21 · NOISE 43 · base 20.6%

| feature | GOOD med | NOISE med | Cohen d | prec uplift | recall | FP removed | GOOD lost |
|---|--:|--:|--:|--:|--:|--:|--:|
| taker_imbalance_15m | 0.0272 | -0.0168 | 0.647 | 0.062 | 0.524 | 28 | 10 |
| eng_void | 0.3038 | 0.1752 | 0.532 | 0.014 | 0.524 | 25 | 10 |
| ms_thin_path_score | 0.1021 | 0.1034 | -0.469 | 0.118 | 0.524 | 26 | 10 |
| book_entropy_top25 | 0.3566 | 0.371 | -0.421 | 0.05 | 0.524 | 26 | 10 |
| ms_large_walls_on_path | 14 | 12 | 0.254 | 0.127 | 0.619 | 24 | 8 |
| prior_move_60m_pct | -0.152 | -0.0001 | -0.233 | 0.039 | 0.524 | 27 | 10 |
| uniq_score_pctile_vs_prior | 41.7 | 47.8 | -0.222 | 0.028 | 0.524 | 25 | 10 |
| explainable_score__pctile_prior | 41.7 | 47.8 | -0.222 | 0.028 | 0.524 | 25 | 10 |
| dist_to_recent_swing_high_pct | 0.5887 | 0.4176 | 0.213 | 0.014 | 0.524 | 25 | 10 |
| dl2_microprice_aligned_delta_5m_bps__pctile_prior | 47.45 | 55.0 | 0.167 | 0.215 | 0.381 | 35 | 13 |
| reclaim_zoneMid_preconfirm | 0 | 0 | -0.157 | 0.0 | 1.0 | 0 | 0 |
| eng_ofi | 0.0526 | -0.0412 | -0.132 | 0.012 | 0.476 | 24 | 11 |
| supportive_taker_imb_15m | 0.0272 | 0.005 | 0.062 | 0.05 | 0.524 | 26 | 10 |
| dl2_supp_minus_opp_net_flow_15m__pctile_prior | 45.5 | 49.75 | 0.006 | 0.023 | 0.524 | 26 | 10 |