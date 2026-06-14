# Full-Day Verification (post-deduplication) — BTCUSDT 2026-02-01

> **This is a full-day technical verification run with deduplication enabled.** Strategy thresholds in `config/strategy.default.json` were not modified — only the same-direction overlap suppression + cooldown rule was added in `zoneDetector.ts`.

- Generated: 2026-05-09T14:07:48.417Z

## 1. Run conditions

| Setting | Value |
|---|---|
| Date | 2026-02-01 |
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
| L2 events processed | 165 962 192 |
| Trades scanned | 6 759 515 |
| Zones found | 25 |
| LONG / SHORT | 16 / 9 |
| Triggered | 11 |
| Reached 4h | 0 |
| Reached 8h | 0 |
| Reached 24h | 4 |
| Failed (RESOLVED_FAILED) | 7 |
| No trigger | 1 |
| Invalidated | 13 |
| Expired | 0 |
| Triggered hit rate 4h | 0.00% (0/11) |
| Triggered hit rate 8h | 0.00% (0/11) |
| Triggered hit rate 24h | 36.36% (4/11) |
| Reached zones (raw) | 4 |
| Unique reached moves | 1 |
| Duplicate move credits | 3 |
| Raw triggered hit rate | 36.36% |
| **Unique-move-adjusted hit rate** | **9.09%** |
| Baseline 4h (up/down) | 0.08% / 20.00% (n=1200) |
| Baseline 8h (up/down) | 0.10% / 46.25% (n=960) |
| Baseline 24h (up/down) | 0.00% / 0.00% (n=0) |
| Duplicate suppressions during this run | 6907 |
| Suppressions `active_open` | 4321 |
| Suppressions `active_triggered` | 2582 |
| Suppressions `cooldown` | 4 |

## 3. All zones (post-dedup)

Total zones: **25** (every zone is included regardless of outcome).

