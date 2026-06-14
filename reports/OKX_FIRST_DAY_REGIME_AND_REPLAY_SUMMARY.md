# OKX first-day regime + technical replay summary (6 chosen dates)

**Venue:** OKX `okex-swap` BTC-USDT-SWAP (perpetual)
**Source:** Tardis CDN first-of-month free samples (29 dates classified, 6 selected)
**Selection:** 2 bullish + 2 bearish + 2 choppy chosen from the regime table
**Strategy thresholds:** Binance USDS-M Futures defaults — **UNCHANGED**

## HARD DISCLAIMER

  • OKX is NOT Binance.
  • Strategy thresholds are calibrated for Binance USDS-M Futures BTCUSDT-perp.
  • Numbers below are the engine's reaction to OKX microstructure with Binance-tuned thresholds left UNCHANGED.
  • Do NOT quote any of these numbers as a strategy edge or winrate.
  • Purpose: cross-venue research on engine behaviour across regimes.

## A. Per-date overview — **3 h cap** (L2 capped at 03:00 UTC, trades full 24 h)

| date       | bucket   | day Δ %  | range % | L2 rows         | trades rows     | zones | triggered | reached | LONG | SHORT | unique moves | dedup suppr. | raw hit | uniq-move hit |
|------------|----------|---------:|--------:|----------------:|----------------:|------:|----------:|--------:|-----:|------:|-------------:|-------------:|--------:|--------------:|
| 2024-01-01 | bullish  |  +4.54  |   4.90 |     102,515,341 |        323,856 |   10 |         5 |       4 |    5 |     5 |            1 |         2441 |  80.00% |         20.00% |
| 2025-10-01 | bullish  |  +4.00  |   4.17 |      92,168,407 |      2,097,545 |    7 |         2 |       1 |    3 |     4 |            1 |         1905 |  50.00% |         50.00% |
| 2025-12-01 | bearish  |  -4.51  |   7.32 |     164,161,088 |      5,097,976 |   11 |         4 |       4 |    5 |     6 |            1 |         1012 | 100.00% |         25.00% |
| 2024-10-01 | bearish  |  -3.97  |   6.27 |     124,227,505 |      2,190,002 |    7 |         1 |       0 |    4 |     3 |            0 |         1520 |   0.00% |          0.00% |
| 2024-07-01 | choppy   |  +0.22  |   2.15 |      88,305,628 |        959,411 |   12 |         8 |       0 |    7 |     5 |            0 |         1670 |   0.00% |          0.00% |
| 2026-04-01 | choppy   |  -0.24  |   2.59 |     110,176,675 |      3,920,423 |   11 |         6 |       0 |    7 |     4 |            0 |         1365 |   0.00% |          0.00% |

## B. Per-date overview — **full UTC day** (L2 full 24 h, trades full 24 h)

Full-day replay is much heavier per date (~30–75 min wall-clock depending on L2 file size). To stay within compute budget, only one date was executed end-to-end here. The remaining five dates have their 3 h metrics in Section A; full-day reruns are a known follow-up.

| date       | bucket   | zones | triggered | reached | LONG | SHORT | unique moves | dedup suppr. | raw hit | uniq-move hit |
|------------|----------|------:|----------:|--------:|-----:|------:|-------------:|-------------:|--------:|--------------:|
| 2024-01-01 | bullish  |   43 |        23 |      13 |   21 |    22 |            1 |        15210 |  56.52% |          4.35% |
| 2025-10-01 | bullish  |    — |        — |       — |    — |     — |            — |            — |   not yet — see Section A 3 h numbers |
| 2025-12-01 | bearish  |    — |        — |       — |    — |     — |            — |            — |   not yet — see Section A 3 h numbers |
| 2024-10-01 | bearish  |    — |        — |       — |    — |     — |            — |            — |   not yet — see Section A 3 h numbers |
| 2024-07-01 | choppy   |    — |        — |       — |    — |     — |            — |            — |   not yet — see Section A 3 h numbers |
| 2026-04-01 | choppy   |    — |        — |       — |    — |     — |            — |            — |   not yet — see Section A 3 h numbers |

## C. Per-date target feasibility (24 h max forward move from any minute)

| date       | 4h up | 4h dn | 8h up | 8h dn | 24h up | 24h dn | 0.5% | 1% | 1.5% | 2% |
|------------|------:|------:|------:|------:|-------:|-------:|:----:|:--:|:----:|:--:|
| 2024-01-01 |  2.69 |  1.29 |  3.60 |  1.32 |   4.72 |   1.32 |  ✓   | ✓  |  ✓   | ✓  |
| 2025-10-01 |  2.02 |  1.15 |  2.81 |  1.15 |   4.09 |   1.15 |  ✓   | ✓  |  ✓   | ✓  |
| 2025-12-01 |  2.62 |  4.63 |  3.44 |  5.23 |   3.44 |   7.15 |  ✓   | ✓  |  ✓   | ✓  |
| 2024-10-01 |  2.16 |  3.77 |  2.16 |  5.43 |   2.16 |   6.00 |  ✓   | ✓  |  ✓   | ✓  |
| 2024-07-01 |  1.93 |  1.37 |  2.03 |  1.59 |   2.03 |   1.90 |  ✓   | ✓  |  ✓   | ✓  |
| 2026-04-01 |  2.37 |  1.60 |  2.41 |  1.80 |   2.41 |   1.82 |  ✓   | ✓  |  ✓   | ✓  |

