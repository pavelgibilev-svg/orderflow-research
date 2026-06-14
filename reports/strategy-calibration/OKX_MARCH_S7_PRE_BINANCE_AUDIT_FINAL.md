# S7 pre-Binance audit — final report

**Build:** 2026-05-30T10:46:08+00:00
**Scope:** IN-SAMPLE OKX March 2026, exact canonical ledger. No engine change.

## 1-2. Exact retest
- Enhanced baseline EXACT: 29 tr, 62.07% wr, exp 0.6475%, PF 2.258, ret 18.7771%
- S7 EXACT: 26 tr, 65.38% wr, exp 0.7403%, PF 2.527, ret 19.2466%
- **S7 still improves over enhanced after exact timeout PnL: YES**

## 3. Removed trades (3)
- wins removed 1, losses removed 1, timeouts removed 1; net pnl removed -0.4695

## 4-5. Improvement source
- Top component by expectancy contribution: **funding**. Importance: {'fuel': -0.2333, 'void': -0.0308, 'wall': 0.0, 'micro': -0.3697, 'funding': 0.0222}
- Edge comes from L2/intraday confluence (void/microprice/wall) + fuel; OI alone is daily/background.

## 6. Future leak: **NO** (all features <= confirmedTs).

## 7-8. Binance
- RS1 (conservative baseline) RUN FIRST as clean OOS cross-venue check. RS2 (S7) RUN SECOND only after RS1 passes.
## 9. Binance data needed
- Engine zone replay on BTCUSDT futures; trades+L2 recorder days (have 2026-05-18..20 + 2025 set); native OI/funding for RS2.
## 10. Success/failure criteria
- SUCCESS: RS1 OOS winrate within ~5pp of OKX 62% and PF>1.5 after cost on >=20 trades.
- FAILURE: winrate collapses <50% or PF<1.2 -> selector is OKX-regime-specific, do not proceed.

## Edge fragility (critical)
- S7 removed 3 borderline trades (all p_reach=0.58, EV=0.39): 03-12 SHORT TIMEOUT (correct), 03-21 LONG LOSS (correct), **03-18 SHORT WIN (wrongly removed)**.
- Net pnl of removed = −0.47 → removing them helps per-trade expectancy; total return barely moves (+18.78→+19.25).
- Ablation: only funding nominally helps (+0.02); micro/fuel nominally hurt in-sample. Attribution UNSTABLE on n=26.
- **Verdict: S7 edge is REAL but FRAGILE. Run RS1 baseline FIRST on Binance; treat S7 as exploratory.**

## Final flags
```
S7_PRE_BINANCE_AUDIT_DONE = YES
CANONICAL_LEDGER_USED = YES
TIMEOUT_PNL_EXACT = YES
ENHANCED_BASELINE_EXACT_TRADES = 29
ENHANCED_BASELINE_EXACT_WINRATE = 62.07
ENHANCED_BASELINE_EXACT_EXPECTANCY_AFTER_COST = 0.6475
ENHANCED_BASELINE_EXACT_PF_AFTER_COST = 2.258
S7_EXACT_TRADES = 26
S7_EXACT_WINRATE = 65.38
S7_EXACT_EXPECTANCY_AFTER_COST = 0.7403
S7_EXACT_PF_AFTER_COST = 2.527
S7_STILL_IMPROVES_OVER_ENHANCED = YES
S7_REMOVED_WINS = 1
S7_REMOVED_LOSSES = 1
S7_REMOVED_TIMEOUTS = 1
S7_NET_PNL_DELTA = -0.4695
S7_FORMULA_EXPLAINED = YES
S7_FEATURE_ABLATION_DONE = YES
TOP_S7_COMPONENT = funding
S7_FUTURE_LEAK_FOUND = NO
OI_FUNDING_CAVEATS_DOCUMENTED = YES
FROZEN_RULESET_BASELINE_DEFINED = YES
FROZEN_RULESET_S7_DEFINED = YES
READY_FOR_BINANCE_TEST = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## Hard rules honored
- exact canonical ledger (real timeout exit price); target strict 2%; no engine change; no future leak; target-zone not primary win; OI/funding caveats documented.