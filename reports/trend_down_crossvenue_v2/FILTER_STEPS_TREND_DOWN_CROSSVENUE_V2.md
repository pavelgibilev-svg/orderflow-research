# FILTER STEPS — TREND_DOWN cross-venue v2

Build 2026-06-12T12:57:48+00:00 · RESEARCH/CALIBRATION (not production).

Candidate library (NOT production). TP=2%/SL=1.5%.

1. Level1=TREND_DOWN (window net<=-1% or prior move down).
2. Capital state (direction-aware).
3. Direction consistency (SHORT-state->SHORT; LONG absorption->reversal-watch).
4. Evidence blocks (real trades).
5. Cross-venue confirm/disagree.
6. Veto.
7. Decision.

## Filter decisions
- TD_ACTIVE_MARKDOWN_SHORT_TEMPLATE: **NEED_MORE_DATA** (n=0, hit2=0.0%, PF=None, windows=[])
- TD_DISTRIBUTION_INTO_BOUNCE_SHORT_TEMPLATE: **REJECT** (n=21, hit2=23.8%, PF=0.473, windows=['W1_NOVEMBER', 'W3_JANUARY', 'W4_APRIL'])
- TD_FORCED_UNWIND_CONTINUATION_SHORT_TEMPLATE: **NEED_MORE_DATA** (n=0, hit2=0.0%, PF=None, windows=[])
- TD_ABSORPTION_AFTER_SELL_PRESSURE_NO_SHORT_OR_REVERSAL_WATCH: **NEED_MORE_DATA** (n=0, hit2=0.0%, PF=None, windows=[])
- TD_NO_CONTROL_CHOP_NO_TRADE: **KEEP_AS_VETO** (n=29, hit2=24.1%, PF=0.529, windows=['W1_NOVEMBER', 'W3_JANUARY', 'W4_APRIL'])
- TD_CROSS_VENUE_CONFIRMED_MARKDOWN_SHORT: **QUARANTINE** (n=6, hit2=33.3%, PF=1.134, windows=['W1_NOVEMBER', 'W3_JANUARY'])
- TD_CROSS_VENUE_DISAGREEMENT_VETO: **KEEP_AS_VETO** (n=64, hit2=25.0%, PF=0.534, windows=['W1_NOVEMBER', 'W3_JANUARY', 'W4_APRIL'])
