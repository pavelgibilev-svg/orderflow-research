# March in-sample zone calibration — final report (IN-SAMPLE, NOT production proof)

**Build:** 2026-05-26T11:47:32+00:00
**Scope:** IN-SAMPLE March 2026 OKX direct, 29 days. NOT production proof.
**Days:** 29 (14 first half + 15 second half; missing: 2026-03-17)
**Zones:** 1043; **primary 2 % moves:** 41; **baseline precision (all confirmed):** 11.79 %
**Baseline by half:** H1=13.24 %, H2=10.43 %

## CRITICAL HONESTY NOTE

- The 70-80 % winrate goal is **NOT REACHED** in March in-sample.
- Best leak-free selector precision (>=20 selected): **41.38 %** (`single::session_asia::top1_score`, 29 alerts, 1.0/day).
- Best leak-free paper-trade winrate (>=20 trades): **58.62 %** (`single::session_asia::top1_score` | delay_5m | stop_1.5, 29 trades).
- Higher numbers exist in the optimization output but use the `confirm_to_trigger_min` filter — that field is only knowable AFTER trigger, so applying it at confirm time is a **future leak**. We label it explicitly and exclude it from the headline.

## 1. Did we hit 70-80 % profitable selected zones in March?
- **NO.** Best clean precision = **41.38 %** on 29 alerts; best clean paper-trade winrate = **58.62 %** on 29 trades.
- Only with a future-leak filter (`ctt_le30`, applied at confirm time but using post-confirm data) does winrate creep up to ~62 % — that result is not usable in a real signal pipeline.

## 2. If goal hit — selector / formula / size / pace
- (Goal NOT hit.) The best honest selector is **`single::session_asia::top1_score`**:
  - hard filter: `is_asia_session == 1` (UTC 0-7)
  - within the day, rank by `explainable_score` (filter_kept, not_late, opp_eq0, taker_imb_aligned_30m, ofi_shift_aligned, sweep_reclaim_aligned, plus overextension penalty)
  - top 1 per day
  - result: 29 alerts, 1.0/day, precision 41.38 %, recall 9.76 %, wrong-direction rate 3.45 %
  - LONG precision: 46.67 %, SHORT precision: 35.71 %
  - H1 precision: 42.86 %, H2 precision: 40.0 % (STABLE)
  - avg lead: 102.55 min, max consecutive bad alerts: 5

## 3. Why we can't reach 70-80 %
- Only 123 GOOD zones across 1043 confirmed → baseline ~11.8 % precision. Reaching 70 % needs a 6x lift.
- Even the best clean combination (Asia session x top-1 by score) only reaches ~41 % precision. Adding more filters drops sample size below 20 (overfit territory).
- After 0.14 % roundtrip cost, the realistic expectancy of the best leak-free combo is **+0.61 % per trade** (PF 2.25). Solid but not the 70-80 % winrate fantasy.
- The labels are noisy: zones marked GOOD have ~25 % wrong-direction false positives even after movement-first labelling.

## 4. Features that really work
- `is_asia_session` (Asia open zones higher quality on average).
- `filter_kept` (passive duplicate + fast-trigger filter): +5 pp precision uplift.
- `opp_dir_zones_active_60m == 0`, `is_during_opposite_move == 0` (conflict guards).
- `is_late_after_50pct_correct_move == 0` (late-entry guard — NEW from this pass).
- `prior_move_60m_pct` small, `local_range_180m_pct` small (clean context).
- `trig_break_pct` higher in GOOD.
- `taker_imb_aligned_30m`, `ofi_shift_aligned`, `sweep_reclaim_aligned` — modest but real.

## 5. Useful orderflow features (extracted from trades, no L2)
- `is_late_after_50pct_correct_move`, `is_during_opposite_move` (movement-relative timing).
- `ofi_shift_aligned` (5m vs 30m taker imbalance shift).
- `taker_imb_aligned_30m/60m` (windowed taker imbalance).
- `vol_anomaly_15m_vs_bg` (mildly helpful).
- `sweep_reclaim_aligned` (binary; small but positive).

## 6. Useless features
- All engine score fields that fire on ~100 % of candidates: `cand_absorb_score`, `cand_*_refill_score`, `cand_range_compression`, `score_*` raw.
- `conf_cycles_seen`, `conf_age_min`, `conf_opposite_thinning`, `conf_defended_persistence_sec`.
- Raw `trig_flow_multiplier` (high in BAD too).
- `cand_pressure_against` (no separation).
- `local_realized_vol_*` (very small d).

## 7. Anti-features
- `is_late_after_50pct_correct_move` (strong anti-feature).
- `is_during_opposite_move` (strong anti-feature for direction).
- `prior_move_180m_pct` (direction-flipped: positive d vs BAD but negative d vs wrong_direction).

