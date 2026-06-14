# OKX MAY MARCH-FILTER RETEST + BINANCE L2 CONVERTER FIX — FINAL COMBINED REPORT

**Build:** 2026-06-04T04:03:06+00:00  ·  RESEARCH ONLY · no engine/detector/TP-SL/threshold/production change · TARDIS_USED=NO

## Track A — OKX May March-filter retest (frozen)
OKX March ref: 29 tr, 62.07%, exp +0.6475, PF 2.258.  OKX May base 2% rate 25.67% vs March 36.63%.

| model | tr | W/L/TO | wr% | exp% | PF | ret% | no-trade |
|---|--:|:--:|--:|--:|--:|--:|--:|
| M0_absolute_march | 9 | 2/2/5 | 22.22 | 0.1473 | 1.35 | 1.3256 | 0 |
| M1_norm_pctile | 9 | 1/3/5 | 11.11 | -0.2275 | 0.623 | -2.0474 | 0 |
| M2_norm_zscore | 9 | 2/2/5 | 22.22 | 0.1614 | 1.384 | 1.4526 | 0 |
| M3_dir_guard | 6 | 1/2/3 | 16.67 | -0.1679 | 0.713 | -1.0074 | 3 |
| M4_noise_confluence | 6 | 1/2/3 | 16.67 | -0.0495 | 0.91 | -0.2968 | 3 |
| M5_live_valid | 6 | 1/2/3 | 16.67 | -0.0495 | 0.91 | -0.2968 | 3 |

**Transfer = PARTIAL**. Strong-move (no-exit MFE): hit2% 53, hit2.5% 36, hit3% 22.

## Track B — Binance L2 converter fix + revalidation
Root cause: frozen orderbook_snapshots_1s + old seed logic. Fix v3: pure-diff reconstruction + crossed-prune.

| metric | before fix | after v3 fix |
|---|--:|--:|
| crossed book | ~100% (208 bps) | **0.0%** |
| median spread | corrupted | 0.013 bps |
| book vs trade | +2.1% stale | +/-0.7% (tracks) |

Re-parity (OKX vs Binance corrected): both 0% crossed, spread 0.0133 bps, top1 9.0 vs 7.8 BTC (USD ratio 1.16x). **COMPARABLE = YES**.

## Answers
**1_okx_may_usable** — YES — L2 10/10, trades 9/10 (05-21 L2-only), reconstruction clean (<0.5% crossed, spread 0.013 bps).

**2_march_transfer** — PARTIAL — absolute M0 stays marginally profitable (PF 1.35, exp 0.1473, ret 1.3256%) but winrate collapses 62%->22.22%. OKX May is a weaker 2% regime (base rate 36.63%->25.67%).

**3_best_model** — M2 z-normalized (wr 22.22%, PF 1.384, ret 1.4526%) ~= M0 absolute. Normalization neither breaks nor improves OKX materially; direction guard/noise HURT here (NO).

**4_strong_labels** — Strong movers exist: hit2.5%=36, hit3%=22 of 187. They tend to reclaim zoneMid (median reclaim=1) — a cleaner signal than absolute flow.

**5_regime** — OKX May is the SAME weak/low-2pct regime as Binance May (same dates) — base 2% rate 25.67% vs March 36.63%. The earlier Binance failure was substantially REGIME, not venue.

**6_binance_fixed** — YES — v3 pure-diff converter (ignore frozen 1s snapshots), reconverted 10/10 days, 0.0% crossed.

**7_binance_valid** — YES — book valid: 0% crossed, spread 0.013 bps, tracks trade price within +/-0.7%.

**8_resume_binance** — YES — but prior Binance L2 features were built on the BROKEN book and are INVALID; must recompute first.

**9_comparable** — YES — after fix, OKX vs Binance L2 comparable in BTC/USD: top1 9.0 vs 7.8 BTC (USD ratio 1.16x), spread identical 0.0133 bps, both 0% crossed.

**10_next** — 1) recompute Binance L2 features on the fixed book; 2) re-run same-date OKX-vs-Binance comparison (now valid); 3) build strong-zone classifier (reclaim-of-zoneMid signal); 4) then OI/fuel-layer + new windows (bull/range). Production frozen.

## Final flags
