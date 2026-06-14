# High-priority Telegram filter research - summary

**Build:** 2026-05-23T09:46:28+00:00
**No engine change. No new backtest. Read-only over existing zones + ledger + price path.**

## 1. Why did OKX stop out?

Filtered baseline on OKX: **41 strict trades / 11 wins / 24 losses (-1 %) / 6 timeouts**.
Section A (Cohen's d feature comparison) ranks features that distinguish winners from stop-out losers.
Section B audits 15 primary unique zones; many of them hit -1 % stop before reaching +2 % target.

## 2. Pre-trigger features that distinguish stop-outs

(See `OKX_STOP_OUT_FEATURE_ANALYSIS.md` for full Cohen's d table.)

## 3. Can we cut alerts to 1-2/day?

- OKX baseline alerts/day = **2.929**, Binance baseline = **1.583**.
- Best ROBUST candidate: **`NONE`** — OKX None/d, BIN None/d.

## 4-6. Target wins kept / expectancy / cross-venue

- Robust expectancy: OKX **None %** / BIN **None %**
- Robust PF: OKX **None** / BIN **None**
- Robust primary recall: OKX **None %** / BIN **None %**
- Robust stop-loss reduction: OKX **None %** / BIN **None %**

## 7. Entry/stop alternatives

See `ENTRY_STOP_ALTERNATIVES_DIAGNOSTIC.md`. Diagnostic only.

## 8-10. Blockers / readiness

- ROBUST_HIGH_PRIORITY_FILTER_FOUND = **NO**
- READY_FOR_HIGH_PRIORITY_PASSIVE_LIVE_OBSERVER = **NO**
- READY_FOR_TELEGRAM_HIGH_ONLY = **NO**
- READY_TO_INTEGRATE_FILTER_IN_STRATEGY = **NO**
- MORE_VALIDATION_REQUIRED = **YES**

## Final flag matrix

```
STOP_OUT_ANALYSIS_DONE = YES
PRIMARY_STOP_OUT_CAUSE_FOUND = PARTIAL
HIGH_PRIORITY_FILTER_CANDIDATES_TESTED = YES
ROBUST_HIGH_PRIORITY_FILTER_FOUND = NO
BEST_FILTER_NAME = NONE
BEST_FILTER_OKX_ALERTS_PER_DAY = None
BEST_FILTER_BINANCE_ALERTS_PER_DAY = None
BEST_FILTER_OKX_EXPECTANCY_PRE_COST_PCT = None
BEST_FILTER_BINANCE_EXPECTANCY_PRE_COST_PCT = None
BEST_FILTER_OKX_PF_PRE_COST = None
BEST_FILTER_BINANCE_PF_PRE_COST = None
BEST_FILTER_OKX_PRIMARY_RECALL_PCT = None
BEST_FILTER_BINANCE_PRIMARY_RECALL_PCT = None
BEST_FILTER_OKX_STOP_LOSS_REDUCTION_PCT = None
BEST_FILTER_BINANCE_STOP_LOSS_REDUCTION_PCT = None
ENTRY_STOP_ALTERNATIVE_LOOKS_NEEDED = UNKNOWN_SEE_F_REPORT
CURRENT_TRIGGER_ENTRY_PROBLEMATIC_ON_OKX = UNKNOWN_SEE_F_REPORT
READY_FOR_HIGH_PRIORITY_PASSIVE_LIVE_OBSERVER = NO
READY_FOR_TELEGRAM_HIGH_ONLY = NO
READY_TO_INTEGRATE_FILTER_IN_STRATEGY = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- strategy / thresholds / `zoneDetector`: UNCHANGED
- NO new backtest spawned; pure post-hoc analysis over existing zones + trade ledger + price path
- NO `uniqueMoveId` / status / reached / target / mfe / mae / resolvedTs in filter decision; ONLY pre-trigger features
- target STRICT 2 % (no 0.5/1/1.5 considered as 'win')
- no production integration; no profitability claim