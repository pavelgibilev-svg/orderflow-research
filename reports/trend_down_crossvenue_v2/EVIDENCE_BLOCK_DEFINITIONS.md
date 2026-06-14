# EVIDENCE BLOCK DEFINITIONS v2 (REAL trades)

Build 2026-06-12T12:57:48+00:00 · 0=none,1=weak,2=med,3=strong,N/A=uncomputable.

1. effort_vs_result — REAL: signed downside efficiency = (-price_change_30m)*(sell-buy)/vol over 30m. SHORT high = price fell on net selling; low = selling absorbed (no progress).
2. absorption_refill — L2 depth_imbalance magnitude toward the defending side (bid refill for long / ask for short markdown).
3. initiative_control — REAL: CVD_60m direction + taker_imbalance_30m aligned with intended direction.
4. background_alignment — prior 60m/180m move down for SHORT continuation (causal).
5. not_overextended — distance above recent low (SHORT) / below recent high (LONG): room to TP2.
6. liquidity_execution — spread tight + real 30m volume present + activity.

Now computed from REAL trades (no L2-only proxy for effort/initiative). N/A only when a field is genuinely absent.