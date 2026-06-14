# BINANCE_2026_05_21_27_INTERIM — RS1 FROZEN BASELINE (7 completed days)

**Build:** 2026-06-01T18:53:04+00:00
**STATUS: INTERIM / PARTIAL — small sample, not conclusive.**

Selector: `dist_to_recent_swing_high_pct <= 0.4616 AND dl2_supp_minus_opp_net_flow_15m <= 4497.76`, top1/day.
Trade: entry=confirmed, TP 2%, SL 1.5%, timeout 24h, no BE, cost 0.14%, canonical ledger (exact timeout PnL).

Candidate zones passing filter: 41; days with a selected trade: 7.

| metric | value | OKX IS ref |
|---|---:|---:|
| trades | 7 | 29 |
| wins | 1 | 18 |
| losses | 3 | 8 |
| timeouts | 3 | 3 |
| winrate % | 14.29 | 62.07 |
| avg win aft % | 1.86 | - |
| avg loss aft % | -1.64 | - |
| avg timeout aft % | -0.2202 | - |
| expectancy aft % | -0.5315 | 0.6475 |
| total return aft % | -3.7205 | 18.78 |
| PF aft | 0.375 | 2.258 |
| max consec losses | 5 | 3 |
| LONG/SHORT winrate | 0.0/25.0 | - |

- correct-direction-but-no-2%: **1**
- wrong-direction: **5**
- stop_no_2pct_either_dir: **3**

**Per-day PnL after cost:** 2026-05-21=+0.371, 2026-05-22=+1.860, 2026-05-23=-1.640, 2026-05-24=-0.760, 2026-05-25=-0.272, 2026-05-26=-1.640, 2026-05-27=-1.640