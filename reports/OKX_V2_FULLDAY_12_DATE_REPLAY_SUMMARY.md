# OKX full-day 24-date combined summary (calibration + OOS_v1 + v2)

**Build time:** 2026-05-18T11:04:02Z
**Venue:** OKX `okex-swap` BTC-USDT-SWAP
**v2 dates completed:** 12 / 12
**v2 dates missing:** (none)

## HARD DISCLAIMER

  • Strategy thresholds: Binance USDS-M Futures defaults — UNCHANGED.
  • `zone_score_v1` is ARCHIVED as a failed OOS hypothesis (see `ZONE_SCORE_V1_FINAL_VERDICT.md`). Not used here.
  • `zone_score_v2` is NOT built. This round is data-collection / labelling only.
  • Headline metric: **`unique_reached_moves`**, NOT raw reached zones.
  • No winrate / profitability claim is made.
  • OKX is NOT Binance.

## A. Aggregates per round

| round | n dates | zones | triggered | reached_raw | **unique moves** | LONG reached | SHORT reached | dup credits | dedup suppr. | wall-clock (h) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| calibration | 6 | 211 | 117 | 42 | **5** | 18 | 24 | 37 | 80161 | 7.13 |
| oos_v1 | 6 | 191 | 116 | 39 | **7** | 24 | 15 | 32 | 80787 | 7.10 |
| v2 | 12 | 382 | 236 | 54 | **9** | 20 | 34 | 45 | 156838 | 18.27 |
| all_24 | 24 | 784 | 469 | 135 | **21** | 62 | 73 | 114 | 317786 | 32.50 |

## B. Per-date table

