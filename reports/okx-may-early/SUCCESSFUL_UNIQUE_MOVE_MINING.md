# SUCCESSFUL UNIQUE MOVE FILTER MINING (OKX 05-03..20)

## ⚠️ IN-SAMPLE RESEARCH — NOT PRODUCTION VALIDATION

**Build:** 2026-06-06T17:44:14+00:00 · unique strong moves 8 · unique hit2 moves 19 · noise candidates 99
N/A features (not in cache): prior_move_30m (not in cache), local_uniqueness_percentile (None in cache), flip_count (not in cache)

## B. Positive feature ranking (hit2 unique vs noise)
| feature | win median | noise median | Cohen d | r | best prec | recall | n+ / n- |
|---|--:|--:|--:|--:|--:|--:|:--:|
| prior_move_1d | 0.5969 | -0.0222 | 0.59 | 0.215 | 0.31 | 0.474 | 19/99 |
| wall_persistence_sec | 283 | 286 | 0.394 | 0.112 | 0.211 | 0.789 | 19/99 |
| microprice_5m_bps | 2.108 | 0.658 | 0.36 | 0.15 | 0.238 | 0.526 | 18/97 |
| OFI | -0.0285 | 0.0353 | -0.351 | -0.121 | 0.22 | 0.474 | 19/99 |
| prior_move_180m | -0.1463 | 0.0185 | 0.218 | 0.085 | 0.204 | 0.579 | 19/99 |
| local_volatility_180m | 0.8199 | 0.7861 | 0.217 | 0.083 | 0.222 | 0.842 | 19/99 |
| rejection_proof | 1 | 1 | 0.193 | 0.066 | 0.172 | 0.895 | 19/99 |
| dist_to_range_mid_pct | 0.244 | 0.263 | -0.191 | -0.065 | 0.206 | 0.684 | 19/99 |
| sweep_high | 0 | 0 | 0.182 | 0.071 | 0.161 | 1.0 | 19/99 |
| taker_imb_15m | -0.1507 | -0.0523 | -0.168 | -0.062 | 0.25 | 0.579 | 19/99 |
| depth_imb_top25 | 0.4432 | 0.2361 | 0.16 | 0.058 | 0.21 | 0.684 | 19/99 |
| prior_move_60m | 0.0463 | -0.0494 | 0.149 | 0.053 | 0.265 | 0.474 | 19/99 |

## C. Successful rule mining
| rule | uniq | W/L/TO | wr% | PF | prec | recall_strong | strong_caught | noise | days |
|---|--:|:--:|--:|--:|--:|--:|--:|--:|--:|
| P6_strict_5of7 | 24 | 7/6/11 | 29.17 | 1.227 | 0.292 | 0.375 | 3 | 17 | 11 |
| P4_absorption | 33 | 9/12/12 | 27.27 | 0.967 | 0.273 | 0.5 | 4 | 24 | 17 |
| P1_edge_reclaim | 34 | 8/12/14 | 23.53 | 0.781 | 0.235 | 0.375 | 3 | 26 | 15 |
| P6_strict_4of7 | 75 | 16/30/29 | 21.33 | 0.674 | 0.213 | 0.875 | 7 | 59 | 17 |
| P6_strict_3of7 | 105 | 21/38/46 | 20.0 | 0.712 | 0.2 | 1.0 | 8 | 84 | 18 |
| P6_strict_2of7 | 111 | 22/38/51 | 19.82 | 0.76 | 0.198 | 1.0 | 8 | 89 | 18 |
| P2_sweep_reversal | 23 | 4/8/11 | 17.39 | 0.545 | 0.174 | 0.125 | 1 | 19 | 15 |
| P3_thin_path | 0 | 0/0/0 | 0.0 | None | 0.0 | 0.0 | 0 | 0 | 0 |
| P5_confluence | 0 | 0/0/0 | 0.0 | None | 0.0 | 0.0 | 0 | 0 | 0 |

## D. Tier-A gates
| gate | rule | alerts | wr% | PF | strong | tag |
|---|---|--:|--:|--:|--:|---|
| min4 | P6_strict_5of7 | 24 | 29.17 | 1.227 | 3 | WEAK |
| min5 | P6_strict_5of7 | 24 | 29.17 | 1.227 | 3 | WEAK |
| min6 | P6_strict_5of7 | 24 | 29.17 | 1.227 | 3 | WEAK |
| min8 | P6_strict_5of7 | 24 | 29.17 | 1.227 | 3 | WEAK |

