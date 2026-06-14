# DATA_CHECK_RESULT — TREND_DOWN windows (integrity only, NO calibration / NO analysis)

Build 2026-06-12 · Source (fresh drop): `C:\Users\gibilev\Downloads\Telegram Desktop` + existing `data/11.06.2026`.
All dates below are **verified from inner record timestamps**, not filenames.

## Per-window coverage (verified)
| window | date | Bybit OB | Bybit trades | OKX OB | OKX trades |
|---|---|:--:|:--:|:--:|:--:|
| W1 | 2025-11-19 | ✅ | ✅ | ❌ | ❌ |
| W1 | 2025-11-20 | ✅ | ✅ | ❌ | ❌ |
| W1 | 2025-11-21 | ✅ | ✅ | ❌ | ❌ |
| W1 | 2025-11-22 | ✅ | ✅ | ✅ | ❌ |
| W3 | 2026-01-28 | ✅ | ✅ | ❌ | ❌ |
| W3 | 2026-01-29 | ✅ | ✅ | ❌ | ❌ |
| W3 | 2026-01-30 | ✅ | ✅ | ❌ | ❌ |
| W3 | 2026-01-31 | ✅ | ✅ | ✅ | ❌ |
| NEW_APRIL | 2024-04-12 | ✅ | ✅ | ❌ | ❌ |
| NEW_APRIL | 2024-04-13 | ✅ | ✅ | ❌ | ❌ |
| NEW_APRIL | 2024-04-14 | ✅ | ✅ | ❌ | ❌ |
| NEW_APRIL | 2024-04-15 | ✅ | ✅ | ❌ | ❌ |
| NEW_APRIL | 2024-04-16 | ✅ | ✅ | ❌ | ❌ |
| NEW_APRIL | 2024-04-17 | ✅ | ✅ | ✅ | ⚠️ PARTIAL |

**Bybit**: every OB and trades file opens cleanly, symbol = `BTCUSDT` (spot-style perpetual, NOT a dated future),
each trades file spans exactly one UTC day 00:00:00→23:59:59, each OB file starts at 00:00:0X UTC (first-line
verified; full last-line not exhaustively read on the multi-GB OB files but the UTC-day start is confirmed).

**OKX timestamp gotcha**: OKX **L2** files are **UTC-day-aligned** (00:00:00→23:59:59). OKX **trades** files use a
**UTC+8 (Beijing) day boundary** — e.g. `trades-2024-04-18` actually contains **2024-04-17 16:00 → 2024-04-18 16:00 UTC**.
So the only in-window OKX trades we have is the *second 8h of 2024-04-17* (16:00→24:00) — marked ⚠️ PARTIAL above;
04-17 00:00→16:00 is missing. The `trades-2026-02-15` file (02-14 16:00→02-15 16:00) belongs to the old W2 window, not these three.

## DATA_CHECK_RESULT
```
1. BYBIT_STATUS: OK   (all 14 OB + 14 trades present for W1/W3/NEW_APRIL; symbol BTCUSDT; no broken files)
2. OKX_STATUS:   MISSING

3. BYBIT_MISSING: none (OB and trades complete for all 3 windows)

4. OKX_MISSING:
   OrderBook (UTC-day): W1 2025-11-19, 2025-11-20, 2025-11-21 ; W3 2026-01-28, 2026-01-29, 2026-01-30 ;
                        NEW_APRIL 2024-04-12, 2024-04-13, 2024-04-14, 2024-04-15, 2024-04-16
                        (only the last day of each window present: 11-22, 01-31, 04-17)
   Trades (UTC-day):    W1 all 4 ; W3 all 4 ; NEW_APRIL 2024-04-12..16 fully + 2024-04-17 first 16h
                        (the only OKX in-window trades data is 04-17 16:00..24:00 from the 04-18 file)

5. ARCHIVE_ISSUES: broken=NONE; bad_symbol=NONE.
   Data duplicates present but OUT OF SCOPE: 'BTC-USDT-SWAP-L2orderbook-400lv-2026-03-14.tar (2).gz',
   'BTC-USDT-SWAP-trades-2026-04 (2).zip' (March/April monthly extras, not part of W1/W3/NEW_APRIL).
   No overwrite collisions among the 3-window files (each extracts to a distinct inner member name).
   (Many personal non-data "(2)" files also sit in the Telegram folder; ignored.)

6. TIMESTAMP_CHECK: CONFIRMED via inner timestamps.
   - Bybit OB/trades: real UTC dates match filenames (single UTC day each).
   - OKX L2: real UTC dates match filenames (single UTC day each).
   - OKX trades: filename != UTC coverage -> UTC+8 boundary; multi-UTC-day:
       trades-2024-04-18 = 2024-04-17 16:00 .. 2024-04-18 16:00 UTC
       trades-2026-02-15 = 2026-02-14 16:00 .. 2026-02-15 16:00 UTC

7. READY_FOR_NEXT_PROMPT: NO (for a cross-venue OKX+Bybit run).
   BUT: BYBIT-ONLY run WITH trade-flow is READY for all 3 windows (the missing-trades blocker from TASK1/2 is now solved on Bybit).
```

## If you want full cross-venue (OKX) coverage — exact files to download
OKX OrderBook (BTC-USDT-SWAP, UTC-day files):
- 2025-11-19, 2025-11-20, 2025-11-21
- 2026-01-28, 2026-01-29, 2026-01-30
- 2024-04-12, 2024-04-13, 2024-04-14, 2024-04-15, 2024-04-16

OKX Trades (BTC-USDT-SWAP) — remember the **UTC+8 boundary**: to cover UTC day D you need the file labeled **D AND D+1**.
- W1 UTC 11-19..11-22  → download OKX trades labeled 2025-11-19, -20, -21, -22, **and 2025-11-23**
- W3 UTC 01-28..01-31  → download OKX trades labeled 2026-01-28, -29, -30, -31, **and 2026-02-01**
- NEW_APRIL UTC 04-12..04-17 → download OKX trades labeled 2024-04-12, -13, -14, -15, -16, -17 (you already have 04-18 for the 04-17 second half)

(If cross-venue is not required for the next prompt, none of the above is needed — Bybit alone is complete.)
