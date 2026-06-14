# V8 LEVEL DEFINITIONS

Build 2026-06-13T03:13:21+00:00 · research branch v8 · skeptical, not production.

Stops: STOP_1 failed-recovery high (max mid[t-15..t]); STOP_2 local swing high; STOP_3 VWAP invalidation; STOP_4 entry+2*ATR14; STOP_5 max(failed-recovery high, swing high).
Targets: TARGET_1..5 fixed 1.0/1.5/2.0/2.5/3.0%; TARGET_6 prior 240m local low; TARGET_7 nearest 60m downside structure.
RR filters: none / 1.2 / 1.5 / 2.0 (skip if target_dist/stop_dist < RR). Stops are distances ABOVE entry (short).
