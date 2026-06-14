# Useless and anti-features (29-day OKX March)

**Build:** 2026-05-25T15:31:41+00:00

## Useless features (27)

| feature | reason |
|---|---|
| `local_range_15m_pct` | |d good vs bad|=0.1447 < 0.15 |
| `local_realized_vol_60m` | |d good vs bad|=0.1446 < 0.15 |
| `zone_width_pct` | |d good vs bad|=0.131 < 0.15 |
| `prior_move_180m_pct` | |d good vs bad|=0.1251 < 0.15 |
| `local_realized_vol_180m` | |d good vs bad|=0.1065 < 0.15 |
| `opp_dir_zones_active_60m` | |d good vs bad|=0.072 < 0.15 |
| `trig_flow_multiplier` | |d good vs bad|=0.0703 < 0.15 |
| `cand_pressure_against` | |d good vs bad|=0.0692 < 0.15 |
| `score_ofi` | |d good vs bad|=0.0685 < 0.15 |
| `cand_absorb_score` | |d good vs bad|=0.0654 < 0.15 |
| `candidate_to_confirm_min` | |d good vs bad|=0.0648 < 0.15 |
| `conf_age_min` | |d good vs bad|=0.0648 < 0.15 |
| `conf_defended_persistence_sec` | |d good vs bad|=0.0648 < 0.15 |
| `conf_cycles_seen` | |d good vs bad|=0.0574 < 0.15 |
| `same_dir_zones_active_60m` | |d good vs bad|=0.0415 < 0.15 |
| `conf_opposite_thinning` | |d good vs bad|=0.0377 < 0.15 |
| `confirm_to_trigger_min` | |d good vs bad|=0.0368 < 0.15 |
| `total_pre_trigger_min` | |d good vs bad|=0.0312 < 0.15 |
| `cand_prior_move_pct` | |d good vs bad|=0.0285 < 0.15 |
| `score_refill` | |d good vs bad|=0.0279 < 0.15 |
| `filter_fast_ok` | near-zero separation (|good-bad|=2.3599999999999994pp) |
| `score_absorption` | |d good vs bad|=0.0196 < 0.15 |
| `score_trigger` | |d good vs bad|=0.0118 < 0.15 |
| `cand_refill_with` | |d good vs bad|=0.0028 < 0.15 |
| `score_liquidity_void` | |d good vs bad|=0 < 0.15 |
| `cand_range_compression` | true for >=95% in both good (100.0%) and bad (100.0%) |
| `trig_side_flow_ok` | near-zero separation (|good-bad|=0pp) |

## Anti-features (1)

| feature | reason |
|---|---|
| `prior_move_180m_pct` | positive d vs bad (0.1251) BUT negative d vs wrong (-0.3032) — direction-flipped |