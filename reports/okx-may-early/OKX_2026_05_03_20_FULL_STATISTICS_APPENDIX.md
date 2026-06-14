# OKX early-May 05-03..20 — FULL STATISTICS APPENDIX

**Build:** 2026-06-06T16:45:39+00:00
Decision-time (causal) vs post-factum outcome separated. No tuning. Conclusions unchanged.

## A. Per-day market + engine
| date | day_regime | net_move_pct | range_pct | realized_vol | zones | triggered | hit_2 | hit_2_5 | hit_3 | long | short | td_short_candidates | td_short_accepted | tu_long_candidates | tu_long_accepted_M6 |
|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|
| 2026-05-03 | RANGE | 0.22 | 1.49 | 0.0034 | 16 | 11 | 6 | 4 | 0 | 9 | 7 | 0 | 0 | 0 | 0 |
| 2026-05-04 | RANGE | 1.73 | 3.14 | 0.0082 | 22 | 18 | 11 | 4 | 1 | 5 | 17 | 0 | 0 | 1 | 0 |
| 2026-05-05 | RANGE | 1.87 | 2.66 | 0.0057 | 27 | 16 | 4 | 0 | 0 | 16 | 11 | 0 | 0 | 3 | 1 |
| 2026-05-06 | RANGE | 0.18 | 2.66 | 0.0063 | 32 | 20 | 3 | 0 | 0 | 14 | 18 | 0 | 0 | 0 | 0 |
| 2026-05-07 | RANGE | -2.22 | 2.78 | 0.0054 | 27 | 16 | 5 | 1 | 1 | 13 | 14 | 0 | 0 | 0 | 0 |
| 2026-05-08 | RANGE | 0.34 | 1.77 | 0.0055 | 24 | 16 | 0 | 0 | 0 | 14 | 10 | 1 | 1 | 0 | 0 |
| 2026-05-09 | RANGE | 0.45 | 1.18 | 0.0036 | 11 | 7 | 0 | 0 | 0 | 6 | 5 | 0 | 0 | 0 | 0 |
| 2026-05-10 | RANGE | 1.07 | 1.24 | 0.0031 | 14 | 8 | 3 | 0 | 0 | 7 | 7 | 0 | 0 | 0 | 0 |
| 2026-05-11 | RANGE | -0.01 | 2.79 | 0.0063 | 22 | 12 | 0 | 0 | 0 | 10 | 12 | 0 | 0 | 0 | 0 |
| 2026-05-12 | RANGE | -1.39 | 2.45 | 0.0051 | 15 | 7 | 3 | 0 | 0 | 7 | 8 | 0 | 0 | 0 | 0 |
| 2026-05-13 | RANGE | -1.85 | 3.25 | 0.0048 | 26 | 17 | 8 | 3 | 1 | 13 | 13 | 0 | 0 | 0 | 0 |
| 2026-05-14 | RANGE | 3.11 | 3.26 | 0.0051 | 27 | 15 | 13 | 12 | 6 | 19 | 8 | 0 | 0 | 3 | 0 |
| 2026-05-15 | RANGE | -2.65 | 4.34 | 0.0063 | 21 | 13 | 11 | 10 | 9 | 9 | 12 | 0 | 0 | 0 | 0 |
| 2026-05-16 | TREND_DOWN | -1.13 | 2.49 | 0.0044 | 21 | 13 | 0 | 0 | 0 | 11 | 10 | 5 | 2 | 0 | 0 |
| 2026-05-17 | RANGE | -0.25 | 1.16 | 0.0035 | 17 | 9 | 2 | 0 | 0 | 9 | 8 | 0 | 0 | 0 | 0 |
| 2026-05-18 | RANGE | -2.08 | 3.2 | 0.007 | 19 | 12 | 1 | 0 | 0 | 7 | 12 | 0 | 0 | 0 | 0 |
| 2026-05-19 | RANGE | 0.16 | 1.67 | 0.0058 | 20 | 12 | 0 | 0 | 0 | 10 | 10 | 0 | 0 | 0 | 0 |
| 2026-05-20 | RANGE | 1.19 | 1.9 | 0.0051 | 21 | 16 | 0 | 0 | 0 | 10 | 11 | 0 | 0 | 0 | 0 |

