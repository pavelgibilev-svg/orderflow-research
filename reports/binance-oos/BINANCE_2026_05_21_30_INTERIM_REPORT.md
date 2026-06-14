# Binance OOS INTERIM report (8 of 10 days)

**Build:** 2026-06-01T18:42:38+00:00
**STATUS: PARTIAL / INTERIM — not the final 10-day verdict. Small sample.**

Completed: ['2026-05-21', '2026-05-22', '2026-05-23', '2026-05-24', '2026-05-25', '2026-05-26', '2026-05-27', '2026-05-28']
Pending: ['2026-05-29', '2026-05-30']

## Engine per day

| date | zones | confirmed | triggered |
|---|---:|---:|---:|
| 2026-05-21 | 25 | 24 | 16 |
| 2026-05-22 | 27 | 23 | 14 |
| 2026-05-23 | 19 | 19 | 12 |
| 2026-05-24 | 7 | 7 | 4 |
| 2026-05-25 | 7 | 7 | 3 |
| 2026-05-26 | 23 | 22 | 15 |
| 2026-05-27 | 15 | 15 | 6 |
| 2026-05-28 | 15 | 14 | 7 |

## RS1 (frozen OKX rules) on completed days

| metric | value | OKX IS ref |
|---|---:|---:|
| trades | 8 | 29 |
| wins | 1 | 18 |
| losses | 4 | 8 |
| timeouts | 3 | 3 |
| winrate % | 12.5 | 62.07 |
| avg win aft | 1.86 | - |
| avg loss aft | -1.64 | - |
| avg timeout aft | -0.2202 | - |
| expectancy aft % | -0.6701 | 0.6475 |
| total return aft % | -5.3605 | 18.78 |
| PF aft | 0.294 | 2.258 |
| max consec losses | 6 | 3 |
| LONG/SHORT winrate | 0.0/25.0 | - |

## RS1 selected trades (interim)

| date | dir | result | pnl_aft% | dist_swh% | supp_opp_15m | thin_path | microprice5m | funding |
|---|:--:|:--:|--:|--:|--:|--:|--:|--:|
| 2026-05-21 | SHORT | TIMEOUT | 0.371 | 0.406 | -414.439 | 0.1066 | 6.54 | 0.24 |
| 2026-05-22 | SHORT | WIN | 1.86 | 0.0868 | -37.543 | 0.1044 | None | 0.41 |
| 2026-05-23 | LONG | LOSS | -1.64 | 0.157 | 1651.095 | 0.1075 | 0.0 | 0.2 |
| 2026-05-24 | SHORT | TIMEOUT | -0.76 | 0.1648 | -3020.726 | 0.1034 | -0.0 | 0.91 |
| 2026-05-25 | SHORT | TIMEOUT | -0.2715 | 0.0372 | 2145.759 | 0.109 | None | 0.65 |
| 2026-05-26 | LONG | LOSS | -1.64 | 0.289 | 720.849 | 0.1016 | None | 0.74 |
| 2026-05-27 | LONG | LOSS | -1.64 | 0.382 | 273.953 | 0.1017 | None | 1.0 |
| 2026-05-28 | LONG | LOSS | -1.64 | 0.0761 | -616.749 | 0.1054 | None | 1.0 |

**Caveat:** PARTIAL interim on completed days only. NOT the final 10-day OOS verdict. Small n; do not treat as conclusive.