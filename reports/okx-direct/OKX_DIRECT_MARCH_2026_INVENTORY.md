# OKX direct Historical Market Data - March 2026 inventory

**Build:** 2026-05-19T13:42:52+00:00
**Venue:** okx-swap  **Symbol:** BTC-USDT-SWAP
**Source:** okx_direct_historical_data
**Scope requested:** March 2026 (2026-03-01 .. 2026-03-31)

## A. Order book archives

| filename | date | size (B) | uncompressed (B) | first ts (UTC) | action | bids/asks | sha256 (8) |
|---|---|---:|---:|---|---|---|---|
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-14.tar.gz` | 2026-03-14 | 261,872,826 | 1,793,847,907 | 2026-03-14T00:00:00.007+00:00 | snapshot | 400/400 | `117bcd97` |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-27.tar.gz` | 2026-03-27 | 519,684,264 | 3,174,682,572 | 2026-03-27T00:00:00.000+00:00 | snapshot | 400/400 | `e74d55d8` |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-28.tar.gz` | 2026-03-28 | 294,746,814 | 2,024,138,593 | 2026-03-28T00:00:00.005+00:00 | snapshot | 400/400 | `cac0efb3` |
| `BTC-USDT-SWAP-L2orderbook-400lv-2026-03-31.tar.gz` | 2026-03-31 | 600,366,011 | 3,580,487,367 | 2026-03-31T00:00:00.003+00:00 | snapshot | 400/400 | `ce57e041` |

## B. Trade archives

| filename | period detected | size (B) | uncompressed (B) | first row ts | sha256 (8) |
|---|---|---:|---:|---|---|
| `BTC-USDT-SWAP-trades-2026-04.zip` | 2026-04 | 577,512,563 | 5,643,624,837 | 2026-03-31T16:00:00.045+00:00 | `bb79b804` |

## C. March 2026 day coverage (order book)

- expected days: **31** (2026-03-01 .. 2026-03-31)
- covered days: **4**: 2026-03-14, 2026-03-27, 2026-03-28, 2026-03-31
- missing days: **27**

Missing list:

```
2026-03-01, 2026-03-02, 2026-03-03, 2026-03-04, 2026-03-05, 2026-03-06, 2026-03-07, 2026-03-08, 2026-03-09, 2026-03-10, 2026-03-11, 2026-03-12, 2026-03-13, 2026-03-15, 2026-03-16, 2026-03-17, 2026-03-18, 2026-03-19, 2026-03-20, 2026-03-21, 2026-03-22, 2026-03-23, 2026-03-24, 2026-03-25, 2026-03-26, 2026-03-29, 2026-03-30
```

- duplicate days: (none)
- covers_full_march = **False**

## D. Trade history coverage

- trade files matching period 2026-03: **0**
- trade files for other periods: **1** (periods: ['2026-04'])
- march_trades_present = **False**

## E. Verdict

- OKX_DIRECT_FILES_READABLE = **YES** (all 4 order-book tar.gz open and first event parses; all trade zips open and CSV header reads)
- OKX_DIRECT_COVERS_FULL_MARCH = **NO** (blocker: 27 March days not supplied)
- OKX_DIRECT_TRADES_AVAILABLE = **NO (only OTHER-month trade files supplied)**