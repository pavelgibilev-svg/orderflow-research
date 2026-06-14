# Orderflow L2 Strategy — Jan-Apr 2026 Final Report

> **This is a compatibility and smoke-test run, not a proof of strategy profitability.**

- Generated: 2026-05-08T16:04:05.072Z
- Symbol: BTCUSDT
- Exchange: binance-futures
- Input: `./data/tardis/binance-futures/BTCUSDT`
- Dates: 2026-01-01, 2026-02-01, 2026-03-01, 2026-04-01

## 1. Data validation summary

| Date | L2 present | Trades present | Optional present | Optional missing | L2 rows | Trades rows | Valid | Quality flag ticks |
|---|---|---|---|---|---|---|---|---|
| 2026-01-01 | yes (331.4 MB) | yes (9.2 MB) | derivative_ticker,book_ticker,liquidations | - | 9480504 | 1056983 | yes | 0 |
| 2026-02-01 | yes (825.8 MB) | yes (55.0 MB) | derivative_ticker,book_ticker,liquidations | - | 23129968 | 6759515 | yes | 0 |
| 2026-03-01 | yes (703.0 MB) | yes (48.5 MB) | derivative_ticker,book_ticker,liquidations | - | 28387554 | 5961363 | yes | 1 |
| 2026-04-01 | yes (643.9 MB) | yes (32.3 MB) | derivative_ticker,book_ticker,liquidations | - | 17950039 | 4104211 | yes | 0 |

## 2. Strategy result summary

> Baseline column is the **4h unconditional 2% hit rate** (samples every 60s, all-day price walk). 24h baseline is omitted because — with only 24h of trades per day — there is at most 1 sample window that fits.

| Date | Zones | Cand | Conf | Trig | Reached 4h | Reached 8h | Reached 24h | Failed / no_trig / invalid | Hit rate (triggered) | Baseline 2% (4h up / down) |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-01-01 | 4 | 4 | 4 | 2 | 0 | 0 | 0 | 4 | 0.00% | 0.00% / 0.00% (n=1200) |
| 2026-02-01 | 3 | 3 | 3 | 1 | 0 | 0 | 1 | 2 | 100.00% | 0.08% / 20.00% (n=1200) |
| 2026-03-01 | 7 | 7 | 6 | 1 | 0 | 0 | 1 | 6 | 100.00% | 7.50% / 10.83% (n=1200) |
| 2026-04-01 | 9 | 9 | 8 | 5 | 0 | 0 | 0 | 9 | 0.00% | 3.67% / 0.00% (n=1200) |
| **TOTAL** | **23** | **23** | **21** | **9** | **0** | **0** | **2** | **21** | **22.22%** | **2.81% / 7.71%** |

## 3. All detected zones
Total zones across all 4 days: **23** (every zone is included regardless of outcome).

