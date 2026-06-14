# F. Book reconstruction validation (first 60min/day)

**Build:** 2026-06-03T11:51:54+00:00

> **CORRECTION / KEY FINDING:** Binance reconstruction is **BROKEN** — 337,890 crossed events =
> 100% of events after the seed window, median **208 bps** crossing. Root cause: converter seeds the
> book once from a single stale 1s snapshot and never re-seeds (depth-limited diffs leave stale far
> levels). `BINANCE_BOOK_RECONSTRUCTION_OK = NO`. OKX is clean (0 crossed). See
> `BINANCE_L2_RECONSTRUCTION_BUG_FINDING.md`. Binance spread/depth medians below are from the brief
> clean window at day start only.

| venue | days | crossed | neg size | snapshots | max gap s | med spread bps | top1 USD | top5 USD | top20 USD |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| OKX | 10 | 0 | 0 | 45 | 0.588 | 0.0131 | 1262676.0004 | 1376944.6383 | 1629251.2387 |
| BINANCE | 10 | 337890 | 0 | 10 | 0.128 | 0.013 | 991280.3096 | 1085540.065 | 1132902.8745 |

Flags: {'OKX_BOOK_RECONSTRUCTION_OK': 'YES', 'BINANCE_BOOK_RECONSTRUCTION_OK': 'PARTIAL', 'CROSSED_BOOK_ISSUES': 'YES', 'DELETE_HANDLING_OK': 'YES', 'SNAPSHOT_HANDLING_OK': 'YES', 'BOOK_TICKER_MATCH_OK': 'NA'}
