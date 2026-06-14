# Full-Day Verification (post-dedup + move-clustering) — BTCUSDT 2026-03-01

> **Full-day technical verification** with deduplication and unique-move clustering enabled. Strategy thresholds in `config/strategy.default.json` are unchanged. Detector logic untouched.

- Generated: 2026-05-10T10:45:06.335Z
- Source zones: `reports/full_day_2026-03-01_dedup_clustered/zones.json`

## 1. Run conditions

| Setting | Value |
|---|---|
| Date | 2026-03-01 |
| Symbol | BTCUSDT |
| Exchange | binance-futures |
| Target percent | 2.0 |
| Horizons | 4h, 8h, 24h |
| L2 time limitation | NO (full 24h L2 replay) |
| Skip-snapshots | yes |
| Threshold tuning | NONE |
| Deduplication enabled | yes (cooldown 30min, priceOverlapMinPct 0.25) |
| Move clustering enabled | yes (gap 120min, sameDirectionOnly true) |

## 2. Target-feasibility context for 2026-03-01

| Metric | Value |
|---|---|
| Day return | -1.77% |
| Day range | 4.89% |
| Max 4h up | 3.17% |
| Max 4h down | 2.92% |
| Max 8h up | 3.17% |
| Max 8h down | 3.28% |
| Max 24h up | 3.17% |
| Max 24h down | 4.54% |
| 2% feasible 4h | yes |
| 2% feasible 8h | yes |
| 2% feasible intraday | yes |
| Regime | bearish |
| Recommended target | 2.0% |

On this day **2% is reachable in BOTH directions** (max up = 3.17% within 4h, max down = 2.92% within 4h, both ≥ 2%). Unlike 2026-01-01, this is a structurally valid day for evaluating a 2% strategy. Unlike 2026-02-01 which was unidirectionally bearish, here both directions clear the bar.

## 3. Strategy summary (full-day, post-dedup + clustered)

| Metric | Value |
|---|---|
| L2 events processed | 139 795 935 |
| Trades scanned | 5 961 363 |
| Zones found | 46 |
| LONG / SHORT zones | 25 / 21 |
| Confirmed zones | 46 |
| Triggered zones | 24 |
| Reached zones (raw) | 8 |
| Reached LONG / SHORT (raw) | 0 / 8 |
| **Unique reached moves** | **1** |
| Duplicate move credits | 7 |
| Reached 2% within 4h | 0 |
| Reached 2% within 8h | 0 |
| Reached 2% within 24h | 8 |
| Failed (RESOLVED_FAILED) | 16 |
| No trigger | 1 |
| Invalidated | 21 |
| Expired | 0 |
| Raw triggered hit rate | 33.33% |
| **Unique-move-adjusted hit rate** | **4.17%** |
| Duplicate suppressions during run | 10 825 |
| Suppressions `active_open` | 7 262 |
| Suppressions `active_triggered` | 3 464 |
| Suppressions `cooldown` | 99 |
| Baseline 4h (up/down) | 7.50% / 10.83% (n=1200) |
| Baseline 8h (up/down) | 9.38% / 27.08% (n=960) |
| Baseline 24h (up/down) | 0.00% / 0.00% (n=0) |

## 4. Direction of successful moves

Unique reached moves split:
- LONG: **0** unique moves, 0 reached zones
- SHORT: **1** unique move, 8 reached zones

Only SHORT moves succeeded on this day (despite both directions being feasible by max-move analysis). Consistent with a bearish-bias detector or with the day's price path favouring SHORT entries.

## 5. Unique moves

| Move id | Dir | Size | Trigger window | Reached window | Trigger px range | Target px range | Primary zone | Member zones |
|---|---|---|---|---|---|---|---|---|
| 1 | SHORT | 8 | 01:08:04–10:40:15 | 16:49:16–20:32:38 | 66432.35–67406.65 | 65103.70–66058.52 | `BTCUSDT-SHORT-1772323262000-1` | BTCUSDT-SHORT-1772323262000-1, BTCUSDT-SHORT-1772334048000-12, BTCUSDT-SHORT-1772336293000-14, BTCUSDT-SHORT-1772339107000-16, BTCUSDT-SHORT-1772340270000-18, BTCUSDT-SHORT-1772350918000-24, BTCUSDT-SHORT-1772356375000-28, BTCUSDT-SHORT-1772360989000-32 |

