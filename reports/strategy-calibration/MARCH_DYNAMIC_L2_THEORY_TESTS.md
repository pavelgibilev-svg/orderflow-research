# Dynamic L2 theory tests (12 theories)

**Build:** 2026-05-26T21:57:40+00:00
**GOOD=123, BAD=774**

## T1: Good LONG = supportive add (bid refill) higher than BAD LONG (5m window)
- feature: dl2_inband_supp_add_5m
- good_mean: 2817006.4202
- bad_mean: 3110088.3967
- d: -0.1845
- verdict: weak

## T2: Good SHORT = supportive add (ask refill) higher than BAD SHORT
- feature: dl2_inband_supp_add_5m
- good_mean: 2753283.2315
- bad_mean: 3354890.4916
- d: -0.3247
- verdict: supported

## T3: Good zones have higher supportive top-1 persistence in 5m
- feature: dl2_top1_supportive_persistence_ge_50_5m_sec
- good_mean: 268.7561
- bad_mean: 250.8837
- d: 0.2571
- verdict: weak

## T4: BAD zones have higher opposing cancel volume (spoof / pull) — 15m
- feature: dl2_inband_opp_cancel_15m
- good_mean: 8268614.402
- bad_mean: 9867550.0586
- d: -0.3329
- verdict_inverse: supported (lower in GOOD)

## T5: Good zones have lower net opposing flow (liquidity void toward target) — 15m
- feature: dl2_net_opposing_flow_15m
- good_mean: 466.9741
- bad_mean: -351.9625
- d: 0.1827
- verdict_inverse: no

## T6: Good zones have stronger net supportive flow (15m)
- feature: dl2_net_supportive_flow_15m
- good_mean: 1664.5207
- bad_mean: 1018.6365
- d: 0.1204
- verdict: false

## T7: Good zones show supportive microprice drift (5m delta aligned)
- feature: dl2_microprice_aligned_delta_5m_bps
- good_mean: 2.6466
- bad_mean: 2.1763
- d: 0.1176
- verdict: false

## T8: Good zones show supportive microprice over 15m (book recovery)
- feature: dl2_microprice_aligned_delta_15m_bps
- good_mean: -1.0538
- bad_mean: 0.2512
- d: -0.0511
- verdict: false

## T9: Wrong-direction zones have HIGHER net opposing flow than GOOD
- feature: dl2_net_opposing_flow_15m
- good_mean: 466.9741
- wrong_mean: -765.9666
- d_good_vs_wrong: 0.2598
- verdict: weak

## T10: Strong flow alone is bad UNLESS paired with supportive bias
- feature: high flow split by supportive vs opposing dominance
- n_high_flow: 263
- high_flow_supp_dominant_good_pct: 3.85
- high_flow_opp_dominant_good_pct: 3.01
- verdict: diagnostic

## T11: Local-normalized supp refill (5m vs avg5m ratio) better than raw refill
- raw_d_good_vs_bad: -0.2518
- normalized_d_good_vs_bad: 0.0252
- verdict: diagnostic

## T12: Dynamic L2 features show |d| > snapshot L2 features
- comment: see MARCH_DYNAMIC_L2_FEATURE_SEPARATION top entries vs snapshot l2_imb5_aligned d (~0.05-0.15 in prior pass)
- verdict: see separation report
