# OKX direct trade history audit - March 2026

**Build:** 2026-05-19T13:42:52+00:00

## A. Files supplied

| filename | period detected | size (B) | uncompressed (B) | first row ts | header |
|---|---|---:|---:|---|---|
| `BTC-USDT-SWAP-trades-2026-04.zip` | 2026-04 | 577,512,563 | 5,643,624,837 | 2026-03-31T16:00:00.045+00:00 | `instrument_name,trade_id,side,price,size,created_time` |

## B. Schema

- columns: `['instrument_name', 'trade_id', 'side', 'price', 'size', 'created_time']`
- OKX direct trades CSV uses 6 columns, comma-separated, with header row. `side` is the aggressor (taker) side, `price`/`size` are floats, `created_time` is millisecond UTC. Suitable for taker-flow / trade-imbalance derivation.

## C. Coverage check

- March-period trade files supplied: **0**
- Other-period trade files supplied: **1** (periods: ['2026-04'])

## D. Blocker (and one important nuance)

Trade history supplied is the Asia-month bucket labelled `2026-04` (April). OKX's UI
appears to bucket monthly trades by China local time (UTC+8), so the actual UTC range
of the file is:

- first row: `created_time=1774972800045` -> **2026-03-31T16:00:00.045 UTC**
- last row:  `created_time=1777564799930` -> **2026-04-30T15:59:59.930 UTC**
- total rows: **98,184,263**

That gives us **8 h of trade overlap** with our 2026-03-31 order-book file
(UTC 16:00 to 24:00 of 2026-03-31). It gives **zero overlap** with the other three
March order-book days (2026-03-14, 03-27, 03-28).

Result: even with this Asia-April file, we still do NOT have a single full UTC day
where both order book and trades are present. Either:
- (a) download the previous monthly trade file (Asia-month March = UTC 2026-02-28T16:00
  to 2026-03-31T16:00) to cover the rest of March 14 / 27 / 28 and the first 16 h of
  March 31; or
- (b) downscope the backtest to April 2026, which would then require April order-book
  archives we do not currently have (only 03-14 / 03-27 / 03-28 / 03-31 supplied).

## E. Comparison with Tardis OKX trades

Tardis OKX trades CSV has columns: exchange,symbol,timestamp,local_timestamp,id,side,price,amount. Same fields are present in OKX direct (column names differ: instrument_name=symbol, trade_id=id, size=amount, created_time=timestamp). No exchange/local_timestamp columns - trivially derivable.

## F. Flags

- OKX_DIRECT_TRADES_READABLE = **YES**
- OKX_DIRECT_TRADES_COVER_FULL_MARCH = **NO**  (covers UTC 2026-03-31T16:00 -> 2026-04-30T15:59; 0 h on 03-14/03-27/03-28; 8 h on 03-31)
- OKX_DIRECT_TRADES_USABLE_FOR_FLOW = **YES** (schema is fine, but month does not match)
- TRADES_SCHEMA_MATCHES_TARDIS_OKX = **PARTIAL**