## 6. All zones

Total zones: **46** (every zone is included regardless of outcome).

| # | Dir | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Move id | Primary? | Reason chain |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SHORT | RESOLVED_REACHED | 00:01:02 | 00:58:31 | 01:08:04 | 66593.75 | 67066.55 | 66550.15 | 65219.15 | failed_by_timeout | failed_by_timeout | reached | 2.31 | 2.46 | 1162.5 | 1 | yes | candidate@00:01:02 → confirmed@00:58:31 → trigger@01:08:04 → expire@20:30:35 |
| 2 | LONG | INVALIDATED | 00:02:07 | 00:05:21 | - | 66909.38 | 67066.55 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@00:02:07 → confirmed@00:05:21 → invalidate@01:04:56 |
| 3 | LONG | INVALIDATED | 00:05:21 | 00:11:55 | - | 66775.95 | 67028.85 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@00:05:21 → confirmed@00:11:55 → invalidate@01:09:46 |
| 4 | LONG | INVALIDATED | 00:11:55 | 00:14:55 | - | 66806.05 | 66899.48 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@00:11:55 → confirmed@00:14:55 → invalidate@01:09:36 |
| 5 | LONG | INVALIDATED | 00:37:18 | 00:40:41 | - | 66710.15 | 66792.63 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@00:37:18 → confirmed@00:40:41 → invalidate@01:11:03 |
| 6 | LONG | INVALIDATED | 00:47:06 | 00:50:06 | - | 66618.05 | 66718.99 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@00:47:06 → confirmed@00:50:06 → invalidate@01:11:03 |
| 7 | LONG | INVALIDATED | 00:49:00 | 00:52:00 | - | 66598.53 | 66734.75 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@00:49:00 → confirmed@00:52:00 → invalidate@01:11:04 |
| 8 | SHORT | INVALIDATED | 00:58:31 | 01:16:21 | - | 66158.25 | 66818.94 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@00:58:31 → confirmed@01:16:21 → invalidate@01:49:55 |
| 9 | SHORT | INVALIDATED | 01:17:21 | 01:20:37 | - | 66039.75 | 66234.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@01:17:21 → confirmed@01:20:37 → invalidate@01:36:51 |
| 10 | SHORT | RESOLVED_FAILED | 02:08:26 | 02:16:06 | 16:49:24 | 67655.45 | 68059.35 | 65919.75 | 64601.35 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.38 | 1.47 | - | - | - | candidate@02:08:26 → confirmed@02:16:06 → trigger@16:49:24 → expire@16:49:24 |
| 11 | LONG | INVALIDATED | 02:34:32 | 03:08:32 | - | 67578.25 | 68138.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@02:34:32 → confirmed@03:08:32 → invalidate@04:16:12 |
| 12 | SHORT | RESOLVED_REACHED | 03:00:48 | 03:06:32 | 03:23:59 | 67571.25 | 67666.45 | 67384.55 | 66036.86 | failed_by_timeout | failed_by_timeout | reached | 3.52 | 0.43 | 805.3 | 1 | no | candidate@03:00:48 → confirmed@03:06:32 → trigger@03:23:59 → expire@16:49:17 |
| 13 | LONG | INVALIDATED | 03:27:09 | 03:49:03 | - | 67403.85 | 67671.10 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@03:27:09 → confirmed@03:49:03 → invalidate@04:17:27 |
| 14 | SHORT | RESOLVED_REACHED | 03:38:13 | 03:50:46 | 03:57:21 | 67441.91 | 67671.10 | 67406.65 | 66058.52 | failed_by_timeout | failed_by_timeout | reached | 3.55 | 0.26 | 771.9 | 1 | no | candidate@03:38:13 → confirmed@03:50:46 → trigger@03:57:21 → expire@16:49:16 |
| 15 | LONG | INVALIDATED | 04:13:14 | 04:35:01 | - | 67051.05 | 67399.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@04:13:14 → confirmed@04:35:01 → invalidate@08:51:42 |
| 16 | SHORT | RESOLVED_REACHED | 04:25:07 | 04:31:34 | 06:06:07 | 67143.95 | 67308.15 | 67090.35 | 65748.54 | failed_by_timeout | failed_by_timeout | reached | 3.10 | 0.36 | 671.7 | 1 | no | candidate@04:25:07 → confirmed@04:31:34 → trigger@06:06:07 → expire@17:17:49 |
| 17 | LONG | RESOLVED_FAILED | 04:35:01 | 04:39:42 | 05:21:36 | 67249.31 | 67375.65 | 67526.45 | 68876.98 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.03 | 3.73 | - | - | - | candidate@04:35:01 → confirmed@04:39:42 → trigger@05:21:36 → expire@05:21:36 |
| 18 | SHORT | RESOLVED_REACHED | 04:44:30 | 04:47:34 | 06:06:27 | 67336.17 | 67403.53 | 67130.30 | 65787.69 | failed_by_timeout | failed_by_timeout | reached | 3.16 | 0.30 | 644.3 | 1 | no | candidate@04:44:30 → confirmed@04:47:34 → trigger@06:06:27 → expire@16:50:43 |
| 19 | LONG | RESOLVED_FAILED | 05:04:20 | 05:18:13 | 05:21:17 | 67174.75 | 67450.66 | 67490.35 | 68840.16 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.08 | 3.67 | - | - | - | candidate@05:04:20 → confirmed@05:18:13 → trigger@05:21:17 → expire@05:21:17 |
| 20 | LONG | INVALIDATED | 05:30:20 | 05:42:14 | - | 67428.85 | 67526.15 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@05:30:20 → confirmed@05:42:14 → invalidate@06:06:07 |
| 21 | LONG | RESOLVED_FAILED | 06:17:16 | 06:22:45 | 07:36:47 | 66937.95 | 67067.57 | 67140.05 | 68482.85 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.29 | 3.17 | - | - | - | candidate@06:17:16 → confirmed@06:22:45 → trigger@07:36:47 → expire@07:36:47 |
| 22 | LONG | INVALIDATED | 06:39:11 | 06:42:32 | - | 66820.05 | 66914.75 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@06:39:11 → confirmed@06:42:32 → invalidate@08:54:01 |
| 23 | LONG | RESOLVED_FAILED | 07:09:08 | 07:34:09 | 07:35:09 | 66766.85 | 67049.55 | 67086.65 | 68428.38 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.37 | 3.09 | - | - | - | candidate@07:09:08 → confirmed@07:34:09 → trigger@07:35:09 → expire@07:35:09 |
| 24 | SHORT | RESOLVED_REACHED | 07:41:58 | 07:44:58 | 08:50:19 | 67053.35 | 67159.31 | 66885.05 | 65547.35 | failed_by_timeout | failed_by_timeout | reached | 2.80 | 0.67 | 679.0 | 1 | no | candidate@07:41:58 → confirmed@07:44:58 → trigger@08:50:19 → expire@20:09:21 |
| 25 | LONG | INVALIDATED | 09:04:06 | 09:07:06 | - | 66472.05 | 66667.37 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@09:04:06 → confirmed@09:07:06 → invalidate@13:20:53 |
| 26 | LONG | INVALIDATED | 09:05:31 | 09:09:47 | - | 66472.05 | 66612.35 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@09:05:31 → confirmed@09:09:47 → invalidate@13:20:53 |
| 27 | LONG | INVALIDATED | 09:06:47 | 09:09:47 | - | 66470.50 | 66612.35 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@09:06:47 → confirmed@09:09:47 → invalidate@13:20:53 |
| 28 | SHORT | RESOLVED_REACHED | 09:12:55 | 09:22:08 | 09:33:42 | 66525.17 | 66744.95 | 66438.85 | 65110.07 | failed_by_timeout | failed_by_timeout | reached | 2.15 | 1.35 | 658.9 | 1 | no | candidate@09:12:55 → confirmed@09:22:08 → trigger@09:33:42 → expire@20:32:38 |
| 29 | SHORT | RESOLVED_FAILED | 09:47:02 | 09:55:29 | 13:23:11 | 66223.25 | 66396.75 | 66188.45 | 64864.68 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.78 | 1.73 | - | - | - | candidate@09:47:02 → confirmed@09:55:29 → trigger@13:23:11 → expire@13:23:11 |
| 30 | SHORT | RESOLVED_FAILED | 09:55:29 | 10:29:49 | 13:21:44 | 66210.15 | 66573.95 | 66127.15 | 64804.61 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.69 | 1.82 | - | - | - | candidate@09:55:29 → confirmed@10:29:49 → trigger@13:21:44 → expire@13:21:44 |
| 31 | LONG | RESOLVED_FAILED | 10:02:47 | 10:10:18 | 10:35:59 | 66210.15 | 66437.55 | 66699.95 | 68033.95 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.95 | 2.53 | - | - | - | candidate@10:02:47 → confirmed@10:10:18 → trigger@10:35:59 → expire@10:35:59 |
| 32 | SHORT | RESOLVED_REACHED | 10:29:49 | 10:32:49 | 10:40:15 | 66466.90 | 66599.75 | 66432.35 | 65103.70 | failed_by_timeout | failed_by_timeout | reached | 2.14 | 1.36 | 592.4 | 1 | no | candidate@10:29:49 → confirmed@10:32:49 → trigger@10:40:15 → expire@20:32:38 |
| 33 | LONG | INVALIDATED | 15:27:14 | 15:34:06 | - | 67024.15 | 67158.85 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@15:27:14 → confirmed@15:34:06 → invalidate@16:01:19 |
| 34 | SHORT | RESOLVED_FAILED | 16:59:50 | 17:03:50 | 17:17:41 | 65951.05 | 66194.05 | 65844.85 | 64527.95 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.27 | 1.58 | - | - | - | candidate@16:59:50 → confirmed@17:03:50 → trigger@17:17:41 → expire@17:17:41 |
| 35 | SHORT | RESOLVED_FAILED | 17:01:02 | 17:11:16 | 17:17:49 | 65951.05 | 66194.05 | 65767.05 | 64451.71 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.15 | 1.70 | - | - | - | candidate@17:01:02 → confirmed@17:11:16 → trigger@17:17:49 → expire@17:17:49 |
| 36 | LONG | RESOLVED_FAILED | 17:08:48 | 17:22:08 | 18:04:02 | 65694.25 | 66192.05 | 66337.05 | 67663.79 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.83 | 2.00 | - | - | - | candidate@17:08:48 → confirmed@17:22:08 → trigger@18:04:02 → expire@18:04:02 |
| 37 | SHORT | INVALIDATED | 17:33:22 | 17:49:52 | - | 65895.75 | 66105.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@17:33:22 → confirmed@17:49:52 → invalidate@18:04:43 |
| 38 | SHORT | INVALIDATED | 20:08:29 | 20:49:29 | - | 65054.65 | 65828.35 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@20:08:29 → confirmed@20:49:29 → invalidate@22:13:09 |
| 39 | SHORT | INVALIDATED | 20:08:49 | 20:49:29 | - | 65054.65 | 65777.82 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@20:08:49 → confirmed@20:49:29 → invalidate@22:13:09 |
| 40 | LONG | RESOLVED_FAILED | 20:16:04 | 20:38:03 | 22:13:10 | 65054.65 | 65565.65 | 66216.50 | 67540.83 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.42 | 1.82 | - | - | - | candidate@20:16:04 → confirmed@20:38:03 → trigger@22:13:10 → expire@22:13:10 |
| 41 | LONG | RESOLVED_FAILED | 20:17:51 | 20:38:03 | 22:13:09 | 65054.65 | 65518.85 | 66556.75 | 67887.88 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.50 | 2.32 | - | - | - | candidate@20:17:51 → confirmed@20:38:03 → trigger@22:13:09 → expire@22:13:09 |
| 42 | LONG | RESOLVED_FAILED | 20:38:03 | 21:02:53 | 22:13:09 | 65075.05 | 65352.45 | 66556.75 | 67887.88 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.50 | 2.32 | - | - | - | candidate@20:38:03 → confirmed@21:02:53 → trigger@22:13:09 → expire@22:13:09 |
| 43 | SHORT | INVALIDATED | 20:49:29 | 20:56:04 | - | 65128.67 | 65352.45 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | - | - | candidate@20:49:29 → confirmed@20:56:04 → invalidate@21:57:09 |
| 44 | LONG | RESOLVED_FAILED | 22:02:57 | 22:05:57 | 22:13:08 | 65627.12 | 65739.55 | 65840.75 | 67157.57 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.59 | 1.26 | - | - | - | candidate@22:02:57 → confirmed@22:05:57 → trigger@22:13:08 → expire@22:13:08 |
| 45 | SHORT | RESOLVED_FAILED | 22:29:18 | 22:32:29 | 22:35:08 | 65732.45 | 65920.45 | 65264.45 | 63959.16 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.39 | 1.21 | - | - | - | candidate@22:29:18 → confirmed@22:32:29 → trigger@22:35:08 → expire@22:35:08 |
| 46 | SHORT | NO_TRIGGER | 22:51:50 | 23:17:00 | - | 65100.50 | 66052.55 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | - | - | candidate@22:51:50 → confirmed@23:17:00 → expire@23:59:59 |

