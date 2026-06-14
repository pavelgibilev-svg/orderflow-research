# Why `zone_score_v1` failed — per-feature retrospective on 24 OKX days

v1 archived as failed: in-sample recall 100 %, OOS recall 14.29 %. This file dissects each of the 12 v1 features across the three rounds to show which features actually flipped.

Sign convention: positive Cohen's d means primary-unique-reached zones have HIGHER values than failed-triggered zones (good for v1 weight sign +1). Negative means LOWER (good for v1 weight sign −1).

## A. Per-round Cohen's d for each v1 feature

| feature | v1 expected sign | calibration d | OOS_v1 d | v2 d | all_24 d | rounds matching v1 |
|---|---:|---:|---:|---:|---:|---:|
| `cand_pressure_against` | -1 | -0.857 | +0.502 | +0.590 | +0.329 | 1/3 |
| `cand_absorb_score` | -1 | -0.841 | -0.580 | +0.450 | -0.023 | 2/3 |
| `cand_refill_with` | +1 | +0.646 | -0.373 | +0.269 | +0.117 | 2/3 |
| `conf_cycles_seen` | -1 | -0.806 | +0.956 | +0.117 | +0.202 | 1/3 |
| `conf_age_min` | +1 | +0.507 | -0.761 | +0.035 | -0.057 | 2/3 |
| `conf_defended_persistence_sec` | +1 | +0.507 | -0.761 | +0.035 | -0.057 | 2/3 |
| `candidate_to_confirm_min` | +1 | +0.507 | -0.761 | +0.035 | -0.057 | 2/3 |
| `confirm_to_trigger_min` | -1 | -0.641 | -0.610 | -0.554 | -0.588 | 3/3 |
| `total_pre_trigger_min` | -1 | -0.570 | -0.666 | -0.532 | -0.579 | 3/3 |
| `trig_flow_multiplier` | +1 | +0.588 | -0.494 | -0.131 | +0.041 | 1/3 |
| `trig_break_pct` | -1 | -0.465 | -0.209 | -0.356 | -0.325 | 3/3 |
| `score_absorption` | -1 | -0.483 | -0.636 | -0.292 | -0.407 | 3/3 |

## B. v1 features that INVERTED on the full 24-day pool

**Count:** 5

| feature | v1 expected sign | all_24 actual sign | all_24 d |
|---|---:|---:|---:|
| `cand_pressure_against` | -1 | +1 | +0.329 |
| `conf_cycles_seen` | -1 | +1 | +0.202 |
| `conf_age_min` | +1 | -1 | -0.057 |
| `conf_defended_persistence_sec` | +1 | -1 | -0.057 |
| `candidate_to_confirm_min` | +1 | -1 | -0.057 |

## C. v1 features that SURVIVED on the full 24-day pool

Definition: full-pool sign matches v1's expected sign AND |d| ≥ 0.2.
**Count:** 4

| feature | v1 expected sign | all_24 d |
|---|---:|---:|
| `confirm_to_trigger_min` | -1 | -0.588 |
| `total_pre_trigger_min` | -1 | -0.579 |
| `trig_break_pct` | -1 | -0.325 |
| `score_absorption` | -1 | -0.407 |

## D. v1 features that became TOO FLAT on the 24-day pool

Definition: full-pool |d| < 0.2 OR sign of full d is 0.
**Count:** 3

| feature | v1 expected sign | all_24 d |
|---|---:|---:|
| `cand_absorb_score` | -1 | -0.023 |
| `cand_refill_with` | +1 | +0.117 |
| `trig_flow_multiplier` | +1 | +0.041 |

## E. Conclusion

- v1 was fitted on 5 positives. With 21 positives in the combined pool, multiple features flipped sign.
- The v1 score's failure on OOS is fully explained by features that look strong on n=5 but reverse direction (or vanish) once the positive sample grows.
- Lesson for v2: select features on a held-out portion of the 21 positives; do NOT reuse the calibration sample for both feature selection and weight fitting.

Companion JSON: `reports/WHY_ZONE_SCORE_V1_FAILED.json`