## C. Would-alert trades (live signals)
| model | date | direction | entry_price | regime | confluence_count | result | MFE | hit_2_5pct | pnl_after_cost |
|--|--|--|--|--|--|--|--|--|--|
| TD_SHORT_HYBRID | 2026-05-16 | SHORT | 79063.6 | TREND_DOWN | 3 | TIMEOUT | 1.851 | 0 | 1.2882 |
| TD_SHORT_HYBRID | 2026-05-08 | SHORT | 79251.9 | TREND_DOWN | 2 | LOSS | 0.058 | 0 | -1.64 |
| TD_SHORT_HYBRID | 2026-05-16 | SHORT | 78520.9 | TREND_DOWN | 2 | TIMEOUT | 1.173 | 0 | 0.4628 |
| TU_LONG_M0_baseline | 2026-05-04 | LONG | 80116.5 | TREND_UP | 1 | LOSS | 0.963 | 0 | -1.64 |
| TU_LONG_M0_baseline | 2026-05-05 | LONG | 80891.6 | TREND_UP | 1 | WIN | 2.359 | 0 | 1.86 |
| TU_LONG_M0_baseline | 2026-05-14 | LONG | 81303.9 | TREND_UP | 1 | LOSS | 0.857 | 0 | -1.64 |
| TU_LONG_M1_TU_LONG_only | 2026-05-04 | LONG | 80116.5 | TREND_UP | 1 | LOSS | 0.963 | 0 | -1.64 |
| TU_LONG_M1_TU_LONG_only | 2026-05-05 | LONG | 80891.6 | TREND_UP | 1 | WIN | 2.359 | 0 | 1.86 |
| TU_LONG_M1_TU_LONG_only | 2026-05-14 | LONG | 81303.9 | TREND_UP | 1 | LOSS | 0.857 | 0 | -1.64 |
| TU_LONG_M2_no_seller_abs | 2026-05-05 | LONG | 81241.0 | TREND_UP | 3 | TIMEOUT | 1.919 | 0 | 1.1662 |
| TU_LONG_M2_no_seller_abs | 2026-05-14 | LONG | 81293.8 | TREND_UP | 1 | LOSS | 0.87 | 0 | -1.64 |
| TU_LONG_M3_plus_reclaim | 2026-05-05 | LONG | 81241.0 | TREND_UP | 3 | TIMEOUT | 1.919 | 0 | 1.1662 |
| TU_LONG_M4_plus_taker_micro | 2026-05-05 | LONG | 81241.0 | TREND_UP | 3 | TIMEOUT | 1.919 | 0 | 1.1662 |
| TU_LONG_M4_plus_taker_micro | 2026-05-14 | LONG | 81293.8 | TREND_UP | 1 | LOSS | 0.87 | 0 | -1.64 |
| TU_LONG_M6_confluence_2of4 | 2026-05-05 | LONG | 81241.0 | TREND_UP | 3 | TIMEOUT | 1.919 | 0 | 1.1662 |
| TU_LONG_M7_live_valid | 2026-05-05 | LONG | 81241.0 | TREND_UP | 3 | TIMEOUT | 1.919 | 0 | 1.1662 |

## E. TU-long all setup zones (why failed)
| date | zone_id | MFE | hit_2 | hit_2_5 | sim_result | n_models_passed | why_failed |
|--|--|--|--|--|--|--|--|
| 2026-05-04 | BTC-USDT-SWAP-LONG-1777863960000-8 | 0.963 | 0 | 0 | LOSS | 2 | seller_absorption;failed_reclaim;thick_ask_path;taker_against |
| 2026-05-05 | BTC-USDT-SWAP-LONG-1777981492000-20 | 2.359 | 1 | 0 | WIN | 2 | seller_absorption;failed_reclaim;thick_ask_path;taker_against |
| 2026-05-05 | BTC-USDT-SWAP-LONG-1777984771000-21 | 1.919 | 0 | 0 | TIMEOUT | 7 | thick_ask_path |
| 2026-05-05 | BTC-USDT-SWAP-LONG-1777986857000-22 | 1.443 | 0 | 0 | TIMEOUT | 7 | thick_ask_path |
| 2026-05-14 | BTC-USDT-SWAP-LONG-1778774359000-27 | 0.857 | 0 | 0 | LOSS | 2 | seller_absorption;failed_reclaim;thick_ask_path;microprice_against |
| 2026-05-14 | BTC-USDT-SWAP-LONG-1778774469000-28 | 0.87 | 0 | 0 | LOSS | 4 | failed_reclaim;thick_ask_path;microprice_against |
| 2026-05-14 | BTC-USDT-SWAP-LONG-1778774480000-29 | 0.864 | 0 | 0 | LOSS | 4 | failed_reclaim;thick_ask_path;microprice_against |

