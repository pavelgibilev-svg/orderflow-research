# COMPARISON WITH v4 (no gate)

Build 2026-06-12T16:24:24+00:00 · research/calibration.

- v4: event trigger with NO gate -> shorts TREND_UP and loses (PF ~0.18); event PF in DOWN below random.
- v5 best gate **GATE_5_COMBINED**: blocks 62.4% of TREND_UP shorts; random+gate PF 1.638 vs random_all PF 1.416.
- fewer TREND_UP shorts? YES.
- DOWN shorts retained? 47.1%.
- edge over random? gate_helps=True, event_adds_over_random+gate=False.
- honest read: a permission gate is the missing layer (it removes UP/RANGE shorting), but the event ENTRY still adds little over random within the allowed regime.
