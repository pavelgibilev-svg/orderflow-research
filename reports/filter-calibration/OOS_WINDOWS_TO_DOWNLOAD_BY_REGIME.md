# OOS WINDOWS TO DOWNLOAD — BY REGIME (for frozen March filters)

Build 2026-06-10T18:12:27+00:00 · RESEARCH ONLY · do not tune filters on these.

Trend windows are true non-March OOS chosen from monthly first-of-month returns; range/vol/sweep use local
May windows for *secondary* sanity (they overlap the mining month) plus a fresh RANGE month to download.

| regime | start | end | month net% | medRange% | why | local | prio |
|---|---|---|--:|--:|---|:--:|:--:|
| TREND_UP | 2024-02-01 | 2024-02-10 | 44.81 | download_to_measure | month 2024-02 MoM 44.81% = strong TREND_UP | NO | HIGH |
| TREND_UP | 2024-11-01 | 2024-11-10 | 39.86 | download_to_measure | month 2024-11 MoM 39.86% = strong TREND_UP | NO | HIGH |
| TREND_UP | 2024-05-01 | 2024-05-10 | 16.18 | download_to_measure | month 2024-05 MoM 16.18% = strong TREND_UP | NO | HIGH |
| TREND_DOWN | 2025-11-01 | 2025-11-10 | -21.63 | download_to_measure | month 2025-11 MoM -21.63% = strong TREND_DOWN | NO | HIGH |
| TREND_DOWN | 2024-04-01 | 2024-04-10 | -16.28 | download_to_measure | month 2024-04 MoM -16.28% = strong TREND_DOWN | NO | HIGH |
| TREND_DOWN | 2026-02-01 | 2026-02-10 | -14.56 | download_to_measure | month 2026-02 MoM -14.56% = strong TREND_DOWN | NO | HIGH |
| RANGE | 2024-01-01 | 2024-01-10 | -2.56 | download_to_measure | month 2024-01 flat MoM -2.56% = RANGE OOS (fresh) | NO | MED |
| RANGE | 2024-07-01 | 2024-07-10 | 3.89 | download_to_measure | month 2024-07 flat MoM 3.89% = RANGE OOS (fresh) | NO | MED |
| HIGH_VOL | 2026-05-13 | 2026-05-15 | -1.46 | 3.26 | local non-March HIGH_VOL window (secondary sanity, May) | YES | LOW |
| HIGH_VOL | 2026-05-23 | 2026-05-23 | -1.67 | 3.77 | local non-March HIGH_VOL window (secondary sanity, May) | YES | LOW |
| REVERSAL_SWEEP | 2024-08-01 | 2024-08-01 | 1.11 | 5.25 | local non-March REVERSAL_SWEEP window (secondary sanity, May) | YES | LOW |

## Download priority (true OOS first)
1. **TREND_DOWN**: 2024-04, 2025-11, 2026-02
2. **TREND_UP**: 2024-02, 2024-05, 2024-11
3. **RANGE (fresh)**: 2024-01, 2024-07
4. HIGH_VOL/SWEEP/LOW_VOL: validate on local May first; download a dedicated month only if filters survive trend OOS.

## Minimum data per window
- OKX L2 (book deltas + snapshots) + trades.csv.gz for each UTC day, >=5 contiguous days.
- For cross-venue: add Binance recorder L2 same days (only local overlap is 2026-05-21..30).
- No Tardis.