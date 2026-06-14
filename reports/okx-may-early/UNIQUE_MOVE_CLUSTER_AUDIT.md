# UNIQUE MOVE / DUPLICATE CLUSTER AUDIT (OKX 05-03..20)

**Build:** 2026-06-06T17:16:34+00:00
Raw hit-zones deduped into independent moves (same direction + target-hit within 120 min). Conclusions unchanged.

## A. Strong zones (>=2.5%)
- raw strong zones: **34**
- unique strong move clusters: **8**
- duplicate strong zones: **26**
- first live-detectable strong clusters: **6**
- hindsight-only strong clusters: **2**
- avg zones/cluster: 4.25

## B. Hit2 zones
- raw hit2 zones: **70** -> unique hit2 moves: **19** (duplicates 51)
- unique hit2.5 moves: 8 · unique hit3 moves: 7

## C. Module coverage by UNIQUE moves (strong)
| module | raw zones | unique moves |
|---|--:|--:|
| TD_SHORT | 0 | 0 |
| TU_LONG | 0 | 0 |
| RANGE_FADE_proto | 5 | 3 |
| SWEEP_proto | 1 | 1 |
| ANY_NEW_proto | 8 | 6 |
| ANY_MODULE | 8 | 6 |

## D. Answers
**1_independent_opportunities** — 8 unique strong-move clusters out of 34 raw zones.
**2_duplicates** — 26 strong zones were duplicate credits of an already-counted move.
**3_live_catchable_before_move** — 6/8 unique strong moves had at least one zone a causal module/proto could alert on before target.
**4_hindsight_only** — 2/8 unique strong moves had NO causal pre-signal (hindsight-only).
**5_range_fade_raw_or_unique** — RANGE_FADE proto touches 5 raw strong zones = 3 unique moves.
**6_still_formalize_range_fade** — PARTIAL — after dedup it covers only 3 unique strong moves; combined with breakeven PF it is a weak standalone edge. Worth a shadow prototype, not a priority module.

## Flags
```
UNIQUE_MOVE_AUDIT_DONE = YES
RAW_STRONG_ZONES = 34
UNIQUE_STRONG_MOVES = 8
DUPLICATE_STRONG_ZONES = 26
HINDSIGHT_ONLY_STRONG_MOVES = 2
FIRST_LIVE_DETECTABLE_STRONG_MOVES = 6
RAW_HIT2_ZONES = 70
UNIQUE_HIT2_MOVES = 19
RANGE_FADE_UNIQUE_MOVES_COVERED = 3
CONCLUSIONS_CHANGED = NO
TARDIS_USED = NO
```