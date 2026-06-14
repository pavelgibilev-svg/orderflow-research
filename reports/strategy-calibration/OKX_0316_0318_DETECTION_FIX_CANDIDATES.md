# Detection fix candidates (research only, NO production integration)

## Earlier TG watch-zone mode

- **What pain it fixes:** Engine triggers late; correct zones detected as candidate/confirmed but trigger happens after >50% of move. Watch-zone alert lets user be ready before trigger.
- **Risks:** More noise; user fatigue; alerts on candidates that never confirm (low precision).
- **Fields needed:** candidate stage timestamps + scores; no new feature engineering.
- **Feasible without engine change:** YES (read-only Telegram path).
- **Validation plan:** Backtest: count watch-zone alerts per day; how many lead to a triggered zone within X minutes; how many lead to a 2 % move regardless.

## Separate LONG/SHORT timing rules

- **What pain it fixes:** 03-16 LONG primary suppressed by fast_trigger<=60m; engine appears to develop LONG zones slower on bull days. Different per-direction caps may unlock LONGs without re-introducing failed SHORTs.
- **Risks:** Asymmetric filters are notoriously easy to overfit; requires more validation periods.
- **Fields needed:** confirm_to_trigger_min split by direction.
- **Feasible without engine change:** YES (filter is post-hoc).
- **Validation plan:** Sweep per-direction caps in {45, 60, 90, 120 m} on full 24-day Tardis OOS pool; check if it inverts SHORT win rate.

## Replace absolute thresholds with local-normalized features

- **What pain it fixes:** On high-vol days, absolute OFI / flow_multiplier triggers fire on noise; on low-vol days, true anomalies are missed. Local percentile/z-score scales to regime.
- **Risks:** Window choice (15 vs 60 vs 180 m) matters; local-normalize on the same data used to design rule = overfit. Need OOS for any threshold.
- **Fields needed:** Local windowed OFI / flow / volume percentiles.
- **Feasible without engine change:** YES (research filter on top of engine output).
- **Validation plan:** Compute local percentile features for every triggered zone in the 24-date Tardis pool + this OKX March; check if primary-unique winners systematically have higher local-anomaly percentile than failed.

## Late-trigger guard

- **What pain it fixes:** Section B classifications show many zones cover late (>50% of move already done by trigger). Late triggers have unfavourable R/R because target is already half-gone.
- **Risks:** Needs reference to actual move start which is hard to define live without future leak; could proxy with local-percentile prior-move metric.
- **Fields needed:** Prior move % over windows 15/30/60 m (already in zone reasons.candidate.downMovePct/upMovePct, but only weakly).
- **Feasible without engine change:** YES (filter on candidate prior-move feature).
- **Validation plan:** Add `prior_move_60m_pct >= X` rule on top of base filter; compare expectancy on held-out pool.

## Wrong-direction guard

- **What pain it fixes:** Section D shows N wrong-direction triggers (engine SHORT on bull-side; engine LONG on bear-side without reversal evidence).
- **Risks:** True countertrend reversal setups would be suppressed.
- **Fields needed:** Local trend over 1h or 3h before trigger.
- **Feasible without engine change:** YES.
- **Validation plan:** Suppress triggers whose direction is opposite to last-3h trend AND there is no `reversal` flag in confirmed reasons; backtest on held-out pool.

## TG selector (1-2 per day)

- **What pain it fixes:** Lots of alerts but only 1-2 actually matter. User fatigue + missed signal-to-noise ratio.
- **Risks:** Subjective ranking; selector itself can overfit.
- **Fields needed:** Composite score from local-anomaly + direction correctness + earliness.
- **Feasible without engine change:** YES.
- **Validation plan:** Force selector to pick top-N per day; measure primary recall + expectancy vs no-selector baseline.

## Movement-coverage metric in CI

- **What pain it fixes:** Currently we have NO metric of how well engine catches REAL market moves. We measure by zone outcome, not by market outcome.
- **Risks:** None — pure read-only metric.
- **Fields needed:** ZigZag detector output.
- **Feasible without engine change:** YES.
- **Validation plan:** Add to per-day report: # of market 2 % moves on the day; engine coverage rate (early/mid/late/missed).
