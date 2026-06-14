# V9 PHASE FEATURE DEFINITIONS (causal)

Build 2026-06-13T07:52:13+00:00 · phase-separation audit v9 · skeptical, not production.

All from minutes <= t. Phases: TREND_DOWN_ACTIVE_MARKDOWN, TREND_DOWN_ABSORPTION_REVERSAL,
RANGE_ACCUMULATION_UNDER_PRESSURE, RANGE_DISTRIBUTION_INTO_DEMAND, LOW_VOL_NO_CONTROL_CHOP, TREND_UP_NO_SHORT, UNKNOWN.
- direction: ret_180m (3h), ret_360m (6h). price_vs_vwap180. range_180m.
- markdown: below VWAP + making new 60m lows / weak bounce + CVD_60<0.
- absorption: still selling (CVD_60<0) BUT not new low AND price holds/bounces (up_from_low>0.6 or ret_30>=0).
- distribution: range + near highs/VWAP + rally failing (mid down, ret_30<=0.1).
- accumulation: range + near lows + sell pressure (CVD_60<0) but lows defended (not new low).
- low-vol/chop: range_180<0.9% or (|ret_3h|<0.3 and range_180<1.3%).

Ex-post outcomes (V4.outcome_short, mid TP2/SL1.5) are used ONLY for per-phase perf diagnostics, not for live classification.
