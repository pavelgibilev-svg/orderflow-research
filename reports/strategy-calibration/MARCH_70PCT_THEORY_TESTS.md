# 14 theory tests for 70 % goal

**Build:** 2026-05-26T12:33:22+00:00
**GOOD=123, BAD=774, wrong=139**
**LONG=508, SHORT=535, H1=506, H2=537**

## T1: Good LONG = sell absorption + bid refill + OFI recovery (proxy: aligned taker imb 30m + cand_sell_pressure)
- features: ['taker_imb_aligned_30m', 'cand_sell_pressure', 'ofi_shift_aligned']
- taker_imb_aligned_30m: {'good_mean': -0.0096, 'bad_mean': -0.0014, 'd': -0.0594}
- cand_sell_pressure: {'good_mean': 0.6009, 'bad_mean': 0.5945, 'd': 0.1452}
- ofi_shift_aligned: {'good_mean': -0.2305, 'bad_mean': -0.2186, 'd': -0.0647}
- verdict_taker_d: false
- verdict_ofi_d: false

## T2: Good SHORT = buy absorption + ask refill + OFI deterioration
- features: ['taker_imb_aligned_30m', 'cand_buy_pressure', 'ofi_shift_aligned']
- taker_imb_aligned_30m: {'good_mean': -0.0521, 'bad_mean': 0.0024, 'd': -0.3767}
- cand_buy_pressure: {'good_mean': 0.6002, 'bad_mean': 0.5998, 'd': 0.0082}
- ofi_shift_aligned: {'good_mean': -0.1757, 'bad_mean': -0.228, 'd': 0.2626}
- verdict_taker_d: supported

## T3: Good zones occur BEFORE impulse, not after prior overextension
- feature: abs_prior_move_180m_pct
- good_mean_abs: 0.5887
- bad_mean_abs: 0.8557
- d_abs: -0.3388
- verdict: supported (BAD has higher abs prior move)

## T4: Strong raw flow appearing late (after 50% of correct move) = anti-feature
- feature: is_late_after_50pct_correct_move
- good_freq_pct: 1.63
- bad_freq_pct: 14.08
- verdict: supported

## T5: Opposite-direction conflict (active opp zone OR opposite move) kills precision
- is_during_opposite_move: {'good_freq_pct': 31.71, 'bad_freq_pct': 17.18}
- opp_dir_zones_active_60m_mean_good: 0.9187
- opp_dir_zones_active_60m_mean_bad: 0.9961
- wrong_dir_during_opp_pct: 79.86
- verdict: supported (wrong-dir zones much more often during opposite move)

## T6: Asia session is genuinely better, not random
- asia_good_pct: 65.85
- asia_bad_pct: 36.3
- verdict: supported

## T7: Clean local range / low prior range helps
- feature: local_range_180m_pct
- good_mean: 1.2194
- bad_mean: 1.5772
- d: -0.3731
- verdict: supported

## T8: High-vol context (local realized vol) hurts; requires local-normalized thresholds
- feature: local_realized_vol_30m
- good_mean: 0.0007
- bad_mean: 0.0007
- d: -0.1819
- verdict: weak (cohen's d small)

## T9: Slow-trigger zones (confirm_to_trigger>60m) useful for watch but bad for trigger entry
- note: confirm_to_trigger_min is POST-confirm — diagnostic only, not selector feature.
- verdict: diagnostic only

## T10: Duplicate clusters: same-dir-active>1 contains followups but should be deduped
- n_in_clusters: 256
- good_in_clusters: 27
- bad_in_clusters: 176
- verdict: supported: same-dir cluster ratio similar to baseline — dedup helps signal-to-noise

## T11: Good zones are near recent 4h mean/VWAP-proxy
- feature: abs_dist_to_4h_mean_pct
- good_mean: 0.3835
- bad_mean: 0.5821
- d: -0.3956
- verdict: weak

## T12: Wrong-direction zones have identifiable conflict (during opposite move)
- wrong_during_opp_pct: 79.86
- good_during_opp_pct: 31.71
- verdict: supported (wrong-direction zones much more often during opposite move)

## T13: Current engine score_* are candidate-definition, not quality
- score_stats_good_bad_d: {'score_absorption': (0.6483, 0.6473, 0.0196), 'score_refill': (0.5002, 0.5003, -0.0279), 'score_ofi': (-0.0087, 0.0052, -0.0685), 'score_trigger': (0.9881, 0.9883, -0.0118), 'score_liquidity_void': (1.0, 1.0, None)}
- verdict: supported (all |d|<0.1)

## T14: Small confluence isolates high-prob zones
- confluence: filter_kept AND not_late AND not_during_opp AND opp_eq0
- n_selected: 74
- n_good: 18
- precision_pct: 24.32
- verdict: supported but precision still ~25-30 %, not 70 %
