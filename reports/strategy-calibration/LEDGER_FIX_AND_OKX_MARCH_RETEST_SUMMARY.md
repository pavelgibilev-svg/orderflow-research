# Ledger fix + OKX March canonical retest - master summary

**Build:** 2026-05-23T15:00:16+00:00
**Diagnostic only. No engine change. Target strict 2 %. PRE_COST main; cost diagnostic separate.**

## Answers

1. **Was the 41 vs 13 issue fixed?** YES.
   Single canonical module: `src/research/canonicalLedger.ts` + `scripts/strategy-calibration/canonical_ledger.py`. 
   Critical line: `open_until_sec = ACTUAL exit timestamp (sim.exit_sec)`, never `trigSec + 24h`.

2. **Canonical model?** `CANONICAL_STRICT_LEDGER_v1` (mirror of TS module).

3. **Did blind 24h hold remain anywhere?** Only in the legacy `hi_priority_filter_research.py` Section F's local helper, which is preserved unchanged for archival report reproducibility. All NEW analyses use the canonical module.

4. **OKX March canonical baseline (trigger + 1 % stop):** 
   - n_trades = **44**
   - expectancy %/trade = **-0.1782 %**
   - PF = **0.732**
   - W/L/T = 10/27/7, winrate 22.73 %

5. **OKX March delay_15m + stop_1.5%:** 
   - n_trades = **30**
   - expectancy %/trade = **0.471 %**
   - PF = **2.053**
   - W/L/T = 12/7/11, winrate 40.0 %
   - **after basic cost (fee 0.08 % + slip 0.06 %): expectancy = 0.331 %**

6. **Variant still promising?** `YES`

7. **Ready for live shadow observer?** `YES`

8. **Ready for production?** `NO`. Need more validation periods.

## Verification vs prior diagnostic

| metric | expected (from prior report) | actual (canonical retest) | delta |
|---|---:|---:|---:|
| baseline trades | 44 | 44 | 0 |
| baseline expectancy % | -0.18 | -0.1782 | 0.0018 |
| baseline PF | 0.73 | 0.732 | 0.002 |
| delay15+stop1.5 expectancy % | 0.47 | 0.471 | 0.001 |
| delay15+stop1.5 PF | 2.05 | 2.053 | 0.003 |

## Final flag matrix

```
LEDGER_BUGFIX_DONE = YES
BLIND_24H_HOLD_REMOVED = YES
CANONICAL_LEDGER_TESTS_PASS = YES
TYPECHECK_PASS = YES
CANONICAL_OKX_BASELINE_TRADES = 44
CANONICAL_OKX_BASELINE_EXPECTANCY_PRE_COST = -0.1782
CANONICAL_OKX_BASELINE_PF_PRE_COST = 0.732
OKX_DELAY15_STOP15_TRADES = 30
OKX_DELAY15_STOP15_EXPECTANCY_PRE_COST = 0.471
OKX_DELAY15_STOP15_PF_PRE_COST = 2.053
OKX_DELAY15_STOP15_EXPECTANCY_AFTER_BASIC_COST = 0.331
EXECUTION_VARIANT_STILL_PROMISING = YES
READY_FOR_PASSIVE_LIVE_OBSERVER = YES
READY_FOR_TELEGRAM_SHADOW_MODE = YES
READY_TO_INTEGRATE_EXECUTION_CHANGES = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- strategy / thresholds / `zoneDetector`: UNCHANGED
- NO new backtest spawned; post-hoc only over existing zones + price path
- NO `uniqueMoveId` in filter decision; NO future-leak
- target STRICT 2 %
- diagnostic variant is RESEARCH-only; no production integration
- `READY_TO_INTEGRATE_EXECUTION_CHANGES` = NO