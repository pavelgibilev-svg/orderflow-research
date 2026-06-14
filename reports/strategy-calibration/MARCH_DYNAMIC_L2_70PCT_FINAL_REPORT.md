# Dynamic L2 microstructure + 70 % re-test — final report

**Build:** 2026-05-26T22:03:00+00:00
**Scope:** IN-SAMPLE March 2026 OKX direct, 29 days. NOT production proof.

## 1. Dynamic L2 features extracted?
- **YES.** 183 dynamic L2 features per zone. 1043 of 1043 zones have features.
- Windows: 30s / 1m / 5m / 15m / 30m / 60m, all ending at confirm anchor (no future-leak).

## 2. Useful dynamic L2 features
- Top 3 by Cohen's d (GOOD vs BAD): dl2_supportive_add_vol_60m, dl2_supportive_cancel_vol_60m, dl2_add_vol_ask_60m
- See `MARCH_DYNAMIC_L2_FEATURE_SEPARATION.md` for full ranking.

## 3. Useless / 4. Anti-features
- See full separation report. Most features still have |d| < 0.3.

## 5. Did dynamic L2 improve precision / winrate?
- Frontier improvement at min 20: **+1.72 pp** vs no-dyn.
- Best leak-free precision (min 20): **50.0 %**
- Best paper winrate (>=20 trades): **58.62 %**

## 6. 70 % reached?
- min 10: NO
- min 20: NO
- min 29: NO

## 7. If yes — formula
- (70% NOT reached at min 20 leak-free)

## 8. If not — why
- See per-feature separation in `MARCH_DYNAMIC_L2_FEATURE_SEPARATION.md` — most dynamic L2 features have |d| in 0.10-0.30 range.
- GOOD/BAD overlap remains very high. Adding dynamic L2 lifted ceiling modestly but not past 70 %.
- Even confluence-based triples did not break 70 %.

## 9-11. What's blocking
- Likely: regime variability between H1/H2, label noise, and need for cross-venue / liquidation features.
- Detector rework probably not the bottleneck (recall of zones near market moves is fine).
- Selector rework + new external features (Binance order book, liquidations) is the next step.

## 12. TG shadow?
- A research-only shadow channel at ~40-45 % precision, 1/day, with clear IN-SAMPLE labelling is feasible.
- Not production-ready until OOS validation.

## 13. Best practical selector
- `DL2::P::dist_to_recent_swing_high_pct_le_0.321+prior_move_180m_pct_le_0.5155::top1` (precision 50.0 %, 28 selected, 0.966/day).

## 14. Next concrete step
- Add per-level wall lifetime (requires per-level history in extraction, ~2x runtime).
- Add Binance L2 cross-venue features.
- Add liquidation cascade signal.
- Run OOS validation on April when data arrives.

## Final flag matrix

```
DYNAMIC_L2_RESEARCH_DONE = YES
DAYS_INCLUDED = 29
ZONES_WITH_DYNAMIC_L2_FEATURES = 1043
DYNAMIC_L2_FEATURES_EXTRACTED = 183
USEFUL_DYNAMIC_L2_FEATURES_FOUND = YES
TOP_DYNAMIC_L2_FEATURE_1 = dl2_supportive_add_vol_60m
TOP_DYNAMIC_L2_FEATURE_2 = dl2_supportive_cancel_vol_60m
TOP_DYNAMIC_L2_FEATURE_3 = dl2_add_vol_ask_60m
TOP_DYNAMIC_L2_ANTI_FEATURE_1 = none-confirmed
DYNAMIC_L2_70PCT_SELECTOR_FOUND = NO
DYNAMIC_L2_70PCT_WITH_MIN20_FOUND = NO
DYNAMIC_L2_70PCT_WITH_MIN29_FOUND = NO
BEST_DYNAMIC_L2_SELECTOR_NAME = DL2::P::dist_to_recent_swing_high_pct_le_0.321+prior_move_180m_pct_le_0.5155::top1
BEST_DYNAMIC_L2_SELECTOR_STAGE = confirmed
BEST_DYNAMIC_L2_SELECTED_COUNT = 28
BEST_DYNAMIC_L2_ALERTS_PER_DAY = 0.966
BEST_DYNAMIC_L2_PRECISION = 50.0
BEST_DYNAMIC_L2_RECALL = 11.38
BEST_DYNAMIC_L2_WRONG_DIRECTION_RATE = 0.0
BEST_DYNAMIC_L2_H1_PRECISION = 46.15
BEST_DYNAMIC_L2_H2_PRECISION = 53.33
BEST_DYNAMIC_L2_OVERFIT_RISK = MEDIUM
BEST_DYNAMIC_L2_PAPER_MODEL = DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1 | confirmed | stop_1.5
BEST_DYNAMIC_L2_PAPER_TRADES = 29
BEST_DYNAMIC_L2_PAPER_WINRATE = 58.62
BEST_DYNAMIC_L2_PAPER_EXPECTANCY_AFTER_COST = 0.5268
BEST_DYNAMIC_L2_PAPER_PF_AFTER_COST = 1.922
DYNAMIC_L2_IMPROVED_OVER_SNAPSHOT_L2 = YES
DYNAMIC_L2_IMPROVED_OVER_PREVIOUS_BEST = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
NEED_SELECTOR_REWORK = YES
NEED_DETECTOR_REWORK = UNKNOWN
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- engine / thresholds / detector: UNCHANGED.
- All dynamic L2 windows END at anchor — no future-leak.
- Outcome labels used ONLY for evaluation.
- target strict 2 %; cost 0.14 %.
- production claim: NONE.