# OKX direct quality replay - 2026-03-02 (converted Tardis-compat files)

**Build:** 2026-05-20T00:20:17+00:00
**Files audited (the bytes the engine consumes):**
  - `incremental_book_L2.csv.gz`  size=1,031,643,566 B
  - `trades.csv.gz`  size=48,011,574 B

## A. L2 reconstruction

- exploded rows: **173,447,649**, distinct events: **7,415,631**
- snapshots: **96**  updates: **7,415,535**
- first event ts UTC: 2026-03-02T00:00:00.002+00:00
- last event ts UTC: 2026-03-02T23:59:59.995+00:00
- coverage: **86,399.993 s**  (100.000% of 86,400 s)
- crossed-book events: **0**  (0.000000%)
- empty-book events: **0**  (0.000000%)
- depth high-water mark: bids=400, asks=400
- ts duplicate events: 0
- ts backward events: 0
- ts gap > 2 s events: 0

## B. Trades

- rows: **7,068,119**  bad: 0
- first trade UTC: 2026-03-02T00:00:00.439+00:00
- last trade UTC: 2026-03-02T23:59:59.612+00:00
- aligned with L2 day window: **True**

## C. Flags

- SINGLE_DAY_REPLAY_OK = **YES**
- CROSSED_BOOK_SHARE_PCT = **0.000000%**
- EMPTY_BOOK_SHARE_PCT = **0.000000%**
- TRADES_ALIGNED = **YES**
- BACKTEST_FILE_READY = **YES**