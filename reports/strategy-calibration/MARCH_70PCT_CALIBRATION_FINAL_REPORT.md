# March 70 % calibration — final report (IN-SAMPLE, NOT production proof)

**Build:** 2026-05-26T12:38:36+00:00
**Scope:** IN-SAMPLE March 2026 OKX direct; 29 days; not production proof.

## 1. >= 70 % leak-free on March?
- **NO** at min 20 selected.
- **NO** at min 29 (1/day pace).
- Exhaustive search over 4315 selector variants.

## 2. If YES — formula and count
- (Not applicable; 70 % was not reached leak-free with min 20.)

## 3. If NO — why
- GOOD vs BAD feature overlap is heavy: on every leak-free single feature, >80 % of BAD zones fall inside the GOOD's p10-p90 value range.
- Multi-feature confluence trims sample size before precision lifts past ~45 %.
- Best leak-free precision found = **48.28 %** at n=29 (selector `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1`).
- Best leak-free paper-trade winrate with >=20 trades = **62.07 %**.

## 4. Best honest selector right now
- `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` — precision 48.28 %, 29 alerts (1.0/day), H1/H2 50.0/46.67 %, overfit risk MEDIUM.

## 5. Oracle / leak selector (NOT live)
- Trivial oracle = pick zones labelled GOOD → 100 % precision (by definition).
- Mid-leak (`confirm_to_trigger_le_30`) lifts precision to ~16 % — usable only at trigger stage; STILL not reaching 70 %.
- Even with future leak via trigger timing, 70 % requires picking on the GOOD label directly. That confirms the ceiling is dataset/feature-bound, not search-bound.

## 6. What blocks 70 %
- Lack of L2 features (refill / defense / wall persistence / microprice / spread / void).
- Lack of cross-venue (Binance) flow / liquidation features.
- No calendar / news flag — instant moves are over-represented in BAD.
- Label noise (~5 % of GOOD zones still go wrong direction in trades).

## 7. Leak features that DO lift precision (and possible proxies)
- `confirm_to_trigger_min ≤ 30` → +4-5 pp precision (post-confirm, trigger-stage only).
  - Possible pre-confirm proxy: `trig_break_pct` magnitude + `taker_total_vol_15m / vol_anomaly_15m_vs_bg` — partly captures the same dynamic.
- `lead_min_before_move ≥ 30` → guarantees 100 % (post-hoc). No clean proxy in current features.

## 8. Orderflow features that work
is_asia_session, filter_kept, is_late_after_50pct_correct_move (anti), is_during_opposite_move (anti), opp_dir_zones_active_60m, taker_imb_aligned_30m, ofi_shift_aligned, sweep_reclaim_aligned, prior_move_60m_pct small, local_range_180m_pct small

## 9. Useless features
score_absorption, score_refill, score_ofi, score_trigger, score_liquidity_void, cand_absorb_score, cand_*_refill_score, cand_range_compression, conf_cycles_seen, conf_age_min, conf_opposite_thinning, conf_defended_persistence_sec, cand_pressure_against, trig_flow_multiplier, local_realized_vol_*

## 10. Anti-features
is_late_after_50pct_correct_move, is_during_opposite_move, prior_move_180m_pct (direction-flipped)

## 11. What's blocking 70 %
- Same as section 6 + section 3.

## 12. What to add to features / data
- L2 reconstruction (highest priority).
- Binance cross-venue mirror.
- Liquidation cascade feed.
- Calendar / news event tag.

## 13. Detector vs selector
- Detector likely fine for *finding* zones (recall ≥ 80 % of 2 % moves at the zone level).
- The problem is *ranking* and *direction guard*. Selector rework + new features should be enough.

## 14. Best practical selector now
- `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` — see Section 4.

## 15. TG shadow possible?
- As a research-only TG channel labelled 'IN-SAMPLE March, NOT validated OOS': **acceptable**.
- As a production live signal: **NO**. Needs OOS validation.

