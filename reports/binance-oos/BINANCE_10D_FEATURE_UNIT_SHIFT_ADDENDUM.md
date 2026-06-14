# Binance 10D OOS — FEATURE UNIT / SCALE SHIFT ADDENDUM

**Status:** INTERPRETATION UPDATE for the Binance 2026-05-21..30 OOS result.
**Production conclusion is NOT changed.**

## Why this addendum exists

The Binance OOS result must **not** be read only as *"the edge died."* A material part of the
frozen OKX rule set **did not transfer correctly** to Binance because several L2 features are
expressed in **different units / scales** across venues (OKX order sizes in contracts vs Binance
in BTC). Absolute-valued thresholds and score terms built on OKX scales therefore became
**degenerate** on Binance, the frozen `explainable_score` lost its L2 discriminators, and the
**ranking/selector degraded** to trend-blind heuristics. This is substantially a cross-venue
**measurement/normalization** problem at the selector layer — not (only) a dead edge.

## The 8 points

1. **Different units/scales.** OKX and Binance L2 order sizes are in different units (OKX contracts
   vs Binance BTC). Absolute-valued L2 features do not share a common scale across venues.
2. **Absolute threshold became a no-op.** The frozen RS1 filter
   `dl2_supp_minus_opp_net_flow_15m <= 4497.76` passes **100%** of Binance confirmed zones — it
   filters nothing. On OKX the same cut removes the top ~25%.
3. **Persistence & microprice terms zeroed out on Binance.**
   `top1_supportive_persistence_ge_50` is >0 for only **7.8%** of Binance zones (vs **93.8%** on
   OKX), and `microprice_aligned_delta` magnitudes are ~0 (median 0.0) — both score terms
   contribute ≈0 on Binance.
4. **Score structurally lower → ranking degraded.** With those terms vanished, Binance
   `explainable_score` median is **0.333** (p90 0.787) vs OKX winner median **1.62**. The frozen
   scorer fell back to trend-blind heuristics (asia-session, no-opposing-zone, sweep, prior_move),
   which on a one-way down week ranked early LONG ACCUMULATION dips highest.
5. **Dominant problem = ranking/selector, NOT the detector.**
6. **Detector found winners, ranking missed them.** The detector produced **31** zones that reached
   the strict 2% target across the 10 days; RS1 selected only **1** of them (30 skipped 2%-winners,
   15 of them SHORT).
7. **Next research.** Build a **venue-normalized feature layer** (per-venue z-scores / percentiles,
   not absolute thresholds) + a **direction/regime guard** + a **live-valid first-eligible selector**;
   then re-test on more OKX and Binance windows. Record native OI for full S7.
8. **Production unchanged.** `READY_FOR_PRODUCTION_TRADING = NO`, `MORE_OOS_REQUIRED = YES`.

## Evidence (grounded numbers)

| feature | Binance | OKX | implication |
|---|---|---|---|
| `dl2_supp_minus_opp_net_flow_15m` | median 17.6, range [−3020, 2896]; **100%** ≤ 4497.76 | median 1408, p90 7752; 75% ≤ 4497.76 | absolute threshold = **no-op** on Binance, discriminative on OKX |
| `top1_supportive_persistence_ge_50_5m_sec` | **7.8%** of zones >0 (max 79) | **93.8%** >0 (median 273) | `≥50` size unit not portable → term ≈0 on Binance |
| `dl2_microprice_aligned_delta_5m_bps` | median 0.0 (65.9% nonzero, tiny) | winner median 4.63 | microprice term ≈0 on Binance |
| `explainable_score` | median **0.333**, p90 0.787, max 1.703 | winner median **1.62** | frozen OKX floor (1.021) ⇒ live-valid selector ≈ stands aside (1 alert/10d) |

**Selected vs skipped:** 153 confirmed zones → 31 reached 2% → RS1 picked 1 → 30 skipped winners (15 SHORT).

## Flags

```
FEATURE_UNIT_SHIFT_ADDENDUM_DONE   = YES
BINANCE_OOS_INTERPRETATION_UPDATED = YES
PROBLEM_IS_RANKING_NOT_DETECTOR    = YES
VENUE_NORMALIZATION_REQUIRED       = YES
ABSOLUTE_L2_THRESHOLDS_NOT_PORTABLE = YES
READY_FOR_PRODUCTION_TRADING       = NO
MORE_OOS_REQUIRED                  = YES
```

Related: `BINANCE_10D_NOISE_TRAP_FINAL_REPORT.md`, `BINANCE_2026_05_21_30_OOS_FINAL_REPORT.md`,
`OKX_VS_BINANCE_FEATURE_DISTRIBUTION_SHIFT.md`, `BINANCE_10D_SELECTED_VS_SKIPPED_AUDIT.md`.
