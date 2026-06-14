# C2. OKX vs Binance — feature distribution shift

**Build:** 2026-06-02T14:02:11+00:00
Cohorts: OKX win=17 OKX loss=9 · Binance win=31 loss=72 sel-loss=6 skipped-win=30

| feature | OKXwin (med) | OKXloss | BNCwin | BNCloss | BNC sel-loss | BNC skip-win |
|---|--:|--:|--:|--:|--:|--:|
| dl2_supp_minus_opp_net_flow_5m | 3384.99 | 5377.51 | -30.739 | -33.4435 | 315.6555 | -36.087 |
| dl2_microprice_aligned_delta_5m_bps | 4.633 | 4.972 | 0.0 | -0.0 | 0.0 | 0.0 |
| dl2_microprice_aligned_delta_15m_bps | 19.58 | 7.343 | 0.0 | -0.0 | None | 0.0 |
| dist_to_recent_swing_high_pct | 0.2049 | 0.1417 | 0.7255 | 0.6741 | 0.1609 | 0.7641 |
| local_range_180m_pct | 0.8705 | 1.0441 | 1.1045 | 0.938 | 0.2757 | 1.1126 |
| prior_move_60m_pct | 0.2572 | 0.3196 | -0.226 | -0.2213 | -0.1456 | -0.2888 |
| explainable_score | 1.6199 | 1.8603 | 0.3279 | 0.3308 | 0.7052 | 0.3251 |
| dl2_top1_supportive_persistence_ge_50_5m_sec | 270.0 | 277.0 | 0 | 0.0 | 0.0 | 0.0 |