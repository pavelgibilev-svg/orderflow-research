# TREND_DOWN ANALYSIS — FINAL REPORT

Build 2026-06-11T16:20:12+00:00 · RESEARCH analysis of saved calibration artifacts · NOT production.

## 1. Executive summary
- 89 unique clusters across 3 windows (Bybit ob200 only). Overall: hit2 21.3%, loss 30.3%, PF 0.798.
- **Only W1 (−8.9%) and W3 (−11.8%) are true TREND_DOWN; W2 (+1.4%) bounced** and is a counter-example, not a down window.
- **53% of clusters are UNKNOWN** and the classifier mislabels 12 LONG zones as ACTIVE_MARKDOWN -> capital-state
  labeling on L2-only proxy is too coarse/direction-blind. No capital_state yet yields a tradeable short edge on both down windows.
- Net: **no RESEARCH_CANDIDATE template** survives; the useful outputs are VETO/NO-TRADE rules + a clear data gap (need trades).

## 2. Windows compared
- W1: 2025-11-19..2025-11-22 (true TD) · W2: 2026-02-11..2026-02-14 (bounce) · W3: 2026-01-28..2026-01-31 (true TD)

## 3. Exchanges
- Bybit ob200 only for clusters. OKX = 1 L2 day/window (no in-window trades) -> CROSS_EXCHANGE = SINGLE_EXCHANGE_ONLY.

## 4. Capital states observed
- {'ACTIVE_MARKDOWN': 13, 'DISTRIBUTION_INTO_BOUNCE': 16, 'ABSORPTION_AFTER_SELL_PRESSURE': 1, 'NO_CONTROL_CHOP': 12, 'UNKNOWN': 47}

## 5. Promising states
- NO_CONTROL_CHOP

## 6-7. Evidence blocks
- Useful: ['absorption_refill'] · Need-more-data (mostly N/A/trades): [] · Junk: ['background_alignment', 'not_overextended', 'liquidity_execution']

## 8-9. Filters/templates
- KEEP as research template: NONE
- KEEP as veto: ['TD_NO_CONTROL_CHOP_NO_TRADE']
- QUARANTINE / need-more-data: ['TD_ACTIVE_MARKDOWN_SHORT_CANDIDATE', 'TD_FORCED_UNWIND_CONTINUATION_CANDIDATE', 'TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH']
- REJECT: ['TD_DISTRIBUTION_INTO_BOUNCE_SHORT_CANDIDATE']

## 10. Continue TREND_DOWN research?
- **YES but data-gated.** The structure is sound; the blocker is missing in-window TRADES (no taker/CVD/effort) and
  only 2 true down windows. Without trades, capital-state separation stays weak (mostly UNKNOWN / NO-TRADE).

## 11. Next windows/data to download
- **In-window TRADES** (Bybit + OKX) for W1 (2025-11-19..22) and W3 (2026-01-28..31) — unlocks effort/CVD/taker.
- **Full 4-day OKX L2** for W1/W3 (currently only last day) -> cross-venue capital-state agreement.
- **2-3 more true TREND_DOWN windows** (e.g. 2025-11 full, 2024-04, 2026-02 only if it actually trends down) with trades.
- Replace the bounce window W2 with a genuine markdown window.

## 12. Outputs location (below)

FINAL_ARTIFACTS_LOCATION:
- analysis_by_window: reports/trend_down_calibration_v1/ANALYSIS_BY_WINDOW.csv/.md
- cross_exchange_comparison: reports/trend_down_calibration_v1/CROSS_EXCHANGE_COMPARISON.csv/.md
- capital_state_scorecard: reports/trend_down_calibration_v1/CAPITAL_STATE_SCORECARD.csv/.md
- evidence_block_analysis: reports/trend_down_calibration_v1/EVIDENCE_BLOCK_ANALYSIS.csv/.md
- filter_comparison: reports/trend_down_calibration_v1/FILTER_COMPARISON_SCORECARD.csv/.md
- template_library: reports/trend_down_calibration_v1/TREND_DOWN_TEMPLATE_LIBRARY_V1.json/.md
- decision_tree: reports/trend_down_calibration_v1/TREND_DOWN_DECISION_TREE_V1.md
- final_report: reports/trend_down_calibration_v1/TREND_DOWN_ANALYSIS_FINAL_REPORT.md