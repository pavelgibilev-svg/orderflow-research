# F. TD-short OOS readiness plan

**Build:** 2026-06-04T17:35:04+00:00

## Data needed
- NEW OKX+Binance L2+trades overlap window (same dates)
- >=10 downtrend days OR >=20 TD-short candidates
- Binance: live recorder -> v3 pure-diff converter ONLY
- OKX: open public L2+trades (no Tardis)
- no threshold tuning on the new window

## Success criteria
- PF > 1.5
- winrate >= 50-55%
- max loss streak acceptable (<= ~5)
- no catastrophic counter-trend losses (MAE not >> SL)
- >=15-20 trades else mark UNKNOWN

## Frozen rules before OOS
- regime == TREND_DOWN (prior_move_1d_pct < -2.5%)
- direction == SHORT (zoneType DISTRIBUTION)
- prior_move_60m_pct < 0  (fresh weakness continuation; strongest signal d=-1.74)
- NOT buyer_absorption (eng_ofi <= 0.2 AND supportive_taker_imb_15m >= -0.1)
- rejection_proof (reclaim_zoneMid==1)
- taker_sell (supp_taker_imb_15m>0)
- microprice_down (microprice_aligned_5m_bps>=0)
- thin_bid_path (void>=0.5 AND no large walls)
