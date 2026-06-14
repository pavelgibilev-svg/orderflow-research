# NEXT WINDOWS TO DOWNLOAD (data-driven from daily OHLCV)

**Build:** 2026-06-10T17:23:39+00:00
Provenance: NO daily CSV at C:\Users\gibilev\orderflow-research\data\daily\BTC_USDT_1d.csv -> wrote schema template C:\Users\gibilev\orderflow-research\data\daily\BTC_USDT_1d.SCHEMA.csv and built a SPARSE daily series from local trades (85 days; mostly first-of-month snapshots + contiguous 2026-03 & 2026-05).

## Top 20 windows overall
| # | regime | start | end | days | score | net% span | med range% | have? | venue |
|--:|---|---|---|--:|--:|--:|--:|:--:|---|
| 1 | TREND_UP | 2026-03-04 | 2026-03-04 | 1 | 20.77 | 6.37 | 9.77 | yes | OKX L2+trades |
| 2 | TREND_UP | 2026-03-10 | 2026-03-16 | 6 | 12.14 | 9.44 | 3.35 | yes | OKX L2+trades |
| 3 | TREND_DOWN | 2026-03-27 | 2026-03-30 | 4 | 11.94 | -2.96 | 3.49 | yes | OKX L2+trades |
| 4 | TREND_DOWN | 2026-03-19 | 2026-03-23 | 4 | 11.42 | -0.49 | 3.81 | yes | OKX L2+trades |
| 5 | TREND_DOWN | 2026-03-07 | 2026-03-08 | 2 | 11.26 | -3.14 | 3.15 | yes | OKX L2+trades |
| 6 | TREND_DOWN | 2026-05-28 | 2026-05-29 | 2 | 9.84 | -2.04 | 3.06 | yes | both |
| 7 | HIGH_VOL | 2026-03-23 | 2026-03-23 | 1 | 9.7 | 4.47 | 6.43 | yes | OKX L2+trades |
| 8 | TREND_DOWN | 2026-05-17 | 2026-05-18 | 2 | 9.44 | -2.32 | 2.13 | yes | OKX L2+trades |
| 9 | TREND_DOWN | 2026-05-13 | 2026-05-13 | 1 | 8.59 | -1.85 | 3.18 | yes | OKX L2+trades |
| 10 | HIGH_VOL | 2026-03-18 | 2026-03-18 | 1 | 8.49 | -3.6 | 5.67 | yes | OKX L2+trades |
| 11 | REVERSAL_SWEEP | 2024-08-01 | 2024-08-01 | 1 | 8.3 | 1.11 | 5.25 | yes | OKX L2+trades |
| 12 | TREND_UP | 2026-03-25 | 2026-03-25 | 1 | 8.0 | 1.11 | 2.31 | yes | OKX L2+trades |
| 13 | REVERSAL_SWEEP | 2026-03-10 | 2026-03-13 | 3 | 7.74 | 3.67 | 4.98 | yes | OKX L2+trades |
| 14 | HIGH_VOL | 2026-03-26 | 2026-03-27 | 2 | 7.4 | -6.93 | 4.97 | yes | OKX L2+trades |
| 15 | TREND_UP | 2026-05-06 | 2026-05-06 | 1 | 6.98 | 0.21 | 2.63 | yes | OKX L2+trades |
| 16 | REVERSAL_SWEEP | 2026-03-01 | 2026-03-03 | 2 | 6.96 | 2.03 | 4.68 | yes | OKX L2+trades |
| 17 | HIGH_VOL | 2026-05-13 | 2026-05-15 | 3 | 6.18 | -1.46 | 3.26 | yes | OKX L2+trades |
| 18 | HIGH_VOL | 2026-05-23 | 2026-05-23 | 1 | 6.11 | -1.67 | 3.77 | yes | both |
| 19 | REVERSAL_SWEEP | 2026-03-24 | 2026-03-24 | 1 | 5.9 | -0.48 | 3.54 | yes | OKX L2+trades |
| 20 | REVERSAL_SWEEP | 2026-03-29 | 2026-04-01 | 3 | 5.81 | 2.62 | 3.29 | yes | OKX L2+trades |

