# Binance OOS 2026-05-21..30 — FINAL REPORT

**Build:** 2026-06-02T10:21:30+00:00
**Scope:** OOS / cross-venue. Frozen OKX rules, NO retuning. Exact canonical ledger. Primary win strict 2%.

## Engine
- zones 160, confirmed 153, triggered 93 over 10 days

## RS1 vs RS2 (Binance OOS)

| model | trades | W | L | TO | winrate% | exp_aft% | PF | totRet% | maxCL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| RS1 | 10 | 1 | 5 | 4 | 10.0 | -0.6738 | 0.27 | -6.7378 | 7 |
| RS2 (partial) | 4 | 1 | 0 | 3 | 25.0 | 0.2999 | 2.163 | 1.1995 | 2 |

## OKX (IS) vs Binance (OOS)

- OKX RS1: 29 tr, 62.07%, exp +0.6475, PF 2.258  →  Binance RS1: 10 tr, 10.0%, exp -0.6738, PF 0.27
- RS1 transfer: **NO** | RS2 transfer: **NO** | confirms OKX edge: **NO**

## Answers
1. Dates: ['2026-05-21', '2026-05-22', '2026-05-23', '2026-05-24', '2026-05-25', '2026-05-26', '2026-05-27', '2026-05-28', '2026-05-29', '2026-05-30'] (all FULL).
2. RS1 transfer to Binance: **NO**.
3. S7 improve RS1 OOS: **YES** (PARTIAL — no true OI).
4. Comparable to OKX: winrate 10.0% vs 62.07% (delta -52.07pp).
5. Sample enough: RS1 n=10 (NO).
6. Confirm/reject OKX edge: **NO**.
7. true OI unavailable on Binance recorder (no OI stream) -> RS2 partial only.
8. Next: more OOS windows; consider native-OI recording for full RS2.
9. Telegram shadow ready: **NO**.

## Final flags
```
BINANCE_OOS_DONE = YES
BINANCE_DATES_PROCESSED = ['2026-05-21', '2026-05-22', '2026-05-23', '2026-05-24', '2026-05-25', '2026-05-26', '2026-05-27', '2026-05-28', '2026-05-29', '2026-05-30']
BINANCE_FULL_DAYS = ['2026-05-21', '2026-05-22', '2026-05-23', '2026-05-24', '2026-05-25', '2026-05-26', '2026-05-27', '2026-05-28', '2026-05-29', '2026-05-30']
BINANCE_PARTIAL_DAYS = []
BINANCE_BAD_DAYS = []
BINANCE_RS1_DONE = YES
BINANCE_RS1_TRADES = 10
BINANCE_RS1_WINS = 1
BINANCE_RS1_LOSSES = 5
BINANCE_RS1_TIMEOUTS = 4
BINANCE_RS1_WINRATE = 10.0
BINANCE_RS1_EXPECTANCY_AFTER_COST = -0.6738
BINANCE_RS1_PF_AFTER_COST = 0.27
BINANCE_RS1_TOTAL_RETURN_AFTER_COST = -6.7378
BINANCE_RS2_DONE = PARTIAL
BINANCE_RS2_TRADES = 4
BINANCE_RS2_WINS = 1
BINANCE_RS2_LOSSES = 0
BINANCE_RS2_TIMEOUTS = 3
BINANCE_RS2_WINRATE = 25.0
BINANCE_RS2_EXPECTANCY_AFTER_COST = 0.2999
BINANCE_RS2_PF_AFTER_COST = 2.163
BINANCE_RS2_IMPROVES_RS1 = YES
BINANCE_RS1_TRANSFER_SUCCESS = NO
BINANCE_RS2_TRANSFER_SUCCESS = NO
BINANCE_CONFIRMS_OKX_EDGE = NO
NO_THRESHOLD_RETUNING_DONE = YES
CANONICAL_LEDGER_USED = YES
TIMEOUT_PNL_EXACT = YES
FUTURE_LEAK_FOUND = NO
BINANCE_TRUE_OI_AVAILABLE = NO
BINANCE_FUNDING_AVAILABLE = YES
BINANCE_LIQUIDATIONS_AVAILABLE = YES
READY_FOR_TELEGRAM_SHADOW_MODE = NO
READY_TO_CHANGE_ENGINE = NO
READY_FOR_PRODUCTION_TRADING = NO
MORE_VALIDATION_REQUIRED = YES
```

## ADDENDUM — interpretation update (feature unit/scale shift)

The diagnostic pass (`BINANCE_10D_*`) revised the interpretation of this OOS result. See
**`BINANCE_10D_FEATURE_UNIT_SHIFT_ADDENDUM.md`**. This result must **not** be read only as
"the edge died": part of the frozen OKX rule set transferred to Binance **incorrectly** because
several L2 features are in different units/scales (OKX contracts vs Binance BTC).

- The absolute filter `dl2_supp_minus_opp_net_flow_15m <= 4497.76` is a **no-op** on Binance (100% pass; median 17.6 vs OKX 1408).
- `top1_supportive_persistence_ge_50` ≈ dead (>0 for only 7.8% of Binance zones vs 93.8% OKX); microprice terms ≈0.
- Hence `explainable_score` is structurally lower on Binance (median 0.333 vs OKX winner 1.62) → **ranking degraded**.
- The dominant problem here is the **ranking/selector, NOT the detector**: the detector produced **31** zones that hit the strict 2% target; RS1 selected only **1** (30 skipped winners, 15 SHORT).
- Next research: **venue-normalized feature layer** (per-venue z/percentile instead of absolute thresholds) + direction/regime guard + live-valid first-eligible selector; re-test on more OKX/Binance windows.

```
FEATURE_UNIT_SHIFT_ADDENDUM_DONE   = YES
BINANCE_OOS_INTERPRETATION_UPDATED = YES
PROBLEM_IS_RANKING_NOT_DETECTOR    = YES
VENUE_NORMALIZATION_REQUIRED       = YES
ABSOLUTE_L2_THRESHOLDS_NOT_PORTABLE = YES
READY_FOR_PRODUCTION_TRADING       = NO
MORE_OOS_REQUIRED                  = YES
```