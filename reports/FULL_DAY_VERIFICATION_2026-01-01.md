# Full-Day Verification — BTCUSDT 2026-01-01

> **This is a full-day technical verification run, not a proof of strategy profitability.**

Second full-day verification, picked deliberately to contrast with the regime of 2026-02-01.

- Generated: 2026-05-08T18:47:25.590Z

## 0. Day regime selection

| Date | First | Last | High | Low | Return % | Range % | Regime | Used in this report |
|---|---|---|---|---|---|---|---|---|
| 2026-01-01 | 87608.30 | 88800.00 | 88881.40 | 87508.40 | +1.36% | 1.57% | choppy | **target** |
| 2026-02-01 | 78706.70 | 76931.50 | 79396.80 | 75644.00 | -2.26% | 4.96% | bearish | **reference** |
| 2026-03-01 | 66937.00 | 65750.00 | 68189.00 | 65011.00 | -1.77% | 4.89% | bearish |  |
| 2026-04-01 | 68241.40 | 68086.50 | 69288.00 | 67534.90 | -0.23% | 2.60% | choppy |  |

Selection rationale: the spec asks for the day "**maximally different from 2026-02-01**", preferably bullish, otherwise the most choppy/flat. Among the four downloaded days, none has a pronounced bullish move (>= 1.5% net return) — `2026-01-01` (choppy, return 1.36%, range 1.57%) is the closest to bullish (mild up-drift) AND has a very different volatility profile from `2026-02-01` (bearish, return -2.26%, range 4.96%). It is the most contrasting day available.

## 1. Run conditions

| Setting | Value |
|---|---|
| Date | 2026-01-01 |
| Symbol | BTCUSDT |
| Exchange | binance-futures |
| Target percent | 2.0 |
| Horizons | 4h, 8h, 24h |
| Files used | incremental_book_L2, trades, liquidations (derivative_ticker / book_ticker present but not consumed by strategy) |
| L2 time limitation | **NO** — full 24h L2 replay (no `--max-l2-hours`) |
| Skip-snapshots used | yes |
| Config file | `config/strategy.default.json` (unchanged from canonical defaults) |
| Threshold tuning | **NONE** — no values in `config/strategy.default.json` were modified |
| targetPct | 2 |
| featureIntervalSec | 1 |
| zone.minAbsorptionScore | 0.6 |
| zone.minLiquidityVoidScore | 0.55 |
| zone.trigger.minBreakDistancePct | 0.05 |
| zone.trigger.minAggressiveFlowMultiplier | 1.4 |

## 2. Data validation

| File type | Present | Size | Rows parsed (first 1000) | Required/Optional | Validation status |
|---|---|---|---|---|---|

## 3. Full-day strategy summary

| Metric | Value |
|---|---|
| L2 events processed | 62 609 291 |
| Trades scanned | 1 056 983 |
| Zones found (total) | 10 |
| LONG zones | 5 |
| SHORT zones | 5 |
| Confirmed zones | 9 |
| Triggered zones | 6 |
| Reached 2% within 4h | 0 |
| Reached 2% within 8h | 0 |
| Reached 2% within 24h | 0 |
| Reached 2% LONG / SHORT | 0 / 0 |
| Failed (RESOLVED_FAILED) | 6 |
| No trigger (NO_TRIGGER) | 2 |
| Invalidated | 2 |
| Expired | 0 |
| Triggered hit rate 4h | 0.00% (0/6) |
| Triggered hit rate 8h | 0.00% (0/6) |
| Triggered hit rate 24h | 0.00% (0/6) |
| Unconditional baseline 4h | 0.00% up / 0.00% down (n=1200) |
| Unconditional baseline 8h | 0.00% up / 0.00% down (n=960) |
| Unconditional baseline 24h | 0.00% up / 0.00% down (n=0) |
| Quality flag ticks | 0 |

## 4. Comparison vs 2026-02-01 (bearish reference day)

| Metric | 2026-02-01 (bearish) | 2026-01-01 (choppy) |
|---|---|---|
| Day return | -2.26% | 1.36% |
| Day range | 4.96% | 1.57% |
| L2 events | 165 962 192 | 62 609 291 |
| Trades scanned | 6 759 515 | 1 056 983 |
| Zones found | 20 | 10 |
| LONG zones | 7 | 5 |
| SHORT zones | 13 | 5 |
| Triggered zones | 11 | 6 |
| Reached 4h | 0 | 0 |
| Reached 8h | 2 | 0 |
| Reached 24h | 6 | 0 |
| Reached LONG / SHORT | 0 / 6 | 0 / 0 |
| Triggered hit rate 24h | 54.55% (6/11) | 0.00% (0/6) |