## Top 5 per regime
### TREND_UP
- 2026-03-04..2026-03-04 (1d) score 20.77 · net 6.37% · medRange 9.77% · calibrate trend-continuation longs / TU module (missing in 05-03..20) · HAVE
- 2026-03-10..2026-03-16 (6d) score 12.14 · net 9.44% · medRange 3.35% · calibrate trend-continuation longs / TU module (missing in 05-03..20) · HAVE
- 2026-03-25..2026-03-25 (1d) score 8.0 · net 1.11% · medRange 2.31% · calibrate trend-continuation longs / TU module (missing in 05-03..20) · HAVE
- 2026-05-06..2026-05-06 (1d) score 6.98 · net 0.21% · medRange 2.63% · calibrate trend-continuation longs / TU module (missing in 05-03..20) · HAVE
- 2026-04-01..2026-04-01 (1d) score 4.0 · net -0.24% · medRange 2.59% · calibrate trend-continuation longs / TU module (missing in 05-03..20) · HAVE
### TREND_DOWN
- 2026-03-27..2026-03-30 (4d) score 11.94 · net -2.96% · medRange 3.49% · validate TD-short module out-of-sample · HAVE
- 2026-03-19..2026-03-23 (4d) score 11.42 · net -0.49% · medRange 3.81% · validate TD-short module out-of-sample · HAVE
- 2026-03-07..2026-03-08 (2d) score 11.26 · net -3.14% · medRange 3.15% · validate TD-short module out-of-sample · HAVE
- 2026-05-28..2026-05-29 (2d) score 9.84 · net -2.04% · medRange 3.06% · validate TD-short module out-of-sample · HAVE
- 2026-05-17..2026-05-18 (2d) score 9.44 · net -2.32% · medRange 2.13% · validate TD-short module out-of-sample · HAVE
### RANGE
- 2026-03-08..2026-03-09 (2d) score 5.33 · net 1.73% · medRange 4.79% · range-fade edge+reclaim positives (already have May; need variety) · HAVE
- 2026-03-18..2026-03-19 (2d) score 4.64 · net -5.4% · medRange 4.82% · range-fade edge+reclaim positives (already have May; need variety) · HAVE
- 2026-03-26..2026-03-26 (1d) score 3.58 · net -3.52% · medRange 4.63% · range-fade edge+reclaim positives (already have May; need variety) · HAVE
- 2026-05-14..2026-05-15 (2d) score 3.24 · net 0.4% · medRange 3.73% · range-fade edge+reclaim positives (already have May; need variety) · HAVE
### HIGH_VOL
- 2026-03-23..2026-03-23 (1d) score 9.7 · net 4.47% · medRange 6.43% · stress strong-move separation; most 2%+ opportunities · HAVE
- 2026-03-18..2026-03-18 (1d) score 8.49 · net -3.6% · medRange 5.67% · stress strong-move separation; most 2%+ opportunities · HAVE
- 2026-03-26..2026-03-27 (2d) score 7.4 · net -6.93% · medRange 4.97% · stress strong-move separation; most 2%+ opportunities · HAVE
- 2026-05-13..2026-05-15 (3d) score 6.18 · net -1.46% · medRange 3.26% · stress strong-move separation; most 2%+ opportunities · HAVE
- 2026-05-23..2026-05-23 (1d) score 6.11 · net -1.67% · medRange 3.77% · stress strong-move separation; most 2%+ opportunities · HAVE
### LOW_VOL
- 2024-06-01..2024-06-01 (1d) score -0.2 · net 0.31% · medRange 0.7% · no-trade / false-positive control set · HAVE
- 2026-05-09..2026-05-10 (2d) score -0.21 · net 1.57% · medRange 1.21% · no-trade / false-positive control set · HAVE
- 2026-05-17..2026-05-19 (2d) score -0.4 · net -2.18% · medRange 1.4% · no-trade / false-positive control set · HAVE
- 2025-11-01..2025-11-01 (1d) score -0.57 · net 0.46% · medRange 1.07% · no-trade / false-positive control set · HAVE
- 2026-03-14..2026-03-14 (1d) score -0.95 · net 0.39% · medRange 1.45% · no-trade / false-positive control set · HAVE
### REVERSAL_SWEEP
- 2024-08-01..2024-08-01 (1d) score 8.3 · net 1.11% · medRange 5.25% · sweep-reversal + false-breakout reclaim setups · HAVE
- 2026-03-10..2026-03-13 (3d) score 7.74 · net 3.67% · medRange 4.98% · sweep-reversal + false-breakout reclaim setups · HAVE
- 2026-03-01..2026-03-03 (2d) score 6.96 · net 2.03% · medRange 4.68% · sweep-reversal + false-breakout reclaim setups · HAVE
- 2026-03-24..2026-03-24 (1d) score 5.9 · net -0.48% · medRange 3.54% · sweep-reversal + false-breakout reclaim setups · HAVE
- 2026-03-29..2026-04-01 (3d) score 5.81 · net 2.62% · medRange 3.29% · sweep-reversal + false-breakout reclaim setups · HAVE
### BREAKOUT
- 2026-05-28..2026-05-28 (1d) score 4.2 · net -3.19% · medRange 3.76% · breakout-continuation / retest setups · HAVE
- 2026-05-23..2026-05-23 (1d) score 3.24 · net -1.67% · medRange 3.77% · breakout-continuation / retest setups · HAVE
- 2026-05-13..2026-05-13 (1d) score 2.94 · net -1.85% · medRange 3.18% · breakout-continuation / retest setups · HAVE
- 2026-05-16..2026-05-18 (2d) score 2.87 · net -3.45% · medRange 2.78% · breakout-continuation / retest setups · HAVE