| Date | Dir | Type | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-01-01 | LONG | ACCUMULATION | RESOLVED_FAILED | 00:00:31 | 00:03:31 | 00:05:15 | 87560.05 | 87659.75 | 87719.45 | 89473.84 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.32 | 0.24 | - | candidate@00:00:31 → confirmed@00:03:31 → trigger@00:05:15 → expire@00:05:15 |
| 2026-01-01 | SHORT | DISTRIBUTION | NO_TRIGGER | 00:10:28 | 00:13:28 | - | 87690.58 | 88064.95 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@00:10:28 → confirmed@00:13:28 → expire@23:59:59 |
| 2026-01-01 | LONG | ACCUMULATION | RESOLVED_FAILED | 00:31:13 | 00:54:33 | 01:07:04 | 87691.18 | 87799.95 | 87843.95 | 89600.83 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.18 | 0.38 | - | candidate@00:31:13 → confirmed@00:54:33 → trigger@01:07:04 → expire@01:07:04 |
| 2026-01-01 | LONG | ACCUMULATION | NO_TRIGGER | 01:22:05 | 01:25:05 | - | 87797.95 | 88064.95 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@01:22:05 → confirmed@01:25:05 → expire@23:59:59 |
| 2026-02-01 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 00:00:37 | 00:18:54 | 01:07:10 | 78606.75 | 79375.45 | 78566.05 | 76994.73 | failed_by_timeout | failed_by_timeout | reached | 3.72 | 0.80 | 859.0 | candidate@00:00:37 → confirmed@00:18:54 → trigger@01:07:10 → expire@15:26:10 |
| 2026-02-01 | LONG | ACCUMULATION | NO_TRIGGER | 01:12:33 | 01:15:55 | - | 78278.55 | 79020.45 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@01:12:33 → confirmed@01:15:55 → expire@23:59:59 |
| 2026-02-01 | SHORT | DISTRIBUTION | NO_TRIGGER | 01:57:14 | 02:26:02 | - | 78343.25 | 79020.45 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@01:57:14 → confirmed@02:26:02 → expire@23:59:59 |
| 2026-03-01 | SHORT | DISTRIBUTION | RESOLVED_REACHED | 00:01:02 | 00:58:31 | 01:08:04 | 66593.75 | 67066.55 | 66550.15 | 65219.15 | failed_by_timeout | failed_by_timeout | reached | 2.31 | 2.46 | 1162.5 | candidate@00:01:02 → confirmed@00:58:31 → trigger@01:08:04 → expire@20:30:35 |
| 2026-03-01 | LONG | ACCUMULATION | INVALIDATED | 00:02:07 | 00:05:21 | - | 66909.38 | 67066.55 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@00:02:07 → confirmed@00:05:21 → invalidate@01:04:56 |
| 2026-03-01 | LONG | ACCUMULATION | EXPIRED | 01:06:00 | - | - | 66039.75 | 68171.40 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@01:06:00 → expire@02:06:01 |
| 2026-03-01 | SHORT | DISTRIBUTION | INVALIDATED | 01:17:21 | 01:20:37 | - | 66039.75 | 66234.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@01:17:21 → confirmed@01:20:37 → invalidate@01:36:51 |
| 2026-03-01 | SHORT | DISTRIBUTION | INVALIDATED | 01:42:11 | 01:45:11 | - | 66578.05 | 66711.05 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@01:42:11 → confirmed@01:45:11 → invalidate@01:49:12 |
| 2026-03-01 | SHORT | DISTRIBUTION | NO_TRIGGER | 02:08:26 | 02:16:06 | - | 67361.05 | 68138.95 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@02:08:26 → confirmed@02:16:06 → expire@23:59:59 |
| 2026-03-01 | LONG | ACCUMULATION | NO_TRIGGER | 02:34:32 | 03:08:32 | - | 67361.05 | 68138.95 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@02:34:32 → confirmed@03:08:32 → expire@23:59:59 |
| 2026-04-01 | LONG | ACCUMULATION | RESOLVED_FAILED | 00:08:26 | 00:15:49 | 00:51:04 | 67989.75 | 68202.03 | 68239.50 | 69604.29 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.54 | 1.03 | - | candidate@00:08:26 → confirmed@00:15:49 → trigger@00:51:04 → expire@00:51:04 |
| 2026-04-01 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 00:49:15 | 00:56:04 | 01:34:36 | 67969.45 | 68287.35 | 67920.05 | 66561.65 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.57 | 2.01 | - | candidate@00:49:15 → confirmed@00:56:04 → trigger@01:34:36 → expire@01:34:36 |
| 2026-04-01 | LONG | ACCUMULATION | INVALIDATED | 01:12:03 | 01:25:21 | - | 67989.75 | 68265.75 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@01:12:03 → confirmed@01:25:21 → invalidate@02:26:48 |
| 2026-04-01 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 01:49:01 | 01:52:39 | 02:29:16 | 67814.95 | 67887.78 | 67595.45 | 66243.54 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.09 | 2.50 | - | candidate@01:49:01 → confirmed@01:52:39 → trigger@02:29:16 → expire@02:29:16 |
| 2026-04-01 | LONG | ACCUMULATION | RESOLVED_FAILED | 02:31:48 | 02:34:48 | 03:10:28 | 67617.05 | 67703.58 | 68009.45 | 69369.64 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.88 | 0.20 | - | candidate@02:31:48 → confirmed@02:34:48 → trigger@03:10:28 → expire@03:10:28 |
| 2026-04-01 | SHORT | DISTRIBUTION | INVALIDATED | 02:45:06 | 02:55:13 | - | 67561.05 | 67705.75 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@02:45:06 → confirmed@02:55:13 → invalidate@03:09:51 |
| 2026-04-01 | SHORT | DISTRIBUTION | NO_TRIGGER | 03:13:58 | 03:18:38 | - | 67877.35 | 68212.65 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@03:13:58 → confirmed@03:18:38 → expire@23:59:59 |
| 2026-04-01 | LONG | ACCUMULATION | RESOLVED_FAILED | 03:16:15 | 03:23:43 | 03:45:52 | 67907.35 | 68013.84 | 68101.60 | 69463.63 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.74 | 0.32 | - | candidate@03:16:15 → confirmed@03:23:43 → trigger@03:45:52 → expire@03:45:52 |
| 2026-04-01 | LONG | ACCUMULATION | EXPIRED | 03:54:40 | - | - | 68064.85 | 68162.71 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@03:54:40 → expire@04:54:41 |

