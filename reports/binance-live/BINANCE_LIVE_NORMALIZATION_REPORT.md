# Binance live-recorder normalization report

**Build:** 2026-05-21T16:57:27+00:00
**Cutover for 2026-05-18 merge:** `event_time >= 1779120815858` (= 2026-05-18T16:13:35.858+00:00) goes to part2; everything earlier stays from part1.

## Per-day normalization

### 2026-05-17  (single part1)

| stream | first ts UTC | last ts UTC | rows | source split (p1/p2) |
|---|---|---|---:|---|
| `raw_depth_events.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part1\2026-05-17\raw_depth_events.jsonl |
| `trades.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part1\2026-05-17\trades.jsonl |
| `book_ticker.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part1\2026-05-17\book_ticker.jsonl |
| `mark_price.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part1\2026-05-17\mark_price.jsonl |
| `orderbook_snapshots_1s.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part1\2026-05-17\orderbook_snapshots_1s.jsonl |
| `health.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part1\2026-05-17\health.jsonl |

### 2026-05-18  (merged from part1 + part2 by cutover)

| stream | first ts UTC | last ts UTC | rows | source split (p1/p2) |
|---|---|---|---:|---|
| `raw_depth_events.jsonl` | 2026-05-18T00:00:00.292+00:00 | 2026-05-19T00:00:00.234+00:00 | 846130 | 571781/274349 |
| `trades.jsonl` | 2026-05-18T00:00:00.298+00:00 | 2026-05-19T00:00:00.219+00:00 | 4311454 | 3188468/1122986 |
| `book_ticker.jsonl` | 2026-05-18T00:00:00.270+00:00 | 2026-05-19T00:00:00.297+00:00 | 34997258 | 24704968/10292290 |
| `mark_price.jsonl` | 2026-05-18T00:00:00.000+00:00 | 2026-05-18T23:59:59.000+00:00 | 85842 | 58027/27815 |
| `liquidations.jsonl` | 2026-05-18T16:19:33.101+00:00 | 2026-05-18T23:54:09.702+00:00 | 271 | 0/271 |
| `orderbook_snapshots_1s.jsonl` | 2026-05-18T00:00:01.149+00:00 | 2026-05-18T23:59:59.789+00:00 | 85843 | 58027/27816 |
| `health.jsonl` | 2026-05-18T00:00:09.863+00:00 | 2026-05-18T23:59:58.836+00:00 | 10911 | 6936/3975 |

### 2026-05-19  (single part2)

| stream | first ts UTC | last ts UTC | rows | source split (p1/p2) |
|---|---|---|---:|---|
| `raw_depth_events.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-19\raw_depth_events.jsonl |
| `trades.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-19\trades.jsonl |
| `book_ticker.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-19\book_ticker.jsonl |
| `mark_price.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-19\mark_price.jsonl |
| `liquidations.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-19\liquidations.jsonl |
| `orderbook_snapshots_1s.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-19\orderbook_snapshots_1s.jsonl |
| `health.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-19\health.jsonl |

### 2026-05-20  (single part2)

| stream | first ts UTC | last ts UTC | rows | source split (p1/p2) |
|---|---|---|---:|---|
| `raw_depth_events.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-20\raw_depth_events.jsonl |
| `trades.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-20\trades.jsonl |
| `book_ticker.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-20\book_ticker.jsonl |
| `mark_price.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-20\mark_price.jsonl |
| `liquidations.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-20\liquidations.jsonl |
| `orderbook_snapshots_1s.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-20\orderbook_snapshots_1s.jsonl |
| `health.jsonl` | (copy) | (copy) | — | C:\Users\gibilev\orderflow-research\data\binance-live-archives\staging\part2\2026-05-20\health.jsonl |
