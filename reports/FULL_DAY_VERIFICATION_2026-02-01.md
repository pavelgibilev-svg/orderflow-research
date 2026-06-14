# Full-Day Verification — BTCUSDT 2026-02-01

> **This is a full-day technical verification run, not a proof of strategy profitability.**

- Generated: 2026-05-08T17:56:44.141Z

## 1. Run conditions

| Setting | Value |
|---|---|
| Date | 2026-02-01 |
| Symbol | BTCUSDT |
| Exchange | binance-futures |
| Target percent | 2.0 |
| Horizons | 4h, 8h, 24h |
| Files used | incremental_book_L2, trades, liquidations (derivative_ticker / book_ticker present but not consumed by strategy) |
| L2 time limitation | **NO** — full 24h L2 replay (no `--max-l2-hours`) |
| Skip-snapshots used | yes (`--skip-snapshots` only suppresses the diagnostic 1s-depth-50 export; it does not affect zone detection) |
| Config file | `config/strategy.default.json` (unchanged from canonical defaults) |
| Threshold tuning | **NONE** — no values in `config/strategy.default.json` were modified for this run |
| targetPct | 2 |
| featureIntervalSec | 1 |
| zone.minAbsorptionScore | 0.6 |
| zone.minLiquidityVoidScore | 0.55 |
| zone.trigger.minBreakDistancePct | 0.05 |
| zone.trigger.minAggressiveFlowMultiplier | 1.4 |

## 2. Data validation

| File type | Present | Size | Rows parsed (first 1000) | Required/Optional | Validation status |
|---|---|---|---|---|---|
| incremental_book_L2 | yes | 825.8 MB | 1000 | required | ok |
| trades | yes | 55.0 MB | 1000 | required | ok |
| derivative_ticker | yes | 2.0 MB | 1000 | optional | ok |
| book_ticker | yes | 277.4 MB | 1000 | optional | ok |
| liquidations | yes | 32.3 KB | 1000 | optional | ok |

## 3. Full-day strategy summary

| Metric | Value |
|---|---|
| L2 events processed | 165 962 192 |
| Trades scanned | 6 759 515 |
| Zones found (total) | 20 |
| Candidate zones (every zone reached at least the candidate stage) | 20 |
| Confirmed zones | 18 |
| Triggered zones | 11 |
| Reached 2% within 4h | 0 |
| Reached 2% within 8h | 2 |
| Reached 2% within 24h | 6 |
| Failed (RESOLVED_FAILED) | 5 |
| No trigger (NO_TRIGGER) | 2 |
| Invalidated | 7 |
| Expired | 0 |
| Triggered hit rate 4h | 0.00% (0/11) |
| Triggered hit rate 8h | 18.18% (2/11) |
| Triggered hit rate 24h | 54.55% (6/11) |
| Unconditional baseline 4h | 0.08% up / 20.00% down (n=1200) |
| Unconditional baseline 8h | 0.10% up / 46.25% down (n=960) |
| Unconditional baseline 24h | 0.00% up / 0.00% down (n=0) |
| Quality flag ticks | 0 |

## 4. Comparison with previous capped run

| Metric | Capped run (4h L2) | Full-day run (24h L2) | Δ |
|---|---|---|---|
| L2 events processed | 23 129 968 | 165 962 192 | +142 832 224 |
| Trades scanned | 6 759 515 | 6 759 515 | +0 |
| Zones found | 3 | 20 | +17 |
| Triggered | 1 | 11 | +10 |
| Reached 2% (any horizon) | 1 | 6 | +5 |

### New zones discovered after 04:00 UTC (i.e. that the capped run could not see)

Found **17** new zones that the capped run could not have seen:

