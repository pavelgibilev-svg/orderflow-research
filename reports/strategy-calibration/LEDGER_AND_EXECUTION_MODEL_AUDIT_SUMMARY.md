# Ledger reconciliation + execution-model audit - master summary

**Build:** 2026-05-23T10:13:09+00:00
**Diagnostic only. NO engine change. NO new backtest. Target strict 2 %.**

## Answers

1. **Why 41 vs 13 OKX trades?** 
   model_v2 holds position for a hard 24h after entry, blocking subsequent signals for the full timeout window. model_v1 holds only until the actual exit (target/stop/timeout), freeing up signal slots as soon as a trade resolves. Same input signals, same simulation, ONLY the next-signal-allowed timestamp differs.

2. **Canonical ledger model:** `CANONICAL_STRICT_LEDGER_v1` (see `CANONICAL_LEDGER_SPEC.md`).

3. **Current trigger entry + 1 % stop under canonical model:** 
   - OKX: n=44, W/L/T=10/27/7, expectancy -0.1782 %, PF 0.732
   - Binance: n=18, W/L/T=5/3/10, expectancy 0.7098 %, PF 4.129

4. **Current trigger entry problematic on OKX?** `YES` (canonical baseline expectancy below 0).

5. **OKX stop-out cause:** `mixed`. 
   See `OKX_STOP_OUTS_UNDER_CANONICAL_LEDGER.md` for per-zone counterfactuals.

6. **Cross-venue variant search:** see `EXECUTION_MODEL_CROSS_VENUE_DECISION.md`. 
   `ROBUST_EXECUTION_VARIANT_FOUND` = **YES**.
   Best (if any): `delay_15m__stop_1.5pct` — OKX exp 0.471 % / PF 2.053, BIN exp 0.6648 % / PF 3.694.

7. **Telegram HIGH-only readiness:** `NO`. 
   Need cross-venue robust variant first; we don't have one with sufficient confidence yet.

8. **Blockers to production:**
   - thin n (OKX strict ledger ≤ 50, Binance ≤ 25)
   - target 2 % / stop 1 % R/R brittle on OKX microstructure
   - first-of-month sampling bias on Binance, 14 consecutive days on OKX
   - no second OOS period for either venue
   - costs would shave ~0.1 pp off expectancy

## Final flag matrix

```
LEDGER_41_VS_13_EXPLAINED = YES
PRIMARY_DIFFERENCE_BETWEEN_LEDGER_MODELS = position carry window: actual exit time (model_v1) vs blind 24h hold gate (model_v2)
CANONICAL_LEDGER_DEFINED = YES
CANONICAL_LEDGER_TRADES_OKX = 44
CANONICAL_LEDGER_TRADES_BINANCE = 18
CANONICAL_OKX_EXPECTANCY_PRE_COST = -0.1782
CANONICAL_OKX_PF_PRE_COST = 0.732
CANONICAL_BINANCE_EXPECTANCY_PRE_COST = 0.7098
CANONICAL_BINANCE_PF_PRE_COST = 4.129
CURRENT_TRIGGER_ENTRY_PROBLEMATIC_ON_OKX = YES
OKX_STOP_OUT_CAUSE = mixed
BEST_EXECUTION_VARIANT = delay_15m__stop_1.5pct
BEST_EXECUTION_OKX_EXPECTANCY_PRE_COST = 0.471
BEST_EXECUTION_OKX_PF_PRE_COST = 2.053
BEST_EXECUTION_BINANCE_EXPECTANCY_PRE_COST = 0.6648
BEST_EXECUTION_BINANCE_PF_PRE_COST = 3.694
ROBUST_EXECUTION_VARIANT_FOUND = YES
READY_FOR_TELEGRAM_HIGH_ONLY = NO
READY_FOR_PASSIVE_LIVE_OBSERVER = YES
READY_TO_INTEGRATE_EXECUTION_CHANGES = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- strategy / thresholds / `zoneDetector`: UNCHANGED
- NO new backtest spawned; post-hoc only
- NO `uniqueMoveId` in filter decision; NO future-leak
- target STRICT 2 %
- no production integration; no profitability claim