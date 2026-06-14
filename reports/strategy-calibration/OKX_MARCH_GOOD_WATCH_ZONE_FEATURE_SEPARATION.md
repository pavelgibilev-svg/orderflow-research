# Feature separation (GOOD vs BAD watch-zones)

**Build:** 2026-05-25T15:31:41+00:00
**GOOD:** 123  **BAD:** 774  **MID:** 146
**wrong_direction:** 139  **missed_no_move:** 539  **late:** 96

## Top discriminating features (sorted by |GOOD vs BAD| separation)

| feature | type | good | bad | wrong | missed | late | d(good vs bad) |
|---|---|---:|---:|---:|---:|---:|---:|
| `local_range_180m_pct` | num | 1.2194 | 1.5772 | 1.7283 | 1.4763 | 1.9247 | -0.3731 |
| `prior_move_60m_pct` | num | 0.1363 | -0.0379 | 0.1168 | -0.1008 | 0.0914 | 0.2629 |
| `trig_break_pct` | num | 0.2743 | 0.2118 | 0.1657 | 0.224 | 0.2025 | 0.2575 |
| `local_range_60m_pct` | num | 0.8411 | 0.9775 | 1.0298 | 0.9161 | 1.2468 | -0.2565 |
| `prior_move_30m_pct` | num | 0.0889 | -0.0145 | 0.0994 | -0.0495 | 0.017 | 0.2377 |
| `local_range_30m_pct` | num | 0.5941 | 0.6706 | 0.6918 | 0.6369 | 0.8288 | -0.2131 |
| `local_realized_vol_15m` | num | 0.0006 | 0.0007 | 0.0007 | 0.0007 | 0.0008 | -0.2003 |
| `local_realized_vol_30m` | num | 0.0007 | 0.0007 | 0.0007 | 0.0007 | 0.0009 | -0.1819 |
| `prior_move_15m_pct` | num | 0.0364 | -0.008 | 0.0048 | -0.0123 | -0.0023 | 0.1656 |
| `local_range_15m_pct` | num | 0.3959 | 0.43 | 0.4494 | 0.412 | 0.5032 | -0.1447 |
| `local_realized_vol_60m` | num | 0.0007 | 0.0007 | 0.0007 | 0.0007 | 0.0009 | -0.1446 |
| `zone_width_pct` | num | 0.3564 | 0.4048 | 0.444 | 0.3939 | 0.4092 | -0.131 |
| `prior_move_180m_pct` | num | 0.1476 | 0.0051 | 0.4595 | -0.1463 | 0.1972 | 0.1251 |
| `local_realized_vol_180m` | num | 0.0007 | 0.0007 | 0.0008 | 0.0006 | 0.0008 | -0.1065 |
| `opp_dir_zones_active_60m` | num | 0.9187 | 0.9961 | 1.3669 | 0.9462 | 0.7396 | -0.072 |
| `trig_flow_multiplier` | num | 2.1545 | 2.0348 | 1.821 | 2.1278 | 1.859 | 0.0703 |
| `cand_pressure_against` | num | 0.6006 | 0.5972 | 0.5946 | 0.5995 | 0.5882 | 0.0692 |
| `score_ofi` | num | -0.0087 | 0.0052 | 0.0427 | -0.0052 | 0.0092 | -0.0685 |
| `cand_absorb_score` | num | 0.6523 | 0.6493 | 0.6488 | 0.6504 | 0.6438 | 0.0654 |
| `candidate_to_confirm_min` | num | 12.4951 | 11.8335 | 12.5429 | 11.9401 | 10.2076 | 0.0648 |
| `conf_age_min` | num | 12.4951 | 11.8335 | 12.5429 | 11.9401 | 10.2076 | 0.0648 |
| `conf_defended_persistence_sec` | num | 749.7073 | 710.009 | 752.5755 | 716.4063 | 612.4583 | 0.0648 |
| `filter_kept` | bool | 26.02% | 20.03% | 20.14% | 18.37% | 29.17% | 5.99 pp |
| `conf_cycles_seen` | num | 53.4309 | 56.2351 | 44.9137 | 59.7347 | 52.9792 | -0.0574 |
| `filter_dup_suppressed` | bool | 21.95% | 27.52% | 17.27% | 25.79% | 52.08% | -5.57 pp |
| `same_dir_zones_active_60m` | num | 0.8293 | 0.8695 | 0.8993 | 0.8609 | 0.875 | -0.0415 |
| `conf_opposite_thinning` | num | 0.5002 | 0.5003 | 0.5003 | 0.5003 | 0.5001 | -0.0377 |
| `confirm_to_trigger_min` | num | 61.5052 | 65.0005 | 43.9167 | 80.0453 | 26.56 | -0.0368 |
| `total_pre_trigger_min` | num | 72.7432 | 75.746 | 54.9437 | 90.7258 | 37.3303 | -0.0312 |
| `cand_prior_move_pct` | num | 0.0003 | 0.0002 | 0.0002 | 0.0003 | 0.0001 | 0.0285 |