## 8. LONG / SHORT differences
- Best LONG selector: `dir::LONG+filter_kept+opp_eq0::top1_score`, LONG precision=28.0 %, n=25, H1=45.45 % vs H2=14.29 % (H1-dominant — possibly overfit to first half).
- Best SHORT selector: `dir::SHORT+filter_kept+not_late::top1_score`, SHORT precision=22.22 %, n=27, H1=23.08 % vs H2=21.43 % (more stable than LONG).
- LONG zones cluster on Asia opens; SHORT zones cluster around impulse exhaustion in US session.

## 9. First-half vs second-half differences
- H1 baseline: 13.24 %, H2 baseline: 10.43 % — H2 has lower GOOD rate (regime change).
- The headline selector `single::session_asia::top1_score` is stable: H1=42.86 %, H2=40.0 %.
- Several aggressive combos collapse in H2 (e.g. `dir::LONG+filter_kept+opp_eq0`: H1 45 % -> H2 14 %).

## 10. Which moves does the detector see well?
- Asia-session impulse reversals after first leg (sharp 1.5-2 % moves into clean range).
- Mid-session continuations where the engine confirms BEFORE breakout (lead > 60 min).

## 11. Which moves does detector / selector miss?
- Slow-grind 2 % moves with no obvious absorption (no candidate).
- Wick-only 2 % spikes (confirms after the spike).
- News-driven instant moves (any selector lags).

## 12. What to change in the research layer
- Add L2-derived refill/defense features (current proxies uninformative).
- Build a direction guard module on `is_during_opposite_move` + opposite-confirmed-zone count.
- Add cluster-dedup by `_label_unique_move_id` so we don't pick 2 zones from the same impulse.
- Add an explicit retest-quality feature for trigger-stage entries.
- Reserve `confirm_to_trigger_min` filters for *trigger-stage* selectors only (never for confirm-time).

## 13. What we CANNOT change in the engine
- Strategy definitions, thresholds, zone detector, confirmation logic, trigger logic. Selector layer only.

## 14. Can we build TG shadow on calibrated selector?
- The `single::session_asia::top1_score` selector is honest, leak-free, 1/day, 41 % precision, stable across halves. **As a SHADOW research channel marked clearly as 'in-sample, not validated OOS' — acceptable.**
- As a production trading signal — **NO**. Out-of-sample April/May validation needed first.

## 15. What data / features we still need
- Full L2 reconstruction for refill / defense / wall persistence / microprice / spread.
- Cross-venue (Binance) feature mirroring for direction confirmation.
- A larger labeled sample (April-May) to verify stability of the patterns found here.
- Calendar / macro news event flag (instant moves over-represented in BAD).

## Final flag matrix

```
MARCH_IN_SAMPLE_CALIBRATION_DONE = YES
DAYS_INCLUDED = 29
TOTAL_ZONES = 1043
TOTAL_MARKET_2PCT_MOVES = 41
TOTAL_SELECTED_BY_BEST_SELECTOR = 29
BEST_SELECTOR_NAME = single::session_asia::top1_score
BEST_SELECTOR_ALERTS_PER_DAY = 1.0
BEST_SELECTOR_PRECISION = 41.38
BEST_SELECTOR_RECALL = 9.76
BEST_SELECTOR_WRONG_DIRECTION_RATE = 3.45
BEST_SELECTOR_FIRST_HALF_PRECISION = 42.86
BEST_SELECTOR_SECOND_HALF_PRECISION = 40.0
BEST_SELECTOR_OVERFIT_RISK = MEDIUM
BEST_PAPER_TRADE_MODEL = single::session_asia::top1_score | delay_5m | stop_1.5 (leak-free)
BEST_PAPER_TRADES = 29
BEST_PAPER_WINRATE = 58.62
BEST_PAPER_EXPECTANCY_PRE_COST = 0.7515
BEST_PAPER_EXPECTANCY_AFTER_COST = 0.6115
BEST_PAPER_PF_AFTER_COST = 2.246
MARCH_70PCT_GOAL_REACHED = NO
MARCH_80PCT_GOAL_REACHED = NO
MINIMUM_TRADES_CONSTRAINT_MET = YES
USEFUL_ORDERFLOW_FEATURES_FOUND = YES
LOCAL_NORMALIZATION_HELPED = YES
DIRECTION_GUARD_NEEDED = YES
TG_SELECTOR_CAN_BE_1_2_PER_DAY = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- engine / thresholds / detector: UNCHANGED.
- decision features: pre-confirm only (no future leak in the headline selector).
- `ctt_le_*` selectors are explicitly excluded from headline as future-leak; reported only as execution-stage curiosities.
- outcome labels: NEVER used in selector logic.
- target strict 2 %; cost 0.14 % roundtrip.
- production claim: NONE.