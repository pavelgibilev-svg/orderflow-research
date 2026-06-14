# COMPARISON WITH L2-ONLY v1

Build 2026-06-12T12:57:48+00:00 · v1 = reports/trend_down_calibration_v1 (L2-proxy, Bybit-only).

## Did labels improve?
- UNKNOWN share: v1 52.8% (47/89) -> v2 77.2% (169/219)  => NOT reduced
- direction-blind bug (ACTIVE_MARKDOWN on LONG zones): v1 12 -> v2 0  => FIXED
- positive evidence blocks (sep>0) after real trades: [('Bybit', 'effort_vs_result', 0.19), ('Bybit', 'initiative_control', 0.6), ('OKX', 'effort_vs_result', 0.13), ('OKX', 'initiative_control', 0.32)]
- tradeable/RESEARCH_CANDIDATE filters: NONE
- overall conclusion still negative? YES for a standalone short ENTRY (no RESEARCH_CANDIDATE, baseline PF 0.72). BUT three real gains from trades:
  (a) direction-blind classifier FIXED (12 -> 0 LONG-as-markdown);
  (b) evidence blocks initiative_control (+0.60 Bybit / +0.32 OKX) and effort_vs_result (+0.19 / +0.13) are now POSITIVE on BOTH venues (v1 had none);
  (c) cross-venue confirmation is a real signal: CONFIRMED PF 0.90 vs DISAGREEMENT PF 0.53.
  Caveat: UNKNOWN ROSE 52.8% -> 77.2% (stricter direction-consistent conditions classify fewer clusters); markdown/unwind/absorption states need a different entry trigger than lower-high pivots (which bias to DISTRIBUTION).