# OKX March OI/funding fuel features

**Build:** 2026-05-30T07:31:29+00:00

## TRUE OI (daily, OKX rubik, USD aggregate BTC)
- oi_at_signal_usd, oi_delta_1d_usd, oi_pct_delta_1d, oi_pct_delta_3d, oi_zscore_14d
- price+OI daily regime flags (price_up_oi_up etc; price proxy = prior_move_180m sign)
- **Daily granularity → no 5m/15m/30m/60m OI deltas possible for March.**

## Funding (8h, OKX public)
- funding_rate_at_signal, funding_zscore_7d, funding_regime, funding_abs_extreme

## FLOW_PROXY (intraday, from trades — explicitly NOT OI)
- flow_taker_imb_15m/30m_z, flow_supp_minus_opp_15m_z, flow_vol_anomaly_15m_z

**TRUE_OI_FEATURES_BUILT = YES (daily) ; FLOW_PROXY_NOT_TRUE_OI = YES**
