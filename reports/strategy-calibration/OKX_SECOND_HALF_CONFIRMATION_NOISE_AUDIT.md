# Confirmation noise audit - why confirmed-only TG-watch gives 50 alerts/day

**Build:** 2026-05-25T09:39:55+00:00
**Total confirmed zones across 15 days:** 537 (~35.8/day)

## Coverage distribution

- missed_no_move_in_4h: **409** (76.2%)
- covered_2pct_move: **60** (11.2%)
- wrong_direction: **41** (7.6%)
- noisy_partial_1_5pct: **27** (5.0%)

## Feature frequency by coverage class (sorted by separation strength covered vs missed)

| feature | covered % | wrong % | noisy % | missed % | sep covered-missed |
|---|---:|---:|---:|---:|---:|
| `defended_long` | 35.0 | 58.54 | 51.85 | 41.32 | 6.32 |
| `ofi_aligned` | 63.33 | 51.22 | 70.37 | 57.7 | 5.63 |
| `filter_kept` | 26.67 | 34.15 | 7.41 | 21.76 | 4.91 |
| `cycles_seen_ge_5` | 98.33 | 92.68 | 96.3 | 93.89 | 4.44 |
| `flow_multiplier_strong` | 33.33 | 60.98 | 33.33 | 29.58 | 3.75 |
| `absorb_score_high` | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 |
| `refill_score_present` | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 |
| `range_compression` | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 |

## HIGH confidence drilldown

- HIGH-confidence confirmed zones: **533** (99.3%)
- coverage among HIGH:
  - missed_no_move_in_4h: **406**
  - covered_2pct_move: **60**
  - wrong_direction: **40**
  - noisy_partial_1_5pct: **27**

**Interpretation:** if HIGH confidence covers ~the same % of misses as the overall distribution,
then current 'HIGH' bar is too permissive — many noisy zones reach 5+ evidence flags.
Better confidence scoring should weight features by their separation strength (see top of feature table).