## Month-level regime (from first-of-month snapshots, for picking months to fully download)
| month start | month end | MoM ret% | regime |
|---|---|--:|---|
| 2024-01-01 | 2024-02-01 | -2.56 | RANGE |
| 2024-02-01 | 2024-03-01 | 44.81 | TREND_UP |
| 2024-03-01 | 2024-04-01 | 11.68 | TREND_UP |
| 2024-04-01 | 2024-05-01 | -16.28 | TREND_DOWN |
| 2024-05-01 | 2024-06-01 | 16.18 | TREND_UP |
| 2024-06-01 | 2024-07-01 | -7.18 | TREND_DOWN |
| 2024-07-01 | 2024-08-01 | 3.89 | RANGE |
| 2024-08-01 | 2024-09-01 | -12.34 | TREND_DOWN |
| 2024-09-01 | 2024-10-01 | 6.15 | TREND_UP |
| 2024-10-01 | 2024-11-01 | 14.28 | TREND_UP |
| 2024-11-01 | 2024-12-01 | 39.86 | TREND_UP |
| 2024-12-01 | 2025-01-01 | -2.67 | RANGE |
| 2025-01-01 | 2025-02-01 | 6.38 | TREND_UP |
| 2025-02-01 | 2025-03-01 | -14.49 | TREND_DOWN |
| 2025-03-01 | 2025-04-01 | -1.04 | RANGE |
| 2025-04-01 | 2025-05-01 | 13.25 | TREND_UP |
| 2025-05-01 | 2025-06-01 | 9.48 | TREND_UP |
| 2025-06-01 | 2025-07-01 | 0.06 | RANGE |
| 2025-07-01 | 2025-08-01 | 7.2 | TREND_UP |
| 2025-08-01 | 2025-09-01 | -3.59 | RANGE |
| 2025-09-01 | 2025-10-01 | 8.59 | TREND_UP |
| 2025-10-01 | 2025-11-01 | -7.18 | TREND_DOWN |
| 2025-11-01 | 2025-12-01 | -21.63 | TREND_DOWN |
| 2025-12-01 | 2026-01-01 | 2.97 | RANGE |
| 2026-01-01 | 2026-02-01 | -13.35 | TREND_DOWN |
| 2026-02-01 | 2026-03-01 | -14.56 | TREND_DOWN |
| 2026-03-01 | 2026-04-01 | 3.56 | RANGE |
| 2026-04-01 | 2026-05-01 | 14.86 | TREND_UP |

## Minimum data requirements
- **per_window**: OKX L2 (book deltas + 3h/full-day snapshots) + trades.csv.gz for each UTC day in the window
- **cross_venue**: for OKX+Binance comparison also capture Binance recorder L2 for the same UTC days (only overlap we have is 2026-05-21..30)
- **minimum_window_length**: >=5 contiguous days per regime so 3d/7d context and >=3-5 unique strong moves can form
- **no_tardis**: use OKX-open / Binance-recorder captures only; Tardis excluded by policy