# Canonical strict ledger - baseline (OKX + Binance)

**Build:** 2026-05-23T10:13:03+00:00
**Entry: trigger (next 1s bucket at/after triggerTs). Stop: fixed 1 %. Target: 2 %. Timeout: 24h.**

| metric | OKX direct March | Binance Tardis 2025 |
|---|---:|---:|
| n_trades | 44 | 18 |
| wins | 10 | 5 |
| losses | 27 | 3 |
| timeouts | 7 | 10 |
| winrate_pct | 22.73 | 27.78 |
| avg_win_pct | 1.6475 | 1.4051 |
| avg_loss_pct | -0.9438 | -0.6806 |
| expectancy_pct_per_trade | -0.1782 | 0.7098 |
| total_return_pct_1unit | -7.8407 | 12.777 |
| profit_factor | 0.732 | 4.129 |
| max_consecutive_losses | 6 | 3 |
| long_n | 25 | 10 |
| long_expectancy_pct | 0.0118 | 0.8335 |
| short_n | 19 | 8 |
| short_expectancy_pct | -0.4281 | 0.5552 |
| avg_mfe_pct | 1.0392 | 1.3065 |
| avg_mae_pct | 0.8586 | 0.5892 |

- OKX signals skipped due to open position: **59**
- Binance signals skipped due to open position: **40**