## 4. Best zones

Top 9 triggered zones, ranked by absorption × void × trigger score:

### BTCUSDT-LONG-1767225631000-1

- Date: 2026-01-01, direction LONG, type ACCUMULATION, final status `RESOLVED_FAILED`
- Trigger time: 2026-01-01T00:05:15.000Z, trigger price: 87719.45, target price: 89473.84
- Scores at trigger: absorption=0.675, void=0.702, trigger=1.000, refill=0.536
- Horizons: 4h=failed_by_timeout, 8h=failed_by_timeout, 24h=failed_by_timeout
- MFE %: 1.325, MAE %: 0.241, t→target min: -
- Reason chain: candidate@2026-01-01T00:00:31.000Z{sellPressure=0.761,bidRefillScore=0.684,downMovePct=0.005,absorbScore=0.667,rangeCompression=true} | confirmed@2026-01-01T00:03:31.000Z{cyclesSeen=182.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.476,voidScore=0.702} | trigger@2026-01-01T00:05:15.000Z{breakPct=0.068,flowMultiplier=1.866,sideFlowOK=true,triggerPrice=87719.450,targetPrice=89473.839} | expire@2026-01-02T00:05:15.000Z{allHorizonsFailed=true,targetPrice=89473.839}

### BTCUSDT-SHORT-1769904037000-5

- Date: 2026-02-01, direction SHORT, type DISTRIBUTION, final status `RESOLVED_REACHED`
- Trigger time: 2026-02-01T01:07:10.000Z, trigger price: 78566.05, target price: 76994.73
- Scores at trigger: absorption=0.601, void=0.532, trigger=1.000, refill=0.502
- Horizons: 4h=failed_by_timeout, 8h=failed_by_timeout, 24h=reached  (earliest reach: **24h**)
- MFE %: 3.719, MAE %: 0.799, t→target min: 859.0
- Reason chain: candidate@2026-02-01T00:00:37.000Z{buyPressure=0.604,askRefillScore=0.600,upMovePct=0.000,absorbScore=0.664,rangeCompression=true} | confirmed@2026-02-01T00:18:54.000Z{cyclesSeen=56.000,ageMin=18.283,defendedPersistenceSec=1097.000,oppositeThinning=0.498,voidScore=0.532} | trigger@2026-02-01T01:07:10.000Z{breakPct=0.052,flowMultiplier=7.703,sideFlowOK=true,triggerPrice=78566.050,targetPrice=76994.729} | expire@2026-02-01T15:26:10.637Z{earliestReachedHorizon=24h,targetPrice=76994.729}

### BTCUSDT-LONG-1767227473000-3

- Date: 2026-01-01, direction LONG, type ACCUMULATION, final status `RESOLVED_FAILED`
- Trigger time: 2026-01-01T01:07:04.000Z, trigger price: 87843.95, target price: 89600.83
- Scores at trigger: absorption=0.603, void=0.467, trigger=0.975, refill=0.497
- Horizons: 4h=failed_by_timeout, 8h=failed_by_timeout, 24h=failed_by_timeout
- MFE %: 1.181, MAE %: 0.382, t→target min: -
- Reason chain: candidate@2026-01-01T00:31:13.000Z{sellPressure=0.560,bidRefillScore=0.502,downMovePct=0.000,absorbScore=0.616,rangeCompression=true} | confirmed@2026-01-01T00:54:33.000Z{cyclesSeen=84.000,ageMin=23.333,defendedPersistenceSec=1400.000,oppositeThinning=0.495,voidScore=0.467} | trigger@2026-01-01T01:07:04.000Z{breakPct=0.050,flowMultiplier=1.425,sideFlowOK=true,triggerPrice=87843.950,targetPrice=89600.829} | expire@2026-01-02T01:07:04.000Z{allHorizonsFailed=true,targetPrice=89600.829}