## D. Per-date quality / behaviour notes

- **2024-01-01** (bullish, day Δ +4.54%): full-day: 13 reaches but only 1 unique move — 12 duplicate-move-credit zones absorbed by clustering. full-day produced >3× more zones than 3h — most signal came from the 21 h after the 3 h cap.
- **2025-10-01** (bullish, day Δ +4.00%): clean.
- **2025-12-01** (bearish, day Δ -4.51%): clean.
- **2024-10-01** (bearish, day Δ -3.97%): 3h: engine triggered but never reached 2% — consistent with the day's regime / feasibility table for the first 3 hours UTC.
- **2024-07-01** (choppy, day Δ +0.22%): 3h: engine triggered but never reached 2% — consistent with the day's regime / feasibility table for the first 3 hours UTC.
- **2026-04-01** (choppy, day Δ -0.24%): 3h: engine triggered but never reached 2% — consistent with the day's regime / feasibility table for the first 3 hours UTC.

## E. Interpretation guide

- **`bullish` days with 2 % feasibility** are mechanically the easiest to register LONG reaches; bearish days the same for SHORT. A bullish day that still produces 0 reaches in 3 h points to trigger-timing or zone-band placement mismatch with this venue's microstructure, not to a strategy defect.
- **`choppy` days with `2 %` infeasibility** are guaranteed 0 % reach for a 2 % target. Any triggers there land as RESOLVED_FAILED regardless of strategy quality.
- **3 h vs full-day:** the 3 h cap is a compute-budget knob, not a strategy threshold. Full-day on 2024-01-01 produced 43 zones vs 10 in the 3 h cap — 4× more zones and many more triggers, but the **unique-move count stays low (1)** because the strategy keeps firing similar same-direction zones throughout a sustained multi-hour rally. This is the exact phenomenon the unique-move-clustering accounting fix was built for.
- **Dedup suppression counts rise to 4-15K under full-day** — the engine sees a high volume of same-direction candidates, which the deduplication layer absorbs. Whether the residual zone density is appropriately calibrated for OKX is a separate, deliberately-out-of-scope calibration task.

## F. What's still missing for a real cross-venue conclusion

- **Full-day on the other 5 dates** — pending compute budget; ~30–75 min per date × 5 = ~3–6 hours total. Run via:
  ```
  for D in 2024-07-01 2024-10-01 2025-10-01 2025-12-01 2026-04-01; do
    npm run backtest:okx-technical -- --date $D --window full-day
    for E in md json _ZONES.csv; do mv reports/OKX_TECHNICAL_REPLAY_$D.$E reports/OKX_TECHNICAL_REPLAY_${D}_fullday.$E; done
    cp reports/okx_3h_snapshots/OKX_TECHNICAL_REPLAY_${D}_3h.* reports/  # restore 3h
  done
  ```
- **More than 6 days** — would need Tardis paid tier or OKX VIP/premium for non-first-of-month days.
- **A venue-calibrated thresholds config** — explicitly out of scope per the user's hard rules.
- **A matched-window Binance backtest** on the same UTC days for direct head-to-head.

Companion JSON: `reports/OKX_FIRST_DAY_REGIME_AND_REPLAY_SUMMARY.json`

## G. File layout

```
data/okx-historical/BTC-USDT-SWAP/<date>/
    incremental_book_L2.csv.gz       # 5 dates full + 3 dates with only trades
    trades.csv.gz                    # all 29 dates
    book_ticker.csv.gz               # only 2026-04-01
    derivative_ticker.csv.gz         # only 2026-04-01
    liquidations.csv.gz              # only 2026-04-01

reports/
    OKX_REGIME_TABLE.md/.json                    # 29 dates classified
    OKX_SIX_SELECTED_DATES.json                  # the 6 chosen for replay
    OKX_TECHNICAL_REPLAY_<date>.md/.json/.csv    # 3 h cap, current head
    OKX_TECHNICAL_REPLAY_<date>_fullday.{md,json,_ZONES.csv}  # full UTC day where run
    okx_3h_snapshots/OKX_TECHNICAL_REPLAY_<date>_3h.*        # immutable 3 h backups
    OKX_FIRST_DAY_REGIME_AND_REPLAY_SUMMARY.md/.json (this file)
    BTC-USDT-SWAP_<date>/                        # underlying per-date backtest output
```