# A. TD-SHORT setup module — specification

**Build:** 2026-06-04T17:35:03+00:00

Trade model UNCHANGED: TP 2%, SL 1.5%, 24h timeout, cost 0.14%.

## Mandatory gates
- regime == TREND_DOWN (prior_move_1d_pct < -2.5%)
- direction == SHORT (zoneType DISTRIBUTION)
- prior_move_60m_pct < 0  (fresh weakness continuation; strongest signal d=-1.74)
- NOT buyer_absorption (eng_ofi <= 0.2 AND supportive_taker_imb_15m >= -0.1)

## Optional confluence (need >= 2 of 4)
- rejection_proof (reclaim_zoneMid==1)
- taker_sell (supp_taker_imb_15m>0)
- microprice_down (microprice_aligned_5m_bps>=0)
- thin_bid_path (void>=0.5 AND no large walls)

## Reject rules
- prior_move_60m_pct > 0 (shorting a bounce)
- buyer_absorption (OFI>0.2 or taker buy-dominant)
- no rejection proof + weak confluence (<2)
- thick bid support / large bid wall on path
- duplicate same-direction cluster within cooldown

## Selection
- live-valid first-eligible, max 2/day/venue, cluster cooldown 120m, no-trade allowed
