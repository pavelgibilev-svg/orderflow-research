# Entry / stop alternatives diagnostic (NOT a strategy change)

**Build:** 2026-05-23T09:46:28+00:00
**Diagnostic only. No engine change. Target=2 %, timeout=24h. Strict-ledger with conservative 24h hold gate.**

## OKX_direct_March

| variant | n trades | W/L/T | winrate % | expectancy % | PF | maxCons | LONG exp % | SHORT exp % | n_skipped |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `entry_delay_0min_stop_1pct` | 13 | 2/10/1 | 15.38 | -0.5258 | 0.369 | 6 | -0.25 | -0.9671 | 0 |
| `entry_delay_5min_stop_1pct` | 13 | 2/10/1 | 15.38 | -0.519 | 0.372 | 6 | -0.25 | -0.9493 | 0 |
| `entry_delay_10min_stop_1pct` | 13 | 2/10/1 | 15.38 | -0.5219 | 0.371 | 6 | -0.25 | -0.9568 | 0 |
| `entry_delay_15min_stop_1pct` | 13 | 3/9/1 | 23.08 | -0.2868 | 0.617 | 6 | 0.125 | -0.9457 | 0 |
| `entry_delay_30min_stop_1pct` | 13 | 4/8/1 | 30.77 | -0.0575 | 0.915 | 4 | 0.5 | -0.9494 | 0 |
| `entry_now_stop_1.25pct` | 13 | 3/9/1 | 23.08 | -0.4681 | 0.496 | 4 | -0.0312 | -1.1671 | 0 |
| `entry_now_stop_1.5pct` | 13 | 5/6/2 | 38.46 | -0.0598 | 0.928 | 3 | 0.3197 | -0.6671 | 0 |
| `entry_now_stop_max_zone_or_1pct` | 13 | 3/9/1 | 23.08 | -0.295 | 0.61 | 6 | 0.125 | -0.9671 | 0 |
| `no_go_gate_0.5pct_in_5min_stop_1pct` | 13 | 1/11/1 | 7.69 | -0.7566 | 0.169 | 10 | -0.625 | -0.9671 | 7 |
| `no_go_gate_0.5pct_in_10min_stop_1pct` | 13 | 1/10/2 | 7.69 | -0.7372 | 0.173 | 10 | -0.5936 | -0.9671 | 13 |

## Binance_Tardis_2025

| variant | n trades | W/L/T | winrate % | expectancy % | PF | maxCons | LONG exp % | SHORT exp % | n_skipped |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `entry_delay_0min_stop_1pct` | 12 | 5/2/5 | 41.67 | 0.982 | 5.351 | 1 | 1.0082 | 0.9558 | 0 |
| `entry_delay_5min_stop_1pct` | 12 | 5/2/5 | 41.67 | 0.9752 | 5.414 | 1 | 0.9872 | 0.9632 | 0 |
| `entry_delay_10min_stop_1pct` | 12 | 5/1/6 | 41.67 | 1.1603 | 9.684 | 1 | 1.3394 | 0.9811 | 0 |
| `entry_delay_15min_stop_1pct` | 12 | 5/2/5 | 41.67 | 0.9861 | 5.496 | 1 | 1.0005 | 0.9717 | 0 |
| `entry_delay_30min_stop_1pct` | 12 | 5/3/4 | 41.67 | 0.9665 | 4.866 | 1 | 1.0135 | 0.9195 | 0 |
| `entry_now_stop_1.25pct` | 12 | 5/1/6 | 41.67 | 1.1172 | 7.846 | 1 | 1.3202 | 0.9142 | 0 |
| `entry_now_stop_1.5pct` | 12 | 5/1/6 | 41.67 | 1.0964 | 6.958 | 1 | 1.3202 | 0.8725 | 0 |
| `entry_now_stop_max_zone_or_1pct` | 12 | 5/2/5 | 41.67 | 0.982 | 5.351 | 1 | 1.0082 | 0.9558 | 0 |
| `no_go_gate_0.5pct_in_5min_stop_1pct` | 12 | 5/2/5 | 41.67 | 0.982 | 5.351 | 1 | 1.0082 | 0.9558 | 0 |
| `no_go_gate_0.5pct_in_10min_stop_1pct` | 12 | 5/2/5 | 41.67 | 0.982 | 5.351 | 1 | 1.0082 | 0.9558 | 0 |

## Notes

- This is a DIAGNOSTIC to understand what entry / stop changes COULD improve outcomes.
- It does NOT propose modifying the strategy engine.
- Strict-ledger uses a conservative 24h hold gate (real hold time would be shorter for early-target/stop, but the count of strict trades stays the same).