# GATE FEATURE DEFINITIONS v6 (causal, pre-minute)

Build 2026-06-12T16:45:47+00:00 · research/calibration.

- ret_30/60/180/360m: higher-timeframe returns (uptrend danger if any > 0).
- price_vs_vwap180_pct: mid vs 180-min volume-weighted price (above => up bias).
- cvd_60/180m, net_taker_60m: seller control if < 0.
- up_from_recent_low_pct: bounce size (danger if large).
- buy_recovery: net taker buy + CVD up over last 15m (buyers returning -> short danger).
- downside_progress: ret60<0 AND making new 60m lows.
- weak_bounce: up_from_low < 0.6.
- bounce_danger / chop / uptrend_danger / downtrend_perm / seller_ctrl_strict: composite flags.
All from minutes <= t. No future data. OKX single-venue (no L2).