## E. Anti-overfit
| slice | alerts | wr% | PF | strong |
|---|--:|--:|--:|--:|
| full | 24 | 29.17 | 1.227 | 3 |
| without_05_14 | 23 | 30.43 | 1.416 | 3 |
| without_05_15 | 24 | 29.17 | 1.227 | 3 |
| without_both | 23 | 30.43 | 1.416 | 3 |
| first_half_03_11 | 14 | 28.57 | 1.297 | 2 |
| second_half_12_20 | 10 | 30.0 | 1.131 | 1 |
| dedup_60m | 24 | 29.17 | 1.227 | 3 |
| dedup_120m | 24 | 29.17 | 1.227 | 3 |
| dedup_240m | 24 | 29.17 | 1.227 | 3 |

- leave-one-cluster-out winrates: [29.2, 26.1, 29.2, 29.2, 29.2, 22.7, 29.2, 29.2]
- **RESULT_DEPENDS_ON_05_14_05_15 = NO** · rule_still_works = STABLE_BUT_LOW
- strong-move first-entry winrate = **100.0%** (ceiling exists; problem is selection)

## F. Positive vs reject architecture
- reject-only: removes obvious traps but leaves ~29% winrate pool (no positive lift).
- positive-only: best positive rule P6_strict_5of7: winrate 29.17% precision 0.292 on 24 alerts.
- combination: reject + positive still <30% winrate; the 8 strong winners are not separable ex-ante from look-alikes.

## G. Final answers
**1_positive_filters** — PARTIAL — weak separation; strongest positive features: prior_move_1d(d=0.59), wall_persistence_sec(d=0.394), microprice_5m_bps(d=0.36), OFI(d=-0.351)
**2_common_winner_traits** — prior_move_1d (win med 0.5969 vs noise -0.0222), wall_persistence_sec (win med 283 vs noise 286), microprice_5m_bps (win med 2.108 vs noise 0.658), OFI (win med -0.0285 vs noise 0.0353)
**3_tier_a_70_80** — NO — best P6_strict_5of7 29.17% on 24 alerts.
**4_unique_trades** — 24 unique deduped trades for the best rule.
**5_holds_without_1415** — depends_on_05_14_05_15=NO; without both -> 30.43% (n=23).
**6_live_or_hindsight** — SELECTION problem: strong moves win 100.0% from first entry but are not separable ex-ante; decisions are causal (live-valid) yet low-precision.
**7_best_family** — range-edge+reclaim and sweep-reversal give the highest precision among positives, but all <breakeven winrate; absorption/thin-path do not help.
**8_next_module** — NONE as a trade trigger yet; only a shadow logger to keep accumulating the rare strong moves until a separating feature emerges.
**9_combine_reject_positive** — Stage1 reject (regime/wall/entropy/dup) + Stage2 positive confluence; combination still <30% winrate, so positive layer is not yet additive.
**10_oos_needs** — more windows with >=15-20 unique strong moves + a feature with real ex-ante separation; freeze rules, no per-date tuning.