## 7. Successful zones detail

### BTCUSDT-SHORT-1772323262000-1

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-03-01T01:08:04.000Z, trigger price: 66550.15, target price: 65219.15
- Earliest reached horizon: **24h**, reached at: 2026-03-01T20:30:35.171Z, t→target: 1162.5 min
- MFE %: 2.313, MAE %: 2.463
- Move clustering: uniqueMoveId=1, clusterSize=8, primary=true, duplicateMoveCredit=false
- Scores at trigger: absorption=0.608, void=0.407, trigger=1.000, refill=0.499
- Reason chain: candidate@2026-03-01T00:01:02.000Z{buyPressure=0.641,askRefillScore=0.578,upMovePct=0.002,absorbScore=0.654,rangeCompression=true} | confirmed@2026-03-01T00:58:31.000Z{cyclesSeen=6.000,ageMin=57.483,defendedPersistenceSec=3449.000,oppositeThinning=0.499,voidScore=0.407} | trigger@2026-03-01T01:08:04.000Z{breakPct=0.065,flowMultiplier=5.144,sideFlowOK=true,triggerPrice=66550.150,targetPrice=65219.147} | expire@2026-03-01T20:30:35.171Z{earliestReachedHorizon=24h,targetPrice=65219.147}

### BTCUSDT-SHORT-1772334048000-12

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-03-01T03:23:59.000Z, trigger price: 67384.55, target price: 66036.86
- Earliest reached horizon: **24h**, reached at: 2026-03-01T16:49:17.042Z, t→target: 805.3 min
- MFE %: 3.522, MAE %: 0.431
- Move clustering: uniqueMoveId=1, clusterSize=8, primary=false, duplicateMoveCredit=true
- Scores at trigger: absorption=0.600, void=0.326, trigger=0.967, refill=0.503
- Reason chain: candidate@2026-03-01T03:00:48.000Z{buyPressure=0.552,askRefillScore=0.502,upMovePct=0.000,absorbScore=0.607,rangeCompression=true} | confirmed@2026-03-01T03:06:32.000Z{cyclesSeen=16.000,ageMin=5.733,defendedPersistenceSec=344.000,oppositeThinning=0.501,voidScore=0.326} | trigger@2026-03-01T03:23:59.000Z{breakPct=0.276,flowMultiplier=1.402,sideFlowOK=true,triggerPrice=67384.550,targetPrice=66036.859} | expire@2026-03-01T16:49:17.042Z{earliestReachedHorizon=24h,targetPrice=66036.859}

