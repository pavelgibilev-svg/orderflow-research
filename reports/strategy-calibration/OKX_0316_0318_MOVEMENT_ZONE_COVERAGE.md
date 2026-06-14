# Movement → zone coverage classification

**Build:** 2026-05-24T15:16:51+00:00

## Classification counts (primary 2 % moves only)

- filtered_correct_zone: **1**
- covered_mid: **2**
- covered_early: **1**

## Per-move detail

| date | dir | size % | move start | best zone class | zone direction | trigger lead min | % move completed at trigger | filter kept | classification |
|---|---|---:|---|---|---|---:|---:|:---:|---|
| 2026-03-16 | UP (N) | 3.0964 | 2026-03-16T03:34:00+00:00 | primary_unique_reached_move | LONG | 3.3 | 0.0 | N | **filtered_correct_zone** |
| 2026-03-16 | DOWN (N) | 2.1772 | 2026-03-16T04:55:01+00:00 | failed_triggered | SHORT | -72.32 | 31.45 | Y | **covered_mid** |
| 2026-03-16 | UP (N) | 2.2946 | 2026-03-16T08:44:57+00:00 | failed_triggered | LONG | -125.35 | 42.22 | Y | **covered_mid** |
| 2026-03-16 | DOWN (N) | 2.0801 | 2026-03-16T13:41:49+00:00 | failed_triggered | SHORT | 90.52 | 0.0 | Y | **covered_early** |
| 2026-03-18 | UP (Y) | 1.5768 | 2026-03-18T03:26:53+00:00 | failed_triggered | LONG | 1.42 | 0.0 | N | **candidate_early_but_trigger_late** |
| 2026-03-18 | UP (Y) | 1.628 | 2026-03-18T15:02:29+00:00 | failed_triggered | LONG | -54.97 | 29.75 | Y | **covered_mid** |