| date | round | regime | day Δ % | 2%-feas | zones | triggered | reached_raw | unique | LONG/SHORT | LONG reached / SHORT reached | raw hit | uniq-move hit | runtime (min) |
|------|-------|--------|--------:|:-------:|------:|----------:|------------:|-------:|------------|-----------------------------:|--------:|--------------:|--------------:|
| 2024-01-01 | calibration | bullish |   4.54 |   yes  |    43 |        23 |          13 | **1** |  21/22   |                   13 / 0        |  56.52% |         4.35% |          63.4 |
| 2025-10-01 | calibration | bullish |   4.00 |   yes  |    41 |        24 |           4 | **1** |  21/20   |                    4 / 0        |  16.67% |         4.17% |          50.4 |
| 2025-12-01 | calibration | bearish |  -4.51 |   yes  |    42 |        20 |          11 | **1** |  21/21   |                    0 / 11       |  55.00% |         5.00% |         109.7 |
| 2024-10-01 | calibration | bearish |  -3.97 |   yes  |    38 |        20 |          13 | **1** |  19/19   |                    0 / 13       |  65.00% |         5.00% |          86.7 |
| 2024-07-01 | calibration | choppy  |   0.22 |   yes  |    17 |         9 |           0 | **0** |   8/9    |                    0 / 0        |   0.00% |         0.00% |          59.2 |
| 2026-04-01 | calibration | choppy  |  -0.24 |   yes  |    30 |        21 |           1 | **1** |  17/13   |                    1 / 0        |   4.76% |         4.76% |          58.6 |
| 2025-04-01 | oos_v1 | bullish |   3.16 |   yes  |    41 |        26 |          10 | **2** |  24/17   |                    9 / 1        |  38.46% |         7.69% |          97.2 |
| 2025-05-01 | oos_v1 | bullish |   2.48 |   yes  |    44 |        28 |           8 | **1** |  25/19   |                    8 / 0        |  28.57% |         3.57% |          68.9 |
| 2024-05-01 | oos_v1 | bearish |  -3.88 |   yes  |    42 |        25 |          14 | **3** |  23/19   |                    7 / 7        |  56.00% |        12.00% |         144.7 |
| 2024-09-01 | oos_v1 | bearish |  -2.86 |   yes  |    42 |        20 |           7 | **1** |  25/17   |                    0 / 7        |  35.00% |         5.00% |          59.6 |
| 2024-06-01 | oos_v1 | choppy  |   0.31 |   no   |     9 |         8 |           0 | **0** |   4/5    |                    0 / 0        |   0.00% |         0.00% |          26.7 |
| 2025-11-01 | oos_v1 | choppy  |   0.46 |   no   |    13 |         9 |           0 | **0** |   7/6    |                    0 / 0        |   0.00% |         0.00% |          28.9 |
| 2026-05-01 | v2 | bullish |   2.47 |   yes  |    28 |        15 |           4 | **1** |  15/13   |                    4 / 0        |  26.67% |         6.67% |          41.1 |
| 2025-03-01 | v2 | bullish |   2.02 |   yes  |    32 |        19 |           2 | **1** |  17/15   |                    2 / 0        |  10.53% |         5.26% |         106.1 |
| 2024-03-01 | v2 | bullish |   1.99 |   yes  |    32 |        23 |           8 | **1** |  21/11   |                    8 / 0        |  34.78% |         4.35% |         122.4 |
| 2026-01-01 | v2 | bullish |   1.38 |   no   |    18 |        11 |           0 | **0** |  10/8    |                    0 / 0        |   0.00% |         0.00% |          23.8 |
| 2024-02-01 | v2 | bullish |   1.20 |   yes  |    36 |        25 |           6 | **1** |  19/17   |                    6 / 0        |  24.00% |         4.00% |         100.5 |
| 2024-04-01 | v2 | bearish |  -2.32 |   yes  |    38 |        22 |          14 | **1** |  14/24   |                    0 / 14       |  63.64% |         4.55% |         103.5 |
| 2026-02-01 | v2 | bearish |  -2.23 |   yes  |    28 |        17 |           7 | **1** |  14/14   |                    0 / 7        |  41.18% |         5.88% |         112.5 |
| 2025-08-01 | v2 | bearish |  -2.12 |   yes  |    35 |        19 |           3 | **1** |  15/20   |                    0 / 3        |  15.79% |         5.26% |         122.6 |
| 2026-03-01 | v2 | bearish |  -1.79 |   yes  |    43 |        26 |           7 | **1** |  19/24   |                    0 / 7        |  26.92% |         3.85% |          93.7 |
| 2025-02-01 | v2 | bearish |  -1.76 |   yes  |    34 |        20 |           3 | **1** |  18/16   |                    0 / 3        |  15.00% |         5.00% |          69.1 |
| 2024-12-01 | v2 | choppy  |   0.80 |   yes  |    27 |        16 |           0 | **0** |  11/16   |                    0 / 0        |   0.00% |         0.00% |          76.5 |
| 2025-09-01 | v2 | choppy  |   0.91 |   yes  |    31 |        23 |           0 | **0** |  10/21   |                    0 / 0        |   0.00% |         0.00% |         124.2 |

## C. Unique-move yield, per round

Why this matters: `unique_reached_moves` is the *positive class* a future v2 calibration will fit on. n=positives is the binding constraint for any held-out validation. Below is what we have accumulated so far.

| round | n dates | unique moves | unique-moves / date |
|---|---:|---:|---:|
| calibration | 6 | 5 | 0.83 |
| oos_v1 | 6 | 7 | 1.17 |
| v2 | 12 | 9 | 0.75 |
| all_24 | 24 | 21 | 0.88 |

## D. What this round does NOT do

- Does NOT build zone_score_v2 (model fitting is a separate task).
- Does NOT filter zones (no score is consulted at entry time).
- Does NOT change strategy thresholds or move weights.
- Does NOT use zone_score_v1 (archived).
- Does NOT claim profitability.

## E. Files

- `reports/OKX_V2_TECHNICAL_REPLAY_<date>_fullday.{md,json,_ZONES.csv}` — 12 per-date triplets.
- `reports/OKX_V2_FULLDAY_CHAIN_RESULTS.json` — chain manifest with per-date exit codes + runtimes.
- `reports/OKX_V2_FULLDAY_12_DATE_REPLAY_SUMMARY.{md,json,csv}` — this combined summary.
- `reports/BTC-USDT-SWAP_<date>/` — per-date underlying backtest output (zones.json, daily_summary.csv, etc.).
