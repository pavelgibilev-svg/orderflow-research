# B. GOOD vs NOISE feature separation (after guard) — OKX_MARCH

**Build:** 2026-06-02T17:15:24+00:00
Kept (guard-passing) n=954 · GOOD 354 · NOISE 518 · base 37.1%

| feature | GOOD med | NOISE med | Cohen d | prec uplift | recall | FP removed | GOOD lost |
|---|--:|--:|--:|--:|--:|--:|--:|
| prior_move_60m_pct | 0.0146 | -0.0624 | 0.106 | 0.015 | 0.5 | 278 | 177 |
| taker_imbalance_15m | 0.0106 | -0.0049 | 0.083 | 0.02 | 0.5 | 272 | 177 |
| eng_ofi | 0.0261 | 0.0026 | 0.081 | 0.023 | 0.5 | 279 | 177 |
| reclaim_zoneMid_preconfirm | 1.0 | 1.0 | -0.071 | -0.007 | 0.517 | 232 | 171 |
| uniq_score_pctile_vs_prior | 57.1 | 57.8 | -0.06 | 0.001 | 0.503 | 263 | 176 |
| explainable_score__pctile_prior | 57.1 | 57.8 | -0.06 | 0.001 | 0.503 | 263 | 176 |
| supportive_taker_imb_15m | -0.0308 | -0.0251 | -0.046 | -0.002 | 0.5 | 266 | 177 |
| dl2_supp_minus_opp_net_flow_15m__pctile_prior | 49.1 | 49.25 | -0.032 | -0.002 | 0.5 | 259 | 177 |
| dl2_microprice_aligned_delta_5m_bps__pctile_prior | 48.75 | 49.7 | -0.02 | 0.006 | 0.497 | 269 | 178 |
| dist_to_recent_swing_high_pct | 0.6028 | 0.6772 | -0.005 | 0.02 | 0.5 | 282 | 177 |
| eng_void | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 0 | 0 |
| ms_thin_path_score | None | None | None | None | None | None | None |
| ms_large_walls_on_path | None | None | None | None | None | None | None |
| book_entropy_top25 | None | None | None | None | None | None | None |