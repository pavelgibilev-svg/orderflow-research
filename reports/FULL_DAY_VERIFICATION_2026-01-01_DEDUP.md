# Full-Day Verification (post-deduplication) — BTCUSDT 2026-01-01

> **This is a full-day technical verification run with deduplication enabled.** Strategy thresholds in `config/strategy.default.json` were not modified — only the same-direction overlap suppression + cooldown rule was added in `zoneDetector.ts`.

- Generated: 2026-05-09T14:07:48.442Z

## 1. Run conditions

| Setting | Value |
|---|---|
| Date | 2026-01-01 |
| Symbol | BTCUSDT |
| Exchange | binance-futures |
| Target percent | 2.0 |
| Horizons | 4h, 8h, 24h |
| L2 time limitation | NO — full 24h L2 replay |
| Skip-snapshots used | yes |
| Config file | config/strategy.default.json (unchanged thresholds) |
| Threshold tuning | NONE |
| Deduplication enabled | **YES** |
| Cooldown after resolve | 30 min |
| Price overlap min pct | 0.25 (= 25% of smaller zone height) |

## 2. Strategy summary (post-dedup)

| Metric | Value |
|---|---|
| L2 events processed | 62 609 291 |
| Trades scanned | 1 056 983 |
| Zones found | 23 |
| LONG / SHORT | 12 / 11 |
| Triggered | 14 |
| Reached 4h | 0 |
| Reached 8h | 0 |
| Reached 24h | 0 |
| Failed (RESOLVED_FAILED) | 14 |
| No trigger | 6 |
| Invalidated | 3 |
| Expired | 0 |
| Triggered hit rate 4h | 0.00% (0/14) |
| Triggered hit rate 8h | 0.00% (0/14) |
| Triggered hit rate 24h | 0.00% (0/14) |
| Reached zones (raw) | 0 |
| Unique reached moves | 0 |
| Duplicate move credits | 0 |
| Raw triggered hit rate | 0.00% |
| **Unique-move-adjusted hit rate** | **0.00%** |
| Baseline 4h (up/down) | 0.00% / 0.00% (n=1200) |
| Baseline 8h (up/down) | 0.00% / 0.00% (n=960) |
| Baseline 24h (up/down) | 0.00% / 0.00% (n=0) |
| Duplicate suppressions during this run | 12822 |
| Suppressions `active_open` | 8881 |
| Suppressions `active_triggered` | 3941 |

## 3. All zones (post-dedup)

Total zones: **23** (every zone is included regardless of outcome).

