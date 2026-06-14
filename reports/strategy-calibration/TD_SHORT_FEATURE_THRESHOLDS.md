# B. TD-short feature thresholds (from existing pool, not month-tuned)

**Build:** 2026-06-04T17:35:03+00:00
| feature | rule | win med | loss med | source | overfit | mandatory |
|---|---|--:|--:|---|:--:|:--:|
| prior_move_60m_pct | < 0 | -0.4284 | -0.4219 | STRONG-vs-WEAK d=-1.74 | LOW (sign-based) | YES |
| eng_ofi | <= 0.2 (no buy flow) | -0.0612 | -0.1056 | stop analysis: buyer_absorption | LOW (structural) | YES |
| supportive_taker_imb_15m | >= -0.1 (not buy-dominant) | -0.0541 | 0.0288 | buyer absorption reject | LOW | YES |
| reclaim_zoneMid_preconfirm | == 1 (rejection proof) | 1.0 | 0.0 | M1 57% wr | LOW (boolean) | OPTIONAL (confluence) |
| ms_thin_path_score+walls | void>=0.5 AND no large walls | 0.0958 | 0.0946 | M4 PF 3.63 (n=11) | MED (n small) | OPTIONAL |
| microprice_aligned_5m_bps | >= 0 (not against short) | 1.101 | 1.1755 | M3 PF 2.13 | LOW | OPTIONAL |
| cluster_cooldown | same dir + price band 0.5% within 120m -> suppress | None | None | dedup | LOW | YES (selection) |