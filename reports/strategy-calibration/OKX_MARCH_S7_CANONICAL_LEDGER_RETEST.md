# S7 exact canonical-ledger retest

**Build:** 2026-05-30T10:46:08+00:00
**Exact `simulate_canonical_trade` — real timeout exit price, no approximation.**

| metric | enhanced baseline | S7 EV-overlay |
|---|---:|---:|
| trades | 29 | 26 |
| wins | 18 | 17 |
| losses | 8 | 7 |
| timeouts | 3 | 2 |
| winrate_pct | 62.07 | 65.38 |
| avg_win_after_cost | 1.86 | 1.86 |
| avg_loss_after_cost | -1.64 | -1.64 |
| avg_timeout_pnl_after_cost | -0.5276 | -0.4467 |
| expectancy_pre_cost_pct | 0.7875 | 0.8803 |
| expectancy_after_cost_pct | 0.6475 | 0.7403 |
| total_return_after_cost_pct | 18.7771 | 19.2466 |
| pf_after_cost | 2.258 | 2.527 |
| max_consecutive_losses | 3 | 3 |
| long_winrate | 55.56 | 58.82 |
| short_winrate | 72.73 | 77.78 |
| h1_winrate | 71.43 | 76.92 |
| h2_winrate | 53.33 | 53.85 |

- Enhanced setup split: {'absorption_reversal_long': 17, 'absorption_reversal_short': 10, 'retest_after_breakout_long': 1, 'retest_after_breakout_short': 1}
- S7 setup split: {'absorption_reversal_long': 16, 'absorption_reversal_short': 8, 'retest_after_breakout_long': 1, 'retest_after_breakout_short': 1}