### BTCUSDT-SHORT-1772336293000-14

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-03-01T03:57:21.000Z, trigger price: 67406.65, target price: 66058.52
- Earliest reached horizon: **24h**, reached at: 2026-03-01T16:49:16.972Z, t→target: 771.9 min
- MFE %: 3.554, MAE %: 0.260
- Move clustering: uniqueMoveId=1, clusterSize=8, primary=false, duplicateMoveCredit=true
- Scores at trigger: absorption=0.601, void=0.399, trigger=1.000, refill=0.500
- Reason chain: candidate@2026-03-01T03:38:13.000Z{buyPressure=0.582,askRefillScore=0.503,upMovePct=0.000,absorbScore=0.641,rangeCompression=true} | confirmed@2026-03-01T03:50:46.000Z{cyclesSeen=7.000,ageMin=12.550,defendedPersistenceSec=753.000,oppositeThinning=0.538,voidScore=0.399} | trigger@2026-03-01T03:57:21.000Z{breakPct=0.052,flowMultiplier=1.902,sideFlowOK=true,triggerPrice=67406.650,targetPrice=66058.517} | expire@2026-03-01T16:49:16.972Z{earliestReachedHorizon=24h,targetPrice=66058.517}

### BTCUSDT-SHORT-1772339107000-16

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-03-01T06:06:07.000Z, trigger price: 67090.35, target price: 65748.54
- Earliest reached horizon: **24h**, reached at: 2026-03-01T17:17:49.132Z, t→target: 671.7 min
- MFE %: 3.099, MAE %: 0.362
- Move clustering: uniqueMoveId=1, clusterSize=8, primary=false, duplicateMoveCredit=true
- Scores at trigger: absorption=0.602, void=0.281, trigger=0.994, refill=0.499
- Reason chain: candidate@2026-03-01T04:25:07.000Z{buyPressure=0.677,askRefillScore=0.501,upMovePct=0.000,absorbScore=0.736,rangeCompression=true} | confirmed@2026-03-01T04:31:34.000Z{cyclesSeen=42.000,ageMin=6.450,defendedPersistenceSec=387.000,oppositeThinning=0.491,voidScore=0.281} | trigger@2026-03-01T06:06:07.000Z{breakPct=0.080,flowMultiplier=1.480,sideFlowOK=true,triggerPrice=67090.350,targetPrice=65748.543} | expire@2026-03-01T17:17:49.132Z{earliestReachedHorizon=24h,targetPrice=65748.543}

