# Live-valid normalized selector — OKX March

**Build:** 2026-06-02T16:57:16+00:00
Days: 29. Thresholds frozen from OKX (supp_opp pctile≤75, score pctile floor 87.0). Causal first-eligible.

| model | tr | W | L | TO | wr% | exp% | PF | maxCL | wrongdir | alerts/d | no-trade days | fake-acc | GOOD skipped |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Model0_top1_day_RS1 | 29 | 18 | 8 | 3 | 62.07 | 0.6475 | 2.258 | 3 | 8 | 1.0 | 0 | 0 | 364 |
| Model1_norm_score_floor | 24 | 11 | 9 | 4 | 45.83 | 0.2474 | 1.384 | 2 | 10 | 0.83 | 5 | 1 | 371 |
| Model2_+dir_guard | 24 | 11 | 9 | 4 | 45.83 | 0.2474 | 1.384 | 2 | 10 | 0.83 | 5 | 0 | 371 |
| Model3_+noise | 17 | 5 | 9 | 3 | 29.41 | -0.2316 | 0.733 | 3 | 9 | 0.59 | 12 | 0 | 377 |
| Model4_max2_cooldown_permissive | 50 | 19 | 26 | 5 | 38.0 | -0.0992 | 0.884 | 4 | 26 | 1.72 | 3 | 0 | 363 |
| Model5_+no_trade_floor | 24 | 7 | 13 | 4 | 29.17 | -0.3123 | 0.66 | 5 | 14 | 0.83 | 12 | 0 | 375 |