# A. Binance 10d — SELECTED vs SKIPPED audit

**Build:** 2026-06-02T14:02:11+00:00  ·  DIAGNOSTIC, no tuning

| date | conf | traded | 2%win | sel dir | sel label | sel pnl | sel score | skipped 2%win | SHORT 2%win | SHORT-winner while sel-LONG-lost |
|---|--:|--:|--:|:--:|:--:|--:|--:|--:|--:|:--:|
| 2026-05-21 | 24 | 24 | 1 | SHORT | MID | 0.371 | 1.335 | 1 | 1 |  |
| 2026-05-22 | 23 | 23 | 11 | SHORT | GOOD | 1.86 | 0.72 | 10 | 11 |  |
| 2026-05-23 | 19 | 19 | 11 | LONG | NOISE | -1.64 | 0.694 | 11 | 0 |  |
| 2026-05-24 | 7 | 7 | 0 | SHORT | NOISE | -0.76 | 0.378 | 0 | 0 |  |
| 2026-05-25 | 7 | 7 | 0 | SHORT | MID | 0.6451 | 0.7 | 0 | 0 |  |
| 2026-05-26 | 22 | 22 | 5 | LONG | NOISE | -1.64 | 0.734 | 5 | 4 | YES |
| 2026-05-27 | 15 | 15 | 0 | LONG | NOISE | -1.64 | 0.723 | 0 | 0 |  |
| 2026-05-28 | 14 | 14 | 0 | LONG | NOISE | -1.64 | 0.688 | 0 | 0 |  |
| 2026-05-29 | 15 | 15 | 3 | LONG | NOISE | -1.64 | 0.717 | 3 | 0 |  |
| 2026-05-30 | 7 | 7 | 0 | LONG | MID | 0.2627 | 0.75 | 0 | 0 |  |

- total confirmed: 153; total 2% winners: 31; total skipped 2% winners: 30
- days where a SHORT 2%-winner existed but RS1 took a losing LONG: **['2026-05-26']**