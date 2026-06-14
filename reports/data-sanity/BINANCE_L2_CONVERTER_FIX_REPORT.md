# B1/B2. Binance L2 converter fix + re-convert

**Build:** 2026-06-03T16:46:22Z
Root cause: orderbook_snapshots_1s is FROZEN/STALE; the old converter seeded from it -> phantom stale levels -> crossed book.
Fix (v3): PURE-DIFF reconstruction from raw_depth_events only (snapshots ignored) + prune crossed levels (amount=0 deletes).

| date | status | rows | diffs | prune_deletes | dur s |
|---|---|---:|---:|---:|---:|
| 2026-05-21 | RECONVERTED | 124547458 | 844043 | 736363 | 1237.1 |
| 2026-05-22 | RECONVERTED | 115700501 | 847028 | 0 | 1096.6 |
| 2026-05-23 | RECONVERTED | 105828458 | 846077 | 553 | 1045.4 |
| 2026-05-24 | RECONVERTED | 116004735 | 840315 | 11478252 | 1338.5 |
| 2026-05-25 | RECONVERTED | 89660664 | 841860 | 476 | 908.4 |
| 2026-05-26 | RECONVERTED | 108145867 | 847010 | 0 | 1583.2 |
| 2026-05-27 | RECONVERTED | 107589538 | 846390 | 139896 | 1536.3 |
| 2026-05-28 | RECONVERTED | 116564437 | 846877 | 0 | 1878.2 |
| 2026-05-29 | RECONVERTED | 104031449 | 846979 | 0 | 1425.2 |
| 2026-05-30 | RECONVERTED | 64413647 | 847013 | 0 | 999.8 |