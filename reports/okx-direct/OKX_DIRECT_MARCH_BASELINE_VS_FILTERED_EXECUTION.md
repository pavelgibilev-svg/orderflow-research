# OKX direct partial March 2026 - baseline vs filtered execution (pre-cost)

**Build:** 2026-05-23T02:06:31+00:00
**Same target=2 %, stop=1 %, timeout=24h applied to BOTH sets.**

## MODE 1 (alert-level)

| metric | baseline | filtered | delta |
|---|---:|---:|---|
| n_trades | 295 | 103 | -192 |
| wins | 56 | 21 | -35 |
| losses | 188 | 63 | -125 |
| timeouts | 51 | 19 | -32 |
| winrate_pct | 18.98 | 20.39 | 1.41 |
| avg_win_pct | 1.5291 | 1.5429 | 0.0138 |
| avg_loss_pct | -0.9368 | -0.9179 | 0.0189 |
| expectancy_pct_per_trade | -0.2179 | -0.2012 | 0.0167 |
| total_return_pct_1unit | -64.2827 | -20.7193 | 43.5634 |
| profit_factor | 0.672 | 0.691 | 0.019 |
| max_consecutive_losses | 18 | 10 | -8 |
| long_n | 158 | 60 | -98 |
| long_expectancy_pct | -0.1016 | -0.0602 | 0.0414 |
| short_n | 137 | 43 | -94 |
| short_expectancy_pct | -0.352 | -0.3978 | -0.0458 |

## MODE 2 (strict ledger)

| metric | baseline | filtered | delta |
|---|---:|---:|---|
| n_trades | 51 | 41 | -10 |
| wins | 11 | 11 | 0 |
| losses | 30 | 24 | -6 |
| timeouts | 10 | 6 | -4 |
| winrate_pct | 21.57 | 26.83 | 5.26 |
| avg_win_pct | 1.5144 | 1.6722 | 0.1578 |
| avg_loss_pct | -0.9242 | -0.9426 | -0.0184 |
| expectancy_pct_per_trade | -0.1592 | -0.0497 | 0.1095 |
| total_return_pct_1unit | -8.1175 | -2.0386 | 6.0789 |
| profit_factor | 0.749 | 0.92 | 0.171 |
| max_consecutive_losses | 8 | 6 | -2 |
| long_n | 25 | 23 | -2 |
| long_expectancy_pct | 0.0115 | 0.0885 | 0.077 |
| short_n | 26 | 18 | -8 |
| short_expectancy_pct | -0.3232 | -0.2263 | 0.0969 |

## Wrong-direction alerts

- baseline: **44** (out of 295 triggered)
- filtered: **15** (out of 103 alerts)