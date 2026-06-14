# Dynamic L2 paper trade optimization (leak-free at confirm)

**Build:** 2026-05-26T22:03:00+00:00
**Models:** 180

## Top 30 by winrate (>=20 trades)

| selector | entry | stop | trades | winrate % | exp aft % | PF aft | maxCL |
|---|---|---|---:|---:|---:|---:|---:|
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | confirmed | stop_1.5 | 29 | 58.62 | 0.5268 | 1.922 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | delay_15m | stop_1.5 | 29 | 55.17 | 0.408 | 1.648 | 3 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | confirmed | stop_1.25 | 29 | 55.17 | 0.4923 | 1.909 | 3 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.4051 | 1.646 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | delay_15m | stop_1.5 | 29 | 51.72 | 0.3198 | 1.479 | 4 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | confirmed | stop_1.25 | 29 | 51.72 | 0.4163 | 1.756 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | confirmed | stop_1.5 | 29 | 51.72 | 0.3215 | 1.498 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | delay_5m | stop_1.25 | 29 | 51.72 | 0.4013 | 1.715 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | delay_5m | stop_1.5 | 29 | 51.72 | 0.3064 | 1.467 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.286 | 1.419 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_1.062+utc_hour_le_4.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.377 | 1.602 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_1.062+utc_hour_le_8.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.4108 | 1.681 | 3 |
| `DL2::P::prior_move_180m_pct_ge_-0.4872+utc_hour_le_4.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.377 | 1.602 | 3 |
| `DL2::P::prior_move_180m_pct_ge_-0.4872+utc_hour_le_8.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.4108 | 1.681 | 3 |
| `DL2::P::dist_to_4h_mean_pct_ge_-0.338+utc_hour_le_4.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.377 | 1.602 | 3 |
| `DL2::P::dist_to_4h_mean_pct_ge_-0.338+utc_hour_le_8.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.4108 | 1.681 | 3 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | confirmed | stop_1.0 | 29 | 51.72 | 0.4744 | 1.957 | 3 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | delay_5m | stop_1.25 | 29 | 51.72 | 0.3793 | 1.644 | 4 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | delay_10m | stop_1.25 | 29 | 51.72 | 0.4664 | 1.826 | 3 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.3716 | 1.563 | 3 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | delay_15m | stop_1.5 | 29 | 51.72 | 0.3649 | 1.547 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.6499+utc_hour_le_4.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.377 | 1.602 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.6499+utc_hour_le_4.0::top1` | delay_15m | stop_1.5 | 29 | 51.72 | 0.3964 | 1.63 | 3 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | confirmed | stop_1.0 | 29 | 48.28 | 0.4145 | 1.837 | 4 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | confirmed | stop_1.25 | 29 | 48.28 | 0.3204 | 1.543 | 4 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | confirmed | stop_1.5 | 29 | 48.28 | 0.2256 | 1.33 | 4 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | delay_5m | stop_1.25 | 29 | 48.28 | 0.3148 | 1.534 | 4 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | delay_5m | stop_1.5 | 29 | 48.28 | 0.2199 | 1.322 | 4 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | delay_10m | stop_1.5 | 29 | 48.28 | 0.1991 | 1.278 | 4 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | delay_15m | stop_1.25 | 29 | 48.28 | 0.2997 | 1.481 | 4 |

## Top 20 by winrate (any size)
| selector | entry | stop | trades | winrate % | exp aft % | PF aft |
|---|---|---|---:|---:|---:|---:|
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | confirmed | stop_1.5 | 29 | 58.62 | 0.5268 | 1.922 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | delay_15m | stop_1.5 | 29 | 55.17 | 0.408 | 1.648 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | confirmed | stop_1.25 | 29 | 55.17 | 0.4923 | 1.909 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | delay_5m | stop_1.5 | 29 | 55.17 | 0.4051 | 1.646 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | delay_15m | stop_1.5 | 29 | 51.72 | 0.3198 | 1.479 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | confirmed | stop_1.25 | 29 | 51.72 | 0.4163 | 1.756 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | confirmed | stop_1.5 | 29 | 51.72 | 0.3215 | 1.498 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | delay_5m | stop_1.25 | 29 | 51.72 | 0.4013 | 1.715 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | delay_5m | stop_1.5 | 29 | 51.72 | 0.3064 | 1.467 |
| `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_4.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.286 | 1.419 |
| `DL2::P::dist_to_recent_swing_high_pct_le_1.062+utc_hour_le_4.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.377 | 1.602 |
| `DL2::P::dist_to_recent_swing_high_pct_le_1.062+utc_hour_le_8.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.4108 | 1.681 |
| `DL2::P::prior_move_180m_pct_ge_-0.4872+utc_hour_le_4.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.377 | 1.602 |
| `DL2::P::prior_move_180m_pct_ge_-0.4872+utc_hour_le_8.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.4108 | 1.681 |
| `DL2::P::dist_to_4h_mean_pct_ge_-0.338+utc_hour_le_4.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.377 | 1.602 |
| `DL2::P::dist_to_4h_mean_pct_ge_-0.338+utc_hour_le_8.0::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.4108 | 1.681 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | confirmed | stop_1.0 | 29 | 51.72 | 0.4744 | 1.957 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | delay_5m | stop_1.25 | 29 | 51.72 | 0.3793 | 1.644 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | delay_10m | stop_1.25 | 29 | 51.72 | 0.4664 | 1.826 |
| `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1` | delay_10m | stop_1.5 | 29 | 51.72 | 0.3716 | 1.563 |