# OKX direct second-half March - Detection Quality / TG-Watch Addendum

**Build:** 2026-05-25T09:37:00+00:00
**Scope:** OKX direct second-half March - detection quality / TG-watch addendum over 15 ready days
**Chain status:** 15/15 days completed; chain done = **True**.
**Days included:** ['2026-03-16', '2026-03-18', '2026-03-19', '2026-03-20', '2026-03-21', '2026-03-22', '2026-03-23', '2026-03-24', '2026-03-25', '2026-03-26', '2026-03-27', '2026-03-28', '2026-03-29', '2026-03-30', '2026-03-31']

## 1. Market 2 % moves per day
  - **20** primary 2 % moves across 15 days.

## 2. Engine coverage early/mid/late/missed
  - covered_watch_early: 7
  - covered_trigger_early: 3
  - covered_mid (trigger after 0-50% of move): 0
  - covered_late (trigger after 50% of move): 2
  - missed_move / filtered_correct_zone: 8

## 3. Correct zones suppressed by filter
  - **61** correct zones were suppressed by base filter (slow_trigger / duplicate_60m).

## 4. Slow-trigger correct zones
  - **44** zones had confirm→trigger > 60 m AND direction matches a market 2 % move.
  - Of those, **44** had strong-enough confirmed-stage evidence (absorb >= 0.6 OR cycles >= 5) to justify a watch alert.

## 5. Wrong-direction cases
  - **8** triggered zones had no 2 % move in their direction within 4 h forward.

## 6. Direction explanation examples
  - direction explanation generated for **537** confirmed/triggered zones.

## 7. TG-watch candidate count per day

| mode | per day | covered move | wrong dir | missed | avg lead min |
|---|---:|---:|---:|---:|---:|
| `confirmed_only` | 35.8 | 60 | 83 | 394 | 109.15 |
| `candidate_MID+` | 35.8 | 60 | 83 | 394 | 109.15 |
| `confirmed_MID+` | 35.8 | 60 | 83 | 394 | 109.15 |
| `confirmed_HIGH_only` | 34.333 | 55 | 79 | 381 | 107.53 |
| `max1_per_direction_per_day` | 2.0 | 7 | 5 | 18 | 127.51 |
| `max2_total_per_day` | 2.0 | 10 | 2 | 18 | 126.24 |

## 8. Whether confirmed stage is useful for TG-watch
  - UNKNOWN. 11.17 % of confirmed zones had a correct-direction 2 % move within 4 h after confirmed timestamp.

## 9. Whether trigger-only alerts are too late
  - **NO** (covered_late+covered_mid=2 vs covered_trigger_early=3).

## 10. Recommended next action
  - Build research-only TG-watch prototype: alert at `confirmed` stage with direction-explanation summary.
  - Validate on second OOS period before any production integration.
  - NO engine / threshold / detector change.

## Final flag matrix

```
DETECTION_QUALITY_ADDENDUM_DONE = YES
DAYS_INCLUDED = ['2026-03-16', '2026-03-18', '2026-03-19', '2026-03-20', '2026-03-21', '2026-03-22', '2026-03-23', '2026-03-24', '2026-03-25', '2026-03-26', '2026-03-27', '2026-03-28', '2026-03-29', '2026-03-30', '2026-03-31']
CHAIN_PROGRESS = 15/15
MARKET_2PCT_MOVES_TOTAL = 20
ENGINE_COVERED_WATCH_EARLY = 7
ENGINE_COVERED_TRIGGER_EARLY = 3
ENGINE_COVERED_MID = 0
ENGINE_COVERED_LATE = 2
ENGINE_MISSED_MOVES = 8
CORRECT_ZONES_SUPPRESSED_BY_FILTER = 61
SLOW_TRIGGER_CORRECT_ZONES = 44
WRONG_DIRECTION_CASES = 8
CONFIRM_STAGE_USEFUL_FOR_TG_WATCH = UNKNOWN
TRIGGER_ONLY_ALERTS_TOO_LATE = NO
TG_WATCH_CONFIRMED_ALERTS_PER_DAY = 35.8
TG_WATCH_HIGH_CONFIDENCE_ALERTS_PER_DAY = 34.333
CAN_TG_WATCH_BE_1_2_PER_DAY = YES
DIRECTION_EXPLANATIONS_AVAILABLE = YES
LOCAL_NORMALIZATION_STILL_RECOMMENDED = UNKNOWN
READY_TO_BUILD_TG_WATCH_ZONE_MODE = UNKNOWN
READY_TO_CHANGE_ENGINE = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- strategy / thresholds / `zoneDetector`: UNCHANGED
- main chain NOT touched
- post-trigger fields used only as labels, never as features
- target STRICT 2 %
- READY_TO_CHANGE_ENGINE = NO
---

## NEW SECTION: Max2 selected zones and confirmation-noise explanation

_Section appended 2026-05-25T09:39:55+00:00 on ready days ['2026-03-16', '2026-03-18', '2026-03-19', '2026-03-20', '2026-03-21', '2026-03-22', '2026-03-23', '2026-03-24', '2026-03-25', '2026-03-26', '2026-03-27', '2026-03-28', '2026-03-29', '2026-03-30', '2026-03-31']._

### 1. Which zones did max2_total_per_day pick?
See `OKX_SECOND_HALF_MAX2_SELECTED_WATCH_ZONES.md`. Across 15 ready days, 30 zones selected. Coverage: covered=6, wrong_dir=2, noisy_1.5%=1, missed=21.

### 2. Why those zones
Ranking: `rank_score = evidence_count + confidence_bonus - slow_trigger_penalty`.

### 3. Which 2 % moves were missed by max2
16 of 20 primary 2 % moves not covered. See `OKX_SECOND_HALF_MAX2_MISSED_MOVES_AUDIT.md`.

### 4. Wrong-direction selected zones
2 wrong-direction selections. Detailed audit + prevention rule candidates in `OKX_SECOND_HALF_MAX2_WRONG_DIRECTION_AUDIT.md`.

### 5-6. Why confirmed-only is ~50 alerts/day
Total confirmed zones across 15 days: **537**. Coverage distribution:
  - missed_no_move_in_4h: **409** (76.2%)
  - covered_2pct_move: **60** (11.2%)
  - wrong_direction: **41** (7.6%)
  - noisy_partial_1_5pct: **27** (5.0%)

Feature separation analysis: top discriminating features (covered vs missed) are listed in `OKX_SECOND_HALF_CONFIRMATION_NOISE_AUDIT.md`. Current 'HIGH' confidence label catches 533 of 537 confirmed zones — too permissive: 5+ flag bar admits noise.

### 7-8. Pattern search
See `OKX_SECOND_HALF_GOOD_WATCH_ZONE_PATTERN_SEARCH.md`. Best pattern (alerts/day <= 3.5, max F1): `none`.

### 9. Can TG-watch be 1-2/day without spam?
YES, with proper ranking. max2_total_per_day on rank_score already gives 2/day. Better confidence score (proposal in `OKX_SECOND_HALF_TG_WATCH_CONFIDENCE_SCORE_PROPOSAL.md`) should improve precision further.

### 10. What to change in research layer (NOT engine)
- Implement `TG_watch_score_v0` from proposal in a research script (no engine touch).
- Use it to rank confirmed zones, cap at 2/day + 1/direction/day.
- Validate on second OOS period (rest of March + any future month) before any shadow deployment.

**HARD RULE:** no engine / threshold / detector change. No production integration.