# E. Cross-venue live-valid selectors (trade Binance, OKX cross-confirm)

**Build:** 2026-06-04T12:12:29+00:00
| model | tr | W/L/TO | wr% | exp% | PF | ret% | no-trade | alerts/d | hit2/2.5/3 | fake |
|---|--:|:--:|--:|--:|--:|--:|--:|--:|:--:|--:|
| M0_single_RS1 | 10 | 1/4/5 | 10.0 | -0.5411 | 0.315 | -5.4107 | 0 | 1.0 | 1/1/1 | 0 |
| M1_norm_guard | 2 | 0/2/0 | 0.0 | -1.64 | 0.0 | -3.28 | 8 | 0.2 | 0/0/0 | 0 |
| M2_cross_confirm | 7 | 2/3/2 | 28.57 | -0.2078 | 0.744 | -1.4547 | 3 | 0.7 | 2/2/1 | 0 |
| M3_divergence_reject | 10 | 2/3/5 | 20.0 | -0.0717 | 0.884 | -0.7169 | 0 | 1.0 | 2/2/1 | 0 |
| M4_reclaim_confirm | 0 | 0/0/0 | 0.0 | None | None | None | 10 | 0.0 | 0/0/0 | 0 |
| M5_strong_score | 8 | 2/4/2 | 25.0 | -0.3868 | 0.577 | -3.0947 | 2 | 0.8 | 2/2/1 | 0 |
| M6_live_valid | 3 | 0/2/1 | 0.0 | -0.9697 | 0.113 | -2.909 | 8 | 0.3 | 0/0/0 | 0 |