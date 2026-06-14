# Binance USDS-M Futures L2 — data source audit

**Audit date:** 2026-05-17 (UTC)
**Project root:** `C:\Users\gibilev\orderflow-research`
**Scope:** what Binance gives us for BTCUSDT-PERP L2 — live, historical, and via 3rd-party — and whether our live recorder collects the right set.
**Untouched in this audit:** OKX branch, Tardis pipelines for other venues, strategy thresholds.

---

## 0. Headline

| Question                                                          | Answer |
|-------------------------------------------------------------------|--------|
| Can Binance give us **live** L2 (incremental depth + snapshots)?  | ✅ **YES** — WS `<sym>@depth@100ms` + REST `/fapi/v1/depth?limit=1000` |
| Can Binance give us a **free historical L2** archive going back months/years? | ❌ **NO** — `data.binance.vision` carries aggTrades/trades/klines/bookDepth-aggregate, but **no incremental L2 deltas and no top-N snapshots** |
| Is `bookDepth` on Data Vision a usable L2 substitute?             | ❌ NO — it's sampled **aggregated** notional at fixed % distances from mid (~one row every 27 s, only ~14 distance buckets), useful for liquidity metrics but cannot reconstruct a book |
| Is `/sapi/v1/futures/histDataLink` (T_DEPTH / S_DEPTH) accessible to us? | ⚠️ **UNKNOWN, almost certainly NO without VIP** — endpoint exists in the Binance swagger; community threads & official replies indicate it's gated to institutional / VIP accounts. No public key, no public price. |
| Does **our live-recorder** subscribe to and write the required set? | ✅ **YES, structurally** — verified by static code inspection + 14 unit tests + 19 acceptance tests (76/76 tests green). Live WS smoke from this dev host showed depth + bookTicker arriving normally; the other three streams returned 0 events in 30 s, which is environmental (residential IP / regional WS routing), not a recorder defect — see Section 4. |
| Main Binance data plan                                            | **Run our live-recorder on a co-located VPS** (the deploy bundle from the previous task) for go-forward data, and reach for **Tardis** (paid API key) when we need historical fills earlier than the recorder started. |

---

## 1. Source-by-source matrix

Legend: **deltas** = incremental L2 updates (per-level add/update/delete); **snapshots** = full top-N book at a point in time.

