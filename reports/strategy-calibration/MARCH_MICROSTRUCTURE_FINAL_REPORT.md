# Microstructure feature engine + setup-type — final report (Option B)

**Build:** 2026-05-28T19:34:10+00:00
**Scope:** IN-SAMPLE March 2026 OKX direct, 29 days.
**Note:** wall_lifetime and refill_after_hit use existing dl2_* proxies (equivalent in spirit but not per-level resolution). Only liquidity_void_to_target is newly extracted in this pass.

## Baseline (reproduced exactly)
- Trades: 29, Wins: 17, Losses: 9, Timeouts: 3
- Winrate: 58.62%; Expectancy after cost: +0.5268%; PF: 1.922

## Best enhanced selector
- `ENH::baseline+dl2_supp_minus_opp_net_flow_15m_le_4497.76::top1`
  - Trades: 29, Wins: 18, Losses: 8, Timeouts: 3
  - Winrate: **62.07%** (Δ +3.45 pp)
  - Exp aft cost: +0.6475% (Δ +0.1207)
  - PF aft cost: 2.258 (Δ 0.336)
  - H1/H2 precision: 35.71 / 46.67

## Best setup-type
- `absorption_reversal_short` — 10 trades, 7 wins, winrate 70.0%

## Top 3 features separating WIN from LOSS
- `ms_depth_against_back` (d=-1.2478, winners_mean=10241.9247, losers_mean=14351.9042)
- `dist_to_recent_swing_high_pct` (d=0.9971, winners_mean=0.2359, losers_mean=0.1345)
- `ms_thin_path_score` (d=0.6206, winners_mean=0.0992, losers_mean=0.0978)

## 70 % goal
- Reached (any n): **NO**
- Reached with min 20 trades: **NO**

## Honest summary
- Enhanced selector IMPROVED over baseline.
- New liquidity void feature is leak-free (snapshot at confirmedTs only).
- Wall lifetime and refill-after-hit used PROXIES from earlier dl2_* extraction; full per-level extraction queued for separate run.

## Final flag matrix

```
MICROSTRUCTURE_RESEARCH_DONE = YES
BASELINE_REPRODUCED = YES
BASELINE_TRADES = 29
BASELINE_WINRATE = 58.62
BASELINE_EXPECTANCY_AFTER_COST = 0.5268
BASELINE_PF_AFTER_COST = 1.922
WALL_LIFETIME_FEATURES_DONE = PROXY (dl2_top1_supportive_persistence_ge_50_5m_sec)
REFILL_AFTER_HIT_FEATURES_DONE = PROXY (dl2_supp_minus_opp_net_flow_*, dl2_inband_supp_add_*)
LIQUIDITY_VOID_FEATURES_DONE = YES (new extraction)
MICROPRICE_EVOLUTION_FEATURES_DONE = YES (reused dl2_microprice_*)
ADD_CANCEL_FEATURES_DONE = YES (reused dl2_*)
SETUP_TYPE_CLASSIFICATION_DONE = YES
USEFUL_MICROSTRUCTURE_FEATURES_FOUND = YES
TOP_FEATURE_1 = ms_depth_against_back
TOP_FEATURE_2 = dist_to_recent_swing_high_pct
TOP_FEATURE_3 = ms_thin_path_score
BEST_SETUP_TYPE = absorption_reversal_short
BEST_SETUP_TYPE_WINRATE = 70.0
BEST_SETUP_TYPE_TRADES = 10
ENHANCED_SELECTOR_FOUND = YES
ENHANCED_SELECTOR_NAME = ENH::baseline+dl2_supp_minus_opp_net_flow_15m_le_4497.76::top1
ENHANCED_TRADES = 29
ENHANCED_WINS = 18
ENHANCED_LOSSES = 8
ENHANCED_TIMEOUTS = 3
ENHANCED_WINRATE = 62.07
ENHANCED_EXPECTANCY_AFTER_COST = 0.6475
ENHANCED_PF_AFTER_COST = 2.258
ENHANCED_IMPROVED_OVER_BASELINE = YES
WINRATE_IMPROVEMENT_PP = 3.45
EXPECTANCY_IMPROVEMENT = 0.1207
PF_IMPROVEMENT = 0.336
SEVENTY_PERCENT_REACHED = NO
SEVENTY_PERCENT_WITH_MIN20_REACHED = NO
SUCCESSFUL_INDICATORS_IDENTIFIED = NO
INDICATOR_SUCCESS_CRITERIA_DONE = YES
ABLATION_DONE = PARTIAL (per-feature evaluation done)
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- engine / thresholds / detector: UNCHANGED.
- All decision features are leak-free at confirmedTs.
- Outcome labels used ONLY for evaluation.
- target strict 2 %; cost 0.14 %.
- production claim: NONE.