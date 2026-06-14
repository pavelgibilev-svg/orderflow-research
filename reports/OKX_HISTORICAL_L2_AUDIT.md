# OKX Historical L2 — audit for `BTC-USDT-SWAP`

**Audit date:** 2026-05-16 (UTC)
**Project root:** `C:\Users\gibilev\orderflow-research`
**Source:** OKX swap (`okex-swap`) historical CSV, distributed via the
Tardis CDN (the OKX-native download channel is gated behind login + paid
tier and could not be reached via public probing — see Section 1 below).
**Sample window:** 2026-04-01 00:00 → 24:00 UTC (one full UTC day)

---

## 0. Headline

| Question                                              | Answer |
|-------------------------------------------------------|--------|
| Did OKX historical L2 data download work?             | ✅ yes, for the 1st day of the month (free tier) |
| Is this `BTC-USDT-SWAP` (OKX perpetual)?              | ✅ yes |
| Is OKX directly equivalent to Binance USDS-M Futures? | ❌ **NO — different exchange.** OKX is a separate venue with different liquidity, participant mix and (subtly) different tick size and contract spec. Strategy was tuned for Binance. |
| L2 stream type                                        | **DELTA-based**, tick-by-tick (`books-l2-tbt`, ~10 ms granularity) with one snapshot anchor at the start of the stream |
| Snapshot every 1 s recoverable?                       | ✅ yes — by replaying deltas and sampling at 1-Hz, exactly the same pattern we use for the live recorder |
| Crossed / empty book on the day                       | 0 / 0 (book_ticker stream) |
| Trades available                                      | ✅ 3 920 423 rows for the day |
| Funding / mark / open interest available              | ✅ via `derivative_ticker` |
| Liquidations available                                | ✅ but only 567 events on this day (quiet day) |
| Coverage for the full week 2026-04-01..04-08          | ⚠️ **only 2026-04-01 free.** 04-02..04-08 require a Tardis API key (which we do not have) **or** an OKX premium/paid subscription |

---

## 1. Access channels — what worked and what didn't

| Channel | Status | Notes |
|---------|--------|-------|
| OKX historical-data page (`https://www.okx.com/historical-data`) | ❌ JS-rendered; the "Download" buttons are gated behind the OKX login + paid tier. No public direct-download URLs found. |
| OKX `priapi/v5/broker/public/orderRecord` (used by `crypto-crawler/historical-data-downloader`) | ❌ all probes (`trades`, `swaprate`, `orderbook`, `books`, `liquidations`, several month/day formats) returned **404 Not Found**. Endpoint appears retired or scoped to logged-in sessions. |
| `static.okx.com/cdn/okex/traderecords/orderbook/...` direct CDN | ❌ 404 on every plausible path. |
| **Tardis CDN** (`datasets.tardis.dev/v1/okex-swap/...`) | ✅ **works**, with a quirk: a bare HEAD request 404s, but a `GET` with `Range: bytes=0-` returns the full file at HTTP 200. First day of every month is **free without API key**; remaining days require paid Tardis credentials. |

Conclusion: the practical channel for verifying OKX L2 historical data
without an OKX paid tier is the Tardis CDN free sample. That gave us a
clean 1-day slice of every data type we asked for; extending the window
to a full week requires paying for Tardis or buying OKX's premium tier.

---

## 2. Files downloaded — `data/okx-historical/BTC-USDT-SWAP/2026-04-01/`

| file (gzipped CSV)               | size on disk | rows         | source channel (OKX)              |
|----------------------------------|-------------:|-------------:|-----------------------------------|
| `incremental_book_L2.csv.gz`     | 627 418 048 B | 110 176 675 | `books-l2-tbt` (10 ms)            |
| `trades.csv.gz`                  |  31 529 024 B |   3 920 423 | `trades`                          |
| `book_ticker.csv.gz`             |  31 983 038 B |   2 558 519 | best bid/ask aggregate            |
| `derivative_ticker.csv.gz`       |   7 306 110 B |     569 575 | funding + mark + index + last     |
| `liquidations.csv.gz`            |       9 674 B |         567 | `liquidations`                    |

