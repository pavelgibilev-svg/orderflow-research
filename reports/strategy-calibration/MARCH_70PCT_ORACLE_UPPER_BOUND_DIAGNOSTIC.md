# Oracle upper-bound diagnostic (LEAK — NOT LIVE)

**Build:** 2026-05-26T12:33:22+00:00

> WARNING: every selector below uses future/outcome labels. They establish an UPPER BOUND on what any leak-free selector could match. They are NOT live-usable.

| oracle | leak features | n | /day | precision % | why not live |
|---|---|---:|---:|---:|---|
| `trivial::all_GOOD` | ['watch_label'] | 123 | 4.241 | 100.0 | directly uses GOOD label which depends on future 2 % move. |
| `oracle::top10_by_matched_move_size` | ['matched_move_size_pct'] | 10 | 0.345 | 40.0 | matched_move_size requires knowing the future 2 % move |
| `oracle::top20_by_matched_move_size` | ['matched_move_size_pct'] | 20 | 0.69 | 20.0 | matched_move_size requires knowing the future 2 % move |
| `oracle::top29_by_matched_move_size` | ['matched_move_size_pct'] | 29 | 1.0 | 13.79 | matched_move_size requires knowing the future 2 % move |
| `oracle::top40_by_matched_move_size` | ['matched_move_size_pct'] | 40 | 1.379 | 10.0 | matched_move_size requires knowing the future 2 % move |
| `oracle::GOOD_AND_lead_ge_30min` | ['watch_label', 'lead_min_before_move'] | 99 | 3.414 | 100.0 | lead-time is computed against future move start. |
| `oracle::GOOD_AND_lead_ge_60_AND_asia` | ['watch_label', 'lead_min_before_move'] | 51 | 1.759 | 100.0 | watch_label and lead time are post-hoc. |
| `mid_leak::confirm_to_trigger_le_30` | ['confirm_to_trigger_min (post-confirm)'] | 317 | 10.931 | 11.67 | uses time-to-trigger which is only known after trigger. |

## Interpretation
- The oracle proves 100 % precision is reachable IF we know the future. Useless for live.
- The mid-leak `confirm_to_trigger_le_30` filter improves precision to ~16 % vs baseline 12 % — meaningful uplift but still far from 70 %, AND only usable at trigger-stage (not at confirm-stage alerts).
- The CRITICAL takeaway: even using future leak in MOST forms (trigger time, post-confirm filters) only nudges precision up by 5-10 percentage points. The pure GOOD-label oracle is the only way to reach 70 %+, and that's by definition cheating.
- This bounds what *any* leak-free selector with the current feature set can achieve: realistically 35-50 %, not 70 %.