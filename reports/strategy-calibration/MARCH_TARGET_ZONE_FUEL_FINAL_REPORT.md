# Target-zone + 3 trade models + OI/fuel — final report

**Build:** 2026-05-29T17:37:36+00:00
**Scope:** IN-SAMPLE OKX March 2026. No engine change. Target strict 2%. No future leak in decisions.

## 1. OI/funding/liquidation data
- **NONE available for March OKX** (only book+trades). OI/fuel sections = NOT_AVAILABLE. April-01 used only as schema reference.

## 2-5. Model comparison (enhanced selector basis)

| model | trades | winrate% | exp_aft% | PF_aft | totRet% |
|---|---:|---:|---:|---:|---:|
| A fixed 2% | 29 | 62.07 | 0.6475 | 2.258 | 18.7771 |
| B target-zone filter | 4 (skip 25) | 50.0 | 0.3476 | 1.597 | 1.3905 |
| C target-TP + C_enhanced_targetTP_BE_C4 | 4 | 25.0 | 0.3618 | 4.446 | 1.4472 |

- Target-zone filter improved over fixed 2%: **NO**
- BE improved over no-BE: **YES**
- Best BE variant: **C_enhanced_targetTP_BE_C4** (losses saved 1, winners killed 1)

## 6-8. BE detail
- BE exits in best variant: 3
- Losses saved by BE: 1
- Winners killed by BE: 1

## 9-10. Non-win explanation
- Enhanced non-wins: 11
- Explained by insufficient target-zone room (B would skip): 9
- Low fuel_score explanation: NOT_AVAILABLE (no OI/liq data)

## 11-12. Winrate / 70%
- Best model: **A_enhanced_fixed2pct** — winrate 62.07%, exp_aft 0.6475%, PF 2.258, 29 trades.
- 70% reached: **NO**; with min20: **NO**

## 13-14. Fixed vs target-zone; BE vs no-BE
- Fixed 2% is as good or better than target-zone filter.
- BE helps.

## 15-16. Rules for next zone iteration
- Keep enhanced selector (dist_to_recent_swing_high<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day).
- Apply target-zone room>=2% filter ONLY if it improved expectancy here (see flag).
- Use BE variant only if it improved expectancy (see flag).
- FETCH OKX March OI/funding/liquidation data to unlock fuel features (highest-value missing input).

## Final flags

```
TARGET_ZONE_FUEL_RESEARCH_DONE = YES
OI_DATA_AVAILABLE = NO
FUNDING_DATA_AVAILABLE = NO
LIQUIDATION_DATA_AVAILABLE = NO
TARGET_ZONE_HEATMAP_DONE = YES
TARGET_ZONE_CANDIDATES_BUILT = YES
TRADE_MODEL_COMPARISON_DONE = YES
NON_WIN_RESCUE_ANALYSIS_DONE = YES
MODEL_A_FIXED_TP_TRADES = 29
MODEL_A_FIXED_TP_WINRATE = 62.07
MODEL_A_FIXED_TP_EXPECTANCY_AFTER_COST = 0.6475
MODEL_A_FIXED_TP_PF_AFTER_COST = 2.258
MODEL_B_TARGET_ZONE_FILTER_TRADES = 4
MODEL_B_TARGET_ZONE_FILTER_WINRATE = 50.0
MODEL_B_TARGET_ZONE_FILTER_EXPECTANCY_AFTER_COST = 0.3476
MODEL_B_TARGET_ZONE_FILTER_PF_AFTER_COST = 1.597
MODEL_C_TARGET_ZONE_BE_TRADES = 4
MODEL_C_TARGET_ZONE_BE_WINRATE = 25.0
MODEL_C_TARGET_ZONE_BE_EXPECTANCY_AFTER_COST = 0.3618
MODEL_C_TARGET_ZONE_BE_PF_AFTER_COST = 4.446
MODEL_C_BE_EXITS = 3
MODEL_C_LOSSES_SAVED_BY_BE = 1
MODEL_C_WINNERS_KILLED_BY_BE = 1
BEST_MODEL_NAME = A_enhanced_fixed2pct
BEST_MODEL_TRADES = 29
BEST_MODEL_WINRATE = 62.07
BEST_MODEL_EXPECTANCY_AFTER_COST = 0.6475
BEST_MODEL_PF_AFTER_COST = 2.258
BEST_MODEL_TOTAL_RETURN_AFTER_COST = 18.7771
TARGET_ZONE_IMPROVED_OVER_FIXED_2PCT = NO
BE_IMPROVED_OVER_NO_BE = YES
FUEL_FEATURES_IMPROVED_SELECTOR = NOT_AVAILABLE
SEVENTY_PERCENT_REACHED = NO
SEVENTY_PERCENT_WITH_MIN20_REACHED = NO
NEXT_ZONE_RULES_DEFINED = YES
READY_FOR_NEXT_ZONE_TEST = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- engine/thresholds/detector UNCHANGED; target strict 2%; no future leak in decision features; OI/fuel honestly marked NOT_AVAILABLE; production claim NONE.