| ID | Dir | Start | Trigger | Status | 4h | 8h | 24h |
|---|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1769929070000-4 | SHORT | 06:57:50 | 07:04:52 | RESOLVED_REACHED | failed_by_timeout | failed_by_timeout | reached |
| BTCUSDT-SHORT-1769931922000-6 | SHORT | 07:45:22 | - | INVALIDATED | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger |
| BTCUSDT-SHORT-1769940184000-7 | SHORT | 10:03:04 | 10:36:21 | RESOLVED_REACHED | failed_by_timeout | reached | reached |
| BTCUSDT-SHORT-1769942488000-8 | SHORT | 10:41:28 | 14:28:51 | RESOLVED_REACHED | failed_by_timeout | failed_by_timeout | reached |
| BTCUSDT-LONG-1769929781000-5 | LONG | 07:09:41 | - | INVALIDATED | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger |
| BTCUSDT-SHORT-1769958085000-9 | SHORT | 15:01:25 | 15:17:03 | RESOLVED_REACHED | failed_by_timeout | reached | reached |
| BTCUSDT-SHORT-1769962684000-11 | SHORT | 16:18:04 | - | INVALIDATED | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger |
| BTCUSDT-SHORT-1769969766000-12 | SHORT | 18:16:06 | 19:57:09 | RESOLVED_FAILED | failed_by_timeout | failed_by_timeout | failed_by_timeout |
| BTCUSDT-LONG-1769960541000-10 | LONG | 15:42:21 | - | INVALIDATED | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger |
| BTCUSDT-SHORT-1769977518000-13 | SHORT | 20:25:18 | 21:09:28 | RESOLVED_FAILED | failed_by_timeout | failed_by_timeout | failed_by_timeout |
| BTCUSDT-LONG-1769977944000-14 | LONG | 20:32:24 | - | INVALIDATED | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger |
| BTCUSDT-LONG-1769980916000-16 | LONG | 21:21:56 | 22:11:01 | RESOLVED_FAILED | failed_by_timeout | failed_by_timeout | failed_by_timeout |
| BTCUSDT-SHORT-1769980511000-15 | SHORT | 21:15:11 | - | INVALIDATED | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger |
| BTCUSDT-SHORT-1769986285000-18 | SHORT | 22:51:25 | 23:05:47 | RESOLVED_FAILED | failed_by_timeout | failed_by_timeout | failed_by_timeout |
| BTCUSDT-LONG-1769985661000-17 | LONG | 22:41:01 | 23:36:10 | RESOLVED_FAILED | failed_by_timeout | failed_by_timeout | failed_by_timeout |
| BTCUSDT-LONG-1769989443000-19 | LONG | 23:44:03 | - | NO_TRIGGER | no_trigger | no_trigger | no_trigger |
| BTCUSDT-SHORT-1769990315000-20 | SHORT | 23:58:35 | - | NO_TRIGGER | no_trigger | no_trigger | no_trigger |

### How much did `--max-l2-hours 4` distort the picture?

The full-day run produced **6.7× more zones** than the capped run (20 vs 3).
Triggered ratio: **11.0×** (11 vs 1).
Both runs found reached zones. Full-day found 5 additional reached zones that the capped run could not see.

## 5. All zones

Total zones across the full day: **20** (every zone is included regardless of outcome — successful, failed, no_trigger, invalidated and expired all appear).

