# OKX direct partial-March 2026 - passive filter v0 analysis (research-only)

**Scope:** 14 UTC days. **NO filter is wired into the strategy.** These rules are evaluated
by re-classifying each already-produced zone post-hoc. No threshold inside the engine is changed.

## A. Baseline (no filter)

- n_zones = 510
- n_triggered = 295
- n_reached_raw = 98
- n_primary_unique = 15  (= the 15 unique moves)
- n_duplicate_reached = 83
- n_failed_triggered = 197
- n_no_trigger = 33
- n_invalidated_or_expired = 182

## B. Single-rule filters

| rule | primary recall | duplicate remove | failed reduce | actionable/day | precision triggered->reached |
|---|---:|---:|---:|---:|---:|
| `duplicate_30m` | 1.0 | 0.458 | 0.406 | 12.643 | 0.339 |
| `duplicate_60m` | 1.0 | 0.578 | 0.538 | 10.071 | 0.355 |
| `late_entry_prior_move<0.5pct` | 1.0 | 0.0 | 0.0 | 21.071 | 0.332 |
| `fast_trigger_<=60min` | 1.0 | 0.349 | 0.284 | 15.0 | 0.329 |
| `fast_trigger_<=30min` | 0.667 | 0.566 | 0.452 | 11.0 | 0.299 |
| `flow_confirmation_>=2x` | 0.333 | 0.759 | 0.736 | 5.5 | 0.325 |
| `flow_confirmation_>=3x` | 0.333 | 0.892 | 0.904 | 2.357 | 0.424 |
| `target_feasibility_width<=0.5pct` | 0.8 | 0.289 | 0.198 | 16.357 | 0.31 |
| `counter_direction_ofi` | 0.6 | 0.253 | 0.289 | 15.071 | 0.336 |

## C. Combinations (AND-of-rules)

| combination | primary recall | duplicate remove | failed reduce | actionable/day | precision triggered->reached |
|---|---:|---:|---:|---:|---:|
| `duplicate_60m_AND_flow>=2x` | 0.333 | 0.892 | 0.888 | 2.571 | 0.389 |
| `duplicate_60m_AND_fast<=60m` | 1.0 | 0.735 | 0.706 | 6.786 | 0.389 |
| `duplicate_60m_AND_late_entry<0.5pct` | 1.0 | 0.578 | 0.538 | 10.071 | 0.355 |
| `duplicate_60m_AND_counter_direction_ofi` | 0.6 | 0.651 | 0.68 | 7.214 | 0.376 |
| `duplicate_60m_AND_flow>=2x_AND_counter_direction_ofi` | 0.2 | 0.928 | 0.909 | 1.929 | 0.333 |
| `duplicate_60m_AND_flow>=2x_AND_fast<=60m` | 0.333 | 0.94 | 0.919 | 1.857 | 0.385 |
| `ALL5: dup60_flow2_fast60_late0.5_counter_ofi` | 0.2 | 0.964 | 0.934 | 1.357 | 0.316 |

## D. Best candidate (research-only, do NOT integrate)

- name: `duplicate_60m_AND_fast<=60m`
- composite score (duplicate_remove + failed_reduce): **1.441**
- primary recall: **1.0**
- duplicate remove rate: **0.735**
- failed reduce rate: **0.706**
- actionable signals per day: **6.786**

## E. Caveats

- 15 primary positives across 14 days is too thin to fit a production filter. These numbers are SUGGESTIVE.
- All filter cuts are evaluated on the SAME 14-day window they were considered against; no held-out OOS.
- Engine thresholds were NOT changed; this is a post-hoc reclassification.