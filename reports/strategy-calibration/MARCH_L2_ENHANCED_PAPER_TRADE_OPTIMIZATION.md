# L2-enhanced paper trade optimization (leak-free at confirm)

**Build:** 2026-05-26T14:32:37+00:00
**Models:** 120 (top L2-enhanced selectors × 4 entries × 3 stops)

## Top 20 by winrate (>=20 trades)

| selector | entry | stop | trades | winrate % | exp aft % | PF aft | maxCL |
|---|---|---|---:|---:|---:|---:|---:|
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.5 | 25 | 56.0 | 0.4417 | 1.725 | 3 |
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_15m | stop_1.5 | 25 | 56.0 | 0.4506 | 1.743 | 4 |
| `L2::P::taker_total_vol_15m_le_69071.8+taker_imb_aligned_60m_le_-0.0591::top1` | delay_10m | stop_1.5 | 27 | 55.56 | 0.3706 | 1.559 | 4 |
| `L2::P::taker_total_vol_15m_le_105386.84+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.5 | 27 | 55.56 | 0.4849 | 1.871 | 3 |
| `L2::P::local_range_180m_pct_le_1.0518+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.5 | 27 | 55.56 | 0.4618 | 1.796 | 3 |
| `L2::P::taker_total_vol_60m_le_291971.48+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.5 | 27 | 55.56 | 0.4618 | 1.796 | 3 |
| `L2::P::taker_total_vol_15m_le_105386.84+taker_imb_aligned_60m_le_-0.0591::top1` | delay_10m | stop_1.5 | 29 | 55.17 | 0.4013 | 1.642 | 7 |
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.25 | 25 | 52.0 | 0.4017 | 1.699 | 4 |
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_5m | stop_1.25 | 25 | 52.0 | 0.4077 | 1.72 | 4 |
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_5m | stop_1.5 | 25 | 52.0 | 0.3077 | 1.462 | 4 |
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_10m | stop_1.5 | 25 | 52.0 | 0.3021 | 1.446 | 4 |
| `L2::P::taker_total_vol_15m_le_69071.8+taker_imb_aligned_60m_le_-0.0591::top1` | delay_15m | stop_1.5 | 27 | 51.85 | 0.2409 | 1.333 | 4 |
| `L2::P::taker_total_vol_15m_le_105386.84+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.25 | 27 | 51.85 | 0.4386 | 1.821 | 4 |
| `L2::P::taker_total_vol_15m_le_105386.84+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_15m | stop_1.5 | 27 | 51.85 | 0.3681 | 1.603 | 4 |
| `L2::P::local_range_180m_pct_le_1.0518+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.25 | 27 | 51.85 | 0.4247 | 1.775 | 4 |
| `L2::P::local_range_180m_pct_le_1.0518+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_15m | stop_1.5 | 27 | 51.85 | 0.35 | 1.556 | 4 |
| `L2::P::taker_total_vol_60m_le_291971.48+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.25 | 27 | 51.85 | 0.4247 | 1.775 | 4 |
| `L2::P::taker_total_vol_60m_le_291971.48+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_15m | stop_1.5 | 27 | 51.85 | 0.35 | 1.556 | 4 |
| `L2::P::taker_total_vol_15m_le_105386.84+taker_imb_aligned_60m_le_-0.0591::top1` | delay_10m | stop_1.25 | 29 | 51.72 | 0.3754 | 1.64 | 7 |
| `L2::P::taker_total_vol_15m_le_105386.84+taker_imb_aligned_60m_le_-0.0591::top1` | delay_15m | stop_1.5 | 29 | 51.72 | 0.2823 | 1.415 | 7 |

## Top 20 by winrate (any size)
| selector | entry | stop | trades | winrate % | exp aft % | PF aft |
|---|---|---|---:|---:|---:|---:|
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.5 | 25 | 56.0 | 0.4417 | 1.725 |
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_15m | stop_1.5 | 25 | 56.0 | 0.4506 | 1.743 |
| `L2::P::taker_total_vol_15m_le_69071.8+taker_imb_aligned_60m_le_-0.0591::top1` | delay_10m | stop_1.5 | 27 | 55.56 | 0.3706 | 1.559 |
| `L2::P::taker_total_vol_15m_le_105386.84+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.5 | 27 | 55.56 | 0.4849 | 1.871 |
| `L2::P::local_range_180m_pct_le_1.0518+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.5 | 27 | 55.56 | 0.4618 | 1.796 |
| `L2::P::taker_total_vol_60m_le_291971.48+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.5 | 27 | 55.56 | 0.4618 | 1.796 |
| `L2::P::taker_total_vol_15m_le_105386.84+taker_imb_aligned_60m_le_-0.0591::top1` | delay_10m | stop_1.5 | 29 | 55.17 | 0.4013 | 1.642 |
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.25 | 25 | 52.0 | 0.4017 | 1.699 |
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_5m | stop_1.25 | 25 | 52.0 | 0.4077 | 1.72 |
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_5m | stop_1.5 | 25 | 52.0 | 0.3077 | 1.462 |
| `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_10m | stop_1.5 | 25 | 52.0 | 0.3021 | 1.446 |
| `L2::P::taker_total_vol_15m_le_69071.8+taker_imb_aligned_60m_le_-0.0591::top1` | delay_15m | stop_1.5 | 27 | 51.85 | 0.2409 | 1.333 |
| `L2::P::taker_total_vol_15m_le_105386.84+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.25 | 27 | 51.85 | 0.4386 | 1.821 |
| `L2::P::taker_total_vol_15m_le_105386.84+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_15m | stop_1.5 | 27 | 51.85 | 0.3681 | 1.603 |
| `L2::P::local_range_180m_pct_le_1.0518+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.25 | 27 | 51.85 | 0.4247 | 1.775 |
| `L2::P::local_range_180m_pct_le_1.0518+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_15m | stop_1.5 | 27 | 51.85 | 0.35 | 1.556 |
| `L2::P::taker_total_vol_60m_le_291971.48+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.25 | 27 | 51.85 | 0.4247 | 1.775 |
| `L2::P::taker_total_vol_60m_le_291971.48+dist_to_recent_swing_high_pct_le_0.321::top1` | delay_15m | stop_1.5 | 27 | 51.85 | 0.35 | 1.556 |
| `L2::P::taker_total_vol_15m_le_105386.84+taker_imb_aligned_60m_le_-0.0591::top1` | delay_10m | stop_1.25 | 29 | 51.72 | 0.3754 | 1.64 |
| `L2::P::taker_total_vol_15m_le_105386.84+taker_imb_aligned_60m_le_-0.0591::top1` | delay_15m | stop_1.5 | 29 | 51.72 | 0.2823 | 1.415 |