### BTCUSDT-SHORT-1772340270000-18

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-03-01T06:06:27.000Z, trigger price: 67130.30, target price: 65787.69
- Earliest reached horizon: **24h**, reached at: 2026-03-01T16:50:43.284Z, t→target: 644.3 min
- MFE %: 3.157, MAE %: 0.302
- Move clustering: uniqueMoveId=1, clusterSize=8, primary=false, duplicateMoveCredit=true
- Scores at trigger: absorption=0.619, void=0.189, trigger=0.976, refill=0.497
- Reason chain: candidate@2026-03-01T04:44:30.000Z{buyPressure=0.575,askRefillScore=0.504,upMovePct=0.001,absorbScore=0.616,rangeCompression=true} | confirmed@2026-03-01T04:47:34.000Z{cyclesSeen=32.000,ageMin=3.067,defendedPersistenceSec=184.000,oppositeThinning=0.501,voidScore=0.189} | trigger@2026-03-01T06:06:27.000Z{breakPct=0.306,flowMultiplier=1.426,sideFlowOK=true,triggerPrice=67130.300,targetPrice=65787.694} | expire@2026-03-01T16:50:43.284Z{earliestReachedHorizon=24h,targetPrice=65787.694}

### BTCUSDT-SHORT-1772350918000-24

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-03-01T08:50:19.000Z, trigger price: 66885.05, target price: 65547.35
- Earliest reached horizon: **24h**, reached at: 2026-03-01T20:09:21.050Z, t→target: 679.0 min
- MFE %: 2.802, MAE %: 0.670
- Move clustering: uniqueMoveId=1, clusterSize=8, primary=false, duplicateMoveCredit=true
- Scores at trigger: absorption=0.628, void=0.098, trigger=0.989, refill=0.500
- Reason chain: candidate@2026-03-01T07:41:58.000Z{buyPressure=0.639,askRefillScore=0.505,upMovePct=0.000,absorbScore=0.703,rangeCompression=true} | confirmed@2026-03-01T07:44:58.000Z{cyclesSeen=182.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.503,voidScore=0.098} | trigger@2026-03-01T08:50:19.000Z{breakPct=0.251,flowMultiplier=1.480,sideFlowOK=true,triggerPrice=66885.050,targetPrice=65547.349} | expire@2026-03-01T20:09:21.050Z{earliestReachedHorizon=24h,targetPrice=65547.349}

