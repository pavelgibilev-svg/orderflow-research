# Expanded feature library — leak-free vs leak-flagged

**Build:** 2026-05-26T12:33:22+00:00

## Numeric features (LEAK-FREE; computed at or before confirmed time)

- `cand_pressure_against`
- `cand_buy_pressure`
- `cand_sell_pressure`
- `cand_absorb_score`
- `cand_bid_refill_score`
- `cand_ask_refill_score`
- `cand_refill_with`
- `cand_prior_move_pct`
- `conf_cycles_seen`
- `conf_age_min`
- `conf_defended_persistence_sec`
- `conf_opposite_thinning`
- `conf_void_score`
- `score_absorption`
- `score_refill`
- `score_ofi`
- `score_liquidity_void`
- `score_trigger`
- `zone_width_pct`
- `same_dir_zones_active_60m`
- `opp_dir_zones_active_60m`
- `prior_move_15m_pct`
- `prior_move_30m_pct`
- `prior_move_60m_pct`
- `prior_move_180m_pct`
- `abs_prior_move_15m_pct`
- `abs_prior_move_30m_pct`
- `abs_prior_move_60m_pct`
- `abs_prior_move_180m_pct`
- `local_range_15m_pct`
- `local_range_30m_pct`
- `local_range_60m_pct`
- `local_range_180m_pct`
- `local_realized_vol_15m`
- `local_realized_vol_30m`
- `local_realized_vol_60m`
- `local_realized_vol_180m`
- `dist_to_recent_swing_high_pct`
- `dist_to_recent_swing_low_pct`
- `dist_to_4h_mean_pct`
- `abs_dist_to_4h_mean_pct`
- `taker_imb_5m`
- `taker_imb_15m`
- `taker_imb_30m`
- `taker_imb_60m`
- `taker_imb_180m`
- `taker_imb_aligned_5m`
- `taker_imb_aligned_15m`
- `taker_imb_aligned_30m`
- `taker_imb_aligned_60m`
- `taker_imb_aligned_180m`
- `taker_total_vol_15m`
- `taker_total_vol_60m`
- `vol_anomaly_15m_vs_bg`
- `ofi_shift_5m_vs_30m`
- `ofi_shift_aligned`
- `pct_correct_move_already_done`
- `pct_opposite_move_already_done`
- `utc_hour`

## Boolean features (LEAK-FREE)

- `filter_kept`
- `filter_dup_suppressed`
- `filter_fast_ok`
- `cand_range_compression`
- `is_during_correct_move`
- `is_during_opposite_move`
- `is_late_after_50pct_correct_move`
- `sweep_reclaim_aligned`
- `is_asia_session`
- `is_us_session`
- `is_session_open_2h`

## LEAKY features (excluded from leak-free selectors)

- `confirm_to_trigger_min`
- `total_pre_trigger_min`
- `trig_break_pct`
- `trig_flow_multiplier`
- `trig_side_flow_ok`
- `trig_price`
- `_label_is_primary`
- `_label_reached_raw`
- `matched_move_size_pct`
- `lead_min_before_move`
- `watch_label`
- `coverage_class`

## L2 features NOT extracted (and why)
- Full refill speed / persistence: requires book reconstruction (not in this pass).
- Wall persistence / cancellation rate: requires per-event book deltas.
- Microprice / spread: requires per-snapshot book state.
- Liquidity void toward target: requires book.
- Depth slope near zone: requires book.
- Liquidity removed opposite side: requires book.
- Engine's `cand_*_refill_score` and `cand_absorb_score` are proxies BUT prior research already flagged them as low-separation (fire on ~100 % of candidates).

## Honesty notes
- Movement-relative features (`pct_correct_move_already_done`, `is_late_after_50pct_correct_move`) are computed using ONLY moves that have already started or completed at confirm time. They are not future-leak.
- Distance / swing features look BACK 4 h from confirm time only.
- Taker imbalance windows end at confirm time (exclusive of future trades).