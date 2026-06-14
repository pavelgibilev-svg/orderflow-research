# OKX direct order book schema audit - partial March 2026

**Build:** 2026-05-19T17:01:15+00:00

## A. Format summary

- format: line-delimited JSON; one event per line
- event keys: `['instId', 'action', 'ts', 'bids', 'asks']`
- actions: `['snapshot', 'update']`
- ts: millisecond UTC, string
- tuple: `[price, size, ordersCount] - all strings`
- depth (snapshot): 400
- update semantics: size=='0' => delete that price level
- snapshot anchoring: ~15 min cadence observed on 2026-03-14 deep scan

## B. First event of each file

| file | first_ts_iso | action | bids/asks |
|---|---|---|---|
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-02.tar.gz` | 2026-03-02T00:00:00.002+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-03.tar.gz` | 2026-03-03T00:00:00.005+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-04.tar.gz` | 2026-03-04T00:00:00.004+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-05.tar.gz` | 2026-03-05T00:00:00.001+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-06.tar.gz` | 2026-03-06T00:00:00.009+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-07.tar.gz` | 2026-03-07T00:00:00.006+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-08.tar.gz` | 2026-03-08T00:00:00.006+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-09.tar.gz` | 2026-03-09T00:00:00.005+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-10.tar.gz` | 2026-03-10T00:00:00.004+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-11.tar.gz` | 2026-03-11T00:00:00.006+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-12.tar.gz` | 2026-03-12T00:00:00.001+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-13.tar.gz` | 2026-03-13T00:00:00.005+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-14.tar.gz` | 2026-03-14T00:00:00.007+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-15.tar.gz` | 2026-03-15T00:00:00.003+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-27.tar.gz` | 2026-03-27T00:00:00.000+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-28.tar.gz` | 2026-03-28T00:00:00.005+00:00 | snapshot | 400/400 |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-31.tar.gz` | 2026-03-31T00:00:00.003+00:00 | snapshot | 400/400 |

## C. Flags

- OKX_DIRECT_ORDERBOOK_READABLE = **YES**
- OKX_DIRECT_ORDERBOOK_IS_L2 = **YES**
- OKX_DIRECT_ORDERBOOK_TYPE = **BOTH** (snapshot anchor + incremental deltas in same stream)
- OKX_DIRECT_ORDERBOOK_CAN_RECONSTRUCT = **YES**
- OKX_DIRECT_ORDERBOOK_DEPTH = **400**
- SCHEMA_MATCHES_TARDIS_OKX = **PARTIAL** (mechanical conversion; same upstream channel)