| # | Dir | Type | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Reason chain |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 00:00:37 | 00:18:54 | 01:07:10 | 78606.75 | 79375.45 | 78566.05 | 76994.73 | failed_by_timeout | failed_by_timeout | reached | 3.72 | 0.80 | 859.0 | candidate@00:00:37 → confirmed@00:18:54 → trigger@01:07:10 → expire@15:26:10 |
| 2 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 00:01:41 | 00:18:54 | 01:11:00 | 78581.84 | 79375.45 | 78538.75 | 76967.98 | failed_by_timeout | failed_by_timeout | reached | 3.69 | 0.83 | 855.2 | candidate@00:01:41 → confirmed@00:18:54 → trigger@01:11:00 → expire@15:26:10 |
| 3 | LONG | ACCUMULATION | INVALIDATED | 01:12:33 | 01:15:55 | - | 78512.55 | 78683.45 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@01:12:33 → confirmed@01:15:55 → invalidate@07:04:52 |
| 4 | LONG | ACCUMULATION | INVALIDATED | 01:13:03 | 01:16:03 | - | 78512.55 | 78683.45 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@01:13:03 → confirmed@01:16:03 → invalidate@07:04:52 |
| 5 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 01:57:14 | 02:26:02 | 06:48:08 | 78343.25 | 78871.75 | 78273.45 | 76707.98 | failed_by_timeout | failed_by_timeout | reached | 3.36 | 1.18 | 820.4 | candidate@01:57:14 → confirmed@02:26:02 → trigger@06:48:08 → expire@20:28:31 |
| 6 | LONG | ACCUMULATION | INVALIDATED | 02:17:24 | 03:00:32 | - | 78474.45 | 79020.45 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@02:17:24 → confirmed@03:00:32 → invalidate@07:06:18 |
| 7 | LONG | ACCUMULATION | RESOLVED_FAILED | 03:00:32 | 03:14:14 | 04:17:40 | 78703.45 | 78969.52 | 79054.45 | 80635.54 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.18 | 4.31 | - | candidate@03:00:32 → confirmed@03:14:14 → trigger@04:17:40 → expire@04:17:40 |
| 8 | LONG | ACCUMULATION | INVALIDATED | 06:53:07 | 06:56:07 | - | 78268.50 | 78346.80 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@06:53:07 → confirmed@06:56:07 → invalidate@14:28:09 |
| 9 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 06:58:01 | 07:01:01 | 07:04:55 | 78247.51 | 78325.79 | 78109.65 | 76547.46 | failed_by_timeout | failed_by_timeout | reached | 3.16 | 1.39 | 803.8 | candidate@06:58:01 → confirmed@07:01:01 → trigger@07:04:55 → expire@20:28:41 |
| 10 | LONG | ACCUMULATION | INVALIDATED | 07:09:41 | 07:12:41 | - | 78158.25 | 78327.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@07:09:41 → confirmed@07:12:41 → invalidate@14:31:19 |
| 11 | LONG | ACCUMULATION | INVALIDATED | 07:12:53 | 07:20:36 | - | 77968.65 | 78239.05 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@07:12:53 → confirmed@07:20:36 → invalidate@14:34:28 |
| 12 | LONG | ACCUMULATION | RESOLVED_FAILED | 08:01:05 | 08:21:22 | 08:38:17 | 78229.15 | 78500.35 | 78767.45 | 80342.80 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.54 | 3.97 | - | candidate@08:01:05 → confirmed@08:21:22 → trigger@08:38:17 → expire@08:38:17 |
| 13 | LONG | ACCUMULATION | INVALIDATED | 10:22:38 | 10:45:44 | - | 78285.05 | 79043.35 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@10:22:38 → confirmed@10:45:44 → invalidate@14:28:03 |
| 14 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 14:10:21 | 14:57:57 | 15:18:54 | 77211.55 | 78489.75 | 77171.60 | 75628.17 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.98 | 1.62 | - | candidate@14:10:21 → confirmed@14:57:57 → trigger@15:18:54 → expire@15:18:54 |
| 15 | LONG | ACCUMULATION | INVALIDATED | 15:42:21 | 15:45:21 | - | 77113.45 | 77299.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@15:42:21 → confirmed@15:45:21 → invalidate@20:28:32 |
| 16 | LONG | ACCUMULATION | INVALIDATED | 15:42:39 | 16:00:05 | - | 77113.45 | 77835.60 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@15:42:39 → confirmed@16:00:05 → invalidate@20:28:32 |
| 17 | SHORT | DISTRIBUTION | INVALIDATED | 16:18:54 | 17:03:12 | - | 77100.65 | 77810.85 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@16:18:54 → confirmed@17:03:12 → invalidate@18:08:40 |
| 18 | LONG | ACCUMULATION | INVALIDATED | 18:19:57 | 18:29:23 | - | 77964.85 | 78404.50 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@18:19:57 → confirmed@18:29:23 → invalidate@19:16:04 |
| 19 | LONG | ACCUMULATION | INVALIDATED | 18:29:23 | 18:32:29 | - | 78050.45 | 78135.30 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@18:29:23 → confirmed@18:32:29 → invalidate@19:15:37 |
| 20 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 19:54:55 | 20:02:19 | 20:04:02 | 76953.35 | 77230.65 | 76906.35 | 75368.22 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.64 | 1.10 | - | candidate@19:54:55 → confirmed@20:02:19 → trigger@20:04:02 → expire@20:04:02 |
| 21 | LONG | ACCUMULATION | RESOLVED_FAILED | 20:08:02 | 20:14:57 | 20:39:21 | 76869.80 | 77269.75 | 77571.55 | 79122.98 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.23 | 2.48 | - | candidate@20:08:02 → confirmed@20:14:57 → trigger@20:39:21 → expire@20:39:21 |
| 22 | SHORT | DISTRIBUTION | INVALIDATED | 21:15:11 | 21:43:33 | - | 76507.15 | 77134.85 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@21:15:11 → confirmed@21:43:33 → invalidate@22:12:21 |
| 23 | LONG | ACCUMULATION | RESOLVED_FAILED | 21:21:56 | 21:51:05 | 22:11:01 | 76410.20 | 77134.85 | 77276.75 | 78822.29 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.62 | 2.11 | - | candidate@21:21:56 → confirmed@21:51:05 → trigger@22:11:01 → expire@22:11:01 |
| 24 | LONG | ACCUMULATION | RESOLVED_FAILED | 22:41:01 | 23:12:12 | 23:36:10 | 75668.95 | 77516.25 | 77560.50 | 79111.71 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.03 | 0.92 | - | candidate@22:41:01 → confirmed@23:12:12 → trigger@23:36:10 → expire@23:36:10 |
| 25 | SHORT | DISTRIBUTION | NO_TRIGGER | 23:59:26 | - | - | 76864.50 | 76941.45 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@23:59:26 → expire@23:59:59 |

## 4. Successful zones

- `BTCUSDT-SHORT-1769904037000-1` SHORT DISTRIBUTION: trigger=2026-02-01T01:07:10.000Z px=78566.05 target=76994.73 reached=**24h** ttt=859.0min MFE=3.72% MAE=0.80%
- `BTCUSDT-SHORT-1769904101000-2` SHORT DISTRIBUTION: trigger=2026-02-01T01:11:00.000Z px=78538.75 target=76967.98 reached=**24h** ttt=855.2min MFE=3.69% MAE=0.83%
- `BTCUSDT-SHORT-1769911034000-5` SHORT DISTRIBUTION: trigger=2026-02-01T06:48:08.000Z px=78273.45 target=76707.98 reached=**24h** ttt=820.4min MFE=3.36% MAE=1.18%
- `BTCUSDT-SHORT-1769929081000-9` SHORT DISTRIBUTION: trigger=2026-02-01T07:04:55.000Z px=78109.65 target=76547.46 reached=**24h** ttt=803.8min MFE=3.16% MAE=1.39%
