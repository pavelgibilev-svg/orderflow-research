# OKX March fuel feature evaluation

**Build:** 2026-05-30T07:31:32+00:00
**Enhanced 29: winners(hit_2pct)=18, non-winners=11**

| feature | win_mean | nonwin_mean | d(win vs nonwin) | n_win | n_nonwin |
|---|---:|---:|---:|---:|---:|
| `flow_taker_imb_30m_z` | -0.388011 | 0.239827 | -0.6303 | 18 | 11 |
| `oi_pct_delta_1d` | 0.954161 | -1.054818 | 0.5971 | 18 | 11 |
| `flow_supp_minus_opp_15m_z` | -0.115428 | -0.367164 | 0.5669 | 18 | 11 |
| `true_fuel_score` | 1.654256 | 1.434591 | 0.3207 | 18 | 11 |
| `flow_vol_anomaly_15m_z` | -0.061791 | -0.127488 | 0.3029 | 11 | 8 |
| `funding_zscore_7d` | -0.395694 | -0.156918 | -0.2656 | 18 | 11 |
| `funding_rate_at_signal` | -4e-06 | 4e-06 | -0.2393 | 18 | 11 |
| `dir_fuel_score` | -1.051589 | -1.776727 | 0.2289 | 18 | 11 |
| `oi_pct_delta_3d` | -0.068167 | 0.711073 | -0.1686 | 18 | 11 |
| `flow_taker_imb_15m_z` | 0.062756 | -0.008355 | 0.072 | 18 | 11 |
| `oi_zscore_14d` | -0.318628 | -0.273618 | -0.0546 | 18 | 11 |
| `funding_abs_extreme` | 3e-05 | 2.9e-05 | 0.0059 | 18 | 11 |

## Hypotheses
- **H1_high_fuel_increases_2pct**: d(true_fuel win vs nonwin)=0.3207 -> supported
- **H2_low_fuel_explains_no2pct**: supported
- **H3_funding_extreme_crowding**: d(funding_zscore win vs nonwin)=-0.2656 -> some signal
- **H4_price_oi_regime_setup**: diagnostic only (daily OI too coarse for setup-level timing)
- **H5_flow_proxy_not_oi**: YES (flow proxy built, labeled non-OI)