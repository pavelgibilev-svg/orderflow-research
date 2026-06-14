# OKX direct - partial March 2026 - backtest summary

**Build:** 2026-05-21T00:50:24+00:00
**Scope:** OKX direct Historical Market Data, BTC-USDT-SWAP perpetual, partial March 2026
**Caveat:** Partial March; NOT full March. Do not treat these zone counts as a profitability claim.

## A. Per-day metrics

| date | regime | d%  | rng% | zones | trig | reached | unique | dup | LONG/SHORT trig | LONG/SHORT reached | failed | noTrig | inv+exp | rawHit% | uniqHit% |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|
| 2026-03-02 | None | None | None | 37 | 21 | 7 | 1 | 6 | 16/21 | 7/0 | 14 | 2 | 14 | 33.333 | 4.762 |
| 2026-03-03 | None | None | None | 46 | 26 | 12 | 2 | 10 | 23/23 | 3/9 | 14 | 1 | 19 | 46.154 | 7.692 |
| 2026-03-04 | None | None | None | 54 | 32 | 15 | 1 | 14 | 30/24 | 15/0 | 17 | 3 | 19 | 46.875 | 3.125 |
| 2026-03-05 | None | None | None | 29 | 13 | 5 | 1 | 4 | 18/11 | 0/5 | 8 | 3 | 13 | 38.462 | 7.692 |
| 2026-03-06 | None | None | None | 43 | 18 | 8 | 1 | 7 | 24/19 | 0/8 | 10 | 3 | 22 | 44.444 | 5.556 |
| 2026-03-07 | None | None | None | 27 | 18 | 0 | 0 | 0 | 14/13 | 0/0 | 18 | 4 | 5 | 0.0 | 0.0 |
| 2026-03-08 | None | None | None | 34 | 21 | 8 | 1 | 7 | 13/21 | 0/8 | 13 | 5 | 8 | 38.095 | 4.762 |
| 2026-03-09 | None | None | None | 48 | 30 | 9 | 1 | 8 | 23/25 | 9/0 | 21 | 2 | 16 | 30.0 | 3.333 |
| 2026-03-10 | None | None | None | 46 | 29 | 14 | 3 | 11 | 24/22 | 12/2 | 15 | 2 | 15 | 48.276 | 10.345 |
| 2026-03-11 | None | None | None | 30 | 21 | 5 | 1 | 4 | 13/17 | 5/0 | 16 | None | 9 | 23.81 | 4.762 |
| 2026-03-12 | None | None | None | 32 | 20 | 0 | 0 | 0 | 15/17 | 0/0 | 20 | 1 | 11 | 0.0 | 0.0 |
| 2026-03-13 | None | None | None | 32 | 18 | 7 | 2 | 5 | 12/20 | 6/1 | 11 | 4 | 10 | 38.889 | 11.111 |
| 2026-03-14 | None | None | None | 16 | 12 | 0 | 0 | 0 | 8/8 | 0/0 | 12 | None | 4 | 0.0 | 0.0 |
| 2026-03-15 | None | None | None | 36 | 16 | 8 | 1 | 7 | 17/19 | 8/0 | 8 | 3 | 17 | 50.0 | 6.25 |

## B. Totals across processed days

- dates processed: **14**  (missing: (none))
- total zones: **510**
- total triggered: **295**
- total reached_raw: **98**
- total unique_moves: **15**
- total duplicate credits: **83**
- LONG reached / SHORT reached: **65 / 33**
- failed / no_trigger / invalidated+expired: **197 / 33 / 182**
- raw hit total %: **33.22**
- unique-move hit total %: **5.085**
- unique_moves per day average: **1.071**

## C. Final flag matrix (Section H)

```
OKX_DIRECT_FILES_READABLE                       = YES
OKX_DIRECT_AVAILABLE_DATES                      = ['2026-03-02', '2026-03-03', '2026-03-04', '2026-03-05', '2026-03-06', '2026-03-07', '2026-03-08', '2026-03-09', '2026-03-10', '2026-03-11', '2026-03-12', '2026-03-13', '2026-03-14', '2026-03-15']
OKX_DIRECT_COVERS_FULL_MARCH                    = NO  (14 / 31 March days supplied)
OKX_DIRECT_ORDERBOOK_USABLE                     = YES
OKX_DIRECT_TRADES_AVAILABLE_FOR_AVAILABLE_DATES = YES (Asia-March covers UTC 2026-03-02..2026-03-15)
OKX_DIRECT_SCHEMA_MATCHES_TARDIS                = PARTIAL (mechanical conversion)
OKX_DIRECT_CONVERSION_DONE                      = YES
OKX_DIRECT_SINGLE_DAY_REPLAY_OK                 = YES
OKX_DIRECT_BACKTEST_RAN                         = YES
OKX_DIRECT_DAYS_PROCESSED                       = 14
OKX_DIRECT_UNIQUE_MOVES_TOTAL                   = 15
OKX_DIRECT_READY_FOR_STRATEGY_RESEARCH          = YES (partial; for research only, not production)
PROFITABILITY_BACKTEST_READY                    = NO  (no explicit execution/stop model)
```

## D. Hard rules honored

- Strategy thresholds: UNCHANGED
- `zoneDetector`: not modified
- `zone_score_v1`: archived, not used as filter
- `zone_score_v2`: research-only, not integrated
- venue label `okx-swap` carried throughout; OKX and Binance not mixed
- raw archives preserved under `data/okx-direct/BTC-USDT-SWAP/2026-03/raw/`
- no profitability claim made or implied