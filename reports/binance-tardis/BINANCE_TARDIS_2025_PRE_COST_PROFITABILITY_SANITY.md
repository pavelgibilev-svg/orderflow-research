# Binance Tardis 2025 - pre-cost profitability sanity

**Build:** 2026-05-22T16:56:41+00:00
**`PRE_COST_ONLY = YES`, `FEES_SLIPPAGE_INCLUDED = NO`, `PROFITABILITY_CLAIM = NO`.**
**Target = 2 % (strict). Stop = 1 % fixed. Timeout = 24h.**

## MODE 1 (alert-level, every filtered signal is an independent trade)

| metric | value |
|---|---:|
| n_trades | 58 |
| wins | 8 |
| losses | 16 |
| timeouts | 34 |
| winrate_pct | 13.79 |
| avg_win_pct | 0.9921 |
| avg_loss_pct | -0.7105 |
| expectancy_pct_per_trade | 0.1995 |
| total_return_pct_1unit | 11.5728 |
| profit_factor | 1.603 |
| max_consecutive_losses | 3 |
| best_day | 2025-08-01 (4.4116%) |
| worst_day | 2025-03-01 (-1.7427%) |
| long_n | 34 |
| long_expectancy_pct | 0.2776 |
| short_n | 24 |
| short_expectancy_pct | 0.0889 |
| result_depends_on_one_day | False |

## MODE 2 (strict ledger, one trade at a time)

- skipped due to open position: **39**

| metric | value |
|---|---:|
| n_trades | 19 |
| wins | 5 |
| losses | 3 |
| timeouts | 11 |
| winrate_pct | 26.32 |
| avg_win_pct | 1.5234 |
| avg_loss_pct | -0.5691 |
| expectancy_pct_per_trade | 0.6423 |
| total_return_pct_1unit | 12.2039 |
| profit_factor | 3.68 |
| max_consecutive_losses | 3 |
| best_day | 2025-12-01 (2.9775%) |
| worst_day | 2025-03-01 (-2.0%) |
| long_n | 10 |
| long_expectancy_pct | 0.7827 |
| short_n | 9 |
| short_expectancy_pct | 0.4864 |
| result_depends_on_one_day | False |