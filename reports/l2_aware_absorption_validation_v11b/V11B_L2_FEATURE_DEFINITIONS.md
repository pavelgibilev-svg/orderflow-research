# V11B L2 FEATURE DEFINITIONS (causal, <=t; higher=markdown-like)

Build 2026-06-14T08:25:30+00:00 · L2-aware absorption validation v11b · skeptical, not production.

L2-FULL (reconstructed book, per-minute, within +-0.5%/0.25% bands):
- BID_REFILL: bid_d50[t] vs mean(bid_d50[t-8..t-3]); refilled bids under selling -> absorption -> low.
- BID_DEFENSE_NEAR_LOW: bid_d25 (close-in) recovery vs baseline.
- BOOK_THINNESS_BELOW: band imbalance (bid_d50-ask_d50)/sum; bids thin vs asks -> markdown.
- MICROPRICE_IMBALANCE: 5m mean top imbalance + microprice offset sign -> seller control.
- SPREAD_STABILITY: spread widening + depth collapse (risk/instability).
- PRICE_RESPONSE_L2: refill score gated by actual selling (cvd_15<0).
- L2FULL_COMBINED = mean(REFILL,DEFENSE,THINNESS,MICROPRICE,PRICE_RESPONSE).

L2-LIGHT (cached di top-of-book depth imbalance + spread; the only L2 the 3 v2okx down windows have):
- L2L_IMBALANCE_LEVEL / _PERSIST(10m mean) / _TREND(10m change) / _SPREAD(widening).
- L2LIGHT_COMBINED = mean(LEVEL,PERSIST,TREND). Orientation assumed di<0=down-lean; AUC MAGNITUDE (|AUC-0.5|) is the separation, sign is orientation.

All causal: book state and trades up to minute t only. Forward labels UNCHANGED from v11.