| # | Dir | Type | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Reason chain |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 00:00:37 | 00:18:54 | 01:07:10 | 78606.75 | 79375.45 | 78566.05 | 76994.73 | failed_by_timeout | failed_by_timeout | reached | 3.72 | 0.80 | 859.0 | candidate@00:00:37 → confirmed@00:18:54 → trigger@01:07:10 → expire@15:26:10 |
| 2 | LONG | ACCUMULATION | INVALIDATED | 01:12:33 | 01:15:55 | - | 78512.55 | 78683.45 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@01:12:33 → confirmed@01:15:55 → invalidate@07:04:52 |
| 3 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 01:57:14 | 02:26:02 | 06:48:08 | 78343.25 | 78871.75 | 78273.45 | 76707.98 | failed_by_timeout | failed_by_timeout | reached | 3.36 | 1.18 | 820.4 | candidate@01:57:14 → confirmed@02:26:02 → trigger@06:48:08 → expire@20:28:31 |
| 4 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 06:57:50 | 07:00:50 | 07:04:52 | 78262.95 | 78366.91 | 78082.25 | 76520.60 | failed_by_timeout | failed_by_timeout | reached | 3.12 | 1.42 | 844.6 | candidate@06:57:50 → confirmed@07:00:50 → trigger@07:04:52 → expire@21:09:27 |
| 5 | LONG | ACCUMULATION | INVALIDATED | 07:09:41 | 07:12:41 | - | 78158.25 | 78327.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@07:09:41 → confirmed@07:12:41 → invalidate@14:31:19 |
| 6 | SHORT | DISTRIBUTION | INVALIDATED | 07:45:22 | 07:55:37 | - | 78373.65 | 78547.65 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@07:45:22 → confirmed@07:55:37 → invalidate@09:58:07 |
| 7 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 10:03:04 | 10:16:44 | 10:36:21 | 78840.65 | 79193.85 | 78500.35 | 76930.34 | failed_by_timeout | reached | reached | 3.64 | 0.43 | 290.7 | candidate@10:03:04 → confirmed@10:16:44 → trigger@10:36:21 → expire@15:27:02 |
| 8 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 10:41:28 | 11:12:01 | 14:28:51 | 78099.85 | 78482.55 | 77816.25 | 76259.93 | failed_by_timeout | failed_by_timeout | reached | 2.79 | 0.88 | 517.8 | candidate@10:41:28 → confirmed@11:12:01 → trigger@14:28:51 → expire@23:06:38 |
| 9 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 15:01:25 | 15:09:06 | 15:17:03 | 77841.65 | 78241.25 | 77288.35 | 75742.58 | failed_by_timeout | reached | reached | 2.13 | 1.47 | 472.5 | candidate@15:01:25 → confirmed@15:09:06 → trigger@15:17:03 → expire@23:09:32 |
| 10 | LONG | ACCUMULATION | INVALIDATED | 15:42:21 | 15:45:21 | - | 77113.45 | 77299.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@15:42:21 → confirmed@15:45:21 → invalidate@20:28:32 |
| 11 | SHORT | DISTRIBUTION | INVALIDATED | 16:18:04 | 17:03:12 | - | 77100.65 | 77810.85 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@16:18:04 → confirmed@17:03:12 → invalidate@18:08:40 |
| 12 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 18:16:06 | 18:43:04 | 19:57:09 | 77964.85 | 78404.50 | 76978.35 | 75438.78 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.73 | 1.01 | - | candidate@18:16:06 → confirmed@18:43:04 → trigger@19:57:09 → expire@19:57:09 |
| 13 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 20:25:18 | 20:57:29 | 21:09:28 | 76556.95 | 77707.95 | 76505.75 | 74975.63 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.13 | 1.63 | - | candidate@20:25:18 → confirmed@20:57:29 → trigger@21:09:28 → expire@21:09:28 |
| 14 | LONG | ACCUMULATION | INVALIDATED | 20:32:24 | 20:51:07 | - | 76850.91 | 77707.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@20:32:24 → confirmed@20:51:07 → invalidate@21:09:38 |
| 15 | SHORT | DISTRIBUTION | INVALIDATED | 21:15:11 | 21:43:33 | - | 76507.15 | 77134.85 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@21:15:11 → confirmed@21:43:33 → invalidate@22:12:21 |
| 16 | LONG | ACCUMULATION | RESOLVED_FAILED | 21:21:56 | 21:51:05 | 22:11:01 | 76410.20 | 77134.85 | 77276.75 | 78822.29 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.62 | 2.11 | - | candidate@21:21:56 → confirmed@21:51:05 → trigger@22:11:01 → expire@22:11:01 |
| 17 | LONG | ACCUMULATION | RESOLVED_FAILED | 22:41:01 | 23:12:12 | 23:36:10 | 75668.95 | 77516.25 | 77560.50 | 79111.71 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.03 | 0.92 | - | candidate@22:41:01 → confirmed@23:12:12 → trigger@23:36:10 → expire@23:36:10 |
| 18 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 22:51:25 | 22:54:25 | 23:05:47 | 77118.05 | 77374.72 | 76740.35 | 75205.54 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.43 | 1.10 | - | candidate@22:51:25 → confirmed@22:54:25 → trigger@23:05:47 → expire@23:05:47 |
| 19 | LONG | ACCUMULATION | NO_TRIGGER | 23:44:03 | - | - | 76846.25 | 77321.25 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@23:44:03 → expire@23:59:59 |
| 20 | SHORT | DISTRIBUTION | NO_TRIGGER | 23:58:35 | - | - | 76899.15 | 77035.05 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@23:58:35 → expire@23:59:59 |

