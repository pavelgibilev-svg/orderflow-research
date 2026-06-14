# OKX MAY 18D DEEP FILTER + ENGINE SELECTION AUDIT — FINAL

## ⚠️ IN-SAMPLE RESEARCH — NOT PRODUCTION VALIDATION

**Build:** 2026-06-10T17:13:48+00:00

## A. Pool reconstruction
- raw_zones: 382
- triggered_zones: 382
- raw_hit2_zones: 70
- raw_strong_zones: 34
- unique_hit2_clusters: 19
- unique_strong_clusters: 8
- live_detectable_strong_clusters: 6
- hindsight_only_strong_clusters: 2
- duplicate_zones_in_hit2_clusters: 51
- avg_zones_per_hit2_cluster: 3.68

## B. Engine / zone selection audit
| group | clusters | first-zone wr | best-MFE wr | first-live wr | earliest-safe wr |
|---|--:|--:|--:|--:|--:|
| strong_clusters | 8 | 100.0 | 100.0 | 100.0 | 100.0 |
| hit2_clusters | 19 | 100.0 | 100.0 | 100.0 | 100.0 |

- First zone of each strong cluster already wins TP2 (100%); best-MFE zone adds +0 pts. => within-cluster selection is NOT the bottleneck; the gap is CROSS-cluster ranking (which of the look-alike clusters to trust), and current features do not separate them.
- flags: {'ENGINE_DUPLICATES_TOO_MANY': 'YES', 'ENGINE_SELECTION_PROBLEM': 'NO', 'RANKING_LAYER_NEEDED': 'PARTIAL', 'ENGINE_REWRITE_NEEDED': 'NO'}

## C. Positive features (hit2 vs noise, by |AUC-0.5|)
| feature | win med | noise med | Cohen d | AUC | prec@decile | date-stab |
|---|--:|--:|--:|--:|--:|--:|
| prior_move_1d | 0.5969 | -0.0222 | 0.59 | 0.669 | 0.455 | 0.64 |
| OFI | -0.0285 | 0.0353 | -0.351 | 0.398 | 0.182 | 0.73 |
| inband_sell_share_30m | 0.47 | 0.5033 | -0.386 | 0.4 | 0.182 | 0.73 |
| microprice_5m_bps | 2.108 | 0.658 | 0.36 | 0.583 | 0.273 | 0.8 |
| local_volatility_180m | 0.8199 | 0.7861 | 0.217 | 0.581 | 0.182 | 0.27 |
| prior_move_60m | 0.0463 | -0.0494 | 0.149 | 0.579 | 0.182 | 0.64 |

## E. Aggressive rule search (in-sample)
| rule | alerts | W/L/TO | wr% | PF | strong | noise | wr_wo_1415 | tier |
|---|--:|:--:|--:|--:|--:|--:|--:|:--:|
| P6_strict_5of7 | 24 | 7/6/11 | 29.17 | 1.227 | 3 | 17 | 30.43 | A |
| P4_absorption | 33 | 9/12/12 | 27.27 | 0.967 | 4 | 24 | 24.14 | A |
| P1_edge_reclaim | 34 | 8/12/14 | 23.53 | 0.781 | 3 | 26 | 24.14 | A |
| B5_taker_aligned | 107 | 25/33/49 | 23.36 | 0.957 | 7 | 82 | 19.35 | A |
| B3_range_edge | 57 | 13/22/22 | 22.81 | 0.713 | 5 | 44 | 22.45 | A |
| B2_edge_only | 60 | 13/24/23 | 21.67 | 0.684 | 6 | 47 | 21.15 | A |
| P6_strict_4of7 | 75 | 16/30/29 | 21.33 | 0.674 | 7 | 59 | 15.62 | A |
| B1_reclaim_only | 103 | 21/33/49 | 20.39 | 0.812 | 8 | 82 | 15.73 | A |
| P6_strict_3of7 | 105 | 21/38/46 | 20.0 | 0.712 | 8 | 84 | 16.48 | A |
| P6_strict_2of7 | 111 | 22/38/51 | 19.82 | 0.76 | 8 | 89 | 15.46 | A |
| B6_prior1d_aligned | 47 | 9/10/28 | 19.15 | 1.259 | 2 | 38 | 22.5 | A |
| B4_sweep_only | 34 | 6/12/16 | 17.65 | 0.614 | 3 | 28 | 19.35 | A |