Magic-byte check confirms all five files are gzip-compressed (`\x1f\x8b`)
despite Tardis serving them with `Content-Type: text/csv`. Total on-disk
~670 MiB.

---

## 3. Schema audit (per file)

All five files share the Tardis-canonical column layout. Crucially this
is the **same schema** our existing `src/data/tardisCsvLoader.ts` already
auto-detects for Binance Futures — see `detectDataType()` lines 155–158:
`(is_snapshot, price, amount)` → incremental_book_L2; `(price, amount,
side)` → trades; `(bid_price, ask_price)` → book_ticker; `(funding_rate,
mark_price)` → derivative_ticker. **No loader changes are needed to read
OKX-swap CSVs.**

### 3.1 `incremental_book_L2`

```
exchange, symbol, timestamp, local_timestamp, is_snapshot, side, price, amount
```

| field            | type           | notes |
|------------------|----------------|-------|
| `exchange`       | string         | always `"okex-swap"` |
| `symbol`         | string         | always `"BTC-USDT-SWAP"` |
| `timestamp`      | int64          | **microseconds** since epoch (OKX matching-engine time) |
| `local_timestamp`| int64          | microseconds, Tardis ingestion time |
| `is_snapshot`    | bool           | `true` for initial-state rows, `false` for deltas |
| `side`           | enum           | `"bid"` or `"ask"` |
| `price`          | decimal (str)  | level price in USDT |
| `amount`         | decimal (str)  | level size **in contracts** (1 contract = 0.01 BTC for BTC-USDT-SWAP); `0` means delete |

Sample first three rows:

```
exchange  symbol         timestamp         local_timestamp   is_snapshot  side  price     amount
okex-swap BTC-USDT-SWAP  1775001600009000  1775001600018221  false        ask   68251.3   0
okex-swap BTC-USDT-SWAP  1775001600009000  1775001600018221  false        ask   68253.9   0.74
okex-swap BTC-USDT-SWAP  1775001600009000  1775001600018221  false        ask   68258.3   0.18
```

### 3.2 `trades`

```
exchange, symbol, timestamp, local_timestamp, id, side, price, amount
```

| field            | type           | notes |
|------------------|----------------|-------|
| `id`             | int64          | monotonic OKX trade id |
| `side`           | enum           | `"buy"` (taker buy) or `"sell"` (taker sell) — taker side |
| `price`          | decimal (str)  | USDT |
| `amount`         | decimal (str)  | contracts |

### 3.3 `book_ticker`

```
exchange, symbol, timestamp, local_timestamp, ask_amount, ask_price, bid_price, bid_amount
```

Top-of-book stream.

### 3.4 `derivative_ticker`

```
exchange, symbol, timestamp, local_timestamp, funding_timestamp, funding_rate,
predicted_funding_rate, open_interest, last_price, index_price, mark_price
```

Most rows fill only some of these (the source emits each value
independently as it updates). For BTCUSDT-Perp on OKX, funding is paid
every 8 h, so `funding_rate` columns are empty most of the time.

### 3.5 `liquidations`

```
exchange, symbol, timestamp, local_timestamp, id, side, price, amount
```

---

## 4. L2 quality

### 4.1 Volumes

| metric                                | value |
|---------------------------------------|------:|
| Total L2 events for the day           | **110 176 675** |
| Of which deltas (`is_snapshot=false`) | 110 175 075 |
| Of which snapshot rows                | **1 600** (one anchor at the start of the stream + reconnect re-snapshots) |
| Mean events per second                | 1 275 |
| p50 / p95 / max events per second     | 930 / 3 359 / 18 155 |
| Seconds with at least 1 event         | 86 400 / 86 400 (100 %) |
| Bid / ask balance                     | 55 212 926 bid (50.1 %) / 54 963 749 ask (49.9 %) |
| `amount == 0` (delete) share          | 18.77 % |
| Intraday price range                  | 67 503.7 → 69 359.8 USDT (≈ 2.75 %) |

