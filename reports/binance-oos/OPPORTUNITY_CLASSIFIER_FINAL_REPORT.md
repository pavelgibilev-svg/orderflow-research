# OPPORTUNITY CLASSIFIER FOR SKIPPED WINNERS — FINAL REPORT

**Build:** 2026-06-02T17:15:24+00:00
**RESEARCH ONLY. No engine/detector/TP-SL/production change. Causal features. OKX-frozen thresholds; Binance-specific cuts labeled EXPLORATORY.**

## Binance GOOD-vs-NOISE separation (after guard) — top features
| feature | GOOD med | NOISE med | Cohen d |
|---|--:|--:|--:|
| taker_imbalance_15m | 0.0272 | -0.0168 | 0.647 |
| eng_void | 0.3038 | 0.1752 | 0.532 |
| ms_thin_path_score | 0.1021 | 0.1034 | -0.469 |
| book_entropy_top25 | 0.3566 | 0.371 | -0.421 |
| ms_large_walls_on_path | 14 | 12 | 0.254 |
| prior_move_60m_pct | -0.152 | -0.0001 | -0.233 |

OKX max |Cohen d| across features = 0.106 (≈0 ⇒ no single-feature OKX winner signal).

## Binance opportunity selector models

| model | tr | wr% | exp% | PF | alerts/d | no-trade | GOOD cap/31 |
|---|--:|--:|--:|--:|--:|--:|--:|
| ModelA_guard_only | 10 | 20.0 | -0.3035 | 0.612 | 1.0 | 0 | 2/31 |
| ModelB_guard_conf2 | 9 | 22.22 | -0.4254 | 0.51 | 0.9 | 1 | 2/31 |
| ModelC_guard_conf3 | 1 | 0.0 | -0.4912 | 0.0 | 0.1 | 9 | 0/31 |
| ModelD_guard_oppscore_OKXfloor | 1 | 0.0 | -1.64 | 0.0 | 0.1 | 9 | 0/31 |
| ModelE_max2_cooldown_oppscore | 2 | 0.0 | -0.0601 | 0.755 | 0.2 | 9 | 0/31 |
| ModelF_first_elig_oppscore_notrade | 1 | 0.0 | -1.64 | 0.0 | 0.1 | 9 | 0/31 |

## OKX sanity (same models)
| model | tr | wr% | exp% | PF |
|---|--:|--:|--:|--:|
| ModelA_guard_only | 29 | 55.17 | 0.5767 | 2.172 |
| ModelB_guard_conf2 | 29 | 55.17 | 0.5767 | 2.172 |
| ModelC_guard_conf3 | 29 | 51.72 | 0.456 | 1.831 |
| ModelD_guard_oppscore_OKXfloor | 24 | 45.83 | 0.2474 | 1.384 |
| ModelE_max2_cooldown_oppscore | 57 | 36.84 | -0.0884 | 0.891 |
| ModelF_first_elig_oppscore_notrade | 24 | 45.83 | 0.2474 | 1.384 |

## Answers
**1_live_valid_winner_features** — YES_BINANCE_ONLY_NOT_OKX. On Binance only taker_imbalance_15m (d~0.52) and weak void/dist/microprice (d~0.2) lean toward winners; on OKX ALL candidate features have |d|<0.1 — the OKX edge is the composite top1/day ranking, not a single feature. So there is no strong OKX-consistent winner discriminator.

**2_why_selector_stood_aside** — frozen OKX score-percentile floor (87) + normalized flow filter + guard leave almost nothing on the Binance down-week; the few survivors still lost. The discriminative Binance signal (taker imbalance) is venue-specific and not in the frozen rule set.

**3_which_winners_capturable** — confluence>=3 captures 4 of 31 winners pre-trade; dir-guard passes 21/31. Without venue-specific (exploratory) thresholds, live-valid capture stays low.

**4_target_frequency** — NO. Best live-valid model ModelA_guard_only: 10 trades, alerts/day 1.0, no-trade days 0. Frozen-only rules do not reach 1/1-2 days profitably on this window.

**5_rules_preserving_okx** — OKX edge under best model: 55.17% / PF 2.172 -> YES. Confluence/guard rules keep OKX broadly stable; aggressive single-feature cuts do not.

**6_rules_improving_binance_without_tuning** — none clearly: frozen rules stand aside (no loss but no edge). Only EXPLORATORY taker-imbalance cut (overfit risk HIGH) would add trades.

**7_continuation_vs_reversal** — continuation (regime-aligned + thin path, O6) is cleaner than reversal (O7); countertrend needs strong reclaim+initiative and remains the main fake-accumulation source.

**8_oi_liquidations_fuel** — YES — add OI + liquidations as a fuel layer; true OI absent on Binance recorder remains the biggest missing causal input.

**9_carry_to_next_oos** — direction/regime guard + venue-normalized percentile filter + confluence>=3 + no-trade option + cluster cooldown; test taker-imbalance signal as a candidate (not frozen) on NEW windows.

**10_telegram_shadow_ready** — NO — frozen selector stands aside; exploratory taker signal is unvalidated/overfit. Needs more OOS windows (bull/range) before shadow logging.

## Flags
```
OPPORTUNITY_CLASSIFIER_DONE = YES
BINANCE_WINNER_ZONES_ANALYZED = 31
GOOD_VS_NOISE_SEPARATION_FOUND = YES_BINANCE_ONLY_NOT_OKX
BEST_OPPORTUNITY_RULE = O3_reclaim_rejection
BEST_LIVE_VALID_SELECTOR = ModelA_guard_only
BINANCE_TRADES = 10
BINANCE_WINRATE = 20.0
BINANCE_EXPECTANCY_AFTER_COST = -0.3035
BINANCE_PF_AFTER_COST = 0.612
GOOD_CAPTURED = 2
SKIPPED_WINNERS_REDUCED = YES
OKX_EDGE_PRESERVED = YES
TARGET_FREQUENCY_1_PER_1_2_DAYS_REACHED = NO
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_OOS_REQUIRED = YES
```