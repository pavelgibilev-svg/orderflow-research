# Kaggle dataset audit — `krrdev1/binance-btcusdt-l3-market-microstructure-data`

**Audit date:** 2026-05-11 (UTC)
**Working directory:** `C:\Users\gibilev\orderflow-research`
**Local path:** `data/kaggle/binance-btcusdt-l3/`
**Source:** https://www.kaggle.com/datasets/krrdev1/binance-btcusdt-l3-market-microstructure-data

---

## 0. TL;DR (read this first)

| Question                                                    | Answer |
|-------------------------------------------------------------|--------|
| Did the download work?                                      | ✅ yes — full 233 MB sample |
| Is this **Binance USDS-M Futures BTCUSDT**?                 | ❌ **NO — it is Binance SPOT BTCUSDT** |
| Is this actually **Level 3** data?                          | ❌ **NO — buyer_order_id / seller_order_id columns are present but always NULL.** It is L2 deltas + non-aggregated trades |
| Are L2 deltas + snapshots + trades all present?             | ✅ yes |
| Is sequence integrity good?                                 | ✅ yes — 1 gap in 863 903 consecutive pairs (0.000116 %) |
| How many days are in the public sample?                     | ⚠️ **just one day: 2026-04-18 UTC** |
| Can we use this **instead of Tardis**?                      | ❌ no — wrong venue (spot vs futures) and only 1 day |
| Can we use it for **parser / replay-engine development**?   | ✅ yes (with caveats — see Section H) |
| Can we use it for **serious backtest of our strategy**?     | ❌ no — strategy is calibrated for USDS-M futures regime |
| License                                                     | CC BY-NC 4.0 (non-commercial only) |

**Closest-to-2026 date found:** 2026-04-18 (the entire public sample). Last updated on Kaggle: 2026-04-20.

---

## A. General information

| Field             | Value |
|-------------------|-------|
| Kaggle slug       | `krrdev1/binance-btcusdt-l3-market-microstructure-data` |
| Title             | Binance BTCUSDT Level 3 Market Data (Ongoing) |
| Owner             | KrrDev (`krrdev1`) |
| Local path        | `data/kaggle/binance-btcusdt-l3/` |
| Total size on disk| 244 128 637 bytes (~233 MiB) |
| Files (data)      | 3 parquet files for 2026-04-18 |
| Date range        | 2026-04-18 00:00:00.011 → 23:59:59.914 UTC (one full trading day) |
| License           | Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) |
| Last updated      | 2026-04-20T10:12:39 Z |
| Version           | 1 ("Initial release") |
| Public download / view counts | 15 / 155 (at audit time) |
| Author claims     | "30+ days of history available, full archive on request via DM" — **not on Kaggle** |

The downloaded zip contains exactly:

```
orderbook_diffs_20260418.parquet       201 282 982 bytes
orderbook_snapshots_20260418.parquet    24 077 717 bytes
trades_20260418.parquet                 18 747 799 bytes
```

---

## B. Market type

**Verdict: Binance SPOT BTCUSDT.**

> _Not directly equivalent to Binance USDS-M Futures BTCUSDT-perpetual that the rest of this project consumes via Tardis._