## 6. Successful 2% zones

**6 zone(s) reached the 2% target.**

### BTCUSDT-SHORT-1769904037000-1

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-02-01T01:07:10.000Z, trigger price: 78566.05
- Target reached time: 2026-02-01T15:26:10.637Z, earliest horizon: **24h**
- Time to target: 859.0 min
- MFE: 3.719 %, MAE: 0.799 %
- Scores at trigger: absorption=0.601, void=0.532, trigger=1.000, refill=0.502
- This zone's start (00:00:37) is **within the first 4h** — it was already visible to the capped run.
- Full reason chain: candidate@2026-02-01T00:00:37.000Z{buyPressure=0.604,askRefillScore=0.600,upMovePct=0.000,absorbScore=0.664,rangeCompression=true} | confirmed@2026-02-01T00:18:54.000Z{cyclesSeen=56.000,ageMin=18.283,defendedPersistenceSec=1097.000,oppositeThinning=0.498,voidScore=0.532} | trigger@2026-02-01T01:07:10.000Z{breakPct=0.052,flowMultiplier=7.703,sideFlowOK=true,triggerPrice=78566.050,targetPrice=76994.729} | expire@2026-02-01T15:26:10.637Z{earliestReachedHorizon=24h,targetPrice=76994.729}

### BTCUSDT-SHORT-1769911034000-3

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-02-01T06:48:08.000Z, trigger price: 78273.45
- Target reached time: 2026-02-01T20:28:31.921Z, earliest horizon: **24h**
- Time to target: 820.4 min
- MFE: 3.359 %, MAE: 1.176 %
- Scores at trigger: absorption=0.601, void=0.474, trigger=1.000, refill=0.501
- This zone's start (01:57:14) is **within the first 4h** — it was already visible to the capped run.
- Full reason chain: candidate@2026-02-01T01:57:14.000Z{buyPressure=0.575,askRefillScore=0.499,upMovePct=0.001,absorbScore=0.614,rangeCompression=true} | confirmed@2026-02-01T02:26:02.000Z{cyclesSeen=52.000,ageMin=28.800,defendedPersistenceSec=1728.000,oppositeThinning=0.502,voidScore=0.474} | trigger@2026-02-01T06:48:08.000Z{breakPct=0.089,flowMultiplier=5.138,sideFlowOK=true,triggerPrice=78273.450,targetPrice=76707.981} | expire@2026-02-01T20:28:31.921Z{earliestReachedHorizon=24h,targetPrice=76707.981}

### BTCUSDT-SHORT-1769929070000-4

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-02-01T07:04:52.000Z, trigger price: 78082.25
- Target reached time: 2026-02-01T21:09:27.819Z, earliest horizon: **24h**
- Time to target: 844.6 min
- MFE: 3.123 %, MAE: 1.424 %
- Scores at trigger: absorption=0.709, void=0.504, trigger=0.975, refill=0.491
- This zone's start (06:57:50) is **after 04:00 UTC** — it is a *new* zone the capped run could not see.
- Full reason chain: candidate@2026-02-01T06:57:50.000Z{buyPressure=0.696,askRefillScore=0.500,upMovePct=0.005,absorbScore=0.605,rangeCompression=true} | confirmed@2026-02-01T07:00:50.000Z{cyclesSeen=163.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.513,voidScore=0.504} | trigger@2026-02-01T07:04:52.000Z{breakPct=0.231,flowMultiplier=1.420,sideFlowOK=true,triggerPrice=78082.250,targetPrice=76520.605} | expire@2026-02-01T21:09:27.819Z{earliestReachedHorizon=24h,targetPrice=76520.605}