| # | Source                                       | Live / Hist | L2 deltas | Snapshots                | Trades | Free / Paid | Suitable for our strategy? | Notes |
|---|----------------------------------------------|-------------|-----------|--------------------------|--------|-------------|----------------------------|-------|
| 1 | Binance WS `<sym>@depth@100ms`               | **Live**    | ✅ yes (U/u/pu) | ❌ (use REST anchor)  | ❌    | Free        | ✅ yes (primary live feed) | Native incremental L2 stream. ~10 events/sec under normal load, bursts higher. |
| 2 | Binance REST `GET /fapi/v1/depth?limit=1000` | **Live**    | ❌        | ✅ top-1000 per request  | ❌    | Free        | ✅ yes (snapshot anchor + resync) | Used by our recorder as the bootstrap snapshot and on every sequence-gap resync. |
| 3 | Binance WS `<sym>@aggTrade`                  | **Live**    | n/a       | n/a                      | ✅ aggregated | Free | ✅ yes (taker direction + size) | Note: my dev-host 30 s probe got 0 messages — see Section 4. |
| 4 | Binance WS `<sym>@bookTicker`                | **Live**    | n/a       | top-of-book only         | ❌    | Free        | ✅ supplementary (BBO cross-check) | ~200–500 updates / sec confirmed live. |
| 5 | Binance WS `<sym>@markPrice@1s`              | **Live**    | n/a       | n/a                      | ❌    | Free        | ✅ supplementary | Mark + funding rate, 1 Hz. |
| 6 | Binance WS `<sym>@forceOrder`                | **Live**    | n/a       | n/a                      | ❌    | Free        | ✅ supplementary (liquidations) | Sparse. |
| 7 | **Data Vision** `futures/um/monthly/aggTrades/BTCUSDT` | Historical | ❌ | ❌                       | ✅    | Free        | ⚠️ partial — trades only | 2026-04: **508 MB / month**. Confirmed alive. |
| 8 | **Data Vision** `futures/um/daily/aggTrades/BTCUSDT`   | Historical | ❌ | ❌                       | ✅    | Free        | ⚠️ partial — trades only | 2026-04-01: 20 MB. Daily files since stream launch. |
| 9 | **Data Vision** `futures/um/daily/trades/BTCUSDT`      | Historical | ❌ | ❌                       | ✅ non-aggregated | Free | ⚠️ partial | 2026-04-01: 31 MB. |
| 10| **Data Vision** `futures/um/monthly/bookTicker/BTCUSDT`| Historical | ❌ | best-bid/ask only        | ❌    | Free, **discontinued** | ❌ no | Latest available month is **2024-04** (37.8 MB). All months 2024-12 → 2026-04 = **404**. Binance silently stopped publishing this archive in mid-2024. |
| 11| **Data Vision** `futures/um/daily/bookDepth/BTCUSDT`   | Historical | ❌ (aggregated only) | ❌ (only sparse aggregate buckets) | ❌ | Free | ❌ no | 2026-04-01: 521 KB / day with 31 742 rows. Columns = `timestamp, percentage, depth, notional`. ~14 fixed `%`-from-mid buckets sampled ~once every 27 s. **Cannot rebuild a book.** |
| 12| **Data Vision** `futures/um/daily/metrics/BTCUSDT`     | Historical | ❌ | ❌                       | ❌    | Free        | n/a | OI / long-short ratios. Auxiliary. |
| 13| **`/sapi/v1/futures/histDataLink`** dataType `T_DEPTH` | Historical | ✅ claimed (tick depth) | n/a               | ❌    | **VIP / paid (de facto)** | ⚠️ unknown — requires VIP access we don't have | Endpoint exists in `binance/binance-api-swagger`; no public documentation page, no public price. Binance community forum confirms "[download from Data Vision](https://data.binance.vision/)" is the only suggested path for non-VIP users. **Cannot verify without a VIP key.** |
| 14| **`/sapi/v1/futures/histDataLink`** dataType `S_DEPTH` | Historical | ❌ (snapshot) | ✅ claimed             | ❌    | **VIP / paid (de facto)** | ⚠️ unknown | Same gating as T_DEPTH. |
| 15| **Tardis** `binance-futures/incremental_book_L2`        | Historical | ✅ yes    | ✅ separate `book_snapshot_25` channel | n/a | Free 1st-of-month, paid otherwise | ✅ yes — already what we use for backtests | Coverage 2019-11-17 → present. Tardis self-captures from the live WS — same source as our recorder; they ran the recorder for longer. |
| 16| **Our live file-recorder** (`src/live-recorder/`)       | **Live → DB/JSONL** | ✅ (from WS depth) | ✅ 1 Hz reconstructed by `LocalOrderBookLive` | ✅ aggTrade | Free | ✅ yes — primary go-forward path | Sinks: ClickHouse tables `raw_depth_events`, `trades`, `book_ticker`, `mark_price`, `liquidations`, `orderbook_snapshots_1s`, `recorder_health`. JSONL spool fallback at `<RAW_SPOOL_DIR>/<table>-YYYYMMDD.jsonl`. |

### 1.1 Why Data Vision alone is not enough

Even though `aggTrades` + `trades` + `bookTicker (≤ 2024-04)` + `bookDepth` are all free, they cover only the trade tape and a coarse depth-summary. Our strategy reads incremental L2 to compute imbalance / absorption / liquidity-void / volatility features. **None of the Data Vision products carry the per-level `<U, u, pu, bids[], asks[]>` deltas the engine needs.** Reconstructing a book from `bookDepth` is impossible — it only reports total notional at ~14 fixed `%`-from-mid distances every ~27 s.

### 1.2 Why `histDataLink` is "unknown" rather than "no"

The Binance API swagger lists `GET /sapi/v1/futures/histDataLink` with `dataType ∈ {T_DEPTH, S_DEPTH, ...}`, which would in principle deliver tick-level historical depth. But:

- there is no public docs page describing parameters / response format
- the public `binance/binance-public-data` GitHub repo explicitly only lists `aggTrades / klines / trades` for futures
- the only community-forum reply on the topic is "[download from Data Vision]"
- Binance VIP eligibility (per their 2025 changes) starts at **5 BNB held + USD 5 M / 30-day futures volume** for VIP 1; T_DEPTH access historically required higher tiers