### 4.2 Snapshot strategy

The L2 stream contains ~1 600 "snapshot rows" concentrated at the start
of the day (and after any operator reconnect during ingestion). After
the initial snapshot, only deltas are emitted. This is the **standard
Tardis layout** and matches what our live recorder produces via Binance
`@depth@100ms`.

**Practical implication for replay:** to know the book at any time T in
the day, you replay every delta from `00:00:00.009 UTC` until T. There
is no per-minute re-anchor like the Kaggle dataset had; instead, the
single-anchor + 24h-of-deltas approach is used. This is fine for offline
replay (a few minutes of wall-clock to chew through 110 M events) and is
the same shape our `tardisCsvLoader.ts` already handles for Binance.

### 4.3 Book quality (independent check)

The `book_ticker` (best-bid-best-ask) stream is independent of the L2
reconstruction and is a direct trust signal for book quality:

| metric                        | value |
|-------------------------------|------:|
| `book_ticker` rows            | 2 558 519 |
| Seconds with at least 1 BBO update | 86 397 / 86 400 |
| **Crossed (bid ≥ ask) rows**  | **0** |
| **Empty (bid = 0 or ask = 0) rows** | **0** |

→ The exchange-published BBO has no quality flags raised on this day.
Any cross we see during reconstruction would be the replay engine's
fault, not the data's.

### 4.4 Sequence integrity

The Tardis OKX L2 export has **no sequence/update id column**. Order is
maintained by timestamp (and Tardis preserves source-order for events
sharing a microsecond). For our strategy this is fine because the engine
consumes the stream in arrival order; we don't need a sequence-gap
metric here.

The trades file does have an `id` column (OKX trade id):

| metric                        | value |
|-------------------------------|------:|
| `trade_id` min                | 2 465 980 933 |
| `trade_id` max                | 2 469 901 375 |
| span                          | 3 920 442 |
| rows                          | 3 920 423 |
| **gaps (`id ≠ prev + 1`)**    | **1** (one) — 0.0000000255 % |

Trade id continuity is essentially perfect.

---

## 5. Trades, ticker, liquidations sanity

### 5.1 Trades

| metric                | value |
|-----------------------|------:|
| Rows                  | 3 920 423 |
| Time range            | 00:00:00.101 → 23:59:59.522 UTC |
| Taker buy / sell      | 1 963 482 (50.1 %) / 1 956 941 (49.9 %) |
| Price min / max       | 67 550.1 / 69 315.8 USDT |
| Mean events / second  | 47 |
| Burst (max events / second) | 8 857 |
| Zero-quantity rows    | 0 |

### 5.2 `derivative_ticker`

| metric                | value |
|-----------------------|------:|
| Rows                  | 569 575 |
| Mean per second       | 7 |
| Has `funding_rate`?   | yes (sparse rows when funding event fires) |
| Has `mark_price`?     | yes |
| Has `index_price`?    | yes |
| Has `open_interest`?  | yes (sparse) |

This gives us **direct equivalents** of the Binance Futures funding /
mark / OI inputs that the live recorder ingests. The strategy doesn't
currently consume any of them, but they're available if needed.

### 5.3 Liquidations

| metric                | value |
|-----------------------|------:|
| Rows                  | 567 |
| Buy / sell            | 266 / 301 |
| Mean per second       | ≈ 1 (very sparse) |
| Notional range        | 0.07 – 6.25 contracts |

A quiet day — no major liquidation cascade observed.

---

## 6. Coverage gap for the full week

The user asked for `2026-04-01 → 2026-04-08`. As of this audit:

