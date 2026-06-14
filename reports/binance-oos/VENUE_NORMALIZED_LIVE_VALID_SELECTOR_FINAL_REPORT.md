# VENUE-NORMALIZED LIVE-VALID SELECTOR — FINAL REPORT

**Build:** 2026-06-02T16:57:17+00:00
**RESEARCH ONLY. No engine/detector/TP-SL/production change. Thresholds frozen from OKX, never tuned on Binance. Causal features.**

## OKX sanity (normalization must not break OKX)
| ruleset | trades | wr% | exp% | PF | overlap |
|---|--:|--:|--:|--:|--:|
| frozen RS1 | 29 | 62.07 | 0.6475 | 2.258 | — |
| NRS1_A pctile | 29 | 55.17 | 0.4061 | 1.647 | 26 |
| NRS1_C pctile+floor | 24 | 50.0 | 0.249 | 1.361 | 21 |

**OKX_EDGE_PRESERVED = PARTIAL**

## Binance: old RS1 vs normalized selector models

| model | tr | wr% | exp% | PF | maxCL | wrongdir | alerts/d | no-trade days | fake-acc | GOOD skipped |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Model0_top1_day_RS1 | 10 | 10.0 | -0.5821 | 0.35 | 4 | 6 | 1.0 | 0 | 3 | 30 |
| Model1_norm_score_floor | 2 | 0.0 | -0.6886 | 0.16 | 1 | 1 | 0.2 | 8 | 0 | 31 |
| Model2_+dir_guard | 2 | 0.0 | -0.6886 | 0.16 | 1 | 1 | 0.2 | 8 | 0 | 31 |
| Model3_+noise | 0 | 0.0 | None | None | 0 | 0 | 0.0 | 10 | 0 | 31 |
| Model4_max2_cooldown_permissive | 1 | 0.0 | -1.64 | 0.0 | 1 | 1 | 0.1 | 9 | 0 | 31 |
| Model5_+no_trade_floor | 0 | 0.0 | None | None | 0 | 0 | 0.0 | 10 | 0 | 31 |

## Answers
**1_replaced_absolute_thresholds** — YES — absolute supp_opp_15m<=4497.76 replaced by OKX-derived pctile<=75 / z<=0.468; all features carry causal prior-normalized forms.

**2_okx_edge_preserved** — PARTIAL — frozen RS1 62.07%/PF2.258/exp0.6475 vs best normalized 55.17%/PF1.647/exp0.4061 (overlap 26/29). Normalized features stay clearly profitable on OKX (PF>1.5, +exp) but lose ~7pp winrate vs the OKX-fit absolute cut — expected (absolute was tuned in-sample on OKX).

**3_binance_improved** — NO net edge. old RS1 10.0%/exp-0.5821/PF0.35 (ret -5.82%) → live-valid Model5_+no_trade_floor: 0 trades, 10/10 no-trade days = STANDS ASIDE. It avoids the RS1 bleed (ret ~0 vs -5.82%) but does NOT recover winners. Deeper finding: after proper venue-normalization Binance zones STILL do not meet the OKX-grade quality profile, so it is NOT only a units artifact — the signal does not transfer on this hostile down-week (and n is small).

**4_fake_accumulation_reduced** — YES — fake-LONG in selection 3→0 (selector stands aside).

**5_direction_guard_helped** — OKX guard kept 37.11% (base 36.63%); Binance guard removed 40 fake-LONG, stops 22.

**6_noise_classifier_helped** — see D tables — strongest portable rules: R1/R3/R4 (regime/ofi/taker conflict).

**7_live_valid_freq** — best model alerts/day 0.0 (~1 per 100.0 days), 10 no-trade days of 10.

**8_no_trade_days** — 10 of 10 Binance days; OKX best 0 of 29.

**9_oi_needed** — YES — true OI still absent on Binance recorder; fuel-layer (S7) remains PARTIAL until native OI is recorded.

**10_next** — re-test normalized selector on NEW Binance/OKX windows incl. bull & range regimes; add OI fuel; keep production frozen.

## Flags
```
VENUE_NORMALIZED_RESEARCH_DONE = YES
OKX_SANITY_DONE = YES
OKX_EDGE_PRESERVED = PARTIAL
BINANCE_10D_RETEST_DONE = YES
BINANCE_NORMALIZED_SELECTOR_TRADES = 0
BINANCE_NORMALIZED_SELECTOR_WINRATE = 0.0
BINANCE_NORMALIZED_SELECTOR_EXPECTANCY_AFTER_COST = None
BINANCE_NORMALIZED_SELECTOR_PF_AFTER_COST = None
FAKE_ACCUMULATION_REDUCED = YES
WRONG_DIRECTION_REDUCED = YES
SKIPPED_WINNERS_REDUCED = NO
LIVE_VALID_SELECTOR_READY_FOR_SHADOW_RESEARCH = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_OOS_REQUIRED = YES
VENUE_NORMALIZED_FEATURES_BUILT = YES
TOP1_DAY_REPLACED = YES
NO_TRADE_OPTION_ENABLED = YES
CLUSTER_COOLDOWN_USED = YES
BINANCE_NORMALIZED_SELECTOR_BEHAVIOR = STANDS_ASIDE_AVOIDS_LOSS
BINANCE_NORMALIZED_SELECTOR_IMPROVES_OLD_RS1 = YES_AVOIDS_LOSS
```