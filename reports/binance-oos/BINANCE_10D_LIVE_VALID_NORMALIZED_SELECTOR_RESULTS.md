# Live-valid normalized selector — Binance 10d

**Build:** 2026-06-02T16:57:17+00:00
Days: 10. Thresholds frozen from OKX (supp_opp pctile≤75, score pctile floor 87.0). Causal first-eligible.

| model | tr | W | L | TO | wr% | exp% | PF | maxCL | wrongdir | alerts/d | no-trade days | fake-acc | GOOD skipped |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Model0_top1_day_RS1 | 10 | 1 | 5 | 4 | 10.0 | -0.5821 | 0.35 | 4 | 6 | 1.0 | 0 | 3 | 30 |
| Model1_norm_score_floor | 2 | 0 | 1 | 1 | 0.0 | -0.6886 | 0.16 | 1 | 1 | 0.2 | 8 | 0 | 31 |
| Model2_+dir_guard | 2 | 0 | 1 | 1 | 0.0 | -0.6886 | 0.16 | 1 | 1 | 0.2 | 8 | 0 | 31 |
| Model3_+noise | 0 | 0 | 0 | 0 | 0.0 | None | None | 0 | 0 | 0.0 | 10 | 0 | 31 |
| Model4_max2_cooldown_permissive | 1 | 0 | 1 | 0 | 0.0 | -1.64 | 0.0 | 1 | 1 | 0.1 | 9 | 0 | 31 |
| Model5_+no_trade_floor | 0 | 0 | 0 | 0 | 0.0 | None | None | 0 | 0 | 0.0 | 10 | 0 | 31 |