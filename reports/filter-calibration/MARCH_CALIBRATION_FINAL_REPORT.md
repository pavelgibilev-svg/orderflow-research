# MARCH 2026 REGIME FILTER CALIBRATION — FINAL REPORT

**RESEARCH ONLY — no production signal, no Telegram.** TP=2%; 2.5/3% are quality labels; forward labels
(true_mfe/time_to_X) computed from trades for OUTCOME labelling only; decisions causal (<= confirmedTs);
engine/TP/SL unchanged; Tardis not used.

## 1. Executive summary
March 2026 gives the regime diversity + sample size May lacked: **1043 zones → 74 unique hit2 / 55 unique
strong / 48 unique hit3 clusters** (vs May's 19 / 8 / 7). Two useful results emerged and one prior belief
was tempered:
- **One filter with real lift: F3_ACCUMULATION** (lower-range absorption-reversal LONG): 62% raw / **50%
  unique** hit2, **PF 1.32**, +20.7pp over base, n=14, date-stability 0.58. Best signal found across May+March.
- **Clean LOW_VOL veto:** low-vol days hit 2% only **6.2%** vs **45.3%** on normal days → strategy should
  stay silent in LOW_VOL.
- **TD-short is NOT confirmed by March:** 19 signals on TREND_DOWN windows → 31.6% winrate, **PF 0.57**
  (full-March breakeven PF 0.98). Tempers the earlier "TD-short is the one robust edge" claim.
- **Cross-cluster separation is still weak even at 7x the data:** best single feature `local_vol_180m`
  AUC 0.62; six-block confluence flat at ~33–37% for 3/4/5/6-of-6. The core problem (winners look like
  noise ex-ante) is real, not a May small-sample artifact.

## 2. March windows processed
All requested windows present except **03-17** (missing data) and **03-01** (not in the DIAG cache).

| regime | window | zones | hit2 | strong | net% | medRange% |
|---|---|--:|--:|--:|--:|--:|
| TREND_UP | 03-10..16 | 236 | 90 | 67 | +9.22 | 3.37 |
| TREND_DOWN | 03-19..23 | 173 | 65 | 52 | −0.40 | 3.64 |
| TREND_DOWN | 03-27..30 | 118 | 42 | 28 | −2.90 | 3.49 |
| HIGH_VOL | 03-26..27 | 82 | 39 | 35 | −6.99 | 4.97 |
| HIGH_VOL | 03-18 | 57 | 36 | 36 | −3.60 | 5.67 |
| HIGH_VOL | 03-23 | 37 | 16 | 14 | +4.36 | 6.42 |
| RANGE | 03-08..09 | 80 | 37 | 31 | +1.72 | 4.79 |
| RANGE | 03-18..19 | 106 | 55 | 50 | −5.44 | 4.82 |
| SWEEP | 03-10..13 | 140 | 64 | 48 | +3.80 | 4.18 |
| SWEEP | 03-01..03 | 82 | 46 | 42 | +3.81 | 6.01 (03-01 not in cache) |

## 3. Data sufficiency by regime
Enough data (>=15 unique strong across windows): **TREND_UP, TREND_DOWN, HIGH_VOL, RANGE, SWEEP all OK**.
Gaps: L2 sub-features N/A on the March DIAG cache (`book_entropy`, `ms_thin_path`, `ms_large_walls`,
top-of-book depth, liquidity-void-to-target). TD-short therefore used `eng_void` as a bid-path proxy.

## 4. Best filters by regime (frozen, March-calibrated)
| filter | regime/dir | n | W/L/TO | winrate | PF | hit2 | hit2.5 | stab | overfit |
|---|---|--:|:--:|--:|--:|--:|--:|--:|:--:|
| **F3_ACCUMULATION** | RANGE/LONG | 14 | 7/6/1 | **50.0** | **1.32** | 50.0 | 35.7 | 0.58 | LOW(small n) |
| F1_TD_SHORT | TREND_DOWN/SHORT | 50 | — | 38.0 | 0.98 | 38.0 | — | 0.33 | LOW |
| F2_SWEEP_REVERSAL | ANY | 83 | — | 36.1 | 0.79 | 36.1 | — | 0.34 | LOW |
| F5_SIXBLOCK_4of6 | ANY | 192 | — | 36.5 | 0.79 | 36.5 | — | 0.29 | LOW |
| F4_DISTRIBUTION | RANGE/SHORT | 0 | — | — | — | — | — | — | did-not-fire |

Only **F3_ACCUMULATION** clears PF>1. Everything else is breakeven-to-losing.

## 5. Six-block confluence
Flat and non-separating: ≥3/6 → 33.6%, ≥4/6 → 35.0%, ≥5/6 → 32.4%, ≥6/6 → 37.5% (n=16). More confluence
does **not** raise winrate. The framework does not solve cross-cluster separation on March.

## 6. Phase candidate results
| phase | raw | hit2% | unique | uprec | lift vs base | helps? |
|---|--:|--:|--:|--:|--:|:--:|
| **ACCUMULATION_CANDIDATE** | 21 | **61.9** | 14 | 0.50 | **+20.7** | **YES** |
| FAILED_BREAKOUT | 92 | 46.7 | 71 | 0.45 | +5.5 | no |
| TREND_CONTINUATION | 314 | 43.9 | 99 | 0.39 | +2.7 | no |
| SWEEP_REVERSAL | 137 | 39.4 | 83 | 0.36 | −1.8 | no |
| BREAKOUT_RETEST | 71 | 38.0 | 59 | 0.41 | −3.2 | no |
| DISTRIBUTION_CANDIDATE | 0 | — | 0 | — | — | did-not-fire |

Asymmetry worth flagging: **accumulation longs (lower-range absorption) carry an edge; the symmetric
distribution-short pattern did not occur in March at all** — test on OOS before trusting either sign.

## 7. TD-short March result
19 signals on TREND_DOWN windows → **6W/12L/1TO, 31.6% winrate, PF 0.57, expectancy −0.45%/trade**.
Full-March BEAR-regime: n=50, PF 0.98 (breakeven). **March does not confirm TD-short.** Caveat: degraded
variant (thin-path feature N/A → eng_void proxy). Needs a clean TREND_DOWN OOS with full feature schema
before declaring dead.

## 8. Low-vol / no-trade result
Low-vol day (03-14): 16 zones, **6.2%** hit2. Normal/high-vol days: 879 zones, **45.3%** hit2. False
signals concentrate in low vol → **recommend silence in LOW_VOL** (a veto filter, high value, robust sign).

## 9. Frozen filter files created
`reports/filter-calibration/`: `FROZEN_FILTER_SET_MARCH_V1.json` (do-not-tune-after-OOS),
`FILTER_CANDIDATES_MARCH_V1.{json,csv}`, `FILTER_SCORECARD_MARCH_V1.csv`, `FILTER_DEFINITIONS_MARCH_V1.md`,
`MARCH_CALIBRATION_FINAL_REPORT.{json,md}`.

## 10. OOS windows to download
See `OOS_WINDOWS_TO_DOWNLOAD_BY_REGIME.{csv,md}`. True non-March OOS (different months/years):
- TREND_DOWN: **2025-11 (−21.6%)**, 2024-04 (−16.3%), 2026-02 (−14.6%).
- TREND_UP: **2024-02 (+44.8%)**, 2024-11 (+39.9%), 2024-05 (+16.2%).
- RANGE (fresh): 2024-01, 2024-07. HIGH_VOL/SWEEP/LOW_VOL: validate on local May first.

## 11. Exact next action
1. **Download TREND_DOWN OOS first** (2025-11, 2024-04, 2026-02) — TD-short and F3 both need a clean
   trend test; TD-short is on the bubble (PF 0.57–0.98) and must be confirmed-or-killed.
2. **Validate F3_ACCUMULATION** on RANGE OOS (2024-01 / 2024-07) — the only PF>1 candidate; freeze, don't tune.
3. **Apply the LOW_VOL veto** as a standing no-trade rule (already robust).
4. **Ignore**: six-block confluence, F2_SWEEP, F5_SIXBLOCK, distribution — no March edge.
5. Rebuild a **full-schema March cache** (with thin-path/book-entropy/depth) before trusting TD-short's
   March result, since the proxy degrades it.

## Flags
```
MARCH_CALIBRATION_DONE=YES
MARCH_DATA_COMPLETE=NO (03-17 missing; 03-01 not in cache; L2 subfeatures N/A)
POSITIVE_FEATURE_FOUND=PARTIAL (local_vol_180m AUC 0.62; F3_ACCUMULATION PF 1.32 n=14)
BEST_PHASE=ACCUMULATION_CANDIDATE  TD_SHORT_MARCH=WEAK (PF 0.57 down-windows / 0.98 full)
LOW_VOL_NO_TRADE=CONFIRMED (6.2% vs 45.3% hit2)
FROZEN_FILTERS_EXPORTED=YES  DO_NOT_TUNE_ON_OOS=YES
READY_FOR_PRODUCTION_TRADING=NO  MORE_OOS_REQUIRED=YES  TARDIS_USED=NO
```
