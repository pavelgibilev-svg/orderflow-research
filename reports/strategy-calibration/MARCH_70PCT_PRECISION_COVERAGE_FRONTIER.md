# Precision/coverage frontier

**Build:** 2026-05-26T12:33:26+00:00

## Leak-free frontier (no future leak)

| min_count | achieved_n | selector | precision % | recall % | wrong % | H1 prec | H2 prec | OF risk |
|---:|---:|---|---:|---:|---:|---:|---:|---|
| 5 | 13 | `TREE::leaf_1::pct_opposite_move_already_done > 66.04 AND local_realized_vol_180m <= 0.00064` | 69.23 | None | None | None | None | HIGH |
| 10 | 13 | `TREE::leaf_1::pct_opposite_move_already_done > 66.04 AND local_realized_vol_180m <= 0.00064` | 69.23 | None | None | None | None | HIGH |
| 15 | 29 | `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | 48.28 | 11.38 | 0.0 | 50.0 | 46.67 | MEDIUM |
| 20 | 29 | `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | 48.28 | 11.38 | 0.0 | 50.0 | 46.67 | MEDIUM |
| 25 | 29 | `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | 48.28 | 11.38 | 0.0 | 50.0 | 46.67 | MEDIUM |
| 29 | 29 | `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | 48.28 | 11.38 | 0.0 | 50.0 | 46.67 | MEDIUM |
| 40 | 58 | `S::dist_to_recent_swing_high_pct_le_0.4616::top2` | 36.21 | 17.07 | 6.9 | 39.29 | 33.33 | LOW |
| 60 | 60 | `T::score_trigger_le_0.9737+pct_correct_move_already_done_le_0.0+is_asia_session_TRUE` | 28.33 | 13.82 | 13.33 | 39.29 | 18.75 | LOW |

## Oracle frontier (uses matched_move_size — LEAK)

| min_count | achieved_n | precision % | note |
|---:|---:|---:|---|
| 5 | 5 | 80.0 | uses matched_move_size_pct (LEAK) |
| 10 | 10 | 40.0 | uses matched_move_size_pct (LEAK) |
| 15 | 15 | 26.67 | uses matched_move_size_pct (LEAK) |
| 20 | 20 | 20.0 | uses matched_move_size_pct (LEAK) |
| 25 | 25 | 16.0 | uses matched_move_size_pct (LEAK) |
| 29 | 29 | 13.79 | uses matched_move_size_pct (LEAK) |
| 40 | 40 | 10.0 | uses matched_move_size_pct (LEAK) |
| 60 | 60 | 10.0 | uses matched_move_size_pct (LEAK) |

## Reading the frontier
- Leak-free precision peaks around **35-45 %** at the 20-40 count range. Beyond 60 it drifts back toward baseline 12 %.
- The oracle frontier proves >=70 % is data-attainable IF you know the future. Leak-free selectors are bounded much lower.