# SHORT-PERMISSION GATE v5 — FINAL REPORT

Build 2026-06-12T16:24:24+00:00 · RESEARCH/CALIBRATION, not production. TP=2%/SL=1.5%. OKX single-venue, di-free, causal gate.

## 1. Executive summary
- A causal regime gate is placed BEFORE the v3 event trigger. Best gate **GATE_5_COMBINED** blocks **62.4%** of TREND_UP shorts and retains **47.1%** of TREND_DOWN shorts.
- gate_helps (random+gate 1.638 > random_all 1.416) = True; event_adds_over_random+gate = False.
- RESEARCH_CANDIDATE gates: NONE.
## 2. Why a regime gate
- v4 proved the event trigger shorts uptrends and has no edge over random; the missing layer is short-permission.
## 3. Gate rules tested
- GATE_1 strict-downtrend, GATE_2 seller-control, GATE_3 no-uptrend, GATE_4 no-chop, GATE_5 combined.
## 4. TREND_UP: 2200 short-events (PF 0.172); best blocker GATE_5_COMBINED removes 62.4%.
## 5. TREND_DOWN: retention per gate in DOWNTREND_RETENTION_TEST (avoid 'no-trade-always').
## 6-7. RANGE/CHOP + REVERSAL/BOUNCE: see RANGE_BOUNCE_BLOCK_TEST.
## 8. event+gate vs random: **event adds nothing over random within the allowed regime — the gate does the work, the entry is still not an edge**.
## 9. RESEARCH_CANDIDATE: NO
## 10. Next: if gate blocks UP/RANGE but event!=edge, pair the gate (as a short-permission veto) with a DIFFERENT entry; OR get Bybit+OKX L2 control data to test cross-venue confirmation inside allowed regimes.

FINAL_ARTIFACTS_LOCATION:
- main_folder: reports/short_permission_gate_v5/
- gate_features: GATE_FEATURES.csv (+ GATE_FEATURE_DEFINITIONS.md)
- gate_rules: GATE_RULES.json/.md
- gate_performance: GATE_PERFORMANCE_BY_REGIME.csv/.md
- trend_up_block_test: TREND_UP_SHORT_BLOCK_TEST.md/.csv
- downtrend_retention_test: DOWNTREND_RETENTION_TEST.md/.csv
- range_bounce_block_test: RANGE_BOUNCE_BLOCK_TEST.md/.csv
- gate_scorecard: GATE_SCORECARD.csv
- gate_decisions: GATE_DECISIONS.md
- comparison_with_v4: COMPARISON_WITH_V4.md
- final_report: SHORT_PERMISSION_GATE_V5_FINAL_REPORT.md