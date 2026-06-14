# Binance archive inventory — requested OOS window 2026-05-21..30

**Build:** 2026-05-31T11:41:22+00:00

## VERDICT: requested window is ABSENT
- **Max Binance date available anywhere: `2026-05-20`.**
- Requested days present: NONE
- Requested days absent: ['2026-05-21', '2026-05-22', '2026-05-23', '2026-05-24', '2026-05-25', '2026-05-26', '2026-05-27', '2026-05-28', '2026-05-29', '2026-05-30']
- The source archive snapshot (`OFFRW`) was created 2026-05-21 ~07:00 and captured only up to the last complete recorded day (2026-05-20). 2026-05-21..30 were never recorded into this archive.

## Archive files (sha256)

| file | size MB | sha256 (first 16) | inner date dirs | streams |
|---|---:|---|---|---|
| BTCUSDT.zip | 694.0 | eca0fdc24398cc0b | 2026-05-17,2026-05-18 | book_ticker,health,liquidations,mark_price,orderbook_snapsho |
| BTCUSDT2.zip | 1221.4 | 6fd67e2ecbaab004 | 2026-05-18,2026-05-19,2026-05-20 | book_ticker,health,liquidations,mark_price,orderbook_snapsho |
| BTCUSDT2_2.zip | 1221.4 | 8a581bc75dcf6cc2 | - | - |
| BTCUSDT2_2.zip.001 | 681.6 | d7fb7c75c3aabf5b | - | - |
| BTCUSDT2_2.zip.002 | 539.8 | 81924d689433762a | - | - |
| OFFRW.zip | 1900.7 | 162b510939cf3d7d | - | - |

## Normalized reference days present (05-17..20, OUTSIDE requested window)

| date | streams |
|---|---|
| 2026-05-17 | book_ticker, derivative_ticker, incremental_book_L2, liquidations, trades |
| 2026-05-18 | book_ticker, derivative_ticker, incremental_book_L2, liquidations, trades |
| 2026-05-19 | book_ticker, derivative_ticker, incremental_book_L2, liquidations, trades |
| 2026-05-20 | book_ticker, derivative_ticker, incremental_book_L2, liquidations, trades |

## Flags
```
BINANCE_ARCHIVES_FOUND = YES (but only up to 2026-05-20; requested 05-21..30 ABSENT)
BINANCE_DATES_DETECTED = ['2026-05-17', '2026-05-18', '2026-05-19', '2026-05-20']
BINANCE_ARCHIVE_SHA256_DONE = YES
BINANCE_RAW_ARCHIVES_UNTOUCHED = YES
REQUESTED_WINDOW_PRESENT_DAYS = 0
REQUESTED_WINDOW_ABSENT_DAYS = 10
```