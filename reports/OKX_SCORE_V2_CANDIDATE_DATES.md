# OKX `zone_score_v2` — candidate dates for full-day replay

**Build time:** 2026-05-17T16:17:55Z
**Goal:** ≥12 NEW OKX BTC-USDT-SWAP first-of-month dates for the v2 full-day chain.
**Excluded:** all 12 dates already used (6 calibration + 6 OOS-v1 for zone_score_v1).

## A. Selection rule

- 5 bullish (top by descending day_return_pct in the remaining pool)
- 5 bearish (top by ascending day_return_pct, most negative first)
- 2 choppy (smallest |day_return_pct|, then smallest range)
- If pool thinner than target, top up by remaining 2%-feasible dates with strongest day_return.

Pool sizes after exclusion: bullish=7, bearish=7, choppy=3.

## B. Chosen dates

| # | date | bucket | day Δ % | range % | 2% feas | 1% feas | L2 on disk | trades |
|--:|------|--------|--------:|--------:|:-------:|:-------:|:----------:|-------:|
| 1 | 2026-05-01 | bullish |  +2.47 |   3.42 |  yes  | yes   |  yes     | 2,734,663 |
| 2 | 2025-03-01 | bullish |  +2.02 |   3.26 |  yes  | yes   |  yes     | 1,910,203 |
| 3 | 2024-03-01 | bullish |  +1.99 |   3.82 |  yes  | yes   |  yes     | 1,059,398 |
| 4 | 2026-01-01 | bullish |  +1.38 |   1.57 |  no   | yes   |  yes     | 945,549 |
| 5 | 2024-02-01 | bullish |  +1.20 |   3.35 |  yes  | yes   |  yes     | 851,462 |
| 6 | 2024-04-01 | bearish |  -2.32 |   4.65 |  yes  | yes   |  yes     | 1,160,425 |
| 7 | 2026-02-01 | bearish |  -2.23 |   4.71 |  yes  | yes   |  yes     | 5,085,587 |
| 8 | 2025-08-01 | bearish |  -2.12 |   2.88 |  yes  | yes   |  yes     | 2,848,302 |
| 9 | 2026-03-01 | bearish |  -1.79 |   4.75 |  yes  | yes   |  yes     | 5,299,982 |
| 10 | 2025-02-01 | bearish |  -1.76 |   2.48 |  yes  | yes   |  yes     | 1,156,904 |
| 11 | 2024-12-01 | choppy  |  +0.80 |   2.79 |  yes  | yes   |  yes     | 1,236,400 |
| 12 | 2025-09-01 | choppy  |  +0.91 |   2.50 |  yes  | yes   |  yes     | 1,978,524 |

**Total chosen:** 12

## C. Caveats

- These dates are CANDIDATES. The v2 full-day chain is **not** started by this script.
- Choppy dates may be 2 %-infeasible (range too tight) — that is information, not failure.
- Once full-day is run on these, the natural pipeline is: (1) regime+replay summary, (2) re-derive v2 weights on a held-out split, (3) OOS-test on yet-another held-out set. Steps 2–3 are explicitly out of scope here.

Companion JSON: `reports/OKX_SCORE_V2_CANDIDATE_DATES.json`