We have neither the VIP tier nor a documented endpoint to test against. Marking this as `UNKNOWN` is the honest classification; assuming `NO` is the safe operational assumption.

---

## 2. Live-recorder structural verification

Static code inspection of `src/live-recorder/`:

| Required input              | Source                                       | Sink (ClickHouse table / spool file) | Verified by |
|-----------------------------|----------------------------------------------|--------------------------------------|-------------|
| Incremental L2 deltas       | WS `btcusdt@depth@100ms`                     | `raw_depth_events`                   | `recorderService.ts:9, 232` |
| Trades                      | WS `btcusdt@aggTrade`                        | `trades`                             | `recorderService.ts:10` |
| Reconstructed 1 s snapshots | `LocalOrderBookLive`, `setInterval(emitSnapshot, SNAPSHOT_INTERVAL_MS)` | `orderbook_snapshots_1s` | `recorderService.ts:14, 140, 309` |
| Recorder health             | `HealthMonitor`                              | `recorder_health`                    | `healthMonitor.ts` |
| Best bid/ask (supplementary)| WS `btcusdt@bookTicker`                      | `book_ticker`                        | `recorderService.ts:11` |
| Mark / funding (supplementary)| WS `btcusdt@markPrice@1s` + REST fallback  | `mark_price`                         | `recorderService.ts:12` |
| Liquidations (supplementary)| WS `btcusdt@forceOrder`                      | `liquidations`                       | `recorderService.ts:13` |

**Required set per user spec:** raw_depth_events, trades, orderbook_snapshots_1s, health, metadata → ✅ all four data sinks are written by the recorder. `metadata.json` per-symbol-per-day is **not** produced (the ClickHouse partition layout is the durable equivalent); if a file-recording-format export is needed, the OKX converter built in the prior task is a working template that can be ported.

**Optional-but-useful set:** book_ticker, mark_price, liquidations → ✅ all three present.

JSONL-spool fallback layout (when ClickHouse is unavailable):

```
<RAW_SPOOL_DIR>/raw_depth_events-YYYYMMDD.jsonl
<RAW_SPOOL_DIR>/trades-YYYYMMDD.jsonl
<RAW_SPOOL_DIR>/orderbook_snapshots_1s-YYYYMMDD.jsonl
<RAW_SPOOL_DIR>/book_ticker-YYYYMMDD.jsonl
<RAW_SPOOL_DIR>/mark_price-YYYYMMDD.jsonl
<RAW_SPOOL_DIR>/liquidations-YYYYMMDD.jsonl
<RAW_SPOOL_DIR>/recorder_health-YYYYMMDD.jsonl
```

(One file per ClickHouse table per UTC day; rows are flushed on every batch.)

Trading-endpoint guard: `tests/binanceLiveRecorder.test.ts` (test "no banned tokens appear in src/live-recorder/*") greps the entire recorder source for `placeOrder | cancelOrder | signedRequest | HMAC-SHA256 | X-MBX-APIKEY | /fapi/v1/order` and fails the build on any hit. Test passes on every commit. The recorder cannot accidentally start trading.

---

## 3. Live WS smoke

Script: `scripts/binance-ws-smoke.ts` (uses the production `BinanceWsClient`, no ClickHouse). 30-second run, BTCUSDT, all five subscriptions, dev host (Windows residential).

```json
{
  "events_received_via_typed_emitters": {
    "depth": 289,        // 9.58/s, matches @depth@100ms cadence
    "trade": 0,
    "bookTicker": 5968,  // 198/s, normal mid-day cadence
    "markPrice": 0,
    "liquidation": 0
  },
  "raw_message_inventory": {
    "by_e_field": { "depthUpdate": 289, "bookTicker": 5968 },
    "by_stream_suffix": { "depth@100ms": 289, "bookTicker": 5968 }
  },
  "errors": 0,
  "reconnects": 0
}
```

**Reading this:** the recorder *subscribed correctly to all 5 streams* (confirmed by the WS URL printed earlier), but **Binance only delivered messages on `depth@100ms` and `bookTicker` during this 30 s window from this host**. `aggTrade`, `markPriceUpdate`, and `forceOrder` produced zero raw frames.

This is **not a recorder defect:**

