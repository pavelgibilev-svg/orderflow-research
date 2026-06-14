# Wrong-direction cases (4h forward window had no 2% in engine direction)

**Build:** 2026-05-25T09:36:59+00:00
**Total wrong-direction triggers:** 8

| date | zone | dir | trigger | 4h up % | 4h down % | engine class | opp candidate? | classification |
|---|---|---|---|---:|---:|---|:---:|---|
| 2026-03-16 | `HORT-1773620946000-4` | SHORT | 2026-03-16T01:05:02+00:00 | 2.8779 | 0.2119 | failed_triggered | Y | wrong_direction_noise |
| 2026-03-16 | `HORT-1773626785000-7` | SHORT | 2026-03-16T02:27:51+00:00 | 2.9008 | 0.0324 | failed_triggered | N | wrong_direction_noise |
| 2026-03-19 | `LONG-1773878683000-1` | LONG | 2026-03-19T03:17:57+00:00 | 0.3265 | 2.2494 | failed_triggered | Y | wrong_direction_noise |
| 2026-03-19 | `ORT-1773929685000-31` | SHORT | 2026-03-19T15:41:24+00:00 | 2.119 | 0.4995 | failed_triggered | Y | wrong_direction_noise |
| 2026-03-23 | `ORT-1774265760000-20` | SHORT | 2026-03-23T11:47:51+00:00 | 2.2777 | 0.7443 | failed_triggered | Y | wrong_direction_noise |
| 2026-03-24 | `ORT-1774372444000-31` | SHORT | 2026-03-24T17:44:26+00:00 | 2.1098 | 0.043 | failed_triggered | N | wrong_direction_noise |
| 2026-03-27 | `ONG-1774594419000-13` | LONG | 2026-03-27T07:11:59+00:00 | 0.2406 | 3.7724 | failed_triggered | Y | filter_removed_correct_side |
| 2026-03-31 | `ORT-1774951968000-23` | SHORT | 2026-03-31T10:42:25+00:00 | 2.3574 | 0.0428 | failed_triggered | Y | wrong_direction_noise |