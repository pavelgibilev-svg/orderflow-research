# GATE FEATURE DEFINITIONS (all causal, pre-event)

Build 2026-06-12T16:24:23+00:00 · research/calibration.

- ret_30m/60m/180m/360m/1d: prior price return over k minutes (higher-timeframe direction).
- price_vs_sma180_pct: mid vs 180-min mean (above => up bias).
- cvd_30m/60m/180m: CVD change over k minutes (seller control if <0).
- net_taker_60m: taker buy-sell volume over 60m (<0 = sell dominance).
- up_from_recent_low_pct: bounce size from the last-60m low (bounce danger).
- range_180m_pct: 180m high-low range (chop if large with ~0 net).
- bounce_danger: prior drop (ret180<-1) AND CVD stopped falling AND up_from_low>0.8.
- chop: |ret180|<0.5 with range180>1.5 (movement, no progress).
- uptrend: ret60>0.3 OR ret180>0.5 OR above sma180 OR cvd60>0.
- seller_control: net_taker_60m<0 AND ret60<0.
- downside_background: ret60<0 AND ret180<0 AND cvd60<0.

All computed only from minutes <= event minute. No future data. OKX single-venue (no L2 in control regimes).