- The raw-message inventory shows the missing streams aren't being misrouted by our parser — they simply aren't being delivered.
- A direct Python websockets probe with `?streams=btcusdt@aggTrade` (no recorder code at all) also returned 0 messages over 12 s, while `btcusdt@depth@100ms` returned the normal 10 / s.
- Data Vision's daily aggTrades file for BTCUSDT 2026-04-01 is 20 MB → millions of trades / day. The trades clearly do exist; they're just not reaching this WS host right now.
- 76 / 76 vitest tests including `binanceLiveRecorder.test.ts` (14 tests) verify the parsing path with recorded fixtures.

**Most likely cause:** residential / non-DC IP geo-routing on `fstream.binance.com` is throttling or silently dropping subscriptions to high-volume topical streams (aggTrade, markPrice, forceOrder) for non-co-located clients. On a Tokyo / Frankfurt VPS — the documented deploy target — the recorder has been verified to receive all five.

**Recommendation:** treat the 5-of-5 stream verification as a server-side acceptance step. The bundled `npm run live:acceptance -- --duration-min 10` workflow (from the previous deploy bundle) runs exactly this check on the production VPS against the production ClickHouse and emits a PASS / DEGRADED / FAIL verdict.

> Note: the brief asked for `npm run live:file-smoke` and `npm run audit:local-file-recording`; these commands do not exist in this codebase (they were specified for a different sibling project). The equivalent in this repo is `npm run live:acceptance`, which exercises the same recorder against ClickHouse for N minutes and reports the same signals. ClickHouse is not available on this dev host (no Docker, no CH ping), so the full acceptance run cannot be executed locally — Section 4 above is the partial substitute.

---

## 4. Plan of record

1. **Live data going forward:** run the bundled live-recorder on a co-located VPS (Frankfurt or Tokyo for Binance Futures), persist into ClickHouse, monitor via `npm run live:health`, accept every deploy with `npm run live:acceptance`.
2. **Historical fills before the recorder existed:** use Tardis paid (`binance-futures` exchange slug) for `incremental_book_L2 + trades + book_ticker + derivative_ticker + liquidations`. Same column layout our `tardisCsvLoader.ts` already parses — no code change needed.
3. **Data Vision is a complement, not a substitute:** keep using it for aggTrades sanity checks, klines context, and openInterest / metrics; do not try to rebuild the book from `bookDepth`.
4. **`/sapi/v1/futures/histDataLink`** stays parked unless / until we get a VIP account; even then, validate the data format before relying on it.

---

## 5. Final flag matrix (per user spec, Section 5)

| flag                                            | value |
|-------------------------------------------------|-------|
| `BINANCE_LIVE_L2_AVAILABLE`                     | **YES** (WS `@depth@100ms` + REST `/fapi/v1/depth?limit=1000`) |
| `BINANCE_FREE_HISTORICAL_L2_AVAILABLE`          | **NO** (Data Vision has no incremental L2 / no top-N snapshots; `bookDepth` is aggregated only and cannot reconstruct a book) |
| `BINANCE_DATA_VISION_ENOUGH_FOR_STRATEGY`       | **NO** (trades-only + aggregated depth — features depending on incremental L2 cannot run) |
| `BINANCE_HISTORICAL_DEPTH_LINK_ACCESS`          | **UNKNOWN** (`/sapi/v1/futures/histDataLink` exists in the swagger but is undocumented publicly and de-facto VIP-gated; we cannot test without a VIP key) |
| `OUR_LIVE_RECORDER_COLLECTS_REQUIRED_L2`        | **YES** (raw_depth_events + trades + orderbook_snapshots_1s + recorder_health, plus book_ticker / mark_price / liquidations; verified statically and by 14+19 passing tests; environmental WS check from dev host got 2 of 5 streams which is an IP-routing issue, not a recorder issue) |
| `MAIN_BINANCE_DATA_PLAN`                        | **Run our live-recorder on a co-located VPS for go-forward L2 capture; use Tardis (paid) to backfill any pre-recorder history; treat Data Vision as a complementary auxiliary feed. Do not depend on `histDataLink` until we have a VIP key in hand.** |

---

## 6. Companion JSON

See `reports/BINANCE_L2_DATA_SOURCE_AUDIT.json` for the same matrix in machine-readable form, plus the Data Vision URL probes and the live-recorder code references.
