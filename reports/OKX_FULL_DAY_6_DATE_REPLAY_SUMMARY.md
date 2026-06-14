# OKX BTC-USDT-SWAP — 6-date **full-day** technical replay summary

**Venue:** OKX `okex-swap` BTC-USDT-SWAP (perpetual)
**Source:** Tardis CDN first-of-month free samples
**Window:** **full UTC day** (24 h of L2 + 24 h of trades for target check)
**Strategy thresholds:** Binance USDS-M Futures defaults — **UNCHANGED**
**Build time:** 2026-05-16T22:53:34Z

## HARD DISCLAIMER

  • OKX is NOT Binance.
  • Strategy thresholds are calibrated for Binance USDS-M Futures BTCUSDT-perp.
  • Numbers below are the engine's reaction to OKX microstructure with Binance-tuned thresholds left UNCHANGED.
  • **Raw `reached_raw` is NOT a winrate.** The honest headline is **`unique_move_adjusted_hit_rate`**.
  • Do NOT quote these numbers as a strategy edge or as a Binance result.
  • Purpose: cross-venue research on engine behaviour across regimes.

## A. Per-date full-day results (6 dates, 2 bullish / 2 bearish / 2 choppy)

| date       | bucket   | day Δ %  | range % | 2% feasibility | zones | triggered | reached_raw | unique moves | dup credits | LONG / SHORT | LONG reached / SHORT reached | raw hit | **unique-move hit** | dedup suppr. |
|------------|----------|---------:|--------:|:---------------:|------:|----------:|------------:|-------------:|------------:|--------------|-----------------------------:|--------:|--------------------:|-------------:|
| 2024-01-01 | bullish  |  +4.54  |   4.90 |       ✓        |   43 |        23 |          13 |            1 |          12 |  21 / 22   |                   13 / 0        |  56.52% | **           4.35%** |        15210 |
| 2025-10-01 | bullish  |  +4.00  |   4.17 |       ✓        |   41 |        24 |           4 |            1 |           3 |  21 / 20   |                    4 / 0        |  16.67% | **           4.17%** |        15287 |
| 2025-12-01 | bearish  |  -4.51  |   7.32 |       ✓        |   42 |        20 |          11 |            1 |          10 |  21 / 21   |                    0 / 11       |  55.00% | **           5.00%** |        10829 |
| 2024-10-01 | bearish  |  -3.97  |   6.27 |       ✓        |   38 |        20 |          13 |            1 |          12 |  19 / 19   |                    0 / 13       |  65.00% | **           5.00%** |        10744 |
| 2024-07-01 | choppy   |  +0.22  |   2.15 |       ✓        |   17 |         9 |           0 |            0 |           0 |   8 / 9    |                    0 / 0        |   0.00% | **           0.00%** |        15104 |
| 2026-04-01 | choppy   |  -0.24  |   2.59 |       ✓        |   30 |        21 |           1 |            1 |           0 |  17 / 13   |                    1 / 0        |   4.76% | **           4.76%** |        12987 |

## B. Status breakdown per date

| date       | RESOLVED_REACHED | RESOLVED_FAILED | INVALIDATED | NO_TRIGGER | EXPIRED |
|------------|-----------------:|----------------:|------------:|-----------:|--------:|
| 2024-01-01 |               13 |              10 |          17 |          3 |       0 |
| 2025-10-01 |                4 |              20 |          15 |          2 |       0 |
| 2025-12-01 |               11 |               9 |          20 |          2 |       0 |
| 2024-10-01 |               13 |               7 |          17 |          1 |       0 |
| 2024-07-01 |                0 |               9 |           7 |          1 |       0 |
| 2026-04-01 |                1 |              20 |           9 |          0 |       0 |

## C. Runtime

| date       | full-day wall-clock |
|------------|---------------------|
| 2024-01-01 | 63.4 min (3802s) |
| 2025-10-01 | 50.4 min (3025s) |
| 2025-12-01 | 109.7 min (6580s) |
| 2024-10-01 | 86.7 min (5202s) |
| 2024-07-01 | 59.2 min (3551s) |
| 2026-04-01 | 58.6 min (3514s) |

## D. Bucket totals

| bucket   | unique moves total | dates |
|----------|-------------------:|------:|
| bullish  |                  2 | 2024-01-01, 2025-10-01 |
| bearish  |                  2 | 2025-12-01, 2024-10-01 |
| choppy   |                  1 | 2024-07-01, 2026-04-01 |
| **total** | **5** | |

## E. Per-date notes

- **2024-01-01** (bullish, day Δ +4.54%): 13 raw reaches collapse into **1 unique move(s)** — the engine fires many same-direction zones on one sustained move; the unique-move clustering accounting fix absorbs 12 duplicate credits.
- **2025-10-01** (bullish, day Δ +4.00%): 4 raw reaches collapse into **1 unique move(s)** — the engine fires many same-direction zones on one sustained move; the unique-move clustering accounting fix absorbs 3 duplicate credits.
- **2025-12-01** (bearish, day Δ -4.51%): 11 raw reaches collapse into **1 unique move(s)** — the engine fires many same-direction zones on one sustained move; the unique-move clustering accounting fix absorbs 10 duplicate credits.
- **2024-10-01** (bearish, day Δ -3.97%): 13 raw reaches collapse into **1 unique move(s)** — the engine fires many same-direction zones on one sustained move; the unique-move clustering accounting fix absorbs 12 duplicate credits.
- **2024-07-01** (choppy, day Δ +0.22%): zero raw reaches over the full 24 h.
- **2026-04-01** (choppy, day Δ -0.24%): clean.

## F. Cross-venue interpretation

- **Unique-move-adjusted hit-rate is the honest metric.** Raw `reached_raw` over-counts because the engine — by design and by deduplication settings — emits multiple same-direction zones across a single multi-hour move. The move-clustering layer collapses those into one unique move and credits the others as duplicates.
- **2024-01-01, 2025-12-01, 2024-10-01** are good calibration anchors: each delivered a clear directional move on a wide range. The full-day shows several raw reaches on each, but always **one unique move per day**, identifying the strategy's same-direction reflex very clearly.
- **2024-07-01, 2026-04-01 (choppy)** delivered very few reaches with the Binance thresholds, consistent with regime.
- **2025-10-01 (bullish, +4 %)** still produced only 1 unique reach despite 24h-up of 4.09 % — Binance thresholds may be too conservative on this venue's bullish intraday profile, but **no thresholds were changed**: this is a calibration observation, not a strategy modification.
- The engine **does** detect plausible cross-venue zones at the expected times. The cross-venue gap is the relationship `(zones_triggered → unique_reached_moves)` not the existence of triggers.

## G. What this does NOT prove

- It does NOT prove the strategy is profitable on OKX.
- It does NOT prove it is profitable on Binance.
- 6 days is not a backtest sample.
- These thresholds were tuned elsewhere; OKX-specific calibration is a separate work item.

Companion files: `OKX_FULL_DAY_6_DATE_REPLAY_SUMMARY.json` (machine), `.csv` (flat table for sheets).