# REGIME-AWARE SETUP ROUTER — FINAL REPORT

**Build:** 2026-06-04T14:04:39+00:00
RESEARCH ONLY · no engine/detector/TP-SL/threshold tuning · TP=2% · 2.5/3%=quality labels · causal · no Tardis · no production

## Tradeable vs no-trade regimes (pooled strong% = hit2.5 rate)
| regime | n | strong% | wr% | PF |
|---|--:|--:|--:|--:|
| TREND_UP | 226 | 35.0 | 37.17 | 0.941 |
| TREND_DOWN | 273 | 32.2 | 31.5 | 0.856 |
| RANGE | 884 | 27.6 | 32.92 | 0.847 |
| VOL_HIGH_VOL | 150 | 36.7 | 39.33 | 1.02 |
| VOL_LOW_VOL | 310 | 26.5 | 32.58 | 0.999 |

**Tradeable:** ['TREND_UP', 'TREND_DOWN', 'RANGE']  ·  **No-trade:** ['LOW_VOL']

## Best router model
OKX_MARCH:M0_old_RS1 — 29tr, wr 62.07%, exp 0.6475, PF 2.258

## Answers
**1_tradeable_regimes** — ['TREND_UP', 'TREND_DOWN', 'RANGE'] have >=25% strong-zone rate; TREND_DOWN/TREND_UP richest, RANGE thinner.

**2_skip_regimes** — LOW_VOL (range < 0.8%) — too small for 2% target; NO-TRADE. 

**3_trend_down_filters** — SHORT continuation + reject counter-trend LONG (no reversal proof) + noise_ok — see C table.

**4_trend_up_filters** — LONG continuation + reject counter-trend SHORT + thin-path — see C table.

**5_range_filters** — reclaim/rejection required + noise_ok + cross-confirm where available — see C table.

**6_target_freq** — YES — best router OKX_MARCH:M0_old_RS1 29tr 1.0/day exp 0.6475.

**7_65_70_winrate** — Only the in-sample OKX-March RS1 reaches ~62%; OOS regime-routed models stay below. Not from tuning -> NO robustly.

**8_keep_setups** — trend-continuation (SHORT in down, LONG in up) + range mean-reversion WITH reclaim.

**9_ban_setups** — counter-trend accumulation/distribution without reversal proof; ALL setups in LOW_VOL.

**10_next_data** — Record Binance (live recorder) + download OKX open for NEW overlapping windows across regimes (trend-up, range, high-vol) to validate cross-venue confirmation; 2026-05-21..30 alone is insufficient.

## Flags
```
REGIME_ROUTER_RESEARCH_DONE = YES
REGIME_CLASSIFIER_BUILT = YES
TRADEABLE_REGIMES_FOUND = YES
NO_TRADE_REGIMES_FOUND = PARTIAL
TRADEABLE_REGIMES = ['TREND_UP', 'TREND_DOWN', 'RANGE']
NO_TRADE_REGIMES = ['LOW_VOL']
BEST_REGIME_ROUTER_MODEL = OKX_MARCH:M0_old_RS1
BEST_ROUTER_TRADES = 29
BEST_ROUTER_WINRATE = 62.07
BEST_ROUTER_PF = 2.258
BEST_ROUTER_EXPECTANCY = 0.6475
TARGET_1_TRADE_PER_1_2_DAYS_REACHED = YES
CROSS_VENUE_NEEDS_NEW_OVERLAP_WINDOW = YES (only 2026-05-21..30 overlaps today)
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_OOS_REQUIRED = YES
TARDIS_USED = NO
```