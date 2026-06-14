# E. TU-long (TREND_UP LONG-continuation) module research

**Build:** 2026-06-06T15:24:02+00:00
Window regime RANGE (ret -1.3%). TU-long zones: 7. Cross-venue NOT AVAILABLE.

| model | tr | W/L/TO | wr% | exp% | PF | ret% | hit2/2.5/3 | FP removed | rej winners |
|---|--:|:--:|--:|--:|--:|--:|:--:|--:|--:|
| M0_baseline_RS1 | 3 | 1/2/0 | 33.33 | -0.4733 | 0.567 | -1.42 | 1/0/0 | 0 | 0 |
| M1_TU_LONG_only | 3 | 1/2/0 | 33.33 | -0.4733 | 0.567 | -1.42 | 1/0/0 | 0 | 0 |
| M2_no_seller_absorption | 2 | 0/1/1 | 0.0 | -0.2369 | 0.711 | -0.4738 | 0/0/0 | 2 | 1 |
| M3_plus_reclaim | 1 | 0/0/1 | 0.0 | 1.1662 | None | 1.1662 | 0/0/0 | 4 | 1 |
| M4_plus_taker_microprice | 2 | 0/1/1 | 0.0 | -0.2369 | 0.711 | -0.4738 | 0/0/0 | 2 | 1 |
| M5_plus_thin_ask | 0 | 0/0/0 | 0.0 | None | None | None | 0/0/0 | 4 | 1 |
| M6_confluence_2of4 | 1 | 0/0/1 | 0.0 | 1.1662 | None | 1.1662 | 0/0/0 | 4 | 1 |
| M7_live_valid_2of4_cooldown | 1 | 0/0/1 | 0.0 | 1.1662 | None | 1.1662 | 0/0/0 | 4 | 1 |