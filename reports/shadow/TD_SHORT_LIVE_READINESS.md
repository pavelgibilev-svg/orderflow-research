# E. TD-short live/OOS readiness

**Build:** 2026-06-04T18:48:39+00:00

**build** — 2026-06-04T18:48:39+00:00
**1_shadow_ready** — YES — frozen causal gates, decision log written, no trading/Telegram.
**2_future_leak** — NO leak — decision log has zero outcome/future fields; outcomes are a separate file.
**3_decision_outcome_separated** — YES — observer writes decisions; updater writes outcomes.
**4_daily_data_needed** — per day: confirmed zones + causal features (regime, prior_move_60m/1d, eng_ofi, taker_imb, microprice, void/walls, reclaim).
**5_how_to_run_daily** — run td_short_shadow_observer.py on the day's confirmed-zone feature cache -> decisions; after 24h run td_short_outcome_updater.py.
**6_min_oos** — >=20 accepted TD-short trades on NEW data (not OKX March).

## OOS success criteria
- PF>1.5
- winrate>=50-55%
- max loss streak<=5
- no catastrophic counter-trend losses (MAE not >> SL)
- results NOT concentrated in one venue/day
