# OKX direct order book schema audit - March 2026 sample

**Build:** 2026-05-19T13:42:52+00:00

## A. Format summary

- **format:** line-delimited JSON; one event per line
- **event keys:** `['instId', 'action', 'ts', 'bids', 'asks']`
- **action ∈** `['snapshot', 'update']`
- **ts** = millisecond UTC, string
- **tuple shape:** `[price, size, ordersCount] - all strings`
- **depth (snapshot):** 400 levels each side
- **update semantics:** size=='0' (and ordersCount=='0') means DELETE that price level; otherwise replace/insert level
- **re-anchoring:** fresh full snapshot embedded roughly every 15 minutes (~900 s) so deltas can be re-anchored if any drop
- **frequency:** 10 ms median between events; some gaps up to ~900 ms observed in 2026-03-14

## B. First event of each file

| file | first_ts_iso | action | bids/asks |
|---|---|---|---|
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-14.tar.gz` | 2026-03-14T00:00:00.007+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-27.tar.gz` | 2026-03-27T00:00:00.000+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-28.tar.gz` | 2026-03-28T00:00:00.005+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-31.tar.gz` | 2026-03-31T00:00:00.003+00:00 | snapshot | 400/400 |

## C. Deep scan of 2026-03-14 (one full day)

- total event lines: **5,241,115**
- snapshots: **96** (≈ 1 every 900 s)
- updates: **5,241,019**
- first ts (UTC): 2026-03-14T00:00:00.007+00:00
- last ts (UTC): 2026-03-14T23:59:59.943+00:00
- span: **86,399.936 s** (≈ full UTC day, 86,400 s expected)
- ts diff between events (ms) — min/median/max: 10 / 10 / 917
- delete-by-size=0 observed: **True**  (sample: side=bids, tuple=['70872.7', '0', '0'])

## D. Comparison with Tardis OKX `books-l2-tbt`

OKX direct files are the same raw `books-l2-tbt` WebSocket payload OKX itself publishes - same keys (instId/action/ts/bids/asks), same tuple shape [price,size,ordersCount], same delete-by-size=0 semantics, same re-anchoring every 15 min. Tardis OKX `books-l2-tbt` is the EXACT SAME upstream channel; what differs is the file packaging and the tuple length (Tardis stores 4 elements [price,size,depr,ordersCount]; OKX direct stores 3 [price,size,ordersCount]) and Tardis decorates each event with extra envelope columns (local_timestamp, symbol, exchange). Conversion is mechanical: drop deprecated column, add envelope.

## E. Flags

- OKX_DIRECT_ORDERBOOK_READABLE = **YES**
- OKX_DIRECT_ORDERBOOK_IS_L2 = **YES**
- OKX_DIRECT_ORDERBOOK_TYPE = **BOTH** (snapshot anchors + incremental deltas in same stream)
- OKX_DIRECT_ORDERBOOK_CAN_RECONSTRUCT = **YES**
- OKX_DIRECT_ORDERBOOK_DEPTH = **400**
- SCHEMA_MATCHES_TARDIS_OKX = **PARTIAL** (same upstream channel; minor tuple-length / envelope diffs)