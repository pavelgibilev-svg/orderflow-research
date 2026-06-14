# Detection root-cause matrix (one row per market 2 % move)

**Build:** 2026-05-24T15:16:56+00:00
**Main root cause:** `mixed`

## Counts by root cause

- trigger_too_slow: **2**
- filter_suppressed_correct_zone: **1**
- normal_market_noise: **1**

## Per-move

| date | dir | size % | start | classification | root cause | best zone |
|---|---|---:|---|---|---|---|
| 2026-03-16 | UP | 3.0964 | 2026-03-16T03:34:00+00:00 | filtered_correct_zone | **filter_suppressed_correct_zone** | `LONG-1773620182000-2` |
| 2026-03-16 | DOWN | 2.1772 | 2026-03-16T04:55:01+00:00 | covered_mid | **trigger_too_slow** | `ORT-1773638712000-12` |
| 2026-03-16 | UP | 2.2946 | 2026-03-16T08:44:57+00:00 | covered_mid | **trigger_too_slow** | `ONG-1773655882000-26` |
| 2026-03-16 | DOWN | 2.0801 | 2026-03-16T13:41:49+00:00 | covered_early | **normal_market_noise** | `ORT-1773660536000-29` |