### BTCUSDT-SHORT-1772323262000-8

- Date: 2026-03-01, direction SHORT, type DISTRIBUTION, final status `RESOLVED_REACHED`
- Trigger time: 2026-03-01T01:08:04.000Z, trigger price: 66550.15, target price: 65219.15
- Scores at trigger: absorption=0.608, void=0.407, trigger=1.000, refill=0.499
- Horizons: 4h=failed_by_timeout, 8h=failed_by_timeout, 24h=reached  (earliest reach: **24h**)
- MFE %: 2.313, MAE %: 2.463, t→target min: 1162.5
- Reason chain: candidate@2026-03-01T00:01:02.000Z{buyPressure=0.641,askRefillScore=0.578,upMovePct=0.002,absorbScore=0.654,rangeCompression=true} | confirmed@2026-03-01T00:58:31.000Z{cyclesSeen=6.000,ageMin=57.483,defendedPersistenceSec=3449.000,oppositeThinning=0.499,voidScore=0.407} | trigger@2026-03-01T01:08:04.000Z{breakPct=0.065,flowMultiplier=5.144,sideFlowOK=true,triggerPrice=66550.150,targetPrice=65219.147} | expire@2026-03-01T20:30:35.171Z{earliestReachedHorizon=24h,targetPrice=65219.147}

### BTCUSDT-SHORT-1775004555000-16

- Date: 2026-04-01, direction SHORT, type DISTRIBUTION, final status `RESOLVED_FAILED`
- Trigger time: 2026-04-01T01:34:36.000Z, trigger price: 67920.05, target price: 66561.65
- Scores at trigger: absorption=0.690, void=0.289, trigger=1.000, refill=0.505
- Horizons: 4h=failed_by_timeout, 8h=failed_by_timeout, 24h=failed_by_timeout
- MFE %: 0.567, MAE %: 2.014, t→target min: -
- Reason chain: candidate@2026-04-01T00:49:15.000Z{buyPressure=0.602,askRefillScore=0.518,upMovePct=0.000,absorbScore=0.662,rangeCompression=true} | confirmed@2026-04-01T00:56:04.000Z{cyclesSeen=4.000,ageMin=6.817,defendedPersistenceSec=409.000,oppositeThinning=0.502,voidScore=0.289} | trigger@2026-04-01T01:34:36.000Z{breakPct=0.073,flowMultiplier=2.233,sideFlowOK=true,triggerPrice=67920.050,targetPrice=66561.649} | expire@2026-04-02T01:34:36.000Z{allHorizonsFailed=true,targetPrice=66561.649}

### BTCUSDT-SHORT-1775008141000-18

- Date: 2026-04-01, direction SHORT, type DISTRIBUTION, final status `RESOLVED_FAILED`
- Trigger time: 2026-04-01T02:29:16.000Z, trigger price: 67595.45, target price: 66243.54
- Scores at trigger: absorption=0.601, void=0.174, trigger=0.966, refill=0.503
- Horizons: 4h=failed_by_timeout, 8h=failed_by_timeout, 24h=failed_by_timeout
- MFE %: 0.090, MAE %: 2.504, t→target min: -
- Reason chain: candidate@2026-04-01T01:49:01.000Z{buyPressure=0.556,askRefillScore=0.498,upMovePct=0.000,absorbScore=0.611,rangeCompression=true} | confirmed@2026-04-01T01:52:39.000Z{cyclesSeen=48.000,ageMin=3.633,defendedPersistenceSec=218.000,oppositeThinning=0.499,voidScore=0.174} | trigger@2026-04-01T02:29:16.000Z{breakPct=0.324,flowMultiplier=1.403,sideFlowOK=true,triggerPrice=67595.450,targetPrice=66243.541} | expire@2026-04-02T02:29:16.000Z{allHorizonsFailed=true,targetPrice=66243.541}

