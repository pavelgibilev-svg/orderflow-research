# Winners vs Losers feature comparison (29 selected paper trades)

**Build:** 2026-05-26T13:03:17+00:00
**Winners: 18; Losers + Timeouts: 11**

## Top 30 most-separating features

| feature | type | winners | losers | sep |
|---|---|---:|---:|---:|
| `cand_bid_refill_score` | num | 0.4989 | 0.5018 | d=-0.8243 |
| `local_range_60m_pct` | num | 0.6125 | 0.3456 | d=0.7675 |
| `vol_anomaly_15m_vs_bg` | num | 1.4081 | 0.7538 | d=0.7311 |
| `local_realized_vol_30m` | num | 0.0006 | 0.0005 | d=0.7238 |
| `local_realized_vol_60m` | num | 0.0006 | 0.0005 | d=0.668 |
| `local_range_30m_pct` | num | 0.5137 | 0.3053 | d=0.6602 |
| `local_realized_vol_180m` | num | 0.0007 | 0.0005 | d=0.6569 |
| `local_realized_vol_15m` | num | 0.0006 | 0.0005 | d=0.6373 |
| `prior_move_15m_pct` | num | 0.1774 | -0.0099 | d=0.6278 |
| `trig_flow_multiplier` | num | 3.7174 | 2.3685 | d=0.6142 |
| `cand_refill_with` | num | 0.4997 | 0.5014 | d=-0.5908 |
| `abs_dist_to_4h_mean_pct` | num | 0.2137 | 0.0945 | d=0.5854 |
| `prior_move_30m_pct` | num | 0.1696 | -0.0228 | d=0.5821 |
| `abs_prior_move_60m_pct` | num | 0.3317 | 0.1735 | d=0.5708 |
| `abs_prior_move_180m_pct` | num | 0.3371 | 0.1598 | d=0.5604 |
| `local_range_180m_pct` | num | 0.7781 | 0.5041 | d=0.5536 |
| `dist_to_recent_swing_low_pct` | num | 0.4736 | 0.2678 | d=0.5397 |
| `cand_up_move_pct` | num | 0.001 | 0.0 | d=0.5303 |
| `taker_total_vol_60m` | num | 210585.0528 | 121607.0282 | d=0.5186 |
| `trig_break_pct` | num | 0.103 | 0.0751 | d=0.4905 |
| `prior_move_60m_pct` | num | 0.1752 | -0.0061 | d=0.488 |
| `cand_prior_move_pct` | num | 0.0007 | 0.0 | d=0.4745 |
| `taker_total_vol_15m` | num | 103527.7217 | 51712.4727 | d=0.4703 |
| `cand_down_move_pct` | num | 0.0005 | 0.0001 | d=0.4593 |
| `prior_move_180m_pct` | num | 0.1561 | -0.029 | d=0.455 |
| `local_range_15m_pct` | num | 0.4092 | 0.2889 | d=0.4168 |
| `taker_imb_aligned_15m` | num | -0.0648 | -0.1223 | d=0.4083 |
| `trig_price` | num | 69737.0389 | 68868.8409 | d=0.4032 |
| `zone_width_pct` | num | 0.3824 | 0.2597 | d=0.3859 |
| `dist_to_4h_mean_pct` | num | 0.0602 | -0.0417 | d=0.3836 |

## Notes
- Sample size 14 winners vs 15 losers is small — Cohen's d is noisy. Trust only |d| >= 0.5.
- This is a within-selector breakdown: ALL 29 zones already pass `score_trigger >= 1.0` and `top1/day`.