| # | Dir | Type | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Reason chain |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | LONG | ACCUMULATION | RESOLVED_FAILED | 00:00:31 | 00:03:31 | 00:05:15 | 87560.05 | 87659.75 | 87719.45 | 89473.84 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.32 | 0.24 | - | candidate@00:00:31 → confirmed@00:03:31 → trigger@00:05:15 → expire@00:05:15 |
| 2 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 00:10:28 | 00:13:28 | 04:12:52 | 87690.58 | 87778.32 | 87645.85 | 85892.93 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.16 | 1.41 | - | candidate@00:10:28 → confirmed@00:13:28 → trigger@04:12:52 → expire@04:12:52 |
| 3 | LONG | ACCUMULATION | RESOLVED_FAILED | 00:31:13 | 00:54:33 | 01:07:04 | 87691.18 | 87799.95 | 87843.95 | 89600.83 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.18 | 0.38 | - | candidate@00:31:13 → confirmed@00:54:33 → trigger@01:07:04 → expire@01:07:04 |
| 4 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 01:02:44 | 01:16:42 | 04:08:00 | 87776.04 | 88016.95 | 87722.65 | 85968.20 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.24 | 1.32 | - | candidate@01:02:44 → confirmed@01:16:42 → trigger@04:08:00 → expire@04:08:00 |
| 5 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 01:16:42 | 01:19:42 | 04:17:16 | 87907.75 | 88001.93 | 87530.55 | 85779.94 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.03 | 1.54 | - | candidate@01:16:42 → confirmed@01:19:42 → trigger@04:17:16 → expire@04:17:16 |
| 6 | LONG | ACCUMULATION | RESOLVED_FAILED | 01:22:05 | 01:25:05 | 17:21:03 | 87882.39 | 87970.31 | 88187.45 | 89951.20 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.79 | 0.17 | - | candidate@01:22:05 → confirmed@01:25:05 → trigger@17:21:03 → expire@17:21:03 |
| 7 | LONG | ACCUMULATION | RESOLVED_FAILED | 01:33:23 | 01:42:04 | 01:54:29 | 87797.95 | 87902.98 | 87948.25 | 89707.21 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.06 | 0.50 | - | candidate@01:33:23 → confirmed@01:42:04 → trigger@01:54:29 → expire@01:54:29 |
| 8 | LONG | ACCUMULATION | RESOLVED_FAILED | 02:16:05 | 02:30:07 | 17:20:47 | 87904.45 | 88064.95 | 88113.35 | 89875.62 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.87 | 0.09 | - | candidate@02:16:05 → confirmed@02:30:07 → trigger@17:20:47 → expire@17:20:47 |
| 9 | SHORT | DISTRIBUTION | INVALIDATED | 04:23:33 | 04:29:11 | - | 87529.56 | 87667.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@04:23:33 → confirmed@04:29:11 → invalidate@17:20:47 |
| 10 | LONG | ACCUMULATION | RESOLVED_FAILED | 17:27:00 | 17:30:00 | 17:30:18 | 88133.06 | 88221.24 | 88285.65 | 90051.36 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.67 | 0.28 | - | candidate@17:27:00 → confirmed@17:30:00 → trigger@17:30:18 → expire@17:30:18 |
| 11 | LONG | ACCUMULATION | NO_TRIGGER | 17:38:55 | 17:49:05 | - | 88037.15 | 88881.35 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@17:38:55 → confirmed@17:49:05 → expire@23:59:59 |
| 12 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 17:43:38 | 17:55:45 | 18:05:22 | 88282.45 | 88420.85 | 88229.75 | 86465.15 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.22 | 0.74 | - | candidate@17:43:38 → confirmed@17:55:45 → trigger@18:05:22 → expire@18:05:22 |
| 13 | LONG | ACCUMULATION | RESOLVED_FAILED | 17:49:05 | 18:00:37 | 22:08:35 | 88250.35 | 88420.85 | 88541.15 | 90311.97 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.38 | 0.19 | - | candidate@17:49:05 → confirmed@18:00:37 → trigger@22:08:35 → expire@22:08:35 |
| 14 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 17:55:45 | 18:03:36 | 18:05:28 | 88243.85 | 88340.40 | 88187.35 | 86423.60 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.17 | 0.79 | - | candidate@17:55:45 → confirmed@18:03:36 → trigger@18:05:28 → expire@18:05:28 |
| 15 | SHORT | DISTRIBUTION | INVALIDATED | 18:12:06 | 18:40:21 | - | 88066.65 | 88228.84 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@18:12:06 → confirmed@18:40:21 → invalidate@23:00:19 |
| 16 | SHORT | DISTRIBUTION | INVALIDATED | 18:40:21 | 19:32:47 | - | 88037.15 | 88186.65 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@18:40:21 → confirmed@19:32:47 → invalidate@22:54:31 |
| 17 | LONG | ACCUMULATION | RESOLVED_FAILED | 19:15:33 | 19:28:08 | 19:41:13 | 88057.10 | 88145.20 | 88283.35 | 90049.02 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.68 | 0.10 | - | candidate@19:15:33 → confirmed@19:28:08 → trigger@19:41:13 → expire@19:41:13 |
| 18 | SHORT | DISTRIBUTION | NO_TRIGGER | 22:30:34 | 22:59:27 | - | 88382.35 | 88881.35 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@22:30:34 → confirmed@22:59:27 → expire@23:59:59 |
| 19 | SHORT | DISTRIBUTION | NO_TRIGGER | 22:59:27 | 23:48:18 | - | 88433.25 | 88881.35 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@22:59:27 → confirmed@23:48:18 → expire@23:59:59 |
| 20 | LONG | ACCUMULATION | NO_TRIGGER | 23:07:38 | 23:11:20 | - | 88505.68 | 88881.35 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@23:07:38 → confirmed@23:11:20 → expire@23:59:59 |
| 21 | LONG | ACCUMULATION | RESOLVED_FAILED | 23:30:13 | 23:37:55 | 23:44:36 | 88681.89 | 88785.95 | 88832.45 | 90609.10 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.06 | 0.14 | - | candidate@23:30:13 → confirmed@23:37:55 → trigger@23:44:36 → expire@23:44:36 |
| 22 | SHORT | DISTRIBUTION | NO_TRIGGER | 23:48:18 | - | - | 88710.85 | 88832.55 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@23:48:18 → expire@23:59:59 |
| 23 | LONG | ACCUMULATION | NO_TRIGGER | 23:53:03 | 23:56:03 | - | 88769.64 | 88858.46 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@23:53:03 → confirmed@23:56:03 → expire@23:59:59 |

## 4. Successful zones

No zones reached the 2 % target.