## F. Strong zones (>=2.5% MFE)
| date | direction | regime | MFE | time_to_2_min | reclaim_zoneMid | eng_ofi | prior_move_60m | caught_by_models | why_skipped |
|--|--|--|--|--|--|--|--|--|--|
| 2026-05-03 | LONG | RANGE | 2.858 | 1101.9 | 1 | -0.10564170069715213 | 0.3101 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-03 | LONG | RANGE | 2.8 | 1055.3 | 0 | 0.21948192158800547 | 0.0528 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-03 | LONG | RANGE | 2.611 | 1420.1 | 0 | -0.0634953893833828 | -0.2363 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-03 | LONG | RANGE | 2.934 | 1118.5 | 0 | 0.16051730291254257 | 0.2714 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-04 | LONG | RANGE | 2.935 | 110.8 | 0 | 0.007297746589111729 | -0.8316 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-04 | SHORT | TREND_UP | 2.874 | 346.0 | 1 | 0.05344798917762761 | 0.3048 |  | gates/cooldown |
| 2026-05-04 | SHORT | TREND_UP | 2.611 | 407.1 | 1 | 0.021622361817146857 | 0.4597 |  | gates/cooldown |
| 2026-05-04 | LONG | RANGE | 3.07 | 257.7 | 1 | -0.02848362208956418 | -1.0239 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-07 | SHORT | RANGE | 3.001 | 470.3 | 1 | -0.04765227722366707 | 0.7483 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-13 | SHORT | RANGE | 3.019 | 596.5 | 1 | -0.1789320218135511 | 0.1849 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-13 | SHORT | RANGE | 2.859 | 806.4 | 1 | -0.21371447412900585 | 0.4676 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-13 | SHORT | RANGE | 2.612 | 854.1 | 1 | -0.08020323267352894 | 0.4661 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-14 | LONG | RANGE | 3.075 | 895.4 | 0 | -0.06344447231335963 | 0.3488 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-14 | LONG | RANGE | 3.175 | 875.2 | 0 | -0.12499005611216495 | 0.1227 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-14 | LONG | RANGE | 3.307 | 593.9 | 0 | 0.19521099357632482 | 0.4505 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-14 | LONG | TREND_DOWN | 3.72 | 655.1 | 0 | -0.08290491004020405 | -0.2132 |  | gates/cooldown |
| 2026-05-14 | LONG | TREND_DOWN | 3.803 | 647.8 | 0 | 0.003787417917804378 | -0.4021 |  | gates/cooldown |
| 2026-05-14 | LONG | RANGE | 3.483 | 699.3 | 1 | 0.12105074149038668 | -0.4111 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-14 | LONG | RANGE | 2.673 | 590.0 | 1 | 0.18093410254697467 | 0.5435 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-14 | LONG | RANGE | 2.757 | 599.9 | 0 | 0.3186830362424694 | 0.5262 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-14 | LONG | RANGE | 2.752 | 460.7 | 1 | -0.1042213548086745 | 0.1687 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-14 | LONG | RANGE | 2.939 | 347.6 | 1 | -0.11951522592276784 | -0.2153 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-14 | LONG | RANGE | 2.773 | 171.9 | 1 | 0.21121871344412282 | 0.6156 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-14 | LONG | RANGE | 2.631 | 159.8 | 0 | 0.35628992187369307 | 0.6425 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-15 | SHORT | RANGE | 3.429 | 782.9 | 0 | 0.05528503904759601 | 0.1328 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-15 | SHORT | RANGE | 3.395 | 788.5 | 0 | 0.0012135024871453416 | 0.2083 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-15 | SHORT | RANGE | 3.54 | 732.9 | 0 | -0.20778996882842118 | 0.1556 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-15 | SHORT | RANGE | 2.819 | 672.9 | 1 | -0.15541490248046974 | -0.6826 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-15 | SHORT | RANGE | 3.047 | 649.1 | 0 | -0.2588777838636058 | -0.2447 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-15 | SHORT | RANGE | 3.335 | 384.8 | 0 | 0.12539788928226486 | 0.3485 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-15 | SHORT | RANGE | 3.279 | 270.1 | 1 | -0.15740782272342857 | -0.1829 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-15 | SHORT | RANGE | 3.185 | 242.4 | 1 | 0.01538314113141114 | -0.2525 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-15 | SHORT | RANGE | 3.21 | 229.5 | 0 | 0.13335693412347338 | -0.227 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |
| 2026-05-15 | SHORT | RANGE | 3.121 | 1058.4 | 0 | -0.10778930631107346 | -0.501 |  | not_TREND_DOWN_short_and_not_TREND_UP_long_setup |

