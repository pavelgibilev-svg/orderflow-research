# Precision frontier — dynamic L2 vs previous

**Build:** 2026-05-26T21:57:48+00:00

## Dynamic L2 frontier

| min_count | achieved_n | selector | precision % | recall % | wrong % | H1 prec | H2 prec | OF risk |
|---:|---:|---|---:|---:|---:|---:|---:|---|
| 5 | 5 | `DL2::T::prior_move_180m_pct_le_-0.4872+dist_to_4h_mean_pct_ge_-0.338+utc_hour_le_4.0` | 60.0 | 2.44 | 0.0 | 100.0 | 50.0 | HIGH |
| 10 | 28 | `DL2::P::dist_to_recent_swing_high_pct_le_0.321+prior_move_180m_pct_le_0.5155::top1` | 50.0 | 11.38 | 0.0 | 46.15 | 53.33 | MEDIUM |
| 15 | 28 | `DL2::P::dist_to_recent_swing_high_pct_le_0.321+prior_move_180m_pct_le_0.5155::top1` | 50.0 | 11.38 | 0.0 | 46.15 | 53.33 | MEDIUM |
| 20 | 28 | `DL2::P::dist_to_recent_swing_high_pct_le_0.321+prior_move_180m_pct_le_0.5155::top1` | 50.0 | 11.38 | 0.0 | 46.15 | 53.33 | MEDIUM |
| 25 | 28 | `DL2::P::dist_to_recent_swing_high_pct_le_0.321+prior_move_180m_pct_le_0.5155::top1` | 50.0 | 11.38 | 0.0 | 46.15 | 53.33 | MEDIUM |
| 29 | 29 | `DL2::P::dist_to_recent_swing_high_pct_le_0.321+utc_hour_le_8.0::top1` | 48.28 | 11.38 | 3.45 | 42.86 | 53.33 | MEDIUM |
| 40 | 58 | `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top2` | 34.48 | 16.26 | 10.34 | 35.71 | 33.33 | LOW |
| 60 | 84 | `DL2::P::dist_to_recent_swing_high_pct_le_0.321+dl2_net_supportive_flow_60m_le_-258.02` | 26.19 | 17.89 | 10.71 | 23.91 | 28.95 | LOW |

## Previous frontier (no dynamic L2)

| min_count | achieved_n | selector | precision % |
|---:|---:|---|---:|
| 5 | 13 | `TREE::leaf_1::pct_opposite_move_already_done > 66.04 AND local_realized_vol_180m <= 0.00064` | 69.23 |
| 10 | 13 | `TREE::leaf_1::pct_opposite_move_already_done > 66.04 AND local_realized_vol_180m <= 0.00064` | 69.23 |
| 15 | 29 | `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | 48.28 |
| 20 | 29 | `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | 48.28 |
| 25 | 29 | `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | 48.28 |
| 29 | 29 | `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | 48.28 |
| 40 | 58 | `S::dist_to_recent_swing_high_pct_le_0.4616::top2` | 36.21 |
| 60 | 60 | `T::score_trigger_le_0.9737+pct_correct_move_already_done_le_0.0+is_asia_session_TRUE` | 28.33 |

## Improvement at min 20: **+1.72 pp**