### BTCUSDT-SHORT-1769940184000-7

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-02-01T10:36:21.000Z, trigger price: 78500.35
- Target reached time: 2026-02-01T15:27:02.143Z, earliest horizon: **8h**
- Time to target: 290.7 min
- MFE: 3.639 %, MAE: 0.431 %
- Scores at trigger: absorption=0.601, void=0.526, trigger=1.000, refill=0.502
- This zone's start (10:03:04) is **after 04:00 UTC** — it is a *new* zone the capped run could not see.
- Full reason chain: candidate@2026-02-01T10:03:04.000Z{buyPressure=0.601,askRefillScore=0.512,upMovePct=0.000,absorbScore=0.661,rangeCompression=true} | confirmed@2026-02-01T10:16:44.000Z{cyclesSeen=17.000,ageMin=13.667,defendedPersistenceSec=820.000,oppositeThinning=0.502,voidScore=0.526} | trigger@2026-02-01T10:36:21.000Z{breakPct=0.432,flowMultiplier=1.758,sideFlowOK=true,triggerPrice=78500.350,targetPrice=76930.343} | expire@2026-02-01T15:27:02.143Z{earliestReachedHorizon=8h,targetPrice=76930.343}

### BTCUSDT-SHORT-1769942488000-8

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-02-01T14:28:51.000Z, trigger price: 77816.25
- Target reached time: 2026-02-01T23:06:38.230Z, earliest horizon: **24h**
- Time to target: 517.8 min
- MFE: 2.792 %, MAE: 0.879 %
- Scores at trigger: absorption=0.602, void=0.452, trigger=0.967, refill=0.494
- This zone's start (10:41:28) is **after 04:00 UTC** — it is a *new* zone the capped run could not see.
- Full reason chain: candidate@2026-02-01T10:41:28.000Z{buyPressure=0.556,askRefillScore=0.501,upMovePct=0.000,absorbScore=0.611,rangeCompression=true} | confirmed@2026-02-01T11:12:01.000Z{cyclesSeen=100.000,ageMin=30.550,defendedPersistenceSec=1833.000,oppositeThinning=0.507,voidScore=0.452} | trigger@2026-02-01T14:28:51.000Z{breakPct=0.363,flowMultiplier=1.404,sideFlowOK=true,triggerPrice=77816.250,targetPrice=76259.925} | expire@2026-02-01T23:06:38.230Z{earliestReachedHorizon=24h,targetPrice=76259.925}

### BTCUSDT-SHORT-1769958085000-9

- Direction: SHORT, type DISTRIBUTION
- Trigger time: 2026-02-01T15:17:03.000Z, trigger price: 77288.35
- Target reached time: 2026-02-01T23:09:32.974Z, earliest horizon: **8h**
- Time to target: 472.5 min
- MFE: 2.128 %, MAE: 1.466 %
- Scores at trigger: absorption=0.604, void=0.481, trigger=0.974, refill=0.506
- This zone's start (15:01:25) is **after 04:00 UTC** — it is a *new* zone the capped run could not see.
- Full reason chain: candidate@2026-02-01T15:01:25.000Z{buyPressure=0.551,askRefillScore=0.505,upMovePct=0.000,absorbScore=0.607,rangeCompression=true} | confirmed@2026-02-01T15:09:06.000Z{cyclesSeen=87.000,ageMin=7.683,defendedPersistenceSec=461.000,oppositeThinning=0.496,voidScore=0.481} | trigger@2026-02-01T15:17:03.000Z{breakPct=0.711,flowMultiplier=1.412,sideFlowOK=true,triggerPrice=77288.350,targetPrice=75742.583} | expire@2026-02-01T23:09:32.974Z{earliestReachedHorizon=8h,targetPrice=75742.583}


## 7. Failed zones analysis

