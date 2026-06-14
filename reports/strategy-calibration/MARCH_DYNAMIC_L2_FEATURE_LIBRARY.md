# Dynamic L2 feature library

**Build:** 2026-05-26T21:57:39+00:00
**Total dynamic L2 features:** 183

## Feature groups

### Microprice evolution
- `dl2_microprice_now`, `dl2_microprice_dev_now_bps`
- `dl2_microprice_delta_1m_bps` ... `dl2_microprice_delta_60m_bps`
- `dl2_microprice_aligned_delta_*_bps` (positive = supportive for direction)
- `dl2_microprice_slope_5m_bps_per_min`, `dl2_microprice_slope_5m_aligned_*`

### Spread evolution
- `dl2_spread_now_bps`, `dl2_spread_mean_5m_bps`, `dl2_spread_max_5m_bps`

### Top-1 (wall persistence proxy)
- `dl2_top1_bid_now`, `dl2_top1_ask_now`
- `dl2_top1_supportive_persistence_ge_50_5m_sec` (seconds in last 5m where supportive top-1 size >= 50)

### Global flow per window (1m / 5m / 15m / 30m / 60m)
- `dl2_add_vol_bid_*`, `dl2_add_vol_ask_*`, `dl2_cancel_vol_bid_*`, `dl2_cancel_vol_ask_*`
- `dl2_n_add_*`, `dl2_n_cancel_*`
- `dl2_n_large_add_*`, `dl2_n_large_cancel_*` (delta >= 20 lots)

### Direction-aligned global flow
- `dl2_supportive_add_vol_*`, `dl2_opposing_add_vol_*`
- `dl2_supportive_cancel_vol_*`, `dl2_opposing_cancel_vol_*`
- `dl2_net_supportive_flow_*`, `dl2_net_opposing_flow_*`, `dl2_supp_minus_opp_net_flow_*`
- `dl2_supportive_large_add_*`, `dl2_supportive_large_cancel_*` etc.

### In-band features (events near zone bounds)
- `dl2_inband_n_events_*`
- `dl2_inband_add_vol_*`, `dl2_inband_cancel_vol_*`
- `dl2_inband_supp_add_*`, `dl2_inband_opp_add_*`, `dl2_inband_supp_cancel_*`, `dl2_inband_opp_cancel_*`
- `dl2_inband_supp_minus_opp_add_*`
- `dl2_inband_supp_refill_ratio_*` (supp adds / supp cancels)

### Normalized vs background
- `dl2_*_5m_vs_avg5m_ratio` (5m value / (60m / 12) — fast-vs-baseline ratio)

## Features NOT extracted (and why)
- Per-level wall lifetime (would need full per-level history per day, ~200 MB extra RAM).
- Cancel-replace disambiguation (no add-cancel matching in incremental data).
- Sweep / reclaim L2-event-level (trades-based version `sweep_reclaim_aligned` already available).
- Depth recovery time after trade hit (would need trade-book correlation).
