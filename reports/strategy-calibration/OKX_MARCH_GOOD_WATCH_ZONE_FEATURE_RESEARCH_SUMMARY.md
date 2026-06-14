# Good watch-zone feature research - master summary

**Build:** 2026-05-25T15:31:41+00:00
**Scope:** Good watch-zone feature research over full OKX March (29 days)
**Days:** 29 (14 first half + 15 second half; missing: ['2026-03-17'])
**Total zones:** 1053; confirmed: **1043**
**Movement-first labels:** GOOD=123, MID=146, BAD=774

## 1. Features that separate GOOD from BAD

Top discriminating features (sorted by separation):
- `local_range_180m_pct`
- `prior_move_60m_pct`
- `trig_break_pct`

## 2. Useless features
  - 27 features have <0.15 Cohen's d or ~100% true in all classes (incl. absorb_score, refill_score, range_compression which fire on every candidate)

## 3. Anti-features
  - 1 features fire more often in BAD/wrong/missed than in GOOD

## 4. Pattern search
  - tested ~25 simple patterns and combos.
  - **Best (alerts/day <= 3, precision > baseline, wrong <= 25%, max F1):** `filter_kept_AND_opp_eq_0_AND_prior_60m_le_1`

## 5. 1-2 zones/day feasible?
  - `YES` — with v1 score: best mode `filter_kept_AND_opp_eq_0_top2` at 1.862/day, precision 29.63%.

## 6. Train/test stability
  - `YES` for best pattern.
  - Stable-both-halves patterns count: **12** out of 24 tested.

## 7. LONG vs SHORT
  - Direction-specific differences captured in feature separation file (cohens_d_good_vs_bad per feature).

## 8. First-half vs second-half
  - First half baseline precision: 13.24%
  - Second half baseline precision: 10.43%

## 9. Why current HIGH confidence is broken
  - 3 features (absorb_score, refill_score, range_compression) fire on ~100% candidate zones — they reflect 'is candidate', not 'is good'. Adding them to confidence ev-count automatically pushes 95%+ of zones to HIGH.

## 10. TG_watch_score_v1 design
  - 8 components from separation-driven selection.
  - See `OKX_MARCH_TG_WATCH_SCORE_V1_PROPOSAL.md` for full breakdown.

## 11. Can build TG-watch selector now?
  - `YES`

## 12. Next steps
  - Validate v1 score on independent OOS period (e.g. April when available).
  - Refine direction guard.
  - Add cluster-dedup logic (don't pick 2 zones from same uniqueMoveId cluster).

## Final flag matrix

```
GOOD_WATCH_ZONE_FEATURE_RESEARCH_DONE = YES
DAYS_INCLUDED = 29
TOTAL_ZONES_ANALYZED = 1053
TOTAL_CONFIRMED_ZONES = 1043
TOTAL_MARKET_2PCT_MOVES = 41
TOTAL_GOOD_WATCH_ZONES = 123
TOTAL_BAD_WATCH_ZONES = 774
USEFUL_FEATURES_FOUND = YES
USELESS_FEATURES_IDENTIFIED = YES
ANTI_FEATURES_IDENTIFIED = YES
TOP_USEFUL_FEATURE_1 = local_range_180m_pct
TOP_USEFUL_FEATURE_2 = prior_move_60m_pct
TOP_USEFUL_FEATURE_3 = trig_break_pct
TOP_ANTI_FEATURE_1 = prior_move_180m_pct
TOP_ANTI_FEATURE_2 = none
GOOD_WATCH_ZONE_PATTERN_FOUND = YES
BEST_PATTERN_NAME = filter_kept_AND_opp_eq_0_AND_prior_60m_le_1
BEST_PATTERN_ALERTS_PER_DAY = 2.862
BEST_PATTERN_PRECISION = 19.28
BEST_PATTERN_RECALL = 13.01
BEST_PATTERN_WRONG_DIRECTION_RATE = 4.82
BEST_PATTERN_TRAIN_TEST_STABLE = YES
TG_WATCH_SCORE_V1_PROPOSED = YES
TG_WATCH_SCORE_V1_ALERTS_PER_DAY = 1.862
TG_WATCH_SCORE_V1_PRECISION = 29.63
TG_WATCH_SCORE_V1_RECALL = 13.01
TG_WATCH_SCORE_V1_TRAIN_TEST_STABLE = YES
CAN_SELECT_1_2_ZONES_PER_DAY = YES
READY_TO_BUILD_TG_WATCH_SELECTOR = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- strategy / thresholds / `zoneDetector`: UNCHANGED
- post-trigger fields used only as labels, NEVER as decision features
- target strict 2 %
- no production integration
- READY_FOR_PRODUCTION_TRADING = NO