# BINANCE_2026_05_21_27_INTERIM — RS2 S7 OVERLAY (PARTIAL, 7 completed days)

**Build:** 2026-06-01T18:53:04+00:00
**STATUS: INTERIM / PARTIAL.** `RS2_PARTIAL = YES` — Binance recorder has **no open-interest stream**, so the true-OI fuel component is omitted (NOT replaced by a proxy). p_reach uses void+wall+microprice+funding only. EV threshold and p_reach weights unchanged.

Applied AFTER RS1. EV>0.4. Removed 4 of 7 RS1 selections.

| metric | value | OKX IS ref |
|---|---:|---:|
| trades | 3 | 29 |
| wins | 1 | 18 |
| losses | 0 | 8 |
| timeouts | 2 | 3 |
| winrate % | 33.33 | 62.07 |
| avg win aft % | 1.86 | - |
| avg loss aft % | None | - |
| avg timeout aft % | 0.0497 | - |
| expectancy aft % | 0.6532 | 0.6475 |
| total return aft % | 1.9595 | 18.78 |
| PF aft | 8.217 | 2.258 |
| max consec losses | 1 | 3 |
| LONG/SHORT winrate | 0.0/33.33 | - |

- RS2 improves RS1 (expectancy): **YES**