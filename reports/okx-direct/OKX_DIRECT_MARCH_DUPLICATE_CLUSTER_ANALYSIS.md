# OKX direct partial-March 2026 - duplicate / move cluster analysis

**Scope:** 14 UTC days 2026-03-02..2026-03-15. 15 unique moves -> 15 clusters.

## A. Per-cluster summary

| date | dir | mid | nZones | nTrig | nDup | trig_to_target_min | dups_after_first | dups_after_half | dt_min mean/max | dprice% mean/max |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2026-03-02 | LONG | 1 | 7 | 7 | 6 | 864.5327333333333 | 6 | 2 | 353.7639 / 829.3333 | 0.5641 / 0.9777 |
| 2026-03-03 | LONG | 1 | 3 | 3 | 2 | 269.63801666666666 | 2 | 1 | 89.65 / 171.75 | 0.1605 / 0.2856 |
| 2026-03-03 | SHORT | 2 | 9 | 9 | 8 | 502.84108333333336 | 8 | 6 | 293.7125 / 489.3333 | 0.7157 / 1.3581 |
| 2026-03-04 | LONG | 1 | 15 | 15 | 14 | 429.20976666666667 | 14 | 12 | 399.5095 / 778.7667 | 2.1952 / 5.2825 |
| 2026-03-05 | SHORT | 1 | 5 | 5 | 4 | 862.8603 | 4 | 0 | 193.4083 / 255.2667 | 0.3284 / 0.6074 |
| 2026-03-06 | SHORT | 1 | 8 | 8 | 7 | 785.0711 | 7 | 1 | 227.1024 / 704.9833 | 0.4514 / 1.2331 |
| 2026-03-08 | SHORT | 1 | 8 | 8 | 7 | 1275.9471166666667 | 7 | 1 | 379.0595 / 681.55 | 0.4558 / 1.1167 |
| 2026-03-09 | LONG | 1 | 9 | 9 | 8 | 247.8109 | 8 | 7 | 288.6208 / 619.55 | 1.3259 / 2.0744 |
| 2026-03-10 | LONG | 1 | 12 | 12 | 11 | 135.58716666666666 | 11 | 11 | 223.4318 / 413.3833 | 1.5121 / 2.3076 |
| 2026-03-10 | SHORT | 2 | 1 | 1 | 0 | 324.05361666666664 | 0 | 0 | None / None | None / None |
| 2026-03-10 | SHORT | 3 | 1 | 1 | 0 | 250.20715 | 0 | 0 | None / None | None / None |
| 2026-03-11 | LONG | 1 | 5 | 5 | 4 | 564.5576166666667 | 4 | 4 | 494.4375 / 538.4333 | 0.236 / 0.5966 |
| 2026-03-13 | LONG | 1 | 6 | 6 | 5 | 767.915 | 4 | 4 | 425.7867 / 584.2833 | 0.8842 / 1.5061 |
| 2026-03-13 | SHORT | 2 | 1 | 1 | 0 | 163.3387 | 0 | 0 | None / None | None / None |
| 2026-03-15 | LONG | 1 | 8 | 8 | 7 | 1339.7325 | 7 | 0 | 196.5095 / 511.7 | 0.3886 / 0.8555 |

## B. Delta-from-first-trigger distribution (duplicate triggered zones, n=83)

- delta_t_min:  {'n': 83, 'mean': 307.3548, 'median': 255.2667, 'p25': 121.5167, 'p75': 482.4, 'min': 0.0, 'max': 829.3333}
- delta_price_pct: {'n': 83, 'mean': 1.0019, 'median': 0.7063, 'p25': 0.219, 'p75': 1.2372, 'min': 0.0303, 'max': 5.2825}

## C. Dedup-rule hypothesis

If a same-direction zone has already triggered within the last X minutes (or within Y% price band),
a subsequent same-direction zone is statistically a duplicate. Candidate cuts to test:
  - X = 30 min, 60 min
  - Y = 0.5 %, 1.0 %

Phase F passive-filter `duplicate_30m` / `duplicate_60m` evaluates the 30-/60-min cuts.