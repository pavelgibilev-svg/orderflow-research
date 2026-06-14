# 70 % paper-trade optimization

**Build:** 2026-05-26T12:38:35+00:00
**Models tested:** 200
**Cost:** 0.14 % roundtrip  |  **Target:** 2.0 %  |  **Timeout:** 24 h

## Top 30 by winrate (any size)

| selector | entry | stop | trades | winrate % | exp aft % | PF aft | total ret aft % | maxCL |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `S::score_trigger_ge_1.0::top1` | delay_10m | stop_1.5 | 29 | 62.07 | 0.6228 | 2.172 | 18.0624 | 3 |
| `S::score_trigger_ge_1.0::top1` | delay_10m | stop_1.5 | 29 | 62.07 | 0.6228 | 2.172 | 18.0624 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 | 16.5059 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 | 16.5059 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 | 16.5059 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 | 16.5059 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 | 16.5059 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 | 16.5059 | 3 |
| `P::score_trigger_ge_1.0+is_during_correct_move_FALSE::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 | 16.5059 | 3 |
| `P::score_trigger_ge_1.0+is_during_correct_move_FALSE::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 | 16.5059 | 3 |
| `S::score_trigger_ge_1.0::top1` | delay_5m | stop_1.5 | 29 | 58.62 | 0.6938 | 2.584 | 20.12 | 3 |
| `S::score_trigger_ge_1.0::top1` | delay_5m | stop_1.5 | 29 | 58.62 | 0.6938 | 2.584 | 20.12 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 | 18.668 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 | 18.668 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 | 18.668 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 | 18.668 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 | 18.668 | 3 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 | 18.668 | 3 |
| `P::score_trigger_ge_1.0+is_during_correct_move_FALSE::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 | 18.668 | 3 |
| `P::score_trigger_ge_1.0+is_during_correct_move_FALSE::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 | 18.668 | 3 |
| `S::score_trigger_ge_1.0::top1` | confirmed | stop_1.25 | 29 | 55.17 | 0.5758 | 2.222 | 16.6985 | 3 |
| `S::score_trigger_ge_1.0::top1` | confirmed | stop_1.5 | 29 | 55.17 | 0.4982 | 1.908 | 14.4485 | 3 |
| `S::score_trigger_ge_1.0::top1` | delay_5m | stop_1.25 | 29 | 55.17 | 0.5822 | 2.229 | 16.8845 | 3 |
| `S::score_trigger_ge_1.0::top1` | delay_10m | stop_1.25 | 29 | 55.17 | 0.4763 | 1.866 | 13.8124 | 3 |
| `S::score_trigger_ge_1.0::top1` | delay_15m | stop_1.5 | 29 | 55.17 | 0.4654 | 1.793 | 13.4967 | 3 |
| `S::score_trigger_ge_1.0::top1` | confirmed | stop_1.25 | 29 | 55.17 | 0.5758 | 2.222 | 16.6985 | 3 |
| `S::score_trigger_ge_1.0::top1` | confirmed | stop_1.5 | 29 | 55.17 | 0.4982 | 1.908 | 14.4485 | 3 |
| `S::score_trigger_ge_1.0::top1` | delay_5m | stop_1.25 | 29 | 55.17 | 0.5822 | 2.229 | 16.8845 | 3 |
| `S::score_trigger_ge_1.0::top1` | delay_10m | stop_1.25 | 29 | 55.17 | 0.4763 | 1.866 | 13.8124 | 3 |
| `S::score_trigger_ge_1.0::top1` | delay_15m | stop_1.5 | 29 | 55.17 | 0.4654 | 1.793 | 13.4967 | 3 |

## Top 20 by winrate with >= 20 trades

| selector | entry | stop | trades | winrate % | exp aft % | PF aft |
|---|---|---|---:|---:|---:|---:|
| `S::score_trigger_ge_1.0::top1` | delay_10m | stop_1.5 | 29 | 62.07 | 0.6228 | 2.172 |
| `S::score_trigger_ge_1.0::top1` | delay_10m | stop_1.5 | 29 | 62.07 | 0.6228 | 2.172 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 |
| `P::score_trigger_ge_1.0+is_during_correct_move_FALSE::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 |
| `P::score_trigger_ge_1.0+is_during_correct_move_FALSE::top1` | delay_10m | stop_1.5 | 29 | 58.62 | 0.5692 | 2.071 |
| `S::score_trigger_ge_1.0::top1` | delay_5m | stop_1.5 | 29 | 58.62 | 0.6938 | 2.584 |
| `S::score_trigger_ge_1.0::top1` | delay_5m | stop_1.5 | 29 | 58.62 | 0.6938 | 2.584 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 |
| `P::score_trigger_ge_1.0+is_during_correct_move_FALSE::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 |
| `P::score_trigger_ge_1.0+is_during_correct_move_FALSE::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.6437 | 2.469 |