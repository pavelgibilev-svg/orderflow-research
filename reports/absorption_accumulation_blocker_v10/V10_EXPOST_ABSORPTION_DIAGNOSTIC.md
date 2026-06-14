# V10 EX-POST ABSORPTION DIAGNOSTIC (future outcome — diagnostic only, NOT a live feature)

Build 2026-06-13T10:18:13+00:00 · absorption/accumulation blocker v10 · skeptical, not production.

Median forward 60m worst-case downside (most negative ret) for g6A-active minutes, blocker-fire vs not:
- TREND_DOWN_ACTIVE_MARKDOWN: b10E FIRES n=626 median_fwd_min -0.48%  |  NOT-fire n=1530 median_fwd_min -0.46%
- TREND_DOWN_ABSORPTION_REVERSAL: b10E FIRES n=71 median_fwd_min -0.94%  |  NOT-fire n=325 median_fwd_min -0.84%
- RANGE_ACCUMULATION_UNDER_PRESSURE: b10E FIRES n=670 median_fwd_min -0.27%  |  NOT-fire n=585 median_fwd_min -0.28%

Interpretation: if in ABSORPTION/ACCUMULATION the blocker-fire minutes have a LESS negative forward downside than not-fire minutes, the blocker is catching genuine absorption (price stops falling). In ACTIVE_MARKDOWN we WANT the opposite ordering / few fires (continuation should remain).
- ex-post ordering consistent with absorption in blocked phases: False.
