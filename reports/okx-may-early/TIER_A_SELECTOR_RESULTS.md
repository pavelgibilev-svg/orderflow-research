# TIER-A HIGH-CONFIDENCE SELECTOR (OKX 05-03..20 unique moves)

## ⚠️ IN-SAMPLE TIER-A DEMO — NOT PRODUCTION VALIDATION

**Build:** 2026-06-06T17:37:33+00:00
Unique strong moves: 8 · unique hit2 moves: 19. One trade per move (deduped). TP=2%.

## E. Tier-A rule results
| rule | uniq | W/L/TO | wr% | PF | exp% | hit2.5 | maxLS | days | caveat |
|---|--:|:--:|--:|--:|--:|--:|--:|--:|---|
| T6_strict_5of7 | 24 | 7/6/11 | 29.17 | 1.227 | 0.1163 | 3 | 4 | 11 | IN-SAMPLE TIER-A DEMO, NOT PRODUCTION VALIDATION |
| T4_absorption | 33 | 9/12/12 | 27.27 | 0.967 | -0.021 | 5 | 3 | 17 | IN-SAMPLE TIER-A DEMO, NOT PRODUCTION VALIDATION |
| T1_edge_reclaim | 34 | 8/12/14 | 23.53 | 0.781 | -0.1462 | 4 | 3 | 15 | IN-SAMPLE TIER-A DEMO, NOT PRODUCTION VALIDATION |
| T6_strict_4of7 | 75 | 16/30/29 | 21.33 | 0.674 | -0.2427 | 8 | 6 | 17 | IN-SAMPLE TIER-A DEMO, NOT PRODUCTION VALIDATION |
| T6_strict_3of7 | 105 | 21/38/46 | 20.0 | 0.712 | -0.204 | 10 | 7 | 18 | IN-SAMPLE TIER-A DEMO, NOT PRODUCTION VALIDATION |
| T6_strict_2of7 | 111 | 22/38/51 | 19.82 | 0.76 | -0.1599 | 11 | 6 | 18 | IN-SAMPLE TIER-A DEMO, NOT PRODUCTION VALIDATION |
| T2_sweep_reversal | 23 | 4/8/11 | 17.39 | 0.545 | -0.3352 | 1 | 4 | 15 | IN-SAMPLE TIER-A DEMO, NOT PRODUCTION VALIDATION |
| T3_thin_path | 0 | 0/0/0 | 0.0 | None | None | 0 | 0 | 0 | IN-SAMPLE TIER-A DEMO, NOT PRODUCTION VALIDATION — n too small |
| T5_confluence | 0 | 0/0/0 | 0.0 | None | None | 0 | 0 | 0 | IN-SAMPLE TIER-A DEMO, NOT PRODUCTION VALIDATION — n too small |

