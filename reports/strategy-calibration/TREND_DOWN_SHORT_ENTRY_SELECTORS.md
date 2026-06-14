# C. TREND_DOWN SHORT — entry-trigger selectors

**Build:** 2026-06-04T15:57:14+00:00
First-eligible 1/day among TREND_DOWN SHORT zones (pooled venues). No norm_filter (standalone setup).

| model | tr | W/L/TO | wr% | exp% | PF | ret% | maxCL | alerts/d | hit2/2.5/3 | FP removed |
|---|--:|:--:|--:|--:|--:|--:|--:|--:|:--:|--:|
| M0_base_TD_short | 15 | 7/4/4 | 46.67 | 0.4749 | 2.014 | 7.1236 | 3 | 1.0 | 7/7/5 | 0 |
| M1_rejection | 14 | 8/5/1 | 57.14 | 0.4445 | 1.719 | 6.2231 | 3 | 0.93 | 8/7/5 | 29 |
| M2_taker_sell | 14 | 6/4/4 | 42.86 | 0.4509 | 1.909 | 6.3132 | 3 | 0.93 | 6/6/5 | 25 |
| M3_microprice_down | 15 | 8/4/3 | 53.33 | 0.5275 | 2.13 | 7.9119 | 3 | 1.0 | 8/7/6 | 8 |
| M4_thin_path | 11 | 6/2/3 | 54.55 | 0.8093 | 3.628 | 8.9023 | 2 | 0.73 | 6/6/5 | 16 |
| M5_confluence_2of4 | 15 | 7/4/4 | 46.67 | 0.4749 | 2.014 | 7.1236 | 3 | 1.0 | 7/7/5 | 8 |
| M6_confluence_3of5 | 15 | 7/4/4 | 46.67 | 0.4749 | 2.014 | 7.1236 | 3 | 1.0 | 7/7/5 | 9 |
| M7_live_valid_2of4_cooldown | 26 | 13/7/6 | 50.0 | 0.5407 | 2.129 | 14.0588 | 5 | 1.73 | 13/13/11 | 8 |