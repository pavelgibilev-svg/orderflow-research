# OKX direct quality replay - 2026-03-14 (first available March day)

**Build:** 2026-05-19T13:48:57+00:00
**Source:** OKX direct Historical Market Data (NOT Tardis)
**Venue:** okx-swap  **Symbol:** BTC-USDT-SWAP  **Depth:** 400

## A. Reconstruction summary

- total events processed: **5,241,115**  (snapshots=96, updates=5,241,019)
- first ts (UTC): 2026-03-14T00:00:00.007+00:00
- last ts (UTC): 2026-03-14T23:59:59.943+00:00
- coverage: **86,399.936 s**  (100.000% of 86,400 s expected)

## B. Book integrity

- crossed-book events (best_bid >= best_ask): **0**  (0.000000%)
- empty-book events (no bids OR no asks): **0**  (0.000000%)
- depth high-water mark: bids=400, asks=400
- snapshot ordering checks: 0 failures over 96 snapshot anchors

## C. Timestamp integrity

- duplicate-ts events: 0
- backward-ts events: 0
- ts gap > 2 s: 0

## D. 1 s snapshots

- 1 s snapshot rows produced: **86,400**  (86,400 expected for a full UTC day)

## E. Trade alignment

- Supplied trade file is Asia-month April = UTC 2026-03-31T16:00 onward; no trade rows exist for 2026-03-14.
- trade-alignment check: SKIPPED (no trade data for 2026-03-14)

## F. Flags

- SINGLE_DAY_REPLAY_OK = **YES (book-only)**
- CROSSED_BOOK_SHARE_PCT = **0.000000%**
- EMPTY_BOOK_SHARE_PCT = **0.000000%**
- TRADES_ALIGNED = **NO (no trade data for this date)**
- BACKTEST_FILE_READY = **NO (trades missing - converter cannot emit trades.jsonl for this day)**

## G. Verdict

Order-book reconstruction PASSES on 2026-03-14: full UTC-day coverage, no crossed
or empty books, snapshot anchors well-ordered, no large ts gaps, no backward ts.
However, the strategy engine consumes `raw_depth_events + trades` together; without
March-period trades, BACKTEST_FILE_READY = NO and we do NOT proceed to stage E/F/G.