### Direction-bias check

- 2026-02-01 (bearish, -2.26%): triggered LONG=2, SHORT=9; reached LONG=0, SHORT=6.
- 2026-01-01 (choppy, 1.36%): triggered LONG=4, SHORT=2; reached LONG=0, SHORT=0.

## 5. All zones

Total zones: **10** (every zone is included regardless of outcome).

| # | Dir | Type | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Reason chain |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | LONG | ACCUMULATION | RESOLVED_FAILED | 00:00:31 | 00:03:31 | 00:05:15 | 87560.05 | 87659.75 | 87719.45 | 89473.84 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.32 | 0.24 | - | candidate@00:00:31 → confirmed@00:03:31 → trigger@00:05:15 → expire@00:05:15 |
| 2 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 00:10:28 | 00:13:28 | 04:12:52 | 87690.58 | 87778.32 | 87645.85 | 85892.93 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.16 | 1.41 | - | candidate@00:10:28 → confirmed@00:13:28 → trigger@04:12:52 → expire@04:12:52 |
| 3 | LONG | ACCUMULATION | RESOLVED_FAILED | 00:31:13 | 00:54:33 | 01:07:04 | 87691.18 | 87799.95 | 87843.95 | 89600.83 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 1.18 | 0.38 | - | candidate@00:31:13 → confirmed@00:54:33 → trigger@01:07:04 → expire@01:07:04 |
| 4 | LONG | ACCUMULATION | RESOLVED_FAILED | 01:22:05 | 01:25:05 | 17:21:03 | 87882.39 | 87970.31 | 88187.45 | 89951.20 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.79 | 0.17 | - | candidate@01:22:05 → confirmed@01:25:05 → trigger@17:21:03 → expire@17:21:03 |
| 5 | SHORT | DISTRIBUTION | INVALIDATED | 04:23:33 | 04:29:11 | - | 87529.56 | 87667.95 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@04:23:33 → confirmed@04:29:11 → invalidate@17:20:47 |
| 6 | LONG | ACCUMULATION | RESOLVED_FAILED | 17:27:00 | 17:30:00 | 17:30:18 | 88133.06 | 88221.24 | 88285.65 | 90051.36 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.67 | 0.28 | - | candidate@17:27:00 → confirmed@17:30:00 → trigger@17:30:18 → expire@17:30:18 |
| 7 | LONG | ACCUMULATION | NO_TRIGGER | 17:38:55 | 17:49:05 | - | 88037.15 | 88881.35 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@17:38:55 → confirmed@17:49:05 → expire@23:59:59 |
| 8 | SHORT | DISTRIBUTION | RESOLVED_FAILED | 17:43:38 | 17:55:45 | 18:05:22 | 88282.45 | 88420.85 | 88229.75 | 86465.15 | failed_by_timeout | failed_by_timeout | failed_by_timeout | 0.22 | 0.74 | - | candidate@17:43:38 → confirmed@17:55:45 → trigger@18:05:22 → expire@18:05:22 |
| 9 | SHORT | DISTRIBUTION | INVALIDATED | 18:12:06 | 18:40:21 | - | 88066.65 | 88228.84 | - | - | invalidated_before_trigger | invalidated_before_trigger | invalidated_before_trigger | - | - | - | candidate@18:12:06 → confirmed@18:40:21 → invalidate@23:00:19 |
| 10 | SHORT | DISTRIBUTION | NO_TRIGGER | 23:48:18 | - | - | 88710.85 | 88832.55 | - | - | no_trigger | no_trigger | no_trigger | - | - | - | candidate@23:48:18 → expire@23:59:59 |

## 6. Successful 2% zones

No zones reached the 2% target on 2026-01-01.

This is itself a meaningful finding: on a non-trending day with only 1.57% intraday range, hitting a ±2% target from any reference price is mathematically constrained — the price simply did not move 2% from many points in the day.

## 7. Failed zones analysis

Failed-or-unfinished zones: **10** of 10.

- `RESOLVED_FAILED`: 6
- `INVALIDATED`: 2
- `NO_TRIGGER`: 2