Failed-or-unfinished zones: **14** out of 20 total.

- `INVALIDATED`: 7
- `RESOLVED_FAILED`: 5
- `NO_TRIGGER`: 2

### Why they broke

- Never reached the trigger stage: 9 zones
- Triggered but failed by timeout (MFE didn't reach 2%): 5 zones
- MFE < 2 % among failed zones: 5
- MAE > 1 % among failed zones: 4
- Below `minLiquidityVoidScore` (0.55) at confirmation: 11
- Below `minAbsorptionScore` (0.60) at confirmation: 0
- Carried at least one data-quality flag: 0

Sample (up to 15) failed zones with their compact reason chain:

- `BTCUSDT-LONG-1769908353000-2` (LONG, INVALIDATED, MFE=-%, MAE=-%): candidate@2026-02-01T01:12:33.000Z{sellPressure=0.580,bidRefillScore=0.499,downMovePct=0.000,absorbScore=0.638,rangeCompression=true} | confirmed@2026-02-01T01:15:55.000Z{cyclesSeen=137.000,ageMin=3.367,defendedPersistenceSec=202.000,oppositeThinning=0.495,voidScore=0.262} | invalidate@2026-02-01T07:04:52.000Z{mid=78082.250,zoneLow=78512.550,zoneHigh=78683.450}
- `BTCUSDT-LONG-1769929781000-5` (LONG, INVALIDATED, MFE=-%, MAE=-%): candidate@2026-02-01T07:09:41.000Z{sellPressure=0.593,bidRefillScore=0.499,downMovePct=0.000,absorbScore=0.653,rangeCompression=true} | confirmed@2026-02-01T07:12:41.000Z{cyclesSeen=170.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.491,voidScore=0.476} | invalidate@2026-02-01T14:31:19.000Z{mid=77764.700,zoneLow=78158.251,zoneHigh=78327.950}
- `BTCUSDT-SHORT-1769931922000-6` (SHORT, INVALIDATED, MFE=-%, MAE=-%): candidate@2026-02-01T07:45:22.000Z{buyPressure=0.641,askRefillScore=0.502,upMovePct=0.001,absorbScore=0.682,rangeCompression=true} | confirmed@2026-02-01T07:55:37.000Z{cyclesSeen=11.000,ageMin=10.250,defendedPersistenceSec=615.000,oppositeThinning=0.500,voidScore=0.412} | invalidate@2026-02-01T09:58:07.000Z{mid=78949.950,zoneLow=78373.650,zoneHigh=78547.650}
- `BTCUSDT-LONG-1769960541000-10` (LONG, INVALIDATED, MFE=-%, MAE=-%): candidate@2026-02-01T15:42:21.000Z{sellPressure=0.553,bidRefillScore=0.500,downMovePct=0.000,absorbScore=0.608,rangeCompression=true} | confirmed@2026-02-01T15:45:21.000Z{cyclesSeen=135.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.500,voidScore=0.579} | invalidate@2026-02-01T20:28:32.000Z{mid=76699.250,zoneLow=77113.450,zoneHigh=77299.950}
- `BTCUSDT-SHORT-1769962684000-11` (SHORT, INVALIDATED, MFE=-%, MAE=-%): candidate@2026-02-01T16:18:04.000Z{buyPressure=0.620,askRefillScore=0.500,upMovePct=0.000,absorbScore=0.682,rangeCompression=true} | confirmed@2026-02-01T17:03:12.000Z{cyclesSeen=104.000,ageMin=45.133,defendedPersistenceSec=2708.000,oppositeThinning=0.493,voidScore=0.244} | invalidate@2026-02-01T18:08:40.000Z{mid=78200.050,zoneLow=77100.650,zoneHigh=77810.850}
- `BTCUSDT-SHORT-1769969766000-12` (SHORT, RESOLVED_FAILED, MFE=1.73%, MAE=1.01%): candidate@2026-02-01T18:16:06.000Z{buyPressure=0.564,askRefillScore=0.502,upMovePct=0.000,absorbScore=0.620,rangeCompression=true} | confirmed@2026-02-01T18:43:04.000Z{cyclesSeen=21.000,ageMin=26.967,defendedPersistenceSec=1618.000,oppositeThinning=0.510,voidScore=0.334} | trigger@2026-02-01T19:57:09.000Z{breakPct=1.265,flowMultiplier=1.419,sideFlowOK=true,triggerPrice=76978.350,targetPrice=75438.783} | expire@2026-02-02T19:57:09.000Z{allHorizonsFailed=true,targetPrice=75438.783}
- `BTCUSDT-SHORT-1769977518000-13` (SHORT, RESOLVED_FAILED, MFE=1.13%, MAE=1.63%): candidate@2026-02-01T20:25:18.000Z{buyPressure=0.550,askRefillScore=0.506,upMovePct=0.000,absorbScore=0.605,rangeCompression=true} | confirmed@2026-02-01T20:57:29.000Z{cyclesSeen=24.000,ageMin=32.183,defendedPersistenceSec=1931.000,oppositeThinning=0.501,voidScore=0.282} | trigger@2026-02-01T21:09:28.000Z{breakPct=0.067,flowMultiplier=4.488,sideFlowOK=true,triggerPrice=76505.750,targetPrice=74975.635} | expire@2026-02-02T21:09:28.000Z{allHorizonsFailed=true,targetPrice=74975.635}
- `BTCUSDT-LONG-1769977944000-14` (LONG, INVALIDATED, MFE=-%, MAE=-%): candidate@2026-02-01T20:32:24.000Z{sellPressure=0.572,bidRefillScore=0.497,downMovePct=0.000,absorbScore=0.630,rangeCompression=true} | confirmed@2026-02-01T20:51:07.000Z{cyclesSeen=67.000,ageMin=18.717,defendedPersistenceSec=1123.000,oppositeThinning=0.499,voidScore=0.548} | invalidate@2026-02-01T21:09:38.000Z{mid=76464.850,zoneLow=76850.905,zoneHigh=77707.950}
- `BTCUSDT-SHORT-1769980511000-15` (SHORT, INVALIDATED, MFE=-%, MAE=-%): candidate@2026-02-01T21:15:11.000Z{buyPressure=0.664,askRefillScore=0.506,upMovePct=0.000,absorbScore=0.731,rangeCompression=true} | confirmed@2026-02-01T21:43:33.000Z{cyclesSeen=18.000,ageMin=28.367,defendedPersistenceSec=1702.000,oppositeThinning=0.498,voidScore=0.131} | invalidate@2026-02-01T22:12:21.000Z{mid=77527.800,zoneLow=76507.150,zoneHigh=77134.850}
- `BTCUSDT-LONG-1769980916000-16` (LONG, RESOLVED_FAILED, MFE=0.62%, MAE=2.11%): candidate@2026-02-01T21:21:56.000Z{sellPressure=0.589,bidRefillScore=0.490,downMovePct=0.000,absorbScore=0.648,rangeCompression=true} | confirmed@2026-02-01T21:51:05.000Z{cyclesSeen=55.000,ageMin=29.150,defendedPersistenceSec=1749.000,oppositeThinning=0.500,voidScore=0.579} | trigger@2026-02-01T22:11:01.000Z{breakPct=0.184,flowMultiplier=1.410,sideFlowOK=true,triggerPrice=77276.750,targetPrice=78822.285} | expire@2026-02-02T22:11:01.000Z{allHorizonsFailed=true,targetPrice=78822.285}
- `BTCUSDT-LONG-1769985661000-17` (LONG, RESOLVED_FAILED, MFE=0.03%, MAE=0.92%): candidate@2026-02-01T22:41:01.000Z{sellPressure=0.552,bidRefillScore=0.506,downMovePct=0.000,absorbScore=0.607,rangeCompression=true} | confirmed@2026-02-01T23:12:12.000Z{cyclesSeen=18.000,ageMin=31.183,defendedPersistenceSec=1871.000,oppositeThinning=0.500,voidScore=0.575} | trigger@2026-02-01T23:36:10.000Z{breakPct=0.057,flowMultiplier=3.235,sideFlowOK=true,triggerPrice=77560.500,targetPrice=79111.710} | expire@2026-02-02T23:36:10.000Z{allHorizonsFailed=true,targetPrice=79111.710}
- `BTCUSDT-SHORT-1769986285000-18` (SHORT, RESOLVED_FAILED, MFE=1.43%, MAE=1.10%): candidate@2026-02-01T22:51:25.000Z{buyPressure=0.588,askRefillScore=0.493,upMovePct=0.000,absorbScore=0.647,rangeCompression=true} | confirmed@2026-02-01T22:54:25.000Z{cyclesSeen=182.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.498,voidScore=0.293} | trigger@2026-02-01T23:05:47.000Z{breakPct=0.490,flowMultiplier=2.289,sideFlowOK=true,triggerPrice=76740.350,targetPrice=75205.543} | expire@2026-02-02T23:05:47.000Z{allHorizonsFailed=true,targetPrice=75205.543}
- `BTCUSDT-LONG-1769989443000-19` (LONG, NO_TRIGGER, MFE=-%, MAE=-%): candidate@2026-02-01T23:44:03.000Z{sellPressure=0.698,bidRefillScore=0.510,downMovePct=0.001,absorbScore=0.719,rangeCompression=true} | expire@2026-02-01T23:59:59.965Z{reason=End of replay; no trigger seen}
- `BTCUSDT-SHORT-1769990315000-20` (SHORT, NO_TRIGGER, MFE=-%, MAE=-%): candidate@2026-02-01T23:58:35.000Z{buyPressure=0.578,askRefillScore=0.493,upMovePct=0.000,absorbScore=0.636,rangeCompression=true} | expire@2026-02-01T23:59:59.965Z{reason=End of replay; no trigger seen}

## 8. Strategy assessment

> **This is a full-day technical verification run, not a proof of strategy profitability.**

**Technical operation:** verified.
Full-day L2 replay processed 165 962 192 events without crashing or running out of memory; the streaming reader, order-book reconstruction, feature engine, zone state machine and target checker all completed end-to-end on the full 24 hours of real Tardis data. This is the first valid proof that the pipeline scales to a complete day.

**Strategy itself:** the full-day run produced 6 zone(s) that reached the +2% target. This is a stronger signal than zero. It is **still not a proof of profitability** — a single day cannot prove anything statistically, and there is no slippage / fee / latency model.

**Worth continuing?**

Yes, conditional on **honest evaluation**:
- The pipeline is fast enough to scale to many days (~166.0M L2 events processed for a single day; multi-day runs are now feasible).
- The detector finds plausible zones with full reason chains. Whether the *trigger* logic and *target* horizons are tuned correctly is an open question that requires a paid-data multi-day sample.
- Failed zones still carry useful information (MFE distribution, MAE distribution) that could feed a calibration loop later.

**What does this say about 2% intraday on 2026-02-01?**

- The unconditional 4h baseline was 0.08% up / 20.00% down (n=1200) — the day was strongly biased **downward**.
- A SHORT zone reaching its target is consistent with that bias; a LONG zone failing on a strongly down day is also consistent.

**Difference from the capped run**

- The capped run saw only the first 4 hours UTC; the full-day run saw all 24 hours.
- Zones found: 3 (capped) → 20 (full-day) — more.
- Triggered: 1 → 11.
- Reached: 1 → 6.
- The capped result on 2026-02-01 (1 reached SHORT) may have been overwritten by a different sequence in the full-day run depending on detection timing.

**Next steps**

- Run a paid Tardis subscription month (≥20 days) at full-day resolution, no L2 cap.
- Generate a per-zone score distribution across days and look at calibration of `absorptionScore`, `liquidityVoidScore`, `triggerScore` against actual MFE.
- Only after that, consider tuning thresholds — and split into in-sample / out-of-sample so the tuning isn't fitted to its own data.
- This run does **not** justify any threshold change.
