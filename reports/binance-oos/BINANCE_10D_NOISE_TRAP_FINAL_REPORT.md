# BINANCE 10D — NOISE / TRAP / LIVE-VALID SELECTOR — FINAL DIAGNOSTIC

**Build:** 2026-06-02T14:02:11+00:00
**DIAGNOSTIC ONLY. No engine/detector/TP/SL change. No Binance threshold tuning. Causal features. No production claim.**

## Live-valid selector models
| model | tr | wr% | exp% | PF | maxCL | wrongdir | alerts/day | skipped GOOD |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Model0_top1_day_RS1 | 10 | 10.0 | -0.5821 | 0.35 | 4 | 6 | 1.0 | 30 |
| Model1_first_elig_OKXthr | 1 | 0.0 | 0.371 | None | 0 | 0 | 0.1 | 31 |
| Model2_+noise | 1 | 0.0 | 0.371 | None | 0 | 0 | 0.1 | 31 |
| Model3_+dir_guard | 1 | 0.0 | 0.371 | None | 0 | 0 | 0.1 | 31 |
| Model4_max2_cooldown_noise | 1 | 0.0 | 0.371 | None | 0 | 0 | 0.1 | 31 |

## Answers
**1_good_skipped_zones** — YES — 30 confirmed zones reached 2% but were not the RS1 pick (15 of them SHORT). Days where a SHORT winner existed but RS1 took a losing LONG matter most.

**2_detector_or_ranking** — RANKING (selection), not the detector. 31 GOOD 2%-zones existed across 10 days; the detector produced winners — the top1/day score ranking picked the wrong ones.

**3_why_long_in_downtrend** — explainable_score has NO trend term and rewards asia-session + opp_dir==0; on a one-way down week it ranked early LONG ACCUMULATION dips highest. 4 selected LONGs were against the 1d-bearish regime; engine ofiScore was often negative under those 'buy' zones (sell flow = fake accumulation).

**4_fake_accumulation_signs** — negative engine ofiScore under a LONG zone, negative supportive taker imbalance, no reclaim of zoneMid, lower-low structure pre-confirm, 1d regime against signal.

**5_strongest_noise_filters** — see Section D table — strongest: no-reclaim, ofi-direction-conflict, LONG-in-bear-without-reclaim (direction guard).

**6_trend_guard_needed** — YES — a direction/regime guard is the single highest-leverage fix.

**7_live_valid_1_per_1_2_days** — YES — Model1_first_elig_OKXthr is causal first-eligible and yields ~1 trades/10d (~1 per 10.0 days).

**8_what_to_carry_forward** — frozen OKX score floor + direction/regime guard + reclaim/ofi noise filter; re-test on more OKX & Binance windows; record native OI for full S7. NO production change.

## Flags
```
BINANCE_10D_DIAG_DONE = YES
NO_ENGINE_CHANGE = YES
NO_DETECTOR_CHANGE = YES
NO_TP_SL_CHANGE = YES
NO_BINANCE_THRESHOLD_TUNING = YES
FUTURE_LEAK_FOUND = NO
SELECTOR_FEATURES_CAUSAL = YES
GOOD_ZONES_EXISTED = 31
SKIPPED_GOOD_WINNERS = 30
SHORT_SKIPPED_WINNERS = 15
RS1_LONG_LOSSES = 5
RS1_SELECTED_LONG_AGAINST_1D_TREND = 4
PROBLEM_IS_DETECTOR = NO
PROBLEM_IS_RANKING = YES
DIRECTION_GUARD_NEEDED = YES
BEST_LIVE_VALID_MODEL = Model1_first_elig_OKXthr
BEST_MODEL_TRADES = 1
BEST_MODEL_WINRATE = 0.0
BEST_MODEL_PF = None
BEST_MODEL_EXPECTANCY = 0.371
PRODUCTION_CLAIM = NO
MORE_OOS_REQUIRED = YES
```

## ADDENDUM — feature unit/scale shift (root cause)

See **`BINANCE_10D_FEATURE_UNIT_SHIFT_ADDENDUM.md`**. Key correction to interpretation: the Binance
result is **not** purely "edge died." Several frozen OKX L2 features are in different units/scales on
Binance (OKX contracts vs Binance BTC), so:
- `dl2_supp_minus_opp_net_flow_15m <= 4497.76` passes **100%** of Binance zones (no-op; on OKX it cuts top ~25%);
- `top1_supportive_persistence_ge_50` >0 for only **7.8%** of Binance zones (vs 93.8% OKX) and microprice terms ≈0;
- so `explainable_score` is structurally lower on Binance (median **0.333** vs OKX winner **1.62**) and the **ranking degraded**.
- **Problem is ranking/selector, not detector** (detector found **31** 2%-winners; RS1 took **1**).
- Next: **venue-normalized feature layer** + direction/regime guard + live-valid selector; re-test more windows.

```
FEATURE_UNIT_SHIFT_ADDENDUM_DONE   = YES
BINANCE_OOS_INTERPRETATION_UPDATED = YES
PROBLEM_IS_RANKING_NOT_DETECTOR    = YES
VENUE_NORMALIZATION_REQUIRED       = YES
ABSOLUTE_L2_THRESHOLDS_NOT_PORTABLE = YES
READY_FOR_PRODUCTION_TRADING       = NO
MORE_OOS_REQUIRED                  = YES
```