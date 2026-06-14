# OKX direct partial-March 2026 - local anomaly analysis

**Scope:** Per-day percentile rank of each pre-trigger feature for each zone, plus full-pool rank.
**Why not minute-windowed:** the existing per-day backtest JSON aggregates each zone into one row; we don't
have a minute-by-minute orderflow stream from these artefacts, so a true 30m/1h/3h/6h z-score is not buildable
without re-running the backtest with extra logging (forbidden per scope).

## A. Mean per-day percentile rank by class

| feature | primary mean / median | duplicate mean / median | failed mean / median |
|---|---|---|---|
| `cand_pressure_against` | 63.7 / 66.3 | 55.69 / 61.46 | 48.6 / 45.59 |
| `cand_absorb_score` | 62.49 / 66.18 | 53.95 / 60.19 | 48.32 / 47.3 |
| `cand_refill_with` | 43.44 / 38.54 | 54.93 / 54.41 | 50.42 / 51.09 |
| `cand_prior_move_pct` | 65.24 / 46.88 | 50.12 / 46.3 | 50.83 / 45.65 |
| `conf_cycles_seen` | 46.69 / 38.3 | 57.81 / 61.67 | 49.56 / 46.88 |
| `conf_age_min` | 45.32 / 51.56 | 47.3 / 50.0 | 48.81 / 48.11 |
| `trig_break_pct` | 31.82 / 29.31 | 52.43 / 54.76 | 50.36 / 50.0 |
| `trig_flow_multiplier` | 61.13 / 63.79 | 47.69 / 45.24 | 50.12 / 51.67 |
| `score_ofi` | 43.64 / 44.57 | 58.62 / 59.78 | 47.73 / 46.74 |
| `score_absorption` | 65.41 / 83.82 | 52.34 / 50.0 | 47.77 / 44.59 |
| `score_trigger` | 56.76 / 69.44 | 46.52 / 48.08 | 50.95 / 63.89 |
| `zone_width_pct` | 42.79 / 38.04 | 42.03 / 35.0 | 47.36 / 46.88 |

## B. Mean full-pool percentile rank by class

| feature | primary mean / median | duplicate mean / median | failed mean / median |
|---|---|---|---|
| `cand_pressure_against` | 63.01 / 62.45 | 55.14 / 60.88 | 49.85 / 48.53 |
| `cand_absorb_score` | 62.38 / 65.98 | 54.52 / 61.47 | 48.79 / 47.16 |
| `cand_refill_with` | 44.41 / 35.0 | 53.87 / 55.78 | 50.87 / 52.06 |
| `cand_prior_move_pct` | 64.38 / 44.31 | 49.21 / 44.31 | 51.42 / 44.31 |
| `conf_cycles_seen` | 48.47 / 35.28 | 55.99 / 57.81 | 50.45 / 48.02 |
| `conf_age_min` | 45.86 / 47.13 | 47.68 / 52.47 | 48.25 / 47.83 |
| `trig_break_pct` | 35.39 / 28.31 | 53.66 / 52.37 | 49.57 / 48.98 |
| `trig_flow_multiplier` | 60.1 / 54.41 | 46.26 / 42.2 | 50.81 / 52.37 |
| `score_ofi` | 43.52 / 37.35 | 58.19 / 59.9 | 47.8 / 46.96 |
| `score_absorption` | 62.05 / 74.41 | 51.38 / 51.08 | 48.94 / 47.75 |
| `score_trigger` | 55.97 / 74.41 | 46.04 / 41.53 | 51.22 / 74.41 |
| `zone_width_pct` | 45.18 / 42.45 | 45.04 / 39.12 | 45.35 / 44.61 |

## C. Reading guide

- Per-day rank of 50 = median zone for that day. If primary's mean is > 60 for a feature, that feature is
  systematically high among primaries vs other zones the same day - candidate for a `local_top` filter.
- Mind the n: 15 primaries spread across 14 days; per-day rank can be noisy.