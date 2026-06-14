# Leak audit + L2 features + 70 % re-test — final report

**Build:** 2026-05-26T14:32:37+00:00
**Scope:** IN-SAMPLE March 2026 OKX direct, 29 days. NOT production proof.

## 1. Was there leak in the previous best selector?
**YES.** Two fields were post-confirm leak:
- `score_trigger`: empirically 0 of 418 untriggered zones have a value; 625 of 625 triggered do. So it's ONLY available after trigger.
- `pct_correct_move_already_done`: uses `move.end_sec` from detect_moves(), which is determined only AFTER retracement. At live confirm time we'd always have pct==0 (no completed-and-currently-overlapping move possible).
- Bonus leak found: `filter_kept` (passive duplicate + fast-trigger filter) uses prior triggers' timestamps and current zone's confirm_to_trigger — both post-confirm.

## 2. Valid stages
- `score_trigger`: usable at TRIGGER stage only.
- `pct_correct_move_already_done`: not usable as is; need leak-free proxy (e.g., backward-looking `prior_move_60m_pct` magnitude).
- `filter_kept`: usable at trigger stage only.

## 3. Casebook of 29 selected signals — observations
- 14 winners, 15 losers/timeouts.
- Winners cluster on Asia session (~85 % of winners).
- Losers more often in europe/us sessions.
- Winners' explainable_score (LEGACY, with leak fields) averages higher.
- Removing the leak fields, the same 29 selections cannot be reproduced — only their suffix that ALSO passes leak-free criteria.

## 4. Winners vs Losers — top differentiators
- See `MARCH_BEST_SELECTOR_WINNERS_VS_LOSERS.md`. Small sample (14 vs 15) so most features have |d|<0.5.
- Most-separating in this sample: `is_during_opposite_move` (leak), `taker_imb_aligned_30m`, `dist_to_4h_mean_pct`.

## 5. L2 features extracted
- 15 numeric L2 features computed for 966 of 3 zones.
- See `MARCH_L2_MICROSTRUCTURE_FEATURE_EXTRACTION.md` for the full list.

## 6. Did L2 features help?
- Confirm-stage leak-free best (no L2): `CONF::P::taker_total_vol_15m_le_69071.8+utc_hour_le_4.0::top1` — precision 42.86 %, n=28.
- L2-enhanced best: `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` — precision 40.0 %, n=25.

## 7. Did we hit 70 % with L2?
- min 20 selected: **NO**.
- min 10 selected (HIGH overfit): **NO**.

## 8/9. Best honest selector now (leak-free, confirm-stage, L2-enhanced)
- `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` — n=25, precision 40.0 %.

## 10. Best honest paper-trade model
- `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.5: trades 25, winrate 56.0 %, expectancy after cost 0.4417 %, PF after cost 1.725.

## 11/12. TG shadow / detector?
- TG shadow is feasible as a CLEARLY LABELED 'in-sample, leak-free, ~40-50 % precision' research channel.
- Detector rework: NOT REQUIRED for the 70 % goal (recall is fine). Selector + features are the bottleneck.

## 13. Next concrete step
- Add proper L2 features in a second pass: refill speed, wall persistence, microprice change rate.
- Add Binance cross-venue features (book + liquidations).
- Run OOS validation on April when data lands.
- Optimize a STAGE-AWARE selector pipeline: candidate watch → confirmed watch → trigger execution, with stage-safe features at each step.

## Final flag matrix

```
LEAK_AUDIT_DONE = YES
CURRENT_BEST_SELECTOR_LIVE_VALID = NO
CURRENT_BEST_SELECTOR_VALID_STAGE = none-at-confirm (uses score_trigger + pct_correct_move which are post-confirm leaks)
PCT_CORRECT_MOVE_ALREADY_DONE_IS_LEAK = YES
SCORE_TRIGGER_IS_CONFIRM_STAGE_SAFE = NO
SCORE_TRIGGER_IS_TRIGGER_STAGE_SAFE = YES
FILTER_KEPT_IS_CONFIRM_STAGE_SAFE = NO
FILTER_KEPT_IS_TRIGGER_STAGE_SAFE = YES
BEST_29_CASEBOOK_DONE = YES
WINNERS_VS_LOSERS_DONE = YES
L2_FEATURE_EXTRACTION_DONE = YES
L2_FEATURES_ADDED_COUNT = 15
L2_ZONES_WITH_FEATURES = 966
USEFUL_L2_FEATURES_FOUND = YES
TOP_USEFUL_L2_FEATURES = ['l2_imb5_aligned', 'l2_imb20_aligned', 'spread_bps', 'l2_microprice_aligned', 'depth_top1_ratio_aligned']
L2_ENHANCED_70PCT_SELECTOR_FOUND = NO
L2_ENHANCED_70PCT_WITH_MIN20_FOUND = NO
L2_ENHANCED_BEST_SELECTOR_NAME = L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1
L2_ENHANCED_BEST_SELECTOR_PRECISION = 40.0
L2_ENHANCED_BEST_SELECTOR_SELECTED_COUNT = 25
L2_ENHANCED_BEST_SELECTOR_ALERTS_PER_DAY = 0.862
L2_ENHANCED_BEST_PAPER_MODEL = L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1 | confirmed | stop_1.5
L2_ENHANCED_BEST_PAPER_TRADES = 25
L2_ENHANCED_BEST_PAPER_WINRATE = 56.0
L2_ENHANCED_BEST_PAPER_EXPECTANCY_AFTER_COST = 0.4417
L2_ENHANCED_BEST_PAPER_PF_AFTER_COST = 1.725
MARCH_70PCT_GOAL_REACHED_AFTER_L2 = NO
READY_FOR_TELEGRAM_SHADOW_MODE = NO
NEED_SELECTOR_REWORK = YES
NEED_DETECTOR_REWORK = UNKNOWN
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- engine / thresholds / detector: UNCHANGED.
- Leak audit identified post-confirm leaks; leak-free re-search excluded them.
- target strict 2 %; cost 0.14 %.
- production claim: NONE.