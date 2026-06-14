# OKX direct March - stop-out feature analysis (pre-trigger features only)

**Build:** 2026-05-23T09:42:51+00:00
**Scope:** filtered triggered zones in strict ledger; target=2 %, stop=1 %, timeout=24h.

## Counts

- filtered kept (after base passive filter): **103**
- of those in strict ledger (not skipped by open-position rule): **41**
- WINS (target_2pct): **11**
- LOSSES (stop_1pct): **24**  (LONG 12 / SHORT 12)
- TIMEOUTS: **6**  (positive 3 / negative 3)

## Feature comparison (Cohen's d, sorted by |d| WIN vs LOSS)

| feature | winners mean | losers mean | timeouts mean | d (W vs L) | d (W vs T) | d (L vs T) |
|---|---:|---:|---:|---:|---:|---:|
| `cand_absorb_score` | 0.6885 | 0.6513 | 0.6494 | 0.658 | 0.527 | 0.055 |
| `score_refill` | 0.4992 | 0.5001 | 0.5006 | -0.529 | -0.858 | -0.305 |
| `score_absorption` | 0.667 | 0.6394 | 0.6529 | 0.484 | 0.218 | -0.262 |
| `trig_flow_multiplier` | 2.9177 | 2.0774 | 1.733 | 0.468 | 0.51 | 0.35 |
| `cand_pressure_against` | 0.638 | 0.6064 | 0.5958 | 0.451 | 0.529 | 0.212 |
| `conf_opposite_thinning` | 0.4997 | 0.5002 | 0.5008 | -0.399 | -0.825 | -0.584 |
| `trig_break_pct` | 0.1963 | 0.1418 | 0.2269 | 0.359 | -0.181 | -0.668 |
| `entry_to_invalidation_pct` | 0.6806 | 0.5639 | 0.8602 | 0.234 | -0.268 | -0.686 |
| `cand_refill_with` | 0.5002 | 0.4999 | 0.5006 | 0.177 | -0.299 | -0.572 |
| `conf_cycles_seen` | 68.5455 | 59.0417 | 55.5 | 0.166 | 0.232 | 0.062 |
| `cand_prior_move_pct` | 0.0003 | 0.0005 | 0.0002 | -0.128 | 0.266 | 0.249 |
| `zone_width_pct` | 0.4848 | 0.4222 | 0.6338 | 0.127 | -0.224 | -0.49 |
| `candidate_to_confirm_min` | 10.5545 | 11.6438 | 10.65 | -0.123 | -0.011 | 0.118 |
| `conf_age_min` | 10.5545 | 11.6438 | 10.65 | -0.123 | -0.011 | 0.118 |
| `conf_defended_persistence_sec` | 633.2727 | 698.625 | 639 | -0.123 | -0.011 | 0.118 |
| `score_ofi` | 0.014 | -0.0015 | -0.0074 | 0.082 | 0.12 | 0.029 |
| `confirm_to_trigger_min` | 17.1515 | 16.2521 | 14.6472 | 0.062 | 0.188 | 0.119 |
| `total_pre_trigger_min` | 27.7061 | 27.8958 | 25.2972 | -0.012 | 0.168 | 0.166 |
| `score_trigger` | 0.9905 | 0.9905 | 0.9833 | 0.004 | 0.529 | 0.517 |

## Notes

- Effect-size on n_win=11, n_loss=24 is SUGGESTIVE only.
- Direction: positive d means winners have LARGER feature value than losers.