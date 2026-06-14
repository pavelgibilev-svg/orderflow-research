# Tardis Compatibility Validation — 2026 YTD (excluding May)

> This is a **compatibility and smoke-test report**, not a proof of strategy profitability.

- Generated: 2026-05-08T17:12:43.786Z
- Input path: `./data/tardis/binance-futures/BTCUSDT`
- Symbol: BTCUSDT
- Exchange: binance-futures
- Dates checked: 2026-02-01

## Per-day verdict

| Date | Verdict | Required types | Optional types | Reasons |
|---|---|---|---|---|
| 2026-02-01 | VALID | incremental_book_L2:ok<br/>trades:ok | derivative_ticker:ok<br/>book_ticker:ok<br/>liquidations:ok | - |

## 2026-02-01

**Verdict:** VALID

| Data type | Required | Status | File | Size | Headers OK | Rows parsed | Notes |
|---|---|---|---|---|---|---|---|
| incremental_book_L2 | yes | ok | `data\tardis\binance-futures\BTCUSDT\2026-02-01\incremental_book_L2.csv.gz` | 825.8 MB | yes | 1000 |  |
| trades | yes | ok | `data\tardis\binance-futures\BTCUSDT\2026-02-01\trades.csv.gz` | 55.0 MB | yes | 1000 |  |
| derivative_ticker | no | ok | `data\tardis\binance-futures\BTCUSDT\2026-02-01\derivative_ticker.csv.gz` | 2.0 MB | yes | 1000 |  |
| book_ticker | no | ok | `data\tardis\binance-futures\BTCUSDT\2026-02-01\book_ticker.csv.gz` | 277.4 MB | yes | 1000 |  |
| liquidations | no | ok | `data\tardis\binance-futures\BTCUSDT\2026-02-01\liquidations.csv.gz` | 32.3 KB | yes | 1000 |  |

## What you can / cannot conclude

- A **VALID** verdict means the file layout, gzip, headers and the first 1000 rows all parse.
- It does **not** mean the strategy makes money on that day.
- Optional missing types (`derivative_ticker`, `book_ticker`, `liquidations`) are not strategy-critical for the smoke test.
- A day is INVALID only if `incremental_book_L2` or `trades` is missing or fails to parse.