### BTCUSDT-LONG-1775010708000-19

- Date: 2026-04-01, direction LONG, type ACCUMULATION, final status `RESOLVED_FAILED`
- Trigger time: 2026-04-01T03:10:28.000Z, trigger price: 68009.45, target price: 69369.64
- Scores at trigger: absorption=0.607, void=0.059, trigger=0.970, refill=0.499
- Horizons: 4h=failed_by_timeout, 8h=failed_by_timeout, 24h=failed_by_timeout
- MFE %: 1.880, MAE %: 0.201, t→target min: -
- Reason chain: candidate@2026-04-01T02:31:48.000Z{sellPressure=0.602,bidRefillScore=0.499,downMovePct=0.000,absorbScore=0.662,rangeCompression=true} | confirmed@2026-04-01T02:34:48.000Z{cyclesSeen=132.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.501,voidScore=0.059} | trigger@2026-04-01T03:10:28.000Z{breakPct=0.452,flowMultiplier=1.404,sideFlowOK=true,triggerPrice=68009.450,targetPrice=69369.639} | expire@2026-04-02T03:10:28.000Z{allHorizonsFailed=true,targetPrice=69369.639}

### BTCUSDT-LONG-1775002106000-15

- Date: 2026-04-01, direction LONG, type ACCUMULATION, final status `RESOLVED_FAILED`
- Trigger time: 2026-04-01T00:51:04.000Z, trigger price: 68239.50, target price: 69604.29
- Scores at trigger: absorption=0.631, void=0.000, trigger=1.000, refill=0.513
- Horizons: 4h=failed_by_timeout, 8h=failed_by_timeout, 24h=failed_by_timeout
- MFE %: 1.537, MAE %: 1.033, t→target min: -
- Reason chain: candidate@2026-04-01T00:08:26.000Z{sellPressure=0.559,bidRefillScore=0.512,downMovePct=0.000,absorbScore=0.615,rangeCompression=true} | confirmed@2026-04-01T00:15:49.000Z{cyclesSeen=60.000,ageMin=7.383,defendedPersistenceSec=443.000,oppositeThinning=0.497,voidScore=0.000} | trigger@2026-04-01T00:51:04.000Z{breakPct=0.055,flowMultiplier=2.212,sideFlowOK=true,triggerPrice=68239.500,targetPrice=69604.290} | expire@2026-04-02T00:51:04.000Z{allHorizonsFailed=true,targetPrice=69604.290}

### BTCUSDT-LONG-1775013375000-22

- Date: 2026-04-01, direction LONG, type ACCUMULATION, final status `RESOLVED_FAILED`
- Trigger time: 2026-04-01T03:45:52.000Z, trigger price: 68101.60, target price: 69463.63
- Scores at trigger: absorption=0.658, void=0.000, trigger=0.996, refill=0.495
- Horizons: 4h=failed_by_timeout, 8h=failed_by_timeout, 24h=failed_by_timeout
- MFE %: 1.742, MAE %: 0.320, t→target min: -
- Reason chain: candidate@2026-04-01T03:16:15.000Z{sellPressure=0.568,bidRefillScore=0.503,downMovePct=0.000,absorbScore=0.625,rangeCompression=true} | confirmed@2026-04-01T03:23:43.000Z{cyclesSeen=44.000,ageMin=7.467,defendedPersistenceSec=448.000,oppositeThinning=0.512,voidScore=0.000} | trigger@2026-04-01T03:45:52.000Z{breakPct=0.129,flowMultiplier=1.453,sideFlowOK=true,triggerPrice=68101.600,targetPrice=69463.632} | expire@2026-04-02T03:45:52.000Z{allHorizonsFailed=true,targetPrice=69463.632}


## 5. Failed zones analysis

Failed-or-unfinished zones: **21** out of 23 total.

Breakdown by status:

- `RESOLVED_FAILED`: 7
- `NO_TRIGGER`: 7
- `INVALIDATED`: 5
- `EXPIRED`: 2

### Where they broke

