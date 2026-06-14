# Good-watch-zone pattern search

**Build:** 2026-05-25T09:39:55+00:00

| pattern | n alerts | per day | covered | wrong | missed | precision % | recall % |
|---|---:|---:|---:|---:|---:|---:|---:|
| `baseline_all_confirmed` | 537 | 35.8 | 60 | 41 | 436 | 11.17 | 100.0 |
| `confidence_HIGH` | 533 | 35.533 | 60 | 40 | 433 | 11.26 | 100.0 |
| `absorb+refill` | 537 | 35.8 | 60 | 41 | 436 | 11.17 | 100.0 |
| `OFI_aligned` | 314 | 20.933 | 38 | 21 | 255 | 12.1 | 63.33 |
| `trigger_flow_strong` | 175 | 11.667 | 20 | 25 | 130 | 11.43 | 33.33 |
| `zone_defended_long` | 228 | 15.2 | 21 | 24 | 183 | 9.21 | 35.0 |
| `cycles_seen_ge_5` | 507 | 33.8 | 59 | 38 | 410 | 11.64 | 98.33 |
| `filter_kept_only` | 121 | 8.067 | 16 | 14 | 91 | 13.22 | 26.67 |
| `absorb+OFI` | 314 | 20.933 | 38 | 21 | 255 | 12.1 | 63.33 |
| `HIGH_AND_filter_kept` | 121 | 8.067 | 16 | 14 | 91 | 13.22 | 26.67 |
| `HIGH_AND_absorb+OFI` | 314 | 20.933 | 38 | 21 | 255 | 12.1 | 63.33 |
| `rank_score_ge_4` | 536 | 35.733 | 60 | 40 | 436 | 11.19 | 100.0 |
| `rank_score_ge_5` | 533 | 35.533 | 60 | 40 | 433 | 11.26 | 100.0 |
| `rank_score_ge_4_AND_filter_kept` | 121 | 8.067 | 16 | 14 | 91 | 13.22 | 26.67 |

**Best pattern (alerts/day <= 3.5, max F1):** `none`