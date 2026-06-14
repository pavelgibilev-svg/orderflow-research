# Exhaustive leak-free selector search

**Build:** 2026-05-26T12:33:26+00:00
**Total selectors evaluated:** 4315
**>=70 % precision with min 10:** False
**>=70 % precision with min 20:** False
**>=70 % precision with min 29:** False
**>=80 % precision with min 10:** False

## Best 5 selectors with selected >= 10
| selector | kind | n | /day | precision % | recall % | H1 prec | H2 prec |
|---|---|---:|---:|---:|---:|---:|---:|
| `TREE::leaf_1::pct_opposite_move_already_done > 66.04 AND local_realized_vol_180m <= 0.00064` | tree_leaf | 13 | 0.448 | 69.23 | None | None | None |
| `TREE::leaf_2::pct_opposite_move_already_done > 66.04 AND local_realized_vol_180m > 0.00064 AND utc_hour <= 8.0` | tree_leaf | 10 | 0.345 | 60.0 | None | None | None |
| `TREE::leaf_3::pct_opposite_move_already_done <= 66.04 AND pct_opposite_move_already_done > 39.88 AND prior_move_15m_pct > 0.059` | tree_leaf | 10 | 0.345 | 50.0 | None | None | None |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |

## Best 5 selectors with selected >= 15
| selector | kind | n | /day | precision % | recall % | H1 prec | H2 prec |
|---|---|---:|---:|---:|---:|---:|---:|
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |

## Best 5 selectors with selected >= 20
| selector | kind | n | /day | precision % | recall % | H1 prec | H2 prec |
|---|---|---:|---:|---:|---:|---:|---:|
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |

## Best 5 selectors with selected >= 25
| selector | kind | n | /day | precision % | recall % | H1 prec | H2 prec |
|---|---|---:|---:|---:|---:|---:|---:|
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |

## Best 5 selectors with selected >= 29
| selector | kind | n | /day | precision % | recall % | H1 prec | H2 prec |
|---|---|---:|---:|---:|---:|---:|---:|
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |
| `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` | pair+top1 | 29 | 1.0 | 48.28 | 11.38 | 50.0 | 46.67 |

## Best 5 selectors with selected >= 40
| selector | kind | n | /day | precision % | recall % | H1 prec | H2 prec |
|---|---|---:|---:|---:|---:|---:|---:|
| `S::dist_to_recent_swing_high_pct_le_0.4616::top2` | single+top2 | 58 | 2.0 | 36.21 | 17.07 | 39.29 | 33.33 |
| `S::pct_correct_move_already_done_le_0.0::top2` | single+top2 | 58 | 2.0 | 32.76 | 15.45 | 39.29 | 26.67 |
| `S::pct_correct_move_already_done_le_0.0::top2` | single+top2 | 58 | 2.0 | 32.76 | 15.45 | 39.29 | 26.67 |
| `S::pct_correct_move_already_done_le_0.0::top2` | single+top2 | 58 | 2.0 | 32.76 | 15.45 | 39.29 | 26.67 |
| `S::is_during_correct_move_FALSE::top2` | single+top2 | 58 | 2.0 | 32.76 | 15.45 | 39.29 | 26.67 |

## Best 5 selectors with selected >= 60
| selector | kind | n | /day | precision % | recall % | H1 prec | H2 prec |
|---|---|---:|---:|---:|---:|---:|---:|
| `T::score_trigger_le_0.9737+pct_correct_move_already_done_le_0.0+is_asia_session_TRUE` | triple | 60 | 2.069 | 28.33 | 13.82 | 39.29 | 18.75 |
| `T::score_trigger_le_0.9737+is_during_correct_move_FALSE+is_asia_session_TRUE` | triple | 60 | 2.069 | 28.33 | 13.82 | 39.29 | 18.75 |
| `T::pct_correct_move_already_done_le_0.0+is_asia_session_TRUE+cand_prior_move_pct_le_0.0` | triple | 296 | 10.207 | 23.99 | 57.72 | 20.44 | 27.04 |
| `T::is_during_correct_move_FALSE+is_asia_session_TRUE+cand_prior_move_pct_le_0.0` | triple | 296 | 10.207 | 23.99 | 57.72 | 20.44 | 27.04 |
| `T::pct_correct_move_already_done_le_0.0+utc_hour_le_4.0+cand_prior_move_pct_le_0.0` | triple | 253 | 8.724 | 23.72 | 48.78 | 20.0 | 26.81 |
