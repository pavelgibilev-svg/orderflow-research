# Venue-normalized feature layer — Binance 10d

**Build:** 2026-06-02T16:57:17+00:00

Zones: 153 · features normalized: 19 · forms: pctile/z vs prior-60m/180m/7d/day, /median, /MAD (all causal, prior-only).

Flags: VENUE_NORMALIZED_FEATURES_BUILT=YES · ABSOLUTE_FEATURES_REPLACED=YES · NORMALIZATION_USES_ONLY_PRIOR_DATA=YES

Full per-zone table in CSV. Key replacement: absolute `dl2_supp_minus_opp_net_flow_15m<=4497.76` → `__pctile_prior<=75` (OKX p75) or `__z_prior<=0.468`.