## Best rule: T6_strict_5of7 — exact unique trades
| date | dir | family | result | pnl | MFE | strong |
|---|:--:|:--:|:--:|--:|--:|:--:|
| 2026-05-04 | SHORT | FALSE_BREAKOUT_RECLAIM | WIN | 1.86 | 2.417 | 0 |
| 2026-05-04 | LONG | LIQUIDITY_SWEEP_REVERSAL | WIN | 1.86 | 3.07 | 1 |
| 2026-05-05 | LONG | LIQUIDITY_SWEEP_REVERSAL | WIN | 1.86 | 2.381 | 0 |
| 2026-05-05 | SHORT | LIQUIDITY_SWEEP_REVERSAL | TIMEOUT | -0.9375 | 0.46 | 0 |
| 2026-05-05 | SHORT | LIQUIDITY_SWEEP_REVERSAL | TIMEOUT | -0.564 | 0.49 | 0 |
| 2026-05-05 | SHORT | FALSE_BREAKOUT_RECLAIM | LOSS | -1.64 | 0.99 | 0 |
| 2026-05-06 | SHORT | LIQUIDITY_SWEEP_REVERSAL | LOSS | -1.64 | 0.866 | 0 |
| 2026-05-06 | SHORT | RANGE_FADE_HIGH_TO_LOW | TIMEOUT | 1.73 | 1.896 | 0 |
| 2026-05-07 | LONG | LIQUIDITY_SWEEP_REVERSAL | LOSS | -1.64 | 0.427 | 0 |
| 2026-05-07 | LONG | FALSE_BREAKOUT_RECLAIM | TIMEOUT | -0.3032 | 0.754 | 0 |
| 2026-05-08 | SHORT | RANGE_FADE_HIGH_TO_LOW | TIMEOUT | -0.2396 | 1.114 | 0 |
| 2026-05-10 | LONG | RANGE_FADE_LOW_TO_HIGH | WIN | 1.86 | 2.301 | 0 |
| 2026-05-10 | SHORT | RANGE_FADE_HIGH_TO_LOW | TIMEOUT | -0.1584 | 1.326 | 0 |
| 2026-05-11 | SHORT | LIQUIDITY_SWEEP_REVERSAL | TIMEOUT | 0.0646 | 0.758 | 0 |
| 2026-05-12 | LONG | RANGE_FADE_LOW_TO_HIGH | TIMEOUT | 0.0538 | 0.819 | 0 |
| 2026-05-12 | LONG | LIQUIDITY_SWEEP_REVERSAL | LOSS | -1.64 | 0.844 | 0 |
| 2026-05-13 | LONG | RANGE_FADE_LOW_TO_HIGH | LOSS | -1.64 | 1.094 | 0 |
| 2026-05-13 | SHORT | RANGE_FADE_HIGH_TO_LOW | WIN | 1.86 | 2.612 | 1 |
| 2026-05-13 | SHORT | RANGE_FADE_HIGH_TO_LOW | WIN | 1.86 | 3.019 | 1 |
| 2026-05-13 | LONG | LIQUIDITY_SWEEP_REVERSAL | TIMEOUT | 0.2156 | 0.412 | 0 |
| 2026-05-14 | SHORT | RANGE_FADE_HIGH_TO_LOW | LOSS | -1.64 | 0.591 | 0 |
| 2026-05-18 | LONG | RANGE_FADE_LOW_TO_HIGH | TIMEOUT | -0.2529 | 0.834 | 0 |
| 2026-05-18 | LONG | LIQUIDITY_SWEEP_REVERSAL | TIMEOUT | 0.002 | 1.201 | 0 |
| 2026-05-18 | SHORT | LIQUIDITY_SWEEP_REVERSAL | WIN | 1.86 | 2.004 | 0 |

## D. Anti-overfit
- full: 29.17% (n=24)
- train 03-11: 28.57% (n=14) | test 12-20: 30.0% (n=10)
- without 05-14: 30.43% (n=23)
- without 05-15: 29.17% (n=24)
- without both: 30.43% (n=23)
- **RESULT_DEPENDS_ON_05_14_05_15 = NO**

## Diagnostic — why winrate is low (SELECTION, not timing)
- All 8 unique strong moves WIN TP2 from their first zone: 8W/0L/0TO = **100.0%**.
- So the ceiling exists; the problem is that no causal rule separates those 8 winners from the ~100 look-alike losers that also pass.

## F. Answers
**1_can_reach_70_80** — NO — best rule T6_strict_5of7: 29.17% on 24 unique alerts.
**2_unique_trades** — 24 unique trades (deduped, one per move).
**3_live_or_hindsight** — It is a SELECTION (precision) problem, not timing/hindsight: all 8 strong moves WIN TP2 from their first zone (100.0%), but no causal rule isolates them from look-alike losers.
**4_exact_rules** — T6_strict_5of7 = >=5 of {edge,sweep,reclaim,no_wall,microprice,taker/ofi,low_entropy}
**5_holds_without_1415** — depends_on_05_14_05_15 = NO; without both -> 30.43% on 23 alerts (stably low, not driven by those days).
**6_can_formalize_shadow** — NO as a winrate edge — best is ~29%. Only worth a shadow logger to KEEP COLLECTING the rare strong moves, not as a Tier-A trade trigger.
**7_oos_needs** — new OKX(+Binance) windows with >=15-20 unique strong moves; a feature with real ex-ante separation power (current microstructure set does not separate the 8 winners); freeze any rule, no re-tuning.

## Flags
```
TIER_A_SEARCH_DONE = YES
TIER_A_70_80_FOUND = NO
BEST_TIER_A_RULE = T6_strict_5of7
BEST_TIER_A_UNIQUE_ALERTS = 24
BEST_TIER_A_WINRATE = 29.17
BEST_TIER_A_PF = 1.227
BEST_TIER_A_HINDSIGHT_RISK = MED
RESULT_DEPENDS_ON_05_14_05_15 = NO
N_UNIQUE_STRONG_MOVES = 8
N_UNIQUE_HIT2_MOVES = 19
READY_FOR_TIER_A_SHADOW = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_OOS_REQUIRED = YES
IN_SAMPLE_DEMO_ONLY = YES
TARDIS_USED = NO
```