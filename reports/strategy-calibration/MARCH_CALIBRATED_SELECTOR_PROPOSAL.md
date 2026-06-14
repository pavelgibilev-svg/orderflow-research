# March-calibrated selector proposal

**Build:** 2026-05-26T12:38:35+00:00

## NO MARCH_70_SELECTOR found leak-free with min 20
### BEST_PRACTICAL_SELECTOR: `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1`
- selected: 29 (1.0/day)
- precision: 48.28 %
- recall: 11.38 %
- wrong direction rate: 0.0 %
- H1/H2: 50.0 / 46.67 %
- LONG / SHORT precision: 50.0 / 46.15 %

### Best HIGH-precision (smaller sample, overfit-prone): `TREE::leaf_1::pct_opposite_move_already_done > 66.04 AND local_realized_vol_180m <= 0.00064`
- selected: 13 (0.448/day)
- precision: 69.23 %  — overfit risk HIGH if n<20

## Why this selector
- It combines the strongest leak-free features observed: filter_kept, session/timing, conflict guards (opp_eq0, not_during_opp), late-move guard.
- Within-day ranking uses `explainable_score` (sum of leak-free contributions).
- All features available at confirm time (no future leak).

## What it catches
- Asia-session impulse reversals into clean range zones.
- Confirmed zones with passive duplicate-filter passed.

## What it misses
- News-driven instant moves.
- Slow-grind 2 % moves without flow signature.
- Wick-only spikes (confirmed after the spike).

## Risks
- IN-SAMPLE March; not validated OOS.
- Sample size 20-30 is small; H2 drift possible.
- 0.14 % cost eats most of the edge if winrate stays under 60 %.