- Never reached the trigger stage: 9 zones
- Below `minLiquidityVoidScore` (0.55) at confirmation: 20 zones
- Below `minAbsorptionScore` (0.60) at confirmation: 0 zones
- Carried at least one data-quality flag: 0 zones

Sample of up to 10 failed zones with their full reason chain:

- `BTCUSDT-LONG-1767225631000-1` (2026-01-01, LONG, RESOLVED_FAILED): candidate@2026-01-01T00:00:31.000Z{sellPressure=0.761,bidRefillScore=0.684,downMovePct=0.005,absorbScore=0.667,rangeCompression=true} | confirmed@2026-01-01T00:03:31.000Z{cyclesSeen=182.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.476,voidScore=0.702} | trigger@2026-01-01T00:05:15.000Z{breakPct=0.068,flowMultiplier=1.866,sideFlowOK=true,triggerPrice=87719.450,targetPrice=89473.839} | expire@2026-01-02T00:05:15.000Z{allHorizonsFailed=true,targetPrice=89473.839}
- `BTCUSDT-SHORT-1767226228000-2` (2026-01-01, SHORT, NO_TRIGGER): candidate@2026-01-01T00:10:28.000Z{buyPressure=0.585,askRefillScore=0.529,upMovePct=0.000,absorbScore=0.643,rangeCompression=true} | confirmed@2026-01-01T00:13:28.000Z{cyclesSeen=81.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.490,voidScore=0.298} | expire@2026-01-01T23:59:59.948Z{reason=End of replay; no trigger seen}
- `BTCUSDT-LONG-1767227473000-3` (2026-01-01, LONG, RESOLVED_FAILED): candidate@2026-01-01T00:31:13.000Z{sellPressure=0.560,bidRefillScore=0.502,downMovePct=0.000,absorbScore=0.616,rangeCompression=true} | confirmed@2026-01-01T00:54:33.000Z{cyclesSeen=84.000,ageMin=23.333,defendedPersistenceSec=1400.000,oppositeThinning=0.495,voidScore=0.467} | trigger@2026-01-01T01:07:04.000Z{breakPct=0.050,flowMultiplier=1.425,sideFlowOK=true,triggerPrice=87843.950,targetPrice=89600.829} | expire@2026-01-02T01:07:04.000Z{allHorizonsFailed=true,targetPrice=89600.829}
- `BTCUSDT-LONG-1767230525000-4` (2026-01-01, LONG, NO_TRIGGER): candidate@2026-01-01T01:22:05.000Z{sellPressure=0.781,bidRefillScore=0.505,downMovePct=0.004,absorbScore=0.715,rangeCompression=true} | confirmed@2026-01-01T01:25:05.000Z{cyclesSeen=63.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.500,voidScore=0.406} | expire@2026-01-01T23:59:59.948Z{reason=End of replay; no trigger seen}
- `BTCUSDT-LONG-1769908353000-6` (2026-02-01, LONG, NO_TRIGGER): candidate@2026-02-01T01:12:33.000Z{sellPressure=0.580,bidRefillScore=0.499,downMovePct=0.000,absorbScore=0.638,rangeCompression=true} | confirmed@2026-02-01T01:15:55.000Z{cyclesSeen=137.000,ageMin=3.367,defendedPersistenceSec=202.000,oppositeThinning=0.495,voidScore=0.262} | expire@2026-02-01T23:59:59.820Z{reason=End of replay; no trigger seen}
- `BTCUSDT-SHORT-1769911034000-7` (2026-02-01, SHORT, NO_TRIGGER): candidate@2026-02-01T01:57:14.000Z{buyPressure=0.575,askRefillScore=0.499,upMovePct=0.001,absorbScore=0.614,rangeCompression=true} | confirmed@2026-02-01T02:26:02.000Z{cyclesSeen=52.000,ageMin=28.800,defendedPersistenceSec=1728.000,oppositeThinning=0.502,voidScore=0.474} | expire@2026-02-01T23:59:59.820Z{reason=End of replay; no trigger seen}
- `BTCUSDT-LONG-1772323327000-9` (2026-03-01, LONG, INVALIDATED): candidate@2026-03-01T00:02:07.000Z{sellPressure=0.590,bidRefillScore=0.523,downMovePct=0.000,absorbScore=0.649,rangeCompression=true} | confirmed@2026-03-01T00:05:21.000Z{cyclesSeen=53.000,ageMin=3.233,defendedPersistenceSec=194.000,oppositeThinning=0.482,voidScore=0.394} | invalidate@2026-03-01T01:04:56.000Z{mid=66570.550,zoneLow=66909.379,zoneHigh=67066.550}
- `BTCUSDT-LONG-1772327160000-10` (2026-03-01, LONG, EXPIRED): candidate@2026-03-01T01:06:00.000Z{sellPressure=0.561,bidRefillScore=0.501,downMovePct=0.000,absorbScore=0.617,rangeCompression=true} | expire@2026-03-01T02:06:01.000Z{dwellMin=60.017,maxFormationDurationMin=60.000}
- `BTCUSDT-SHORT-1772327841000-11` (2026-03-01, SHORT, INVALIDATED): candidate@2026-03-01T01:17:21.000Z{buyPressure=0.553,askRefillScore=0.498,upMovePct=0.000,absorbScore=0.608,rangeCompression=true} | confirmed@2026-03-01T01:20:37.000Z{cyclesSeen=10.000,ageMin=3.267,defendedPersistenceSec=196.000,oppositeThinning=0.498,voidScore=0.391} | invalidate@2026-03-01T01:36:51.000Z{mid=66567.750,zoneLow=66039.750,zoneHigh=66234.950}
- `BTCUSDT-SHORT-1772329331000-12` (2026-03-01, SHORT, INVALIDATED): candidate@2026-03-01T01:42:11.000Z{buyPressure=0.552,askRefillScore=0.504,upMovePct=0.000,absorbScore=0.608,rangeCompression=true} | confirmed@2026-03-01T01:45:11.000Z{cyclesSeen=90.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.498,voidScore=0.287} | invalidate@2026-03-01T01:49:12.000Z{mid=67050.050,zoneLow=66578.050,zoneHigh=66711.050}


