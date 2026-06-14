# OKX direct mini-OOS filter validation - 2026-03-11..2026-03-13

**Build:** 2026-05-21T14:03:24+00:00
**Scope:** 3 days only (2026-03-11, 2026-03-12, 2026-03-13). Read-only over already-produced replay JSONs.
**Filter under test:** `duplicate_60m_STRICT AND fast_trigger<=X` for X in [30, 60, 90] min.

## HARD DISCLAIMER

  - 3 days is a very small OOS sample. Conclusions here are SUGGESTIVE.
  - The filter is post-hoc and PASSIVE. It does not alter the engine or thresholds.
  - No production integration. No profitability claim.

## A. duplicate_60m STRICT definition

For each triggered zone Z (direction D, triggerTs T):
  Z is SUPPRESSED if there exists ANOTHER triggered zone Z' such that
    (a) Z'.triggerTs < T  (strict past, no future leak)
    (b) 0 < T - Z'.triggerTs <= 60 min
    (c) Z'.direction == D
    (d) (same uniqueMoveId as Z) OR (zone midpoint within +/- 2.0 % of Z's midpoint)

## B. Future-leak audit

- `FILTER_INVALID_FUTURE_LEAK` = **NO**
- allowed fields used: `['triggerTs', 'confirmedTs', 'direction', 'uniqueMoveId', 'zoneLow', 'zoneHigh']`
- forbidden fields referenced: `[]`

Notes:
  - compute_duplicate60m_suppress reads only zone.triggerTs, zone.direction, zone.uniqueMoveId and zone midpoint (from zoneLow/zoneHigh).
  - fast_trigger_keep reads only zone.confirmedTs and zone.triggerTs.
  - All prior-zone comparisons are STRICT past (prior.triggerTs < current.triggerTs).
  - uniqueMoveId is engine move-cluster metadata; the user spec explicitly allows it. In a live setting this metadata would require an online clustering algorithm — this offline post-hoc filter uses the already-resolved label only as a grouping key, not as a future outcome.

## C. Per-day baseline + filtered (3 X sensitivity values)

### X = 30 min

| date | baseline zones/trig/reached/prim/dup/fail | filtered trig_kept/reached_kept/prim_kept/dup_kept/fail_kept | prec base->filt |
|---|---|---|---|
| 2026-03-11 | 30/21/5/1/4/16 | 4/2/1/1/2 | 0.2381 -> 0.5 |
| 2026-03-12 | 32/20/0/0/0/20 | 1/0/0/0/1 | 0.0 -> 0.0 |
| 2026-03-13 | 32/18/7/2/5/11 | 7/4/2/2/3 | 0.3889 -> 0.5714 |

**Aggregate (X=30m):** primary recall **100.0%**, duplicate removal **66.67%**, failed reduction **87.23%**, precision delta **29.66 pp**, actionable signals/day **4.0**, mute-day **YES**

### X = 60 min

| date | baseline zones/trig/reached/prim/dup/fail | filtered trig_kept/reached_kept/prim_kept/dup_kept/fail_kept | prec base->filt |
|---|---|---|---|
| 2026-03-11 | 30/21/5/1/4/16 | 6/3/1/2/3 | 0.2381 -> 0.5 |
| 2026-03-12 | 32/20/0/0/0/20 | 3/0/0/0/3 | 0.0 -> 0.0 |
| 2026-03-13 | 32/18/7/2/5/11 | 7/4/2/2/3 | 0.3889 -> 0.5714 |

**Aggregate (X=60m):** primary recall **100.0%**, duplicate removal **55.56%**, failed reduction **80.85%**, precision delta **23.41 pp**, actionable signals/day **5.333**, mute-day **YES**

### X = 90 min

| date | baseline zones/trig/reached/prim/dup/fail | filtered trig_kept/reached_kept/prim_kept/dup_kept/fail_kept | prec base->filt |
|---|---|---|---|
| 2026-03-11 | 30/21/5/1/4/16 | 7/3/1/2/4 | 0.2381 -> 0.4286 |
| 2026-03-12 | 32/20/0/0/0/20 | 3/0/0/0/3 | 0.0 -> 0.0 |
| 2026-03-13 | 32/18/7/2/5/11 | 7/4/2/2/3 | 0.3889 -> 0.5714 |

**Aggregate (X=90m):** primary recall **100.0%**, duplicate removal **55.56%**, failed reduction **78.72%**, precision delta **20.84 pp**, actionable signals/day **5.667**, mute-day **YES**

## D. Sensitivity comparison (aggregate over the 3 days)

| X (min) | primary recall % | dup removal % | failed reduce % | prec delta pp | actionable/day | mute-day |
|---:|---:|---:|---:|---:|---:|---|
| 30 | 100.0 | 66.67 | 87.23 | 29.66 | 4.0 | YES |
| 60 | 100.0 | 55.56 | 80.85 | 23.41 | 5.333 | YES |
| 90 | 100.0 | 55.56 | 78.72 | 20.84 | 5.667 | YES |

## E. Late-entry hypothesis (across all suppressed zones)

| X (min) | n suppressed with cluster meta | median dt from first trigger (min) | median dt from primary (min) | median price dist from primary % |
|---:|---:|---:|---:|---:|
| 30 | 6 | 512.4 | 512.4 | 0.446 |
| 60 | 5 | 538.433 | 538.433 | 0.763 |
| 90 | 5 | 538.433 | 538.433 | 0.763 |

Hypothesis: filter preferentially removes LATE-entry continuation zones, NOT early primaries.
Pass condition: median delta_t from primary is positive (suppressed zones trigger AFTER primary) and reasonably large.

## F. Mute-day (2026-03-12) audit

- baseline 03-12: zones=32, triggered=20, reached=0, primary=0
- filtered (X=60m): triggered_kept=3, reached_kept=0
- precision becomes undefined (0/0) after filter? **False**
- filter introduced any new positives? **False**

Comment: The filter cannot manufacture reached zones. The risk is degenerate-empty: removing every triggered zone on a mute day so a downstream precision check uses 0/0 = NaN. We flag the day with 'NO_DEGENERATE' if the filter removes ALL triggered zones.

## G. Verdict

- FILTER_LOOKS_STABLE = **YES**
- FILTER_PROBABLY_OVERFIT = **NO**
- best X (passing good criteria): **30**

## H. Final flag matrix

```
MINI_OOS_FILTER_VALIDATION_DONE = YES
FILTER_30M_PRIMARY_RECALL_PCT = 100.0
FILTER_60M_PRIMARY_RECALL_PCT = 100.0
FILTER_90M_PRIMARY_RECALL_PCT = 100.0
FILTER_30M_DUPLICATE_REMOVAL_PCT = 66.67
FILTER_60M_DUPLICATE_REMOVAL_PCT = 55.56
FILTER_90M_DUPLICATE_REMOVAL_PCT = 55.56
FILTER_30M_FAILED_REDUCTION_PCT = 87.23
FILTER_60M_FAILED_REDUCTION_PCT = 80.85
FILTER_90M_FAILED_REDUCTION_PCT = 78.72
FILTER_30M_PRECISION_DELTA_PCT = 29.66
FILTER_60M_PRECISION_DELTA_PCT = 23.41
FILTER_90M_PRECISION_DELTA_PCT = 20.84
FILTER_30M_ACTIONABLE_PER_DAY = 4.0
FILTER_60M_ACTIONABLE_PER_DAY = 5.333
FILTER_90M_ACTIONABLE_PER_DAY = 5.667
MINI_OOS_MUTE_DAY_STABLE = YES
MINI_OOS_MUTE_DAY_STATUS_PER_X = {30: 'YES', 60: 'YES', 90: 'YES'}
FILTER_LOOKS_STABLE = YES
FILTER_PROBABLY_OVERFIT = NO
FILTER_INVALID_FUTURE_LEAK = NO
READY_FOR_PASSIVE_LIVE_OBSERVER = YES
best_x_min_under_good_criteria = 30
```

## I. Hard rules honored

- strategy / thresholds / `zoneDetector`: UNCHANGED
- no new backtest spawned; no conversion re-run
- post-trigger outcomes used only as labels (precision/recall denominators),
  NEVER in the suppress decision
- `zone_score_v1`/`v2`: not used as filter
- no profitability claim
- raw archives and Tardis-compat files untouched