## 16. Next step
- Validate this selector + score on April (when data lands) — pure OOS.
- Add L2-derived refill / defense / microprice features.
- Add cross-venue direction-confirmation feature.
- Re-run this exact calibration with the expanded feature set.

## Final flag matrix

```
MARCH_70PCT_CALIBRATION_DONE = YES
DAYS_INCLUDED = 29
TOTAL_ZONES = 1043
TOTAL_CONFIRMED_ZONES = 1043
TOTAL_MARKET_2PCT_MOVES = 41
LEAK_FREE_70PCT_SELECTOR_FOUND = NO
LEAK_FREE_80PCT_SELECTOR_FOUND = NO
LEAK_FREE_70PCT_WITH_MIN20_FOUND = NO
LEAK_FREE_70PCT_WITH_MIN29_FOUND = NO
BEST_LEAK_FREE_SELECTOR_NAME = P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1
BEST_LEAK_FREE_SELECTOR_FORMULA = P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1
BEST_LEAK_FREE_SELECTED_COUNT = 29
BEST_LEAK_FREE_ALERTS_PER_DAY = 1.0
BEST_LEAK_FREE_PRECISION = 48.28
BEST_LEAK_FREE_RECALL = 11.38
BEST_LEAK_FREE_WRONG_DIRECTION_RATE = 0.0
BEST_LEAK_FREE_H1_PRECISION = 50.0
BEST_LEAK_FREE_H2_PRECISION = 46.67
BEST_LEAK_FREE_OVERFIT_RISK = MEDIUM
BEST_LEAK_FREE_PAPER_MODEL = S::score_trigger_ge_1.0::top1 | delay_10m | stop_1.5
BEST_LEAK_FREE_PAPER_TRADES = 29
BEST_LEAK_FREE_PAPER_WINRATE = 62.07
BEST_LEAK_FREE_PAPER_EXPECTANCY_AFTER_COST = 0.6228
BEST_LEAK_FREE_PAPER_PF_AFTER_COST = 2.172
ORACLE_70PCT_POSSIBLE = YES
ORACLE_BEST_PRECISION = 100.0
ORACLE_LEAK_FEATURES_USED = ['watch_label', 'matched_move_size_pct', 'lead_min_before_move']
WHY_70PCT_NOT_REACHED_IF_NO = GOOD/BAD feature overlap >80 % on every leak-free single feature; even 3-4 feature confluence collapses sample size before precision lifts past ~50 %. Need L2 / cross-venue / news features.
USEFUL_ORDERFLOW_FEATURES_FOUND = YES
TOP_USEFUL_FEATURES = ['is_asia_session', 'filter_kept', 'is_late_after_50pct_correct_move (anti)', 'is_during_opposite_move (anti)', 'opp_dir_zones_active_60m', 'taker_imb_aligned_30m', 'ofi_shift_aligned', 'sweep_reclaim_aligned', 'prior_move_60m_pct small', 'local_range_180m_pct small']
USELESS_FEATURES = ['score_absorption', 'score_refill', 'score_ofi', 'score_trigger', 'score_liquidity_void', 'cand_absorb_score', 'cand_*_refill_score', 'cand_range_compression', 'conf_cycles_seen', 'conf_age_min', 'conf_opposite_thinning', 'conf_defended_persistence_sec', 'cand_pressure_against', 'trig_flow_multiplier', 'local_realized_vol_*']
ANTI_FEATURES = ['is_late_after_50pct_correct_move', 'is_during_opposite_move', 'prior_move_180m_pct (direction-flipped)']
NEED_NEW_FEATURES = YES
NEED_DETECTOR_REWORK = UNKNOWN
NEED_SELECTOR_REWORK = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- engine / thresholds / detector: UNCHANGED.
- leak-free selectors use only pre-confirm features.
- oracle diagnostic is explicitly labelled NOT LIVE.
- target strict 2 %; cost 0.14 %.
- production claim: NONE.