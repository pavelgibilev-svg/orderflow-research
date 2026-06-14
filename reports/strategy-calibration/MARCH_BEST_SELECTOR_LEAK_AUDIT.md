# Best selector leak audit

**Build:** 2026-05-26T12:58:50+00:00

## Summary
Both headline selectors use FUTURE_LEAK fields. Need to re-derive leak-free selectors per stage.

## Suspect fields — verdict

| field | confirm-safe? | trigger-safe? | classification |
|---|:---:|:---:|---|
| `score_trigger` | NO (verified: 0 of 418 zones without triggerTs have score_trigger) | YES (verified: 625 of 625 triggered zones have score_trigger) | FUTURE_LEAK at confirm; SAFE at trigger stage |
| `pct_correct_move_already_done` | NO (requires move.end_sec which is determined only when retracement triggers, possibly after anchor) | PARTIAL — even at trigger we don't know future end_sec of in-progress moves | FUTURE_LEAK |
| `is_during_correct_move` | N/A | N/A | FUTURE_LEAK (same root cause) |
| `pct_opposite_move_already_done` | N/A | N/A | FUTURE_LEAK |
| `is_during_opposite_move` | N/A | N/A | FUTURE_LEAK |
| `is_late_after_50pct_correct_move` | N/A | N/A | FUTURE_LEAK |

## Detailed audit
### `score_trigger`
- definition: engine's trigger-quality score, populated in zone.scores when a trigger event fires
- source: scripts/strategy-calibration/march_in_sample_calibration.py extract_features() -> scores.get('triggerScore')
- available_at_candidate: NO
- available_at_confirmed: NO (verified: 0 of 418 zones without triggerTs have score_trigger)
- available_at_trigger: YES (verified: 625 of 625 triggered zones have score_trigger)
- uses_future_market_move: NO directly, but knowing trigger happened is future info at confirm time
- leak_classification: FUTURE_LEAK at confirm; SAFE at trigger stage
- empirical_count_no_trig_with_value: 0
- empirical_count_trig_with_value: 625

### `pct_correct_move_already_done`
- definition: pct of correct-direction 2 % move completed at anchor, where move is detected via full-day scan with start/end determined by retracement
- source: scripts/strategy-calibration/march_in_sample_calibration.py compute_orderflow_features() — uses moves_today list scanned over full day
- available_at_candidate: NO
- available_at_confirmed: NO (requires move.end_sec which is determined only when retracement triggers, possibly after anchor)
- available_at_trigger: PARTIAL — even at trigger we don't know future end_sec of in-progress moves
- uses_future_market_move: YES (move.end_sec is by definition determined by future retracement)
- leak_classification: FUTURE_LEAK
- empirical_pct_zero_count: 808
- empirical_pct_nonzero_GOOD: 2
- empirical_pct_nonzero_BAD: 117
- live_behavior: would always be 0 since at live time no completed move can overlap anchor (its end_sec is past, can't be > anchor)

### `is_during_correct_move`
- definition: boolean wrapper of pct_correct_move_already_done > 0
- leak_classification: FUTURE_LEAK (same root cause)

### `pct_opposite_move_already_done`
- definition: same as pct_correct but for opposite direction
- leak_classification: FUTURE_LEAK

### `is_during_opposite_move`
- leak_classification: FUTURE_LEAK

### `is_late_after_50pct_correct_move`
- leak_classification: FUTURE_LEAK

### `filter_kept`
- definition: passive filter: zone is kept iff NOT duplicate of prior trigger AND confirm_to_trigger <= 60min. Both inputs require post-confirm info.
- source: scripts/strategy-calibration/good_watch_zone_feature_research.py apply_passive_filter() — iterates over TRIGGERED zones only, uses prior['triggerTs'] and confirm_to_trigger_min
- available_at_candidate: NO
- available_at_confirmed: NO (uses triggerTs of prior zones AND of current zone)
- available_at_trigger: YES (all inputs known at trigger of THIS zone, modulo timing of subsequent zones)
- leak_classification: FUTURE_LEAK at confirm; SAFE at trigger stage IF computed once at trigger of this zone
- empirical_kept_count: 224
- empirical_kept_count_no_trig: 0

### `filter_dup_suppressed`
- leak_classification: FUTURE_LEAK at confirm; SAFE at trigger

### `filter_fast_ok`
- definition: confirm_to_trigger_min <= 60 — uses triggerTs
- leak_classification: FUTURE_LEAK at confirm; SAFE at trigger

### `confirm_to_trigger_min`
- leak_classification: FUTURE_LEAK at confirm; SAFE at trigger

### `total_pre_trigger_min`
- leak_classification: FUTURE_LEAK at confirm; SAFE at trigger

### `trig_break_pct / trig_flow_multiplier / trig_side_flow_ok / trig_price`
- leak_classification: FUTURE_LEAK at confirm; SAFE at trigger

### `matched_move_size_pct / lead_min_before_move / watch_label / coverage_class`
- leak_classification: LABEL_ONLY (use only for evaluation)

### `taker_imb_aligned_30m / ofi_shift_aligned / vol_anomaly_15m_vs_bg / sweep_reclaim_aligned`
- definition: trade-derived, computed using only trades with timestamp <= anchor (confirmedTs)
- available_at_confirmed: YES
- leak_classification: SAFE_AT_CONFIRM

### `prior_move_*m_pct / local_range_*m_pct / local_realized_vol_*m / dist_to_recent_swing_* / dist_to_4h_mean_pct`
- definition: backward-looking on 1s buckets ending at anchor
- leak_classification: SAFE_AT_CONFIRM

### `cand_* / conf_* / score_absorption / score_refill / score_ofi / score_liquidity_void`
- definition: engine-computed at candidate or confirm stage
- leak_classification: SAFE_AT_CONFIRM

### `is_asia_session / is_us_session / is_session_open_2h / utc_hour / weekday / session`
- leak_classification: SAFE_AT_CONFIRM

### `same_dir_zones_active_60m / opp_dir_zones_active_60m`
- definition: count of PRIOR confirmed zones in past 60m — uses only confirmedTs < anchor
- leak_classification: SAFE_AT_CONFIRM


## Current best selector — live validity
- pair selector: `P::score_trigger_ge_1.0+pct_correct_move_already_done_le_0.0::top1` — **LIVE VALID: NO at confirm stage**
  - leak fields: ['score_trigger', 'pct_correct_move_already_done']
  - reason: LEAK — both fields are FUTURE_LEAK at confirm stage
- paper selector: `S::score_trigger_ge_1.0::top1 | delay_10m | stop_1.5%` — **LIVE VALID: NO if used as watch alert at confirm; PARTIALLY valid as trigger-stage execution rule**
  - leak fields: ['score_trigger']
  - reason: LEAK — score_trigger only available after trigger fires

## Flags
```
BEST_SELECTOR_LEAK_AUDIT_DONE = YES
PCT_CORRECT_MOVE_ALREADY_DONE_LEAK_FREE = NO
SCORE_TRIGGER_AVAILABLE_AT_CONFIRM = NO
SCORE_TRIGGER_AVAILABLE_AT_TRIGGER = YES
FILTER_KEPT_AVAILABLE_AT_CONFIRM = NO
FILTER_KEPT_AVAILABLE_AT_TRIGGER = YES
CURRENT_BEST_SELECTOR_LIVE_VALID = NO
CURRENT_BEST_SELECTOR_VALID_STAGE = none-at-confirm; partial-at-trigger
```