## G. Summary — by model
| model | alerts | trades | W | L | TO | winrate | pf | expectancy | total_return | hit2_5 | max_loss_streak |
|--|--|--|--|--|--|--|--|--|--|--|--|
| TD_SHORT_HYBRID | 3 | 3 | 0 | 1 | 2 | 0.0 | 1.068 | 0.037 | 0.111 | 0 | 1 |
| TD_SHORT_M4_THIN | 0 | 0 | 0 | 0 | 0 | 0.0 | None | None | None | 0 | 0 |
| TU_LONG_M0_baseline | 3 | 3 | 1 | 2 | 0 | 33.33 | 0.567 | -0.4733 | -1.42 | 0 | 1 |
| TU_LONG_M1_TU_LONG_only | 3 | 3 | 1 | 2 | 0 | 33.33 | 0.567 | -0.4733 | -1.42 | 0 | 1 |
| TU_LONG_M2_no_seller_abs | 2 | 2 | 0 | 1 | 1 | 0.0 | 0.711 | -0.2369 | -0.4738 | 0 | 1 |
| TU_LONG_M3_plus_reclaim | 1 | 1 | 0 | 0 | 1 | 0.0 | None | 1.1662 | 1.1662 | 0 | 0 |
| TU_LONG_M4_plus_taker_micro | 2 | 2 | 0 | 1 | 1 | 0.0 | 0.711 | -0.2369 | -0.4738 | 0 | 1 |
| TU_LONG_M5_plus_thin_ask | 0 | 0 | 0 | 0 | 0 | 0.0 | None | None | None | 0 | 0 |
| TU_LONG_M6_confluence_2of4 | 1 | 1 | 0 | 0 | 1 | 0.0 | None | 1.1662 | 1.1662 | 0 | 0 |
| TU_LONG_M7_live_valid | 1 | 1 | 0 | 0 | 1 | 0.0 | None | 1.1662 | 1.1662 | 0 | 0 |

## G. TD-short sanity
- false shorts in TREND_UP: **0**; accepted shorts 3 (TREND_DOWN 3); outcomes {'WIN': 0, 'LOSS': 1, 'TIMEOUT': 2}

## H. Final answers
**1_total_zones** — 382
**2_hit_counts** — {'hit_2pct': 70, 'hit_2_5pct': 34, 'hit_3pct': 18}
**3_live_signals_total** — 16
**3_live_signals_by_module** — {'TD_SHORT_HYBRID': 3, 'TU_LONG_M0_baseline': 3, 'TU_LONG_M1_TU_LONG_only': 3, 'TU_LONG_M2_no_seller_abs': 2, 'TU_LONG_M3_plus_reclaim': 1, 'TU_LONG_M4_plus_taker_micro': 2, 'TU_LONG_M6_confluence_2of4': 1, 'TU_LONG_M7_live_valid': 1}
**4_which_trades** — see WOULD_ALERT table (C). TD-short HYBRID accepted 3 shorts (all in TREND_DOWN).
**5_strong_skipped** — 34
**5_strong_total** — 34
**6_why_tu_long_failed** — few TREND_UP zones (RANGE window), 0 strong winners, PF<=0.71 — long-continuation not viable here
**7_td_short_stood_aside_in_TREND_UP** — YES — false shorts in TREND_UP = 0
**8_other_setup_to_explore** — RANGE-window: mean-reversion / range-fade with reclaim is the untested candidate (most zones are RANGE; strong moves exist but neither TD-short nor TU-long covers RANGE).