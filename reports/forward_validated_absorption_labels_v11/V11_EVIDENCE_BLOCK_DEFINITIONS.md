# V11 EVIDENCE BLOCK DEFINITIONS (causal, <=t; higher = more markdown-like)

Build 2026-06-13T10:39:27+00:00 · forward-validated absorption labels v11 · skeptical, not production.

- EFFORT_VS_RESULT: clip(disp_30m/0.6) — did recent selling actually displace price down.
- ABSORPTION_REFILL: 1 - clip(0.34*low_touches_30m + failed_breakdown) — defended/refilled lows lower the score.
- INITIATIVE_CONTROL: below-VWAP + selling last 15m + no VWAP reclaim -> seller initiative.
- BACKGROUND_ALIGNMENT: clip(0.5 + (-ret_180m)/4) — downtrend background.
- EXTENSION_NOT_LATE: 1 - clip((dist_below_vwap-0.6)/1.6) — penalise overextension below VWAP.
- EXECUTION_QUALITY: trade-count & ATR viability proxy (NOT a markdown separator; L2/spread only in 3 windows).
- COMBINED = mean(EFFORT,REFILL,INITIATIVE,BACKGROUND,EXTENSION). Outside layer sees blocks, not raw conditions.