| date       | status |
|------------|--------|
| 2026-04-01 | ✅ downloaded (Tardis free first-of-month sample) |
| 2026-04-02 | ❌ requires Tardis paid API key OR OKX premium tier |
| 2026-04-03 | ❌ same |
| 2026-04-04 | ❌ same |
| 2026-04-05 | ❌ same |
| 2026-04-06 | ❌ same |
| 2026-04-07 | ❌ same |
| (2026-04-08 = exclusive end) | n/a |

Without either credential the audit is limited to a single day. The
quality of that one day is high enough that extending coverage is purely
a credential problem, not a data-quality problem.

---

## 7. Final flag matrix (per user spec, Section 10)

| flag                                          | value          |
|-----------------------------------------------|----------------|
| `OKX_L2_ACCESS_OK`                            | **YES** (via Tardis CDN, first-of-month free; OKX-native channel is paid/gated) |
| `OKX_L2_IS_SNAPSHOT_OR_DELTA`                 | **BOTH** (initial snapshot anchor at stream start + subsequent deltas) |
| `OKX_L2_FREQUENCY`                            | tick-by-tick (`books-l2-tbt`, ≈ 10 ms cadence, mean 1 275 events/sec, max 18 155) |
| `OKX_TRADES_AVAILABLE`                        | **YES** (3.92 M rows / day) |
| `CAN_RECONSTRUCT_ORDERBOOK`                   | **YES** |
| `CAN_CREATE_1S_SNAPSHOTS`                     | **YES** (via 1-Hz sampling of the reconstructed book — same algorithm as the live recorder) |
| `CAN_RUN_STRATEGY_REPLAY`                     | **YES** structurally (loader is already compatible); **but not invoked here** — see Section 8 |
| `SUITABLE_FOR_BINANCE_STRATEGY_DIRECTLY`      | **NO** — different exchange (see hard-rule below) |
| `SUITABLE_FOR_ORDERFLOW_RESEARCH`             | **YES**, as a supplementary venue (rich L2 stream + 24/7 BTC volume + funding/mark/OI/liquidations included) |

---

## 8. Hard rule: OKX is **not** Binance

| dimension                | Binance USDS-M Futures BTCUSDT-PERP | OKX `BTC-USDT-SWAP` |
|--------------------------|-------------------------------------|---------------------|
| venue                    | Binance                             | OKX                 |
| settlement / collateral  | USDT, 8 h funding                   | USDT, 8 h funding (compatible cadence) |
| contract size            | 0.001 BTC minimum lot               | 1 contract = **0.01 BTC** (fixed multiplier) |
| tick size                | $0.10                               | $0.10               |
| trading hours            | 24/7                                | 24/7                |
| volume profile           | dominant venue (largest perpetual book worldwide) | top-5, smaller order book depth on average |
| participant mix          | retail-heavy + large props          | mix; less retail than Binance |
| WS depth stream          | `@depth@100ms` (top-N levels)        | `books-l2-tbt` (10 ms, full incremental) |

The two contracts look similar on paper (USDT-margined perpetual, $0.10
tick, 8 h funding) but the **liquidity profile, taker-flow imbalance
distribution, and exact funding rates differ enough** that a strategy
hand-tuned to Binance will not produce comparable triggers, hit rates,
or zone counts on OKX without recalibration. Per the user's instructions
("Не менять thresholds. Не менять стратегию.") we will **not** invoke
the strategy engine on OKX data. The parser-correctness replay in
Section 9 stays strictly at "can we rebuild the book and stream trades?"
and avoids any zone / target output.

---

## 9. Companion reports

- `reports/OKX_HISTORICAL_L2_TEST_REPLAY.md` — parser-correctness replay,
  3-hour window on 2026-04-01.
- `reports/OKX_HISTORICAL_L2_AUDIT.json` — machine-readable sidecar of
  the numbers in Sections 2–7.
