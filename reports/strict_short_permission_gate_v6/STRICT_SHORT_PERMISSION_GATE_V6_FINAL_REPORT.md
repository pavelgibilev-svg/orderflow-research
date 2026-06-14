# STRICT SHORT-PERMISSION GATE v6 — FINAL REPORT

Build 2026-06-12T16:45:47+00:00 · RESEARCH/CALIBRATION, not production. TP=2%/SL=1.5%. OKX single-venue, di-free, causal gate.

## 1. Executive summary
- Stricter gates raise TREND_UP blocking from v5 62.4% to **85.1%** (GATE_6E_COMBINED_STRICT), keeping 18.1% of TREND_DOWN shorts.
- random+gate PF 2.16 > random_all 1.416 (gate_helps=True); event_adds_over_random+gate=False.
- RESEARCH_CANDIDATE: NONE (ceiling is NEED_MORE_DATA — only ONE trend-up window available).
## 2. Why v6 after v5
- v5 GATE_5 left ~828 losing uptrend shorts; v6 tightens the no-uptrend / downtrend-only logic (ret_3h+ret_6h, VWAP, buy-recovery).
## 3. Gates tested
- 6A strict-no-uptrend, 6B downtrend-only, 6C seller-control-strict, 6D no-bounce-no-chop, 6E combined-strict.
## 4. Best TREND_UP blocker: GATE_6E_COMBINED_STRICT (85.1%).
## 5. TREND_DOWN not killed: retained 18.1% (winners kept).
## 6. random+gate beats random_all: True (2.16 vs 1.416).
## 7. event adds after gate: False (NO -> entry still not an edge).
## 8. Statuses: see GATE_DECISIONS_V6 — best gates NEED_MORE_DATA, weak ones REJECT.
## 9. Next: (a) get >=2 more TREND_UP/RANGE/BOUNCE windows to lift the gate from NEED_MORE_DATA to RESEARCH_CANDIDATE; (b) pair the gate with a NON-event entry (event adds nothing); (c) add Bybit+OKX L2 for cross-venue confirmation inside allowed regimes.

FINAL_ARTIFACTS_LOCATION:
- main_folder: reports/strict_short_permission_gate_v6/
- gate_features: GATE_FEATURES_V6.csv (+ GATE_FEATURE_DEFINITIONS_V6.md)
- gate_rules: GATE_RULES_V6.json/.md
- trend_up_block_test: TREND_UP_STRICT_BLOCK_TEST.csv/.md
- downtrend_retention_test: DOWNTREND_RETENTION_TEST_V6.csv/.md
- range_bounce_block_test: RANGE_BOUNCE_BLOCK_TEST_V6.csv/.md
- edge_decomposition: GATE_EDGE_DECOMPOSITION.csv/.md
- gate_scorecard: GATE_SCORECARD_V6.csv
- gate_decisions: GATE_DECISIONS_V6.md
- comparison_with_v5: COMPARISON_WITH_V5.md
- final_report: STRICT_SHORT_PERMISSION_GATE_V6_FINAL_REPORT.md