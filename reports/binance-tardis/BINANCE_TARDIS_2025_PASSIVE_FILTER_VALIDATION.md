# Binance Tardis 2025 - passive filter validation (true held-out)

**Build:** 2026-05-22T15:27:33+00:00
**Filter:** `duplicate_60m_PRICE_BAND_ONLY(price_pct<=1.0) AND fast_trigger<=60min` (NO uniqueMoveId, NO future-leak).
**Scope:** Binance Futures BTCUSDT, Tardis 2025 first-of-month (12 dates, live-valid filter) - 12 first-of-month dates, n_zones=384, n_primary=7.

## A. Baseline vs filtered

| metric | baseline | filtered |
|---|---:|---:|
| n_zones | 384 | (triggered-only subset) |
| n_triggered | 209 | 58 |
| n_reached_raw | 37 | 8 |
| n_primary_unique | 7 | 5 |
| n_duplicate_reached | 30 | 3 |
| n_failed_triggered | 172 | 50 |

- primary recall: **71.43 %**
- duplicate removal: **90.0 %**
- failed reduction: **70.93 %**
- actionable signals/day: **4.833**
- baseline precision: 17.7 %  ->  filtered precision: 13.79 %  (-3.91 pp)

## B. Per-date breakdown

| date | regime | trig b/f | prim b/f | dup b/f | fail b/f | recall % | dup_rem % | fail_red % |
|---|---|---|---|---|---|---:|---:|---:|
| 2025-01-01 | bullish | 16/6 | 0/0 | 0/0 | 16/6 | None | None | 62.5 |
| 2025-02-01 | bearish | 16/3 | 1/1 | 0/0 | 15/2 | 100.0 | None | 86.67 |
| 2025-03-01 | bullish | 16/6 | 1/1 | 1/0 | 14/5 | 100.0 | 100.0 | 64.29 |
| 2025-04-01 | bullish | 23/6 | 1/0 | 8/1 | 14/5 | 0.0 | 87.5 | 64.29 |
| 2025-05-01 | bullish | 22/7 | 1/1 | 8/1 | 13/5 | 100.0 | 87.5 | 61.54 |
| 2025-06-01 | choppy | 19/4 | 0/0 | 0/0 | 19/4 | None | None | 78.95 |
| 2025-07-01 | bearish | 14/3 | 0/0 | 0/0 | 14/3 | None | None | 78.57 |
| 2025-08-01 | bearish | 19/7 | 1/1 | 3/1 | 15/5 | 100.0 | 66.67 | 66.67 |
| 2025-09-01 | choppy | 17/3 | 0/0 | 0/0 | 17/3 | None | None | 82.35 |
| 2025-10-01 | bullish | 21/6 | 1/0 | 5/0 | 15/6 | 0.0 | 100.0 | 60.0 |
| 2025-11-01 | choppy | 8/2 | 0/0 | 0/0 | 8/2 | None | None | 75.0 |
| 2025-12-01 | bearish | 18/5 | 1/1 | 5/0 | 12/4 | 100.0 | 100.0 | 66.67 |

## C. Per-direction

| dir | trig b | prim b | dup b | fail b | recall % | dup_rem % | fail_red % |
|---|---:|---:|---:|---:|---:|---:|---:|
| LONG | 121 | 4 | 22 | 95 | 50.0 | 90.91 | 68.42 |
| SHORT | 88 | 3 | 8 | 77 | 100.0 | 87.5 | 74.03 |

## D. Per-regime

| regime | trig b | prim b | dup b | fail b | recall % | dup_rem % | fail_red % |
|---|---:|---:|---:|---:|---:|---:|---:|
| bullish | 98 | 4 | 22 | 72 | 50.0 | 90.91 | 62.5 |
| bearish | 67 | 3 | 8 | 56 | 100.0 | 87.5 | 75.0 |
| choppy | 44 | 0 | 0 | 44 | None | None | 79.55 |

## E. Flags

- `BINANCE_TARDIS_FILTER_VALIDATION_DONE` = **YES**
- `FILTER_DECISION_USED_UNIQUEMOVEID` = **NO**
- `FILTER_INVALID_FUTURE_LEAK` = **NO**
- `BINANCE_TARDIS_FILTER_PRIMARY_RECALL_PCT` = **71.43**
- `BINANCE_TARDIS_FILTER_DUPLICATE_REMOVAL_PCT` = **90.0**
- `BINANCE_TARDIS_FILTER_FAILED_REDUCTION_PCT` = **70.93**
- `BINANCE_TARDIS_FILTER_ACTIONABLE_PER_DAY` = **4.833**
- `BINANCE_TARDIS_FILTER_PRECISION_DELTA_PP` = **-3.91**