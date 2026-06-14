# Orderflow theory tests (10 theories)

**Build:** 2026-05-26T11:40:11+00:00
**GOOD=123, BAD=774, wrong=139, missed=539, late=96**
**LONG=508, SHORT=535, H1=506, H2=537**

## Theory 1: Good zones have stronger local absorption anomaly (15m vs 30-180m background).
- feature: `vol_anomaly_15m_vs_bg`
  - good_mean: 3.4083
  - bad_mean: 2.7776
  - d_good_vs_bad: 0.068
  - LONG: good_mean=2.8753, bad_mean=2.5826, d=0.0347
  - SHORT: good_mean=3.9621, bad_mean=2.9632, d=0.0997
  - H1: good_mean=3.0842, bad_mean=3.6558, d=-0.0441
  - H2: good_mean=3.7864, bad_mean=2.0029, d=0.5643
  - **verdict:** no

## Theory 2: Good LONG zones show sell absorption + bid refill + OFI recovery (proxy: aligned taker imb 30m).
- feature: `taker_imb_aligned_30m (LONG only)`
  - good_mean: -0.0096
  - bad_mean: -0.0014
  - d_good_vs_bad: -0.0594
  - **verdict:** no

## Theory 3: Good SHORT zones show buy absorption + ask refill + OFI deterioration (proxy: aligned taker imb 30m).
- feature: `taker_imb_aligned_30m (SHORT only)`
  - good_mean: -0.0521
  - bad_mean: 0.0024
  - d_good_vs_bad: -0.3767
  - **verdict:** yes

## Theory 4: Bad zones often appear after prior move exhaustion / overextension (|prior_move_180m|).
- feature: `abs(prior_move_180m_pct)`
  - good_mean_abs: 0.5887
  - bad_mean_abs: 0.8557
  - d_good_vs_bad_abs: -0.3388
  - **verdict:** no

## Theory 5: Wrong-direction zones occur during an opposite-direction 2% move.
- feature: `is_during_opposite_move`
  - good_freq_pct: 31.71
  - wrong_freq_pct: 79.86
  - missed_freq_pct: 3.71
  - **verdict:** yes

## Theory 6: Strong raw flow appearing AFTER >50% of correct move = anti-feature.
- feature: `is_late_after_50pct_correct_move`
  - good_late_count: 2
  - bad_late_count: 109
  - good_late_pct: 1.63
  - bad_late_pct: 14.08
  - **verdict:** yes

## Theory 7: Good zones have lower local 180m range (cleaner context).
- feature: `local_range_180m_pct`
  - good_mean: 1.2194
  - bad_mean: 1.5772
  - d_good_vs_bad: -0.3731
  - **verdict:** yes

## Theory 8: Good zones appear closer to recent 4h mean / VWAP-proxy than bad zones.
- feature: `abs(dist_to_4h_mean_pct)`
  - good_mean_abs: 0.3835
  - bad_mean_abs: 0.5821
  - d_good_vs_bad_abs: -0.3956
  - **verdict:** yes

## Theory 9: slow_trigger zones (>60min confirm→trigger) may still be good watch-zones.
- feature: `confirm_to_trigger_min>60`
  - good_slow_count: 19
  - bad_slow_count: 129
  - good_slow_pct: 15.45
  - bad_slow_pct: 16.67
  - **verdict:** diagnostic

## Theory 10: Confirmed stage is useful only with additional scoring (baseline precision << good zones rate).
- feature: `raw confirmed = baseline`
  - baseline_precision_pct: 11.79
  - **verdict:** yes (baseline only 11-12% precision)
