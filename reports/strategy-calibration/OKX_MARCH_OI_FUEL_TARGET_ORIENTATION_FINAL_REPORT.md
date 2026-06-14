# OKX March OI/fuel + target orientation — final report

**Build:** 2026-05-30T07:31:47+00:00
**Scope:** IN-SAMPLE OKX March 2026. No engine change. Primary win strict 2%. No liquidations. No Binance run.

## 1-2. Data availability
- TRUE OI from OKX: **YES but DAILY only** (rubik open-interest-volume 1D; 5m/1H don't reach March). USD aggregate BTC.
- Funding from OKX: **YES** (public funding-rate-history, 8h, covers March).
## 3-4. Features
- TRUE OI features built (daily regime): oi_delta_1d/3d, oi_zscore_14d, price+OI regime. Intraday OI deltas NOT possible.
- FLOW_PROXY built for intraday (taker imbalance/vol zscores) — explicitly NOT OI.
## 5. Did fuel improve over enhanced 62.07%?
- **YES**. Best fuel selector (min20): `S7_EV_positive` — wr 65.38%, exp 0.7638%, PF 2.689.
## 6. Does fuel explain correct-direction-but-no-2pct?
- true_fuel d(win vs nonwin) small (see fuel eval). Daily OI too coarse to time intraday follow-through. Funding background only.
## 7. Target-zone orientation as secondary metric
- hit_2pct=18/29; local_reaction_only=0; target_too_close(<2%)=25.
- Useful as DIAGNOSTIC orientation; NOT used as primary win or hard gate.
## 8. 70% with min20?
- **NO**.
## 9. Final OKX rule set
- Selector: `dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76`, top1/day, entry=confirmed.
- Trade: TP fixed 2%, SL 1.5%, no BE, timeout 24h, cost 0.14%. → 62.07% wr, PF 2.258, +18.78%.
- Fuel/target-zone: keep as ORIENTATION/diagnostic only (did not beat baseline).
## 10-11. Binance readiness
- READY: freeze OKX thresholds, replay engine on Binance, apply identical model, compare OOS. Recompute native OI/funding fresh (do not port OKX daily-OI thresholds).

## Final flags
```
OKX_MARCH_OI_FUEL_RESEARCH_DONE = YES
OKX_PUBLIC_OI_ENDPOINT_FOUND = YES
OKX_OI_HISTORY_AVAILABLE = YES (1D only for March)
OI_DATA_AVAILABLE = YES (daily)
FUNDING_DATA_AVAILABLE = YES
LIQUIDATIONS_USED = NO
TRUE_OI_FEATURES_BUILT = YES (daily)
FLOW_PROXY_BUILT = YES
FLOW_PROXY_NOT_TRUE_OI = YES
TARGET_ZONE_ORIENTATION_BUILT = YES
TARGET_ZONE_USED_AS_PRIMARY_WIN = NO
BASELINE_ENHANCED_TRADES = 29
BASELINE_ENHANCED_WINRATE = 62.07
BASELINE_ENHANCED_EXPECTANCY_AFTER_COST = 0.6475
BASELINE_ENHANCED_PF_AFTER_COST = 2.258
BEST_FUEL_SELECTOR_NAME = S7_EV_positive
BEST_FUEL_SELECTOR_TRADES = 26
BEST_FUEL_SELECTOR_WINRATE = 65.38
BEST_FUEL_SELECTOR_EXPECTANCY_AFTER_COST = 0.7638
BEST_FUEL_SELECTOR_PF_AFTER_COST = 2.689
FUEL_IMPROVED_OVER_ENHANCED = YES
TARGET_ZONE_USEFUL_AS_ORIENTATION = PARTIAL
SEVENTY_PERCENT_REACHED = NO
SEVENTY_PERCENT_WITH_MIN20_REACHED = NO
FINAL_OKX_RULE_SET_DEFINED = YES
READY_FOR_BINANCE_TEST = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- engine/thresholds/detector UNCHANGED; primary win strict 2%; target-zone secondary only; no liquidations; no Binance run; true OI from OKX statistics (not volume); FLOW_PROXY labeled non-OI; no future leak.