## Per-date casebook
- **2026-05-03** [RANGE] hit2=0 strong=1 hit3=0 · day-family=SLOW_GRIND_CONTINUATION · repeats=YES · separated by: sweep%: win 33 vs noise 0; median_OFI: win 0.16 vs noise 0.08; median_taker15: win -0.16 vs noise -0.1; median_entropy: 
- **2026-05-04** [RANGE] hit2=3 strong=2 hit3=1 · day-family=UNCLEAR · repeats=YES · separated by: sweep%: win 33 vs noise 0; median_OFI: win 0.01 vs noise -0.05; median_taker15: win -0.19 vs noise -0.05; median_entropy
- **2026-05-05** [RANGE] hit2=3 strong=0 hit3=0 · day-family=SLOW_GRIND_CONTINUATION · repeats=YES · separated by: reclaim%: win 67 vs noise 100; sweep%: win 67 vs noise 33; median_OFI: win 0.12 vs noise 0.08; median_taker15: win -0.01
- **2026-05-06** [RANGE] hit2=2 strong=0 hit3=0 · day-family=RANGE_FADE_HIGH_TO_LOW · repeats=YES · separated by: reclaim%: win 33 vs noise 0; sweep%: win 33 vs noise 67; median_OFI: win 0.07 vs noise 0.21; median_taker15: win 0.11 vs
- **2026-05-07** [RANGE] hit2=3 strong=1 hit3=1 · day-family=RANGE_FADE_HIGH_TO_LOW · repeats=YES · separated by: sweep%: win 0 vs noise 33; median_OFI: win -0.2 vs noise 0.23; median_taker15: win -0.17 vs noise 0.06; median_entropy: 
- **2026-05-08** [RANGE] hit2=0 strong=0 hit3=0 · day-family=NONE · repeats=NO · separated by: nothing clear on decision features
- **2026-05-09** [RANGE] hit2=0 strong=0 hit3=0 · day-family=NONE · repeats=NO · separated by: nothing clear on decision features
- **2026-05-10** [RANGE] hit2=1 strong=0 hit3=0 · day-family=SLOW_GRIND_CONTINUATION · repeats=YES · separated by: reclaim%: win 67 vs noise 100; median_OFI: win 0.2 vs noise -0.16; median_taker15: win -0.08 vs noise -0.07; median_entr
- **2026-05-11** [RANGE] hit2=0 strong=0 hit3=0 · day-family=NONE · repeats=NO · separated by: nothing clear on decision features
- **2026-05-12** [RANGE] hit2=1 strong=0 hit3=0 · day-family=SLOW_GRIND_CONTINUATION · repeats=YES · separated by: reclaim%: win 0 vs noise 100; sweep%: win 0 vs noise 67; median_OFI: win -0.29 vs noise -0.07; median_taker15: win -0.13
- **2026-05-13** [RANGE] hit2=1 strong=1 hit3=1 · day-family=RANGE_FADE_HIGH_TO_LOW · repeats=YES · separated by: reclaim%: win 100 vs noise 33; sweep%: win 0 vs noise 33; median_OFI: win -0.18 vs noise 0.26; median_taker15: win -0.24
- **2026-05-14** [RANGE] hit2=1 strong=1 hit3=1 · day-family=UNCLEAR · repeats=YES · separated by: sweep%: win 0 vs noise 33; median_OFI: win 0.0 vs noise 0.12; median_taker15: win -0.23 vs noise -0.17; median_entropy: 
- **2026-05-15** [RANGE] hit2=2 strong=2 hit3=2 · day-family=RANGE_FADE_HIGH_TO_LOW · repeats=YES · separated by: reclaim%: win 0 vs noise 33; sweep%: win 67 vs noise 33; median_OFI: win 0.0 vs noise 0.11; median_taker15: win 0.15 vs 
- **2026-05-16** [TREND_DOWN] hit2=0 strong=0 hit3=0 · day-family=NONE · repeats=NO · separated by: nothing clear on decision features
- **2026-05-17** [RANGE] hit2=1 strong=0 hit3=0 · day-family=SLOW_GRIND_CONTINUATION · repeats=YES · separated by: median_OFI: win -0.1 vs noise -0.03; median_taker15: win -0.05 vs noise 0.04; median_entropy: win 0.29 vs noise 0.31
- **2026-05-18** [RANGE] hit2=1 strong=0 hit3=0 · day-family=LIQUIDITY_SWEEP_REVERSAL · repeats=NO · separated by: sweep%: win 100 vs noise 67; median_OFI: win -0.13 vs noise -0.0; median_taker15: win 0.05 vs noise -0.04; median_entrop
- **2026-05-19** [RANGE] hit2=0 strong=0 hit3=0 · day-family=NONE · repeats=NO · separated by: nothing clear on decision features
- **2026-05-20** [RANGE] hit2=0 strong=0 hit3=0 · day-family=NONE · repeats=NO · separated by: nothing clear on decision features

## Flags
```
SUCCESSFUL_UNIQUE_MOVE_MINING_DONE = YES
POSITIVE_FILTERS_FOUND = PARTIAL
BEST_POSITIVE_RULE = P6_strict_5of7
TIER_A_70_80_FOUND = NO
BEST_TIER_A_ALERTS = 24
BEST_TIER_A_WINRATE = 29.17
BEST_TIER_A_PF = 1.227
BEST_TIER_A_HINDSIGHT_RISK = MED
RESULT_DEPENDS_ON_05_14_05_15 = NO
READY_FOR_TIER_A_SHADOW_MODULE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_OOS_REQUIRED = YES
N_UNIQUE_STRONG = 8
N_UNIQUE_HIT2 = 19
STRONG_FIRST_ENTRY_WINRATE = 100.0
TARDIS_USED = NO
```