## 6. Strategy assessment

> **This is a compatibility and smoke-test run, not a proof of strategy profitability.**

**Pipeline (technical):** works — every day produced non-zero L2 and trade rows; the streaming reader, replay engine, feature engine, zone detector and target checker all completed without errors.

**Detector found zones?** yes — 23 zones across 4 days.

**Triggered zones?** yes — 9 triggered (39.13% of all zones).

**Reached the 2% target?** yes — at least one zone reached 2% within an horizon. Per-horizon counts: 4h=0, 8h=0, 24h=2.

### Hit rate vs baseline — honest reading

Aggregated **4h** unconditional baseline (24h horizon does not have enough forward samples in a single-day file): 2.81% up / 7.71% down → 10.52% combined.

Triggered-zone hit rate over the **24h horizon**: 22.22% (2 reached / 9 triggered).

**These two numbers are not directly comparable.** The triggered hit rate uses a 24h horizon; the baseline uses 4h windows. A 24h baseline would be substantially higher than the 4h baseline. With only 9 triggered zones, no statistical conclusion is possible either way — the result confirms the pipeline produces real numbers on real data, nothing more.

### Run caveats

- The strategy was run with `--max-l2-hours 4` for compute-budget reasons. Heavy L2 replay covers only the **first 4 hours UTC** of each day; the full 24h trade tape is retained for target checking. Zones can only be detected in the morning UTC slice.
- The strategy was run with `--skip-snapshots`, so no `snapshots_1s_d50.jsonl` was written. This is a diagnostic-only export; it does not affect zone detection.
- `derivative_ticker` and `book_ticker` files are present and validated, but the current strategy code does not consume them, so they were excluded from the replay merge.
- All thresholds in `config/strategy.default.json` were left **unchanged** — no tuning to fit the result.

### Which signals look useful

- The **absorption + bid/ask refill** combination did successfully form Confirmed zones on every valid day, which means the orderflow features are responsive on real Tardis data.
- The **liquidity void** score behaves as expected — it climbs when the far side of the book is thin, which the candidate gating relies on.

### Which signals look noisy

