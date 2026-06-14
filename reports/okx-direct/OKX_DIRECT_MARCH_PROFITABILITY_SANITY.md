# OKX direct partial March 2026 - profitability sanity (pre-cost + cost diagnostic)

**Build:** 2026-05-23T02:06:29+00:00
**Main metric: `PRE_COST_ONLY = YES`.**
**Cost diagnostic: fee_roundtrip = 0.08 %, slippage scenarios {0.02, 0.06, 0.10} %.**
**Target = 2 % strict. Stop = 1 % fixed. Timeout = 24h.**

## MODE 1 (alert-level, pre-cost)

| metric | value |
|---|---:|
| n_trades | 103 |
| wins | 21 |
| losses | 63 |
| timeouts | 19 |
| winrate_pct | 20.39 |
| avg_win_pct | 1.5429 |
| avg_loss_pct | -0.9179 |
| expectancy_pct_per_trade | -0.2012 |
| total_return_pct_1unit | -20.7193 |
| profit_factor | 0.691 |
| max_consecutive_losses | 10 |
| best_day | 2026-03-15 (4.0932%) |
| worst_day | 2026-03-08 (-5.5397%) |
| long_n | 60 |
| long_expectancy_pct | -0.0602 |
| short_n | 43 |
| short_expectancy_pct | -0.3978 |
| result_depends_on_one_day | False |
| exit_breakdown | _see exit_breakdown table below_ |

## MODE 1 exit-reason breakdown (pre-cost)

| metric | value |
|---|---:|
| pnl_from_wins | 42.0 |
| pnl_from_losses | -63.0 |
| pnl_from_timeouts | 0.2807 |
| timeout_positive_count | 9 |
| timeout_negative_count | 10 |
| timeout_nearzero_count | 0 |
| expectancy_if_timeouts_zero | -0.2039 |
| expectancy_if_timeouts_negative_0_5pct | -0.2961 |

## MODE 1 cost-aware diagnostic

| cost scenario (roundtrip %) | expectancy %/trade | profit factor | winrate % | total return % |
|---|---:|---:|---:|---:|
| 0.10 (fees0.08_slip0.02) | -0.3012 | 0.583 | 20.39 | -31.0193 |
| 0.14 (fees0.08_slip0.06) | -0.3412 | 0.545 | 20.39 | -35.1393 |
| 0.18 (fees0.08_slip0.1) | -0.3812 | 0.511 | 20.39 | -39.2593 |

## MODE 2 (strict ledger, pre-cost)

- skipped due to open position: **62**

| metric | value |
|---|---:|
| n_trades | 41 |
| wins | 11 |
| losses | 24 |
| timeouts | 6 |
| winrate_pct | 26.83 |
| avg_win_pct | 1.6722 |
| avg_loss_pct | -0.9426 |
| expectancy_pct_per_trade | -0.0497 |
| total_return_pct_1unit | -2.0386 |
| profit_factor | 0.92 |
| max_consecutive_losses | 6 |
| best_day | 2026-03-10 (5.0%) |
| worst_day | 2026-03-02 (-2.8885%) |
| long_n | 23 |
| long_expectancy_pct | 0.0885 |
| short_n | 18 |
| short_expectancy_pct | -0.2263 |
| result_depends_on_one_day | False |
| exit_breakdown | _see exit_breakdown table below_ |

## MODE 2 exit-reason breakdown (pre-cost)

| metric | value |
|---|---:|
| pnl_from_wins | 22.0 |
| pnl_from_losses | -24.0 |
| pnl_from_timeouts | -0.0386 |
| timeout_positive_count | 3 |
| timeout_negative_count | 3 |
| timeout_nearzero_count | 0 |
| expectancy_if_timeouts_zero | -0.0488 |
| expectancy_if_timeouts_negative_0_5pct | -0.122 |

## MODE 2 cost-aware diagnostic

| cost scenario (roundtrip %) | expectancy %/trade | profit factor | winrate % | total return % |
|---|---:|---:|---:|---:|
| 0.10 (fees0.08_slip0.02) | -0.1497 | 0.782 | 26.83 | -6.1386 |
| 0.14 (fees0.08_slip0.06) | -0.1897 | 0.734 | 26.83 | -7.7786 |
| 0.18 (fees0.08_slip0.1) | -0.2297 | 0.69 | 26.83 | -9.4186 |