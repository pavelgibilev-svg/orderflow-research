# TREND_DOWN SHORT-CONTINUATION DEEP DIVE — FINAL REPORT

**Build:** 2026-06-04T15:57:14+00:00
RESEARCH ONLY · no engine/detector/TP-SL change · TP=2% · 2.5/3%=quality · causal · no Tardis · no production

## Casebook (133 TREND_DOWN SHORT zones)
Classes: {'LOSS': 36, 'STRONG_3': 51, 'TIMEOUT_POS': 23, 'WIN_2': 5, 'STRONG_2_5': 10, 'TIMEOUT_NEG': 8}

## Entry-trigger selectors
| model | tr | wr% | exp% | PF | ret% | hit2.5 | FP removed |
|---|--:|--:|--:|--:|--:|--:|--:|
| M0_base_TD_short | 15 | 46.67 | 0.4749 | 2.014 | 7.1236 | 7 | 0 |
| M1_rejection | 14 | 57.14 | 0.4445 | 1.719 | 6.2231 | 7 | 29 |
| M2_taker_sell | 14 | 42.86 | 0.4509 | 1.909 | 6.3132 | 6 | 25 |
| M3_microprice_down | 15 | 53.33 | 0.5275 | 2.13 | 7.9119 | 7 | 8 |
| M4_thin_path | 11 | 54.55 | 0.8093 | 3.628 | 8.9023 | 6 | 16 |
| M5_confluence_2of4 | 15 | 46.67 | 0.4749 | 2.014 | 7.1236 | 7 | 8 |
| M6_confluence_3of5 | 15 | 46.67 | 0.4749 | 2.014 | 7.1236 | 7 | 9 |
| M7_live_valid_2of4_cooldown | 26 | 50.0 | 0.5407 | 2.129 | 14.0588 | 13 | 8 |

## Stop analysis (40 losses)
Causes: {'no_rejection_proof': 15, 'buyer_absorption': 13, 'clean_loss': 10, 'overextended_bounce': 2} · pre-signal avoidable: 28/40

## Answers
**1_can_reach_60_70** — NO — best filter M4_thin_path: wr 54.55% PF 3.628 (n=11). Base TD-short wr 46.67%.

**2_filters_removing_bad_shorts** — buyer-absorption (eng_ofi>0 / taker buy) and no-rejection-proof — see stop analysis + WIN-vs-NOISE separation.

**3_filters_for_strong_2_5_3** — top STRONG-vs-WEAK separators (Cohen d): [('prior_move_60m_pct', -1.742), ('dist_to_recent_swing_high_pct', 1.008), ('supportive_taker_imb_15m', 0.686), ('taker_imbalance_15m', -0.686)].

**4_frequency** — best M4_thin_path: 0.73/day, 4 no-trade days.

**5_setup_module** — YES_CANDIDATE — TD-short is the only PF>1.5 regime setup; gate it behind a TREND_DOWN regime detector.

**6_live_observer** — needs: causal 1d-trend regime detector + reclaim/rejection + taker-sell + thin-bid-path; log as shadow only.

**7_next_cross_venue** — validate TD-short + cross-venue SELL-pressure confirmation on NEW overlapping OKX+Binance down-trend windows.

## Flags
```
TD_SHORT_DEEPDIVE_DONE = YES
TD_SHORT_ZONES = 133
BASE_TD_SHORT = 15tr wr 46.67% PF 2.014
BEST_FILTER_MODEL = M4_thin_path
BEST_FILTER_TRADES = 11
BEST_FILTER_WINRATE = 54.55
BEST_FILTER_PF = 3.628
BEST_FILTER_EXPECTANCY = 0.8093
CAN_REACH_60_70_WINRATE = NO
PRE_SIGNAL_AVOIDABLE_LOSSES = 28/40
USABLE_AS_SETUP_MODULE = YES_CANDIDATE
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_OOS_REQUIRED = YES
TARDIS_USED = NO
```