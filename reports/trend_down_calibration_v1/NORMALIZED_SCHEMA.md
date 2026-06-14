# NORMALIZED SCHEMA — TREND_DOWN calibration v1

Build: research/calibration. Sources are **not modified**; everything below is produced into
`reports/trend_down_calibration_v1/_normalized/` as unified per-second L2 CSVs (`.csv.gz`).

## Source formats detected (from peeking, no assumptions)

### Bybit OrderBook (ob200)  — `data/11.06.2026/<date>_BTCUSDT_ob200.data.zip`
- Container: `.zip` with one member `<date>_BTCUSDT_ob200.data` (JSONL, ~1.6 GB/day uncompressed).
- Line: `{"topic":"orderbook.200.BTCUSDT","type":"snapshot|delta","ts":<ms int>,"data":{"s":"BTCUSDT","b":[[px,sz],...],"a":[[px,sz],...]}}`
- `type=snapshot` = full 200-level book; `type=delta` = level changes; `sz="0"` = remove level.
- Parser: maintain bid/ask dicts; clear on snapshot; apply deltas; **size 0 deletes**. ts already ms.

### OKX OrderBook (400lv) — `data/11.06.2026/BTC-USDT-SWAP-L2orderbook-400lv-<date>.tar.gz`
- Container: `.tar.gz` with one member `...-<date>.data` (JSONL).
- Line: `{"instId":"BTC-USDT-SWAP","action":"snapshot|update","ts":"<ms str>","asks":[[px,sz,#orders],...],"bids":[...]}`
- `action=snapshot` = full book; `action=update` = changes; `sz="0.0"`/`#orders="0"` = remove level. ts is a string.
- Parser: same book maintenance; cast ts to int; levels are `[px, sz, num_orders]` (we use px, sz).

### OKX Trades — `data/11.06.2026/BTC-USDT-SWAP-trades-<date>.zip`
- Container: `.zip` -> CSV: `instrument_name,trade_id,side,price,size,created_time(ms)`. `side` = aggressor (buy/sell).
- **Only out-of-window days present (2025-11-23, 2026-02-01, 2026-02-15)** -> not usable for the 3 windows.

### Bybit Trades — **NOT PROVIDED** (0 files).

## Unified per-second L2 table (output)
`_normalized/<EX>_<symbol>_<date>_l2_1s.csv.gz`, one row per second that had >=1 update:

| field | source | notes |
|---|---|---|
| exchange | both | Bybit / OKX |
| ts_sec | both | unix seconds (UTC) |
| best_bid / best_ask | both | top of reconstructed book |
| mid | both | (best_bid+best_ask)/2 — **the price series used for OHLCV + MFE labels** |
| spread_bps | both | (ask-bid)/mid*1e4 |
| top_bid_size / top_ask_size | both | size at best level |
| bid_depth_top10 / ask_depth_top10 | both | summed size of best 10 levels |
| depth_imbalance | both | (bidDepth-askDepth)/(bidDepth+askDepth) |
| update_count | both | L2 events in that second (activity proxy) |

## Unified trades table (intended)
`exchange, ts, symbol, price, size, side/aggressor, notional, raw_file` — **EMPTY for all 3 windows**
(no in-window trades on either venue). Produced only if in-window trade files appear later.

## Feature availability for this calibration
| feature | status | how |
|---|---|---|
| price / OHLCV / MFE / hit2/2.5/3 | **OK** | from Bybit ob200 mid (full coverage) |
| spread_bps, spread stability | **OK** | per-second spread series |
| top-of-book depth, depth_topN, depth_imbalance | **OK** | reconstructed book |
| order-book pressure / refill proxy | **PROXY** | derived from depth & depth_imbalance dynamics (not true passive fills) |
| update/activity rate | **OK** | update_count |
| **taker buy/sell imbalance, CVD, aggressor side** | **N/A** | no in-window trades |
| **effort_vs_result from real executions** | **PROXY** | uses L2 depth-imbalance vs price change instead of trade flow |
| true volume / trade count | **N/A in-window** | proxied by update_count only |
| OKX cross-venue | **PARTIAL** | only last day of each window (L2 only) |

All N/A fields are reported as N/A downstream and never fabricated.
