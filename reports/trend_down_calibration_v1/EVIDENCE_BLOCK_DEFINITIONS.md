# EVIDENCE BLOCK DEFINITIONS (TREND_DOWN v1)

Build 2026-06-11T16:16:37+00:00 · scores 0=none,1=weak,2=med,3=strong, N/A=feature absent.

1. **effort_vs_result** — PROXY (no trades): L2 depth_imbalance vs price progress. SHORT: ask-heavy depth + weak bounce = high. True taker-effort N/A.
2. **absorption_refill** — PROXY: magnitude of depth_imbalance toward the defending side (bid refill after dip / ask refill after pop).
3. **initiative_control** — PROXY: depth_imbalance sign aligned with intended direction (seller initiative for SHORT).
4. **background_alignment** — prior 60m/180m move down for SHORT continuation (causal).
5. **not_overextended** — distance above recent low (SHORT) so there is room to TP2; penalize entries already at the low.
6. **liquidity_execution** — spread tight, top-10 depth present, update activity sufficient.

Reliable on this dataset: background_alignment, not_overextended, liquidity_execution, absorption_refill/initiative (L2 proxy).
N/A: effort_vs_result from real executions, taker imbalance, CVD, true volume (no in-window trades).