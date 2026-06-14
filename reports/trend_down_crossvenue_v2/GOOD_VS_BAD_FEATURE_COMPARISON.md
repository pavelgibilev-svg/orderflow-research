# GOOD vs BAD FEATURE COMPARISON (medians)

Build 2026-06-12T13:42:04+00:00 · cross-confirmed SHORT winners vs losers vs disagreement losers.
n: winners 28, confirmed-losers 48, disagreement-losers 26.

| feature | GOOD_winners | BAD_confirmed_losers | DISAGREEMENT_losers |
|---|--:|--:|--:|
| cvd_delta_60m | -391.4395 | 36.719 | -1255.8755 |
| taker_imb_30m | 0.0668 | 0.1031 | -0.0052 |
| net_taker_30m | 829.891 | 604.0745 | -39.0555 |
| sell_frac_30m | 0.4665 | 0.4485 | 0.5025 |
| effort_vs_result_raw | 0.0077 | 0.0149 | 0.0001 |
| price_change_30m | 0.1455 | 0.2095 | 0.254 |
| spread_bps | 0.012 | 0.012 | 0.016 |
| depth_imbalance | -0.0635 | 0.0201 | -0.0393 |
| trade_count_spike | 0.745 | 0.85 | 1.21 |
| dist_from_recent_low_pct | 0.764 | 1.027 | 1.5825 |
| dist_from_recent_high_pct | 0.6675 | 1.0175 | 1.4585 |
| bounce_into_pivot_pct | 0.41 | 0.5215 | 0.7085 |
| vol_30m_btc | 44405.653 | 31740.468 | 64711.0245 |
| local_vol_180m | 0.0815 | 0.0895 | 0.1225 |
| prior_move_60m | -0.157 | -0.163 | -0.3615 |
| effort_vs_result | 1.0 | 1.0 | 0.5 |
| absorption_refill | 1.0 | 2.0 | 1.0 |
| initiative_control | 2.0 | 0.5 | 2.0 |
| background_alignment | 1.0 | 1.0 | 2.0 |
| not_overextended | 1.5 | 2.0 | 3.0 |
| liquidity_execution | 3.0 | 3.0 | 3.0 |

_CVD during/after, refill-after-hit, post-flow price response are N/A here (need re-parse). volume_burst≈trade_count_spike, late-entry≈dist_from_recent_low/room-to-TP2._