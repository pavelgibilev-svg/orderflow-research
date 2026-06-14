# C1. Binance 10d — local/daily background-normalized features

**Build:** 2026-06-02T14:02:11+00:00
Per-zone raw + day-cohort z-score (`__z_day`) + causal percentile-vs-prior-zones (uniqueness). Full data in CSV/JSON.

Confirmed zones: 153. Features: dl2_supp_minus_opp_net_flow_15m, dl2_microprice_aligned_delta_5m_bps, supportive_taker_imb_15m, taker_imbalance_15m, book_entropy_top25, spread_instability_5m_bps, depth_imbalance_top25, ms_thin_path_score, dl2_supp_refill_ratio_5m, eng_ofi, eng_refill, eng_void, eng_absorption, explainable_score
