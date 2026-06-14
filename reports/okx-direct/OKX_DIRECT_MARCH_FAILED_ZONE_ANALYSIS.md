# OKX direct partial-March 2026 - failed_triggered analysis

**Scope:** 14 UTC days, n_failed = 197.

## A. Counts

- n_failed = 197
- n with opposite direction reaching the move later same day: 0
- n with an active same-direction triggered zone in prior 60 min: 106

## B. Feature distributions (failed_triggered only)

| feature | n | mean | median | p25 | p75 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| `prior_move_pct` | 197 | 0.0002 | 0 | 0.0 | 0.0 | 0 | 0.0059 |
| `pressure_against` | 197 | 0.5949 | 0.5806 | 0.5634 | 0.6179 | 0.55 | 0.7769 |
| `absorb_score` | 197 | 0.6472 | 0.6332 | 0.6168 | 0.6639 | 0.6006 | 0.8546 |
| `trig_break_pct` | 197 | 0.2395 | 0.1346 | 0.0713 | 0.2815 | 0.0502 | 1.6668 |
| `trig_flow_multiplier` | 197 | 1.9522 | 1.5262 | 1.4129 | 2.0477 | 1.4 | 9.7457 |
| `confirm_to_trigger_min` | 197 | 60.5433 | 23.1 | 9.0333 | 73.8 | 0.15 | 517.8667 |
| `total_pre_trigger_min` | 197 | 72.4536 | 37.3833 | 18.65 | 88.8 | 3.7333 | 531.0 |
| `score_ofi` | 197 | -0.0095 | -0.0036 | -0.1571 | 0.1457 | -0.4782 | 0.4791 |
| `score_absorption` | 197 | 0.6455 | 0.6285 | 0.6105 | 0.6712 | 0.6 | 0.8399 |
| `target_24h_mfePct` | 197 | 0.8462 | 0.7881 | 0.3987 | 1.238 | -0.0001 | 1.9808 |

## C. Headline observations

- High n_with_active_same_dir_duplicate_in_60m suggests many failures are late-entry duplicates of an earlier
  triggered zone that has already exhausted its move; flagging via `duplicate_60m` should remove a chunk.
- If opposite-direction reaches later on a failed zone's day, that day's regime is hostile to this side -
  not a feature we can use as a strategy filter (would be lookahead), but informative for context.