Evidence (from the dataset's own description and from observed schemas):

| Indicator             | Spot? Futures? | Source |
|-----------------------|----------------|--------|
| `@trade` WebSocket stream | spot | author description |
| `@depth@100ms`        | spot (futures uses `@depth@100ms` on `fstream.binance.com`; description says "Binance API" + REST `/api/v3/depth`, which is spot) | author description |
| REST snapshot endpoint `GET /api/v3/depth?limit=1000` | **spot** (futures uses `/fapi/v1/depth`) | author description |
| `funding_rate` column | absent | observed schemas |
| `mark_price` column   | absent | observed schemas |
| `open_interest` column| absent | observed schemas |
| `liquidations` file   | absent | observed file list |

Practical consequences for orderflow-research:

1. Price levels and tick density differ from perpetual (smaller perp tick, different VWAP at peak hours).
2. Strategy logic that depends on funding-driven directional flow, mark-price drift, and liquidation cascades has **no input** here.
3. Spread on spot BTCUSDT is typically tighter than perp (observed: $0.01 / ~0.13 bps in this sample); your zone thresholds calibrated for perp may misfire.

---

## C. Data types present

| Type                                | Present? | Notes |
|-------------------------------------|----------|-------|
| trades                              | ✅       | 1 941 077 rows for 2026-04-18 |
| L2 deltas / book updates            | ✅       | 863 904 rows (one row per ~100 ms window, **JSON-encoded multi-level changes**) |
| snapshots                           | ✅       | 1 434 rows (~every 60 s, top-1000 each side) |
| 100 ms depth                        | ✅       | confirmed by row cadence (~24h × 36 000 = 864 000) |
| L3 individual events (with order IDs) | ❌     | `buyer_order_id` / `seller_order_id` columns exist on the trades file but are **always NULL** in the sample → not L3 |
| book_ticker / best bid-ask          | ❌       | not as a separate file (derivable from snapshots + diffs) |
| liquidations                        | ❌       | spot, doesn't exist |
| mark price / funding                | ❌       | spot, doesn't exist |

---

## D. Schema audit (per file)

### D.1 `trades_20260418.parquet`

| column          | arrow type              | role                             |
|-----------------|-------------------------|----------------------------------|
| `time`          | `timestamp[ns, tz=UTC]` | execution timestamp (precision **ns**, but values land on **ms** boundaries — see note below) |
| `symbol`        | `string`                | always `"BTCUSDT"`               |
| `trade_id`      | `int64`                 | Binance unique trade id          |
| `price`         | `double`                | execution price (USDT)           |
| `qty`           | `double`                | trade quantity (BTC)             |
| `buyer_order_id`| `null`                  | always NULL in this sample       |
| `seller_order_id`| `null`                 | always NULL in this sample       |
| `is_buyer_maker`| `bool`                  | aggressor side. `True` = seller was aggressor (taker sell); `False` = taker buy |
| `received_at`   | `timestamp[ns, tz=UTC]` | ingestion-side timestamp         |

Sample rows:

```
trade 0: trade_id=6229721083  price=77072.01  qty=0.01143   is_buyer_maker=False
trade 1: trade_id=6229721084  price=77072.01  qty=0.00097   is_buyer_maker=False
trade 2: trade_id=6229721085  price=77072.01  qty=6e-05     is_buyer_maker=False
```

Note on precision: arrow type advertises ns, but observed `.011000+00:00` and `.014000+00:00` values show all timestamps land on whole milliseconds. Effective resolution is **ms**, despite the schema claim.

### D.2 `orderbook_diffs_20260418.parquet`

| column            | arrow type              | role                                          |
|-------------------|-------------------------|-----------------------------------------------|
| `time`            | `timestamp[ns, tz=UTC]` | timestamp of this 100 ms batch (effective ms) |
| `symbol`          | `string`                | `"BTCUSDT"`                                   |
| `first_update_id` | `int64`                 | Binance `U`                                   |
| `final_update_id` | `int64`                 | Binance `u`                                   |
| `bids`            | `string` (JSON)         | array of `[price_str, qty_str]` changed bid levels |
| `asks`            | `string` (JSON)         | array of `[price_str, qty_str]` changed ask levels |
| `received_at`     | `timestamp[ns, tz=UTC]` | ingestion-side timestamp                      |

Sample first row:

```
time              = 2026-04-18 00:00:00.014 UTC
first_update_id   = 92 213 721 397
final_update_id   = 92 213 721 429
bid_levels_in_row = 18  (of which 6 are qty=0 deletions)
ask_levels_in_row = 13  (of which 2 are qty=0 deletions)
```

**Important shape detail:** each row carries between 1 and dozens of level changes packed into the JSON string. **One Kaggle row ≠ one `BookL2Event`** in our internal model — the converter must flatten.

### D.3 `orderbook_snapshots_20260418.parquet`

| column           | arrow type              | role                                          |
|------------------|-------------------------|-----------------------------------------------|
| `time`           | `timestamp[ns, tz=UTC]` | snapshot timestamp                            |
| `symbol`         | `string`                | `"BTCUSDT"`                                   |
| `last_update_id` | `int64`                 | anchor for applying diffs (`last_update_id+1` ≤ first applicable diff `first_update_id`) |
| `bids`           | `string` (JSON)         | top **1000** bid levels                       |
| `asks`           | `string` (JSON)         | top **1000** ask levels                       |
| `received_at`    | `timestamp[ns, tz=UTC]` | ingestion-side timestamp                      |

First snapshot:

```
time              = 2026-04-18 00:00:00.834663 UTC
last_update_id    = 92 213 722 282
bid_levels        = 1000  (top 3: 77069.59 / 77069.58 / 77069.26)
ask_levels        = 1000  (top 3: 77069.60 / 77069.87 / 77069.88)
spread            = 0.01 USDT  (≈ 0.13 bps at mid 77069.595)
```

---

## E. L2 reconstructability

| Question                                                | Answer / Number |
|---------------------------------------------------------|-----------------|
| Initial snapshots present?                              | ✅ yes (1 434 over the day, ~every 60 s) |
| Incremental updates present?                            | ✅ yes (863 904 rows, ~every 100 ms) |
| Add / update / delete logic clear?                      | ✅ yes — `qty == 0` ⇒ delete level; `qty > 0` ⇒ replace level (standard Binance) |
| Sequence ids?                                           | ✅ `first_update_id` / `final_update_id` per diff row, `last_update_id` per snapshot |
| Sequence continuity                                     | **863 903 consecutive pairs, 1 gap → 0.000116 % gap rate** |
| Anchor between snapshot and diffs                       | ✅ `last_update_id` matches Binance contract: apply diffs where `first_update_id ≤ last_update_id+1 ≤ final_update_id` |
| `qty=0` deletion share (first 5 000 rows)               | bid: 32 515 / 88 192 = **36.9 %**; ask: 30 719 / 81 098 = **37.9 %** — confirms standard delete semantics |
| Crossed book in raw deltas                              | not measured by direct reconstruction in this audit (see test replay) |
| Empty book                                              | not observed at any sampled snapshot |
| Spread (first snapshot)                                 | 0.01 USDT / ~0.13 bps — normal for spot BTC |

Reconstructing the book is straightforward following the standard Binance procedure documented by the dataset author and already implemented for the live recorder (`src/live-recorder/localOrderBookLive.ts`).

---

## F. Trades quality

| Question                              | Answer |
|---------------------------------------|--------|
| Aggressor side derivable?             | ✅ via `is_buyer_maker` (Binance convention) |
| `trade_id` present?                   | ✅ int64 |
| `trade_id` monotonic?                 | ✅ density 1 941 077 / 1 941 111 = **99.998 %** — essentially every id accounted for, span equals row count plus a handful |
| Price / qty present?                  | ✅ double / double |
| Zero-qty rows                         | 0 (clean) |
| Time range                            | 00:00:00.011 → 23:59:59.766 UTC (full day) |
| Total rows                            | 1 941 077 |
| Total volume                          | 9 141.19 BTC (≈ $700 M USD at $77 k mid) |
| Price min / max                       | 75 445.16 → 77 420.08 USDT (intraday range ≈ 2.6 %) |
| Taker direction split                 | taker-sell 1 037 236 (53.4 %) vs taker-buy 903 841 (46.6 %) → mildly bearish day |

Quality is high. Trade IDs match Binance public ID space (10-digit), continuous, monotonic.

---

## G. Compatibility with our orderflow-research module

Our `MarketDataSource` interface, used by both the Tardis CSV path and the live recorder's ClickHouse path, expects:

| our requirement              | Kaggle dataset provides? |
|------------------------------|--------------------------|
| `incremental_book_L2`        | ✅ but as JSON-packed multi-level rows, not flat events |
| `trades`                     | ✅ |
| `book_ticker`                | ❌ (derivable on the fly from snapshots+diffs, but no native column) |
| `liquidations`               | ❌ (spot, doesn't exist) |
| `derivative_ticker`          | ❌ (spot, no funding/mark) |

**Verdict:** **partially compatible**.

- Compatible **for parser / replay engine development**: yes — covers the standard Binance L2 reconstruction flow (`U`, `u`, `pu` chain logic) and trades.
- Compatible **for our actual strategy backtest**: **no**, for two reasons:
  1. **Spot vs futures regime mismatch.** Strategy thresholds, dedup parameters, and zone-detection feature engine are tuned to the USDS-M perpetual market. Cross-venue backtest results would not be comparable without re-calibration, and the user's instructions explicitly forbid changing thresholds.
  2. **Single-day coverage.** One day cannot replace the multi-month Tardis archive.

- Suitable **as a Tardis replacement for production**: **no.** Wrong venue, license is non-commercial, public coverage is one day, full archive is gated by direct contact with the dataset author.

---

## H. Conversion plan (if we ever do use it for parser dev)

Two options. The lower-risk choice is option **(2)**.

### H.1 Option 1: a `KaggleDataSource` adapter

A new class in `src/data/` that implements `MarketDataSource` directly against the parquet files. Pros: no extra disk. Cons: introduces parquet+JSON-string parsing into the strategy hot path.

Streaming approach:

```text
foreach diff row:
  ts = row.time (ms)
  for [price_str, qty_str] in JSON.parse(row.bids):
    yield BookL2Event {
      eventTimeMs: ts,
      side: "BID",
      price: Number(price_str),
      amount: Number(qty_str),                   // 0 means delete
      isSnapshot: false,
      sequenceId: row.final_update_id,           // u (last in batch)
    }
  for [price_str, qty_str] in JSON.parse(row.asks):
    yield BookL2Event { side: "ASK", ... same as above }

foreach snapshot row:
  ts = row.time (ms)
  for [price_str, qty_str] in JSON.parse(row.bids):
    yield BookL2Event { isSnapshot: true, sequenceId: row.last_update_id, ... }
  for [price_str, qty_str] in JSON.parse(row.asks): ...

foreach trade row:
  yield TradeEvent {
    eventTimeMs: ts,
    side: row.is_buyer_maker ? "SELL" : "BUY",   // taker side
    priceUsd: row.price,
    qtyBase: row.qty,
    tradeId: row.trade_id,
  }
```

The Binance-spot `U`/`u` resync rule (already in `localOrderBookLive.ts`) applies unchanged: a fresh diff stream must be anchored on a snapshot whose `last_update_id` falls inside the first diff's `[first_update_id, final_update_id]` range, and on every diff thereafter `first_update_id` must be `previous final_update_id + 1` (which the audit confirms holds 99.9999 % of the time).

### H.2 Option 2: one-shot converter to Tardis-like CSV.gz

Write a Node/Python script `scripts/kaggle/to-tardis.ts` that, for each calendar day on disk, emits Tardis-shaped files into `data/tardis/spot/binance/BTCUSDT/YYYY-MM-DD/`:

| Tardis filename pattern             | Kaggle source                   | Column mapping |
|-------------------------------------|---------------------------------|----------------|
| `incremental_book_L2_YYYY-MM-DD.csv.gz` | `orderbook_snapshots_*.parquet` (initial state) + `orderbook_diffs_*.parquet` | flatten JSON levels into one row per (timestamp, side, price, amount); first row of the day from the earliest snapshot is `is_snapshot=true`; sequence id = `final_update_id` for diffs, `last_update_id` for snapshots |
| `trades_YYYY-MM-DD.csv.gz`          | `trades_*.parquet`              | `is_buyer_maker = True ⇒ side = "sell"`, else `"buy"`; otherwise passthrough |

Pros: zero changes to the existing strategy reader. Cons: doubles disk during conversion.

**Recommended:** option 2, only if/when we deliberately decide to build a spot-side parallel run. **Not** recommended for replacing the existing Tardis-based futures backtest.

---

## 9. Test replay

A 3-hour test replay was attempted on 2026-04-18 06:00–09:00 UTC. See sibling file:

→ `reports/KAGGLE_BTCUSDT_L3_TEST_REPLAY.md`

(Generated alongside this audit. Note: this is parser-correctness validation only; no winrate or strategy-suitability claim is made.)

---

## 10. Final verdict

| Question                                                  | Answer |
|-----------------------------------------------------------|--------|
| Closest-to-2026 date in the public sample                 | **2026-04-18** (one full UTC day) |
| Files downloaded                                          | 3 parquet files + 1 metadata JSON |
| On-disk size                                              | 233 MiB |
| Spot or futures?                                          | **SPOT** (NOT directly equivalent to Binance USDS-M Futures) |
| Suitable for parser / replay-engine development?          | ✅ yes — clean, well-documented, sequence-continuous |
| Suitable for serious backtest of our strategy?            | ❌ no — wrong venue, only 1 day, license non-commercial |
| Can it replace Tardis?                                    | ❌ no |
| Limitations to remember                                   | spot ≠ futures; "L3" branding is misleading (order_id columns are NULL); only 1 day public; CC BY-NC 4.0; full archive is paid/DM-gated |
| Path to audit report                                      | `reports/KAGGLE_BTCUSDT_L3_DATA_AUDIT.md` (this file) |
| Path to audit JSON                                        | `reports/KAGGLE_BTCUSDT_L3_DATA_AUDIT.json` |
| Path to test replay report                                | `reports/KAGGLE_BTCUSDT_L3_TEST_REPLAY.md` |

**Hard rules honored:**

- Strategy thresholds were not changed.
- Strategy was not curve-fit; replay outputs are parser-correctness only.
- No winrate or profitability claim is made.
- Spot vs futures distinction is called out explicitly throughout.
- The dataset has incremental L2 + snapshots + trades, so it is **not flat-out unsuitable** — but the spot/futures mismatch and single-day coverage make it inappropriate as a Tardis replacement for our specific strategy.