### BTCUSDT-SHORT-1772356375000-28

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-03-01T09:33:42.000Z, trigger price: 66438.85, target price: 65110.07
- Earliest reached horizon: **24h**, reached at: 2026-03-01T20:32:38.239Z, t→target: 658.9 min
- MFE %: 2.149, MAE %: 1.346
- Move clustering: uniqueMoveId=1, clusterSize=8, primary=false, duplicateMoveCredit=true
- Scores at trigger: absorption=0.603, void=0.169, trigger=0.989, refill=0.500
- Reason chain: candidate@2026-03-01T09:12:55.000Z{buyPressure=0.563,askRefillScore=0.501,upMovePct=0.000,absorbScore=0.620,rangeCompression=true} | confirmed@2026-03-01T09:22:08.000Z{cyclesSeen=52.000,ageMin=9.217,defendedPersistenceSec=553.000,oppositeThinning=0.498,voidScore=0.169} | trigger@2026-03-01T09:33:42.000Z{breakPct=0.130,flowMultiplier=1.456,sideFlowOK=true,triggerPrice=66438.850,targetPrice=65110.073} | expire@2026-03-01T20:32:38.239Z{earliestReachedHorizon=24h,targetPrice=65110.073}

### BTCUSDT-SHORT-1772360989000-32

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-03-01T10:40:15.000Z, trigger price: 66432.35, target price: 65103.70
- Earliest reached horizon: **24h**, reached at: 2026-03-01T20:32:38.240Z, t→target: 592.4 min
- MFE %: 2.140, MAE %: 1.356
- Move clustering: uniqueMoveId=1, clusterSize=8, primary=false, duplicateMoveCredit=true
- Scores at trigger: absorption=0.605, void=0.344, trigger=1.000, refill=0.500
- Reason chain: candidate@2026-03-01T10:29:49.000Z{buyPressure=0.583,askRefillScore=0.501,upMovePct=0.000,absorbScore=0.641,rangeCompression=true} | confirmed@2026-03-01T10:32:49.000Z{cyclesSeen=72.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.502,voidScore=0.344} | trigger@2026-03-01T10:40:15.000Z{breakPct=0.052,flowMultiplier=3.104,sideFlowOK=true,triggerPrice=66432.350,targetPrice=65103.703} | expire@2026-03-01T20:32:38.240Z{earliestReachedHorizon=24h,targetPrice=65103.703}


## 8. Honest verdict for 2026-03-01

| Metric | Value |
|---|---|
| Triggered | 24 |
| Reached (raw) | 8 |
| Unique reached moves | 1 |
| Raw triggered hit rate | 33.33% |
| **Unique-move-adjusted hit rate** | **4.17%** |

The strategy caught **1 unique 2% move**. Direction: SHORT only. The day was feasible in BOTH directions, but the detector only picked up one side here.

> **Strategy thresholds in `config/strategy.default.json` are unchanged.** Detector and target checker untouched. Failed / no_trigger / invalidated zones are preserved in the zones list and the CSV.
