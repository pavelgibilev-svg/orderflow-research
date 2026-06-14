# Binance Tardis 2025 - baseline vs filtered execution (pre-cost)

**Build:** 2026-05-22T16:56:43+00:00
**Same target=2 %, stop=1 %, timeout=24h applied to BOTH sets.**

## MODE 1 (alert-level)

| metric | baseline | filtered | delta |
|---|---:|---:|---|
| n_trades | 209 | 58 | -151 |
| wins | 33 | 8 | -25 |
| losses | 77 | 16 | -61 |
| timeouts | 99 | 34 | -65 |
| winrate_pct | 15.79 | 13.79 | -2.0 |
| avg_win_pct | 1.1475 | 0.9921 | -0.1554 |
| avg_loss_pct | -0.7914 | -0.7105 | 0.0809 |
| expectancy_pct_per_trade | 0.1548 | 0.1995 | 0.0447 |
| total_return_pct_1unit | 32.3633 | 11.5728 | -20.7905 |
| profit_factor | 1.382 | 1.603 | 0.221 |
| max_consecutive_losses | 11 | 3 | -8 |
| long_n | 121 | 34 | -87 |
| long_expectancy_pct | 0.3289 | 0.2776 | -0.0513 |
| short_n | 88 | 24 | -64 |
| short_expectancy_pct | -0.0845 | 0.0889 | 0.1734 |

## MODE 2 (strict ledger)

| metric | baseline | filtered | delta |
|---|---:|---:|---|
| n_trades | 24 | 19 | -5 |
| wins | 5 | 5 | 0 |
| losses | 7 | 3 | -4 |
| timeouts | 12 | 11 | -1 |
| winrate_pct | 20.83 | 26.32 | 5.49 |
| avg_win_pct | 1.2572 | 1.5234 | 0.2662 |
| avg_loss_pct | -0.8108 | -0.5691 | 0.2417 |
| expectancy_pct_per_trade | 0.3955 | 0.6423 | 0.2468 |
| total_return_pct_1unit | 9.4923 | 12.2039 | 2.7116 |
| profit_factor | 2.171 | 3.68 | 1.509 |
| max_consecutive_losses | 3 | 3 | 0 |
| long_n | 15 | 10 | -5 |
| long_expectancy_pct | 0.4874 | 0.7827 | 0.2953 |
| short_n | 9 | 9 | 0 |
| short_expectancy_pct | 0.2424 | 0.4864 | 0.244 |

## Wrong-direction alerts

- baseline: **38** (out of 209 triggered)
- filtered: **10** (out of 58 alerts)