- gates: min4=P6_strict_5of7 29.17% n24 WEAK · min5=P6_strict_5of7 29.17% n24 WEAK · min6=P6_strict_5of7 29.17% n24 WEAK · min8=P6_strict_5of7 29.17% n24 WEAK · min10=P6_strict_5of7 29.17% n24 WEAK · min15=P6_strict_5of7 29.17% n24 WEAK · min20=P6_strict_5of7 29.17% n24 WEAK
- selector policies (winrate per unique cluster): {'first_eligible_per_cluster': 100.0, 'best_live_per_cluster': 100.0, 'earliest_safe_per_cluster': 100.0}
- depends_on_0514_0515 = NO

## F. Engine rework proposals
- **1_cluster_aware_selector** — fixes: duplicate inflation (70 hit2 raw -> 19 unique; 34 strong raw -> 8 unique); impact: removes ~73% duplicate alerts; winrate unchanged (selection within cluster already fine); cost: low
- **2_zone_quality_score** — fixes: cross-cluster ranking (the real gap); impact: LIMITED — current features have AUC~0.5-0.65, do not separate the 8 winners; cost: medium
- **3_delayed_confirmation** — fixes: late/early entry timing; impact: NEGLIGIBLE — strong first-entry already 100% TP2; timing is not the bottleneck; cost: medium
- **4_event_driven_entry** — fixes: noise suppression; impact: reduces alert count but precision stays <30% (events fire on losers too); cost: medium-high
- **5_duplicate_suppression** — fixes: duplicate credits / over-alerting; impact: same as #1; cleaner live stream; cost: low
- ENGINE_REWORK_RECOMMENDED = PARTIAL

## I. Answers
**1_better_filter** — NO clean win — best in-sample rule P6_strict_5of7 29.17% on 24 alerts; no rule reaches 70% at n>=6.
**2_positive_feature** — PARTIAL — top by AUC: prior_move_1d(AUC 0.669), OFI(AUC 0.398), inband_sell_share_30m(AUC 0.4), microprice_5m_bps(AUC 0.583); all near 0.5-0.65, none separates the 8 strong winners.
**3_where_is_the_problem** — Not engine/TP/SL and not within-cluster selection (strong first-zone TP2 = 100%). It is FEATURE SEPARATION + cross-cluster RANKING: winners look like noise ex-ante.
**4_tier_a_possible** — NO.
**5_if_yes_overfit** — n/a (not found at n>=6).
**6_if_no_why** — Only 8 unique strong moves; positive features have AUC~0.5-0.65 and sign flips across dates; any 70%+ rule is n<=4 curve-fit.
**7_engine_rebuild** — NO rewrite. Add a cluster-aware / duplicate-suppression layer (cheap, fixes alert inflation). A scoring/ranking layer is only worth it once a separating feature exists.
**8_next_step** — Run the daily windows scanner, download TREND_UP + TREND_DOWN + HIGH_VOL windows (the regimes missing here — 16/18 days were RANGE), rebuild caches, re-mine features across regimes.
**9_dates_to_download** — See NEXT_WINDOWS_TO_DOWNLOAD (data-driven). This 18d pool is almost all RANGE; trend/high-vol windows are required.
**10_windows_for_full_calibration** — See CALIBRATION_WINDOW_PLAN: feature-discovery vs validation vs holdout split, >=15-20 unique strong moves per regime, OKX+Binance overlap for cross-venue.

## Flags
```
DEEP_18D_AUDIT_DONE = YES
POSITIVE_FEATURE_FOUND = PARTIAL
TIER_A_FOUND_ON_18D = NO
ENGINE_SELECTION_PROBLEM = NO
ENGINE_REWORK_RECOMMENDED = PARTIAL
NEXT_WINDOWS_SCANNER_DONE = SEE scripts/research/select_next_windows_from_daily.py
NEXT_WINDOWS_TO_DOWNLOAD_READY = SEE reports/strategy-calibration/NEXT_WINDOWS_TO_DOWNLOAD.*
READY_FOR_PRODUCTION_TRADING = NO
MORE_OOS_REQUIRED = YES
BEST_RULE = P6_strict_5of7
BEST_RULE_WINRATE = 29.17
BEST_RULE_ALERTS = 24
STRONG_FIRST_ENTRY_WINRATE = 100.0
DEPENDS_ON_0514_0515 = NO
TARDIS_USED = NO
```