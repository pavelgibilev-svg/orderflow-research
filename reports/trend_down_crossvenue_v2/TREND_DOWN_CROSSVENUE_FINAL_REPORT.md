# TREND_DOWN CROSS-VENUE v2 — FINAL REPORT

Build 2026-06-12T12:57:48+00:00 · RESEARCH/CALIBRATION, not production.

## 1. Executive summary
- 219 unique clusters (Bybit+OKX, real trade-flow). Baseline: hit2 25.1%, loss 39.7%, PF 0.717, exp -0.184%.
- Capital-state is now DIRECTION-AWARE (v1 bug fixed). UNKNOWN clusters: 169/219.
- RESEARCH_CANDIDATE templates: NONE; VETO: ['TD_NO_CONTROL_CHOP_NO_TRADE', 'TD_CROSS_VENUE_DISAGREEMENT_VETO'].

## 2-3. Data / windows
- Bybit BTCUSDT + OKX BTC-USDT-SWAP, windows W1_NOV/W3_JAN/W4_APRIL. See WINDOWS_SUMMARY.
## 4. What changed after adding trades
- effort_vs_result & initiative_control now use real taker volume + CVD (not L2 proxy).
- capital_state uses net taker flow and CVD slope, and is direction-consistent.

## 5-7. Results
| category | n | hit2% | PF |
|---|--:|--:|--:|
| CROSS_CONFIRMED | 144 | 26.4 | 0.898 |
| BYBIT_ONLY | 5 | 0.0 | 0.0 |
| OKX_ONLY | 6 | 16.7 | 0.567 |
| CROSS_DISAGREEMENT | 64 | 25.0 | 0.534 |

## 8. Capital states that separate
| state | n | hit2 | loss |
|---|--:|--:|--:|
| UNKNOWN | 169 | 43 | 60 |
| NO_CONTROL_CHOP | 29 | 7 | 15 |
| DISTRIBUTION_INTO_BOUNCE | 21 | 5 | 12 |

## 9-10. Evidence blocks (real trades)
- Bybit effort_vs_result: sep 0.19 (win 0.59 vs loss 0.4)
- Bybit absorption_refill: sep -0.02 (win 1.41 vs loss 1.43)
- Bybit initiative_control: sep 0.6 (win 1.19 vs loss 0.59)
- Bybit background_alignment: sep -0.08 (win 1.26 vs loss 1.34)
- Bybit not_overextended: sep -0.22 (win 1.85 vs loss 2.07)
- Bybit liquidity_execution: sep -0.01 (win 2.89 vs loss 2.9)
- OKX effort_vs_result: sep 0.13 (win 0.5 vs loss 0.37)
- OKX absorption_refill: sep -0.0 (win 1.11 vs loss 1.11)
- OKX initiative_control: sep 0.32 (win 1.04 vs loss 0.72)
- OKX background_alignment: sep -0.14 (win 1.21 vs loss 1.35)
- OKX not_overextended: sep -0.26 (win 1.82 vs loss 2.09)
- OKX liquidity_execution: sep -0.01 (win 2.89 vs loss 2.9)

## 11-12. Filters
- KEEP_TEMPLATE: NONE
- KEEP_AS_VETO: ['TD_NO_CONTROL_CHOP_NO_TRADE', 'TD_CROSS_VENUE_DISAGREEMENT_VETO']
- QUARANTINE/NEED_MORE_DATA: ['TD_ACTIVE_MARKDOWN_SHORT_TEMPLATE', 'TD_FORCED_UNWIND_CONTINUATION_SHORT_TEMPLATE', 'TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH', 'TD_CROSS_VENUE_CONFIRMED_MARKDOWN_SHORT']
- REJECT: ['TD_DISTRIBUTION_INTO_BOUNCE_SHORT_TEMPLATE']

## 13. RESEARCH_CANDIDATE short-template?
- NO — see scorecard; most states remain QUARANTINE/NEED_MORE_DATA or VETO.

## 14. Next
- More true TREND_DOWN windows (W2 was a bounce); true OOS; freeze any surviving template, no tuning.

## 15. Artifacts

FINAL_ARTIFACTS_LOCATION:
- main_folder: reports/trend_down_crossvenue_v2/
- dataset_coverage: DATASET_COVERAGE.csv
- windows_summary: WINDOWS_SUMMARY.csv/.md
- zones_raw: ZONES_RAW.csv
- unique_clusters: UNIQUE_CLUSTERS.csv
- capital_state_casebook: CAPITAL_STATE_CASEBOOK.csv/.json/.md
- evidence_scores: EVIDENCE_BLOCK_SCORES.csv (+ ANALYSIS.md)
- cross_venue_comparison: CROSS_VENUE_COMPARISON.md + CROSS_VENUE_MATCHED_CLUSTERS.csv + CROSS_VENUE_SCORECARD.csv
- filter_candidates: FILTER_CANDIDATES_TREND_DOWN_CROSSVENUE_V2.json/.csv
- filter_scorecard: FILTER_COMPARISON_SCORECARD.csv
- template_library: TREND_DOWN_TEMPLATE_LIBRARY_V2.json/.md
- decision_tree: TREND_DOWN_DECISION_TREE_V2.md
- final_report: TREND_DOWN_CROSSVENUE_FINAL_REPORT.md