- **Range compression** is binary and depends on a 1-minute realised-range threshold. On choppy days many candidates either over- or under-fire on this gate; it will need calibration on a larger paid sample.
- **Trigger break + flow multiplier** (currently `zone.trigger.minBreakDistancePct=0.05`, `minAggressiveFlowMultiplier=1.4`) is the bottleneck: zones reach Confirmed but rarely break out with the required flow burst on these specific days.
- The **forced flow** signal from `liquidations` is collected but not yet gating zone state — its small file sizes on these days (~7-33 KB) suggest low signal-to-noise on Jan-Apr 2026 first-of-month days specifically.

### What cannot be claimed based on 4 days

- That the strategy "works" or "doesn't work". Four first-of-month days is not a representative sample of any market regime.
- Any winrate / Sharpe / drawdown number. The triggered-zone count is too small to support any rate estimate.
- That thresholds are correct or wrong. They have not been tuned on this sample, and they are intentionally untouched by this run.
- Anything about execution realism — there is no slippage, fee, latency or order-book impact modelling. This is a research module, not a trading bot.

## 7. Files generated

- `reports/tardis_validation_2026_ytd_except_may.md`
- `reports/tardis_validation_2026_ytd_except_may.json`
- `reports/sample_2026_ytd_except_may/summary.csv`
- `reports/sample_2026_ytd_except_may/summary.json`
- `reports/sample_2026_ytd_except_may/report.md`
- `reports/sample_2026_ytd_except_may/backtests/2026-01-01/zones.csv`
- `reports/sample_2026_ytd_except_may/backtests/2026-01-01/zones.json`
- `reports/sample_2026_ytd_except_may/backtests/2026-01-01/daily_summary.csv`
- `reports/sample_2026_ytd_except_may/backtests/2026-01-01/report.md`
- `reports/sample_2026_ytd_except_may/backtests/2026-01-01/chart_annotations.json`
- `reports/sample_2026_ytd_except_may/backtests/2026-01-01/config.echo.json`
- `reports/sample_2026_ytd_except_may/snapshots/2026-01-01/snapshots_1s_d50.jsonl`  *(missing)*
- `reports/sample_2026_ytd_except_may/backtests/2026-02-01/zones.csv`
- `reports/sample_2026_ytd_except_may/backtests/2026-02-01/zones.json`
- `reports/sample_2026_ytd_except_may/backtests/2026-02-01/daily_summary.csv`
- `reports/sample_2026_ytd_except_may/backtests/2026-02-01/report.md`
- `reports/sample_2026_ytd_except_may/backtests/2026-02-01/chart_annotations.json`
- `reports/sample_2026_ytd_except_may/backtests/2026-02-01/config.echo.json`
- `reports/sample_2026_ytd_except_may/snapshots/2026-02-01/snapshots_1s_d50.jsonl`  *(missing)*
- `reports/sample_2026_ytd_except_may/backtests/2026-03-01/zones.csv`
- `reports/sample_2026_ytd_except_may/backtests/2026-03-01/zones.json`
- `reports/sample_2026_ytd_except_may/backtests/2026-03-01/daily_summary.csv`
- `reports/sample_2026_ytd_except_may/backtests/2026-03-01/report.md`
- `reports/sample_2026_ytd_except_may/backtests/2026-03-01/chart_annotations.json`
- `reports/sample_2026_ytd_except_may/backtests/2026-03-01/config.echo.json`
- `reports/sample_2026_ytd_except_may/snapshots/2026-03-01/snapshots_1s_d50.jsonl`  *(missing)*
- `reports/sample_2026_ytd_except_may/backtests/2026-04-01/zones.csv`
- `reports/sample_2026_ytd_except_may/backtests/2026-04-01/zones.json`
- `reports/sample_2026_ytd_except_may/backtests/2026-04-01/daily_summary.csv`
- `reports/sample_2026_ytd_except_may/backtests/2026-04-01/report.md`
- `reports/sample_2026_ytd_except_may/backtests/2026-04-01/chart_annotations.json`
- `reports/sample_2026_ytd_except_may/backtests/2026-04-01/config.echo.json`
- `reports/sample_2026_ytd_except_may/snapshots/2026-04-01/snapshots_1s_d50.jsonl`  *(missing)*
- `reports/ORDERFLOW_STRATEGY_JAN_APR_2026_FINAL_REPORT.md` (this file)
- `reports/ORDERFLOW_STRATEGY_JAN_APR_2026_ZONES.csv` (consolidated zones)
