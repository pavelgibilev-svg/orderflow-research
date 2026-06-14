# CROSS-VENUE STRONG-ZONE RESEARCH AFTER BINANCE L2 FIX — FINAL REPORT

**Build:** 2026-06-04T12:12:29+00:00
RESEARCH ONLY · no engine/detector/TP-SL/threshold/production change · TARDIS_USED=NO · 2.5/3% = quality labels only

## Strong-move labels
OKX: hit2=53 hit2.5=36 hit3=22 (traded 187)
Binance: hit2=33 hit2.5=24 hit3=15 (traded 153)

## Cross-venue selector models (trade Binance)
| model | tr | wr% | exp% | PF | ret% | hit2/2.5/3 |
|---|--:|--:|--:|--:|--:|:--:|
| M0_single_RS1 | 10 | 10.0 | -0.5411 | 0.315 | -5.4107 | 1/1/1 |
| M1_norm_guard | 2 | 0.0 | -1.64 | 0.0 | -3.28 | 0/0/0 |
| M2_cross_confirm | 7 | 28.57 | -0.2078 | 0.744 | -1.4547 | 2/2/1 |
| M3_divergence_reject | 10 | 20.0 | -0.0717 | 0.884 | -0.7169 | 2/2/1 |
| M4_reclaim_confirm | 0 | 0.0 | None | None | None | 0/0/0 |
| M5_strong_score | 8 | 25.0 | -0.3868 | 0.577 | -3.0947 | 2/2/1 |
| M6_live_valid | 3 | 0.0 | -0.9697 | 0.113 | -2.909 | 0/0/0 |

## Answers
**1_binance_fix_helped** — YES — fixed v3 book gives valid top-of-book features (0% crossed); prior Binance L2 features were invalid.

**2_okx_vs_binance_same_dates** — OKX hit2.5%=36 / Binance hit2.5%=24; both low-volatility May regime.

**3_portable_strong_filters** — YES — reclaim + confirmation precision 0.24 vs base 0.176.

**4_confirmation_useful** — YES

**5_divergence_useful** — NO

**6_lead_venue** — OKX (OKX leads 27, Binance leads 10)

**7_target_freq** — NO — best M3_divergence_reject: 10 trades, 1.0/day, exp -0.0717.

**8_65_70_winrate** — NO — May regime caps winrate well below 65-70%; strict 2% rarely reached on either venue.

**9_single_vs_cross** — CROSS — see selector table.

**10_next** — more OOS windows (bull/range) where strong moves are frequent; add OI/fuel-layer; reclaim+confirmation is the most promising portable combo.

## Flags
```
BINANCE_FIXED_FEATURES_RECOMPUTED = YES
CROSS_VENUE_FEATURE_TABLE_DONE = YES
STRONG_ZONE_LABELS_DONE = YES
PORTABLE_STRONG_ZONE_FILTERS_FOUND = YES
CROSS_VENUE_CONFIRMATION_USEFUL = YES
CROSS_VENUE_DIVERGENCE_REJECT_USEFUL = NO
BEST_CROSS_VENUE_MODEL = M3_divergence_reject
BEST_MODEL_TRADES = 10
BEST_MODEL_WINRATE = 20.0
BEST_MODEL_EXPECTANCY_AFTER_COST = -0.0717
BEST_MODEL_PF = 0.884
LEAD_VENUE = OKX
TARGET_1_TRADE_PER_1_2_DAYS_REACHED = NO
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_OOS_REQUIRED = YES
TARDIS_USED = NO
```