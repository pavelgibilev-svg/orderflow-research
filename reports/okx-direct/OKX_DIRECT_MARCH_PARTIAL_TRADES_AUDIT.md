# OKX direct trades audit - partial March 2026

**Build:** 2026-05-19T17:01:15+00:00

## A. Files

| filename | period in name | size (B) | first ts UTC | last ts UTC |
|---|---|---:|---|---|
| `BTC-USDT-SWAP-trades-2026-03.zip` | 2026-03 | 861,648,859 | 2026-02-28T16:00:00.128+00:00 | 2026-03-31T15:59:59.944+00:00 |
| `BTC-USDT-SWAP-trades-2026-04.zip` | 2026-04 | 577,512,563 | 2026-03-31T16:00:00.045+00:00 | 2026-04-30T15:59:59.930+00:00 |

## B. Asia-month bucket note

OKX monthly trade-history files are bucketed by China local time (UTC+8). `trades-2026-03.zip` covers UTC 2026-02-28T16:00 .. 2026-03-31T16:00. `trades-2026-04.zip` covers UTC 2026-03-31T16:00 .. 2026-04-30T16:00.

## C. Coverage of target window 2026-03-02 .. 2026-03-15

- covers fully: **True** (UTC 2026-03-02T00:00 .. 2026-03-16T00:00 is inside Asia-March span)

## D. Flags

- OKX_DIRECT_TRADES_READABLE = **YES**
- OKX_DIRECT_TRADES_COVER_AVAILABLE_DATES = **YES**
- OKX_DIRECT_TRADES_USABLE_FOR_FLOW = **YES**
- TRADES_SCHEMA_MATCHES_TARDIS_OKX = **PARTIAL** (column renames + microsecond timestamps)