- Never reached the trigger stage: 4
- Triggered but failed by timeout (MFE didn't reach 2%): 6
- MFE < 2 % among failed zones: 6
- MAE > 1 % among failed zones: 1
- Below `minLiquidityVoidScore` (0.55) at confirmation: 9
- Below `minAbsorptionScore` (0.60) at confirmation: 0

Sample (up to 15) failed zones with reason chain:

- `BTCUSDT-LONG-1767225631000-1` (LONG, RESOLVED_FAILED, MFE=1.32%, MAE=0.24%): candidate@2026-01-01T00:00:31.000Z{sellPressure=0.761,bidRefillScore=0.684,downMovePct=0.005,absorbScore=0.667,rangeCompression=true} | confirmed@2026-01-01T00:03:31.000Z{cyclesSeen=182.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.476,voidScore=0.702} | trigger@2026-01-01T00:05:15.000Z{breakPct=0.068,flowMultiplier=1.866,sideFlowOK=true,triggerPrice=87719.450,targetPrice=89473.839} | expire@2026-01-02T00:05:15.000Z{allHorizonsFailed=true,targetPrice=89473.839}
- `BTCUSDT-SHORT-1767226228000-2` (SHORT, RESOLVED_FAILED, MFE=0.16%, MAE=1.41%): candidate@2026-01-01T00:10:28.000Z{buyPressure=0.585,askRefillScore=0.529,upMovePct=0.000,absorbScore=0.643,rangeCompression=true} | confirmed@2026-01-01T00:13:28.000Z{cyclesSeen=81.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.490,voidScore=0.298} | trigger@2026-01-01T04:12:52.000Z{breakPct=0.051,flowMultiplier=1.400,sideFlowOK=true,triggerPrice=87645.850,targetPrice=85892.933} | expire@2026-01-02T04:12:52.000Z{allHorizonsFailed=true,targetPrice=85892.933}
- `BTCUSDT-LONG-1767227473000-3` (LONG, RESOLVED_FAILED, MFE=1.18%, MAE=0.38%): candidate@2026-01-01T00:31:13.000Z{sellPressure=0.560,bidRefillScore=0.502,downMovePct=0.000,absorbScore=0.616,rangeCompression=true} | confirmed@2026-01-01T00:54:33.000Z{cyclesSeen=84.000,ageMin=23.333,defendedPersistenceSec=1400.000,oppositeThinning=0.495,voidScore=0.467} | trigger@2026-01-01T01:07:04.000Z{breakPct=0.050,flowMultiplier=1.425,sideFlowOK=true,triggerPrice=87843.950,targetPrice=89600.829} | expire@2026-01-02T01:07:04.000Z{allHorizonsFailed=true,targetPrice=89600.829}
- `BTCUSDT-LONG-1767230525000-4` (LONG, RESOLVED_FAILED, MFE=0.79%, MAE=0.17%): candidate@2026-01-01T01:22:05.000Z{sellPressure=0.781,bidRefillScore=0.505,downMovePct=0.004,absorbScore=0.715,rangeCompression=true} | confirmed@2026-01-01T01:25:05.000Z{cyclesSeen=63.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.500,voidScore=0.406} | trigger@2026-01-01T17:21:03.000Z{breakPct=0.247,flowMultiplier=1.417,sideFlowOK=true,triggerPrice=88187.450,targetPrice=89951.199} | expire@2026-01-02T17:21:03.000Z{allHorizonsFailed=true,targetPrice=89951.199}
- `BTCUSDT-SHORT-1767241413000-5` (SHORT, INVALIDATED, MFE=-%, MAE=-%): candidate@2026-01-01T04:23:33.000Z{buyPressure=0.559,askRefillScore=0.501,upMovePct=0.000,absorbScore=0.615,rangeCompression=true} | confirmed@2026-01-01T04:29:11.000Z{cyclesSeen=11.000,ageMin=5.633,defendedPersistenceSec=338.000,oppositeThinning=0.493,voidScore=0.303} | invalidate@2026-01-01T17:20:47.000Z{mid=88113.350,zoneLow=87529.563,zoneHigh=87667.950}
- `BTCUSDT-LONG-1767288420000-6` (LONG, RESOLVED_FAILED, MFE=0.67%, MAE=0.28%): candidate@2026-01-01T17:27:00.000Z{sellPressure=0.643,bidRefillScore=0.505,downMovePct=0.000,absorbScore=0.708,rangeCompression=true} | confirmed@2026-01-01T17:30:00.000Z{cyclesSeen=85.000,ageMin=3.000,defendedPersistenceSec=180.000,oppositeThinning=0.500,voidScore=0.132} | trigger@2026-01-01T17:30:18.000Z{breakPct=0.073,flowMultiplier=1.482,sideFlowOK=true,triggerPrice=88285.650,targetPrice=90051.363} | expire@2026-01-02T17:30:18.000Z{allHorizonsFailed=true,targetPrice=90051.363}
- `BTCUSDT-LONG-1767289135000-7` (LONG, NO_TRIGGER, MFE=-%, MAE=-%): candidate@2026-01-01T17:38:55.000Z{sellPressure=0.556,bidRefillScore=0.496,downMovePct=0.000,absorbScore=0.612,rangeCompression=true} | confirmed@2026-01-01T17:49:05.000Z{cyclesSeen=11.000,ageMin=10.167,defendedPersistenceSec=610.000,oppositeThinning=0.490,voidScore=0.021} | expire@2026-01-01T23:59:59.991Z{reason=End of replay; no trigger seen}
- `BTCUSDT-SHORT-1767289418000-8` (SHORT, RESOLVED_FAILED, MFE=0.22%, MAE=0.74%): candidate@2026-01-01T17:43:38.000Z{buyPressure=0.579,askRefillScore=0.503,upMovePct=0.000,absorbScore=0.637,rangeCompression=true} | confirmed@2026-01-01T17:55:45.000Z{cyclesSeen=10.000,ageMin=12.117,defendedPersistenceSec=727.000,oppositeThinning=0.501,voidScore=0.174} | trigger@2026-01-01T18:05:22.000Z{breakPct=0.060,flowMultiplier=1.484,sideFlowOK=true,triggerPrice=88229.750,targetPrice=86465.155} | expire@2026-01-02T18:05:22.000Z{allHorizonsFailed=true,targetPrice=86465.155}
- `BTCUSDT-SHORT-1767291126000-9` (SHORT, INVALIDATED, MFE=-%, MAE=-%): candidate@2026-01-01T18:12:06.000Z{buyPressure=0.555,askRefillScore=0.501,upMovePct=0.000,absorbScore=0.610,rangeCompression=true} | confirmed@2026-01-01T18:40:21.000Z{cyclesSeen=121.000,ageMin=28.250,defendedPersistenceSec=1695.000,oppositeThinning=0.503,voidScore=0.197} | invalidate@2026-01-01T23:00:19.000Z{mid=88677.750,zoneLow=88066.650,zoneHigh=88228.842}
- `BTCUSDT-SHORT-1767311298000-10` (SHORT, NO_TRIGGER, MFE=-%, MAE=-%): candidate@2026-01-01T23:48:18.000Z{buyPressure=0.588,askRefillScore=0.503,upMovePct=0.000,absorbScore=0.642,rangeCompression=true} | expire@2026-01-01T23:59:59.991Z{reason=End of replay; no trigger seen}

## 8. Strategy assessment — does the 2026-02-01 result hold across regimes?

> **This is a full-day technical verification run, not a proof of strategy profitability.**

**The central question:** is the strategy able to find ±2 % zones on a non-bearish day, or was the 2026-02-01 result a side-effect of a strongly directional bearish regime?

**Answer:** **NO zones reached the 2 % target on 2026-01-01** (a choppy day with 1.57% intraday range), while 2026-02-01 (a bearish day with 4.96% range) had 6 reached zones.

This is consistent with two non-exclusive explanations:
  1. The current strategy is **regime-dependent** — it works best when the market actually moves 2 % within a horizon. On a flat day, no signal can hit a 2 % target the price never reaches.
  2. The 2026-02-01 success was at least partly **a directional tailwind**: 13 of 20 zones were SHORT, all 6 successful zones were SHORT, in a -2.26 % bearish day. The strategy "rode the bias".

Both explanations are consistent with the data. Neither is proof.

### Direction split tells the same story

On 2026-02-01 (bearish): 7 LONG / 13 SHORT zones, 0 LONG reached / 6 SHORT reached.
On 2026-01-01 (choppy): 5 LONG / 5 SHORT zones, 0 LONG reached / 0 SHORT reached.

### Honest verdict

- **2026-02-01 result confirmed on another regime: NOT confirmed.** Hit rate dropped from 54.55% (bearish) to 0 % (choppy) on this single comparison.
- **Current strategy: very likely regime-dependent / directional.** It does fire signals across regimes (6 triggered on 2026-01-01 vs 11 on 2026-02-01), but on a flat / non-trending day the 2 % target is unreachable for most of the day's price walk.

### What should be tested next

1. A **paid Tardis subscription** for ≥ 1 calendar month at full-day resolution — every day, not just first-of-month boundaries.
2. **Conditional hit rate by regime:** classify each day by net return / range, then compute triggered hit rate within each bucket. This is the only way to disentangle "the strategy works" from "the day moved enough for any 2 % zone to win".
3. **Symmetric baseline comparison:** for each successful zone direction, compare its hit rate to the unconditional probability of price moving ±2 % in the matching horizon, computed on the SAME days. The current per-day baseline is computed on the full day's price walk and is not directly horizon-matched to triggered-zone hit rate.
4. **Drawdown + slippage realism:** add a simple fill model and an assumed maker-taker fee schedule before any "profitability" claim is made.
5. **Do not retune thresholds on this 2-day sample.** Two days is far too few to justify changing `config/strategy.default.json`.
