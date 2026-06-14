# OKX direct Historical Market Data - March 2026 - final audit + flag matrix

**Build:** 2026-05-19
**Source:** OKX direct Historical Market Data (NOT Tardis)
**Venue:** okx-swap  **Symbol:** BTC-USDT-SWAP  **Depth:** 400
**Strategy / thresholds / engine:** UNCHANGED.
**zone_score_v1 / v2:** not used as filter, not integrated.

## A. What was supplied

| kind | files | scope |
|---|---|---|
| order book (`L2orderbook-400lv`, tar.gz, line-delimited JSON) | 4 | UTC days 2026-03-14, 03-27, 03-28, 03-31 |
| trade history (`trades-2026-04.zip`, single CSV) | 1 | UTC 2026-03-31T16:00:00 to 2026-04-30T15:59:59 (= Asia-month April, UTC+8 bucketed) |
| trade history for March (Asia or UTC) | **0** | none supplied |

Companion details: `OKX_DIRECT_MARCH_2026_INVENTORY.md/.json`.

## B. Order book schema verdict (cleanly determined)

| flag | value |
|---|---|
| `OKX_DIRECT_ORDERBOOK_READABLE` | **YES** |
| `OKX_DIRECT_ORDERBOOK_IS_L2` | **YES** |
| `OKX_DIRECT_ORDERBOOK_TYPE` | **BOTH** (snapshot anchor + incremental deltas in same line-delimited JSON stream) |
| `OKX_DIRECT_ORDERBOOK_CAN_RECONSTRUCT` | **YES** |
| `OKX_DIRECT_ORDERBOOK_DEPTH` | **400** |
| `SCHEMA_MATCHES_TARDIS_OKX` | **PARTIAL** (same upstream `books-l2-tbt` channel; OKX direct tuple is `[price,size,ordersCount]` 3-elements, Tardis tuple is `[price,size,deprecated,ordersCount]` 4-elements; OKX direct has no `local_timestamp` / `exchange` envelope columns; conversion is mechanical) |

Companion details: `OKX_DIRECT_MARCH_2026_ORDERBOOK_SCHEMA_AUDIT.md/.json`.

## C. Single-day quality replay (book-only, 2026-03-14)

- 5,241,115 events processed, full UTC-day coverage 86,399.936 s
- crossed-book share: **0.000000%**
- empty-book share: **0.000000%**
- snapshot ordering failures: **0** over 96 snapshot anchors (one every 15 min)
- duplicate-ts events: **0**, backward-ts events: **0**, gap-greater-than-2s events: **0**
- depth high-water mark: 400 bids / 400 asks
- 1 s snapshots produced: **86,400 / 86,400**

Result: order book reconstruction is **clean**. The data is research-grade.

Companion details: `OKX_DIRECT_2026-03-14_QUALITY_REPLAY.md/.json`.

## D. Trades audit verdict

| flag | value |
|---|---|
| `OKX_DIRECT_TRADES_READABLE` | **YES** (single 5.6 GB CSV inside zip, schema clean) |
| `OKX_DIRECT_TRADES_COVER_FULL_MARCH` | **NO** (covers UTC 2026-03-31T16:00 -> 2026-04-30T15:59) |
| `OKX_DIRECT_TRADES_USABLE_FOR_FLOW` | **YES** (schema-wise; `side` = taker side; `created_time` is ms UTC) |
| `TRADES_SCHEMA_MATCHES_TARDIS_OKX` | **PARTIAL** (column renames only: `instrument_name->symbol`, `trade_id->id`, `size->amount`, `created_time->timestamp`; no `exchange`/`local_timestamp` columns) |

Critical UTC nuance: the file is labelled `trades-2026-04` but its true UTC span is
**2026-03-31T16:00:00 -> 2026-04-30T15:59:59** — OKX UI buckets monthly trade history
by China local time (UTC+8). That gives us **8 h of trade overlap** with our
2026-03-31 order-book day, and **zero overlap** with 03-14 / 03-27 / 03-28. None of
our four March order-book days has full-day trade coverage.

Companion details: `OKX_DIRECT_MARCH_2026_TRADES_AUDIT.md/.json`.

## E. Why conversion + backtest were NOT executed

The user's spec explicitly says:

> Если trades нет или они не читаются:
> - НЕ делать полноценный strategy backtest;
> - можно сделать только parser/orderbook replay;
> - явно написать `FULL_STRATEGY_BACKTEST_READY = NO`.

and:

> Если один день не проходит — НЕ запускать весь март.

Our state is: order book is perfect, but NO single UTC day in our March 2026 set has
a full 24 h of paired trades. The strategy engine consumes
`raw_depth_events + trades` together (taker-side flow is a primary signal in the
`zoneDetector` confirm/trigger logic); without trades, the converter can emit
`raw_depth_events.jsonl` and `orderbook_snapshots_1s.jsonl` but `trades.jsonl` would
be empty, which fails the engine's preflight check. So:

- E. Conversion to file-recording layout: **SKIPPED** (would emit empty `trades.jsonl`)
- F. Strategy backtest per day: **SKIPPED**
- G. March summary: **SKIPPED**

We did NOT change the strategy or thresholds to "tolerate missing trades" — that
would be a parameter change in violation of the hard rules.

## F. Costs / profitability sanity

Cannot be computed without a backtest output (no entry/target/stop rows produced).

`PROFITABILITY_BACKTEST_READY = NO`
reason: no execution/stop model output exists for March 2026 (backtest was not run).

## G. Final flag matrix (strict)

```
OKX_DIRECT_FILES_READABLE              = YES
OKX_DIRECT_COVERS_FULL_MARCH           = NO  (4 / 31 order-book days supplied;
                                              0 March-bucketed trade files;
                                              specific gaps: 03-01..03-13, 03-15..03-26,
                                              03-29, 03-30)
OKX_DIRECT_ORDERBOOK_USABLE            = YES (for the 4 days supplied)
OKX_DIRECT_TRADES_AVAILABLE            = NO   (only Asia-April trade bucket supplied,
                                              which covers UTC 2026-03-31T16:00 onward;
                                              no overlap with 03-14/03-27/03-28; only
                                              8 h overlap on 03-31)
OKX_DIRECT_SCHEMA_MATCHES_TARDIS       = PARTIAL (same upstream channels;
                                                  trivial column/tuple-shape renames)
OKX_DIRECT_CONVERSION_DONE             = NO   (blocked by missing trades)
OKX_DIRECT_SINGLE_DAY_REPLAY_OK        = YES (book-only, 2026-03-14: 0% crossed,
                                              0% empty, full UTC-day coverage)
OKX_DIRECT_BACKTEST_RAN                = NO   (blocked by missing trades)
OKX_DIRECT_DAYS_PROCESSED              = 0    (no full strategy day processed)
OKX_DIRECT_UNIQUE_MOVES_TOTAL          = 0    (no backtest run)
OKX_DIRECT_READY_FOR_STRATEGY_RESEARCH = NO   (insufficient March coverage + missing
                                              March trades; would need Asia-March
                                              trade file + 27 more order-book days
                                              to do full March)
PROFITABILITY_BACKTEST_READY           = NO   (no execution/stop model output)
```

### Explicit blocker list (per user spec)

- **missing orderbook files** (27 of 31 March days not supplied)
- **missing trade history** (no Asia-March or UTC-March trade file supplied; the
  Asia-April file only overlaps the last 8 h of 2026-03-31 UTC)
- **trades not aligned** (no UTC day in our set has full-day order book + full-day
  trades together)

### NOT blockers

- bad archive: NO (all 5 archives open cleanly, SHAs computed, headers/first rows parse)
- duplicate days: NO
- schema unknown: NO (order book + trades schemas are fully characterised above)
- cannot reconstruct book: NO (2026-03-14 reconstructs cleanly with 0% crossed/empty)
- crossed book too high: NO (0%)
- converter failed: N/A (converter not invoked because of trade gap)
- backtest command missing: NO (`npm run backtest:file` exists in the repo)
- memory/disk issue: NO

## H. Recommended unblocks (research-only suggestions, not actions to auto-execute)

To make a full-March backtest possible without violating the hard rules:

1. Download Asia-March trade bucket from OKX (UI label `trades-2026-03`,
   actual UTC range 2026-02-28T16:00 -> 2026-03-31T16:00). This alone covers the
   first 16 h of 2026-03-31 plus all of 03-14 / 03-27 / 03-28 UTC.
2. Download the missing 27 order-book days (03-01..03-13, 03-15..03-26, 03-29, 03-30).
3. Re-run this audit and proceed to stages E/F/G with the same script set.

Alternative: pivot the study window to April 2026 — we already have full Asia-April
trades; we would need April order-book days from OKX direct.

## I. Hard rules honored

- strategy / thresholds / `zoneDetector`: UNCHANGED
- `zone_score_v1`: not used as filter (still archived per
  `reports/ZONE_SCORE_V1_FINAL_VERDICT.md`)
- `zone_score_v2`: not built, not integrated (per
  `reports/OKX_ZONE_SCORE_V2_RESEARCH_ANALYSIS.md`)
- no production model fitted
- no profitability claim
- venue label `okx-swap` carried in every metadata field; OKX and Binance not mixed
- raw archives preserved at:
  - `data/okx-direct/BTC-USDT-SWAP/2026-03/raw/orderbook/*.tar.gz`
  - `data/okx-direct/BTC-USDT-SWAP/2026-03/raw/trades/*.zip`
- no `backtest:okx-technical` chain started on March

## J. Companion artefacts written

- `reports/okx-direct/OKX_DIRECT_MARCH_2026_INVENTORY.md/.json`
- `reports/okx-direct/OKX_DIRECT_MARCH_2026_ORDERBOOK_SCHEMA_AUDIT.md/.json`
- `reports/okx-direct/OKX_DIRECT_MARCH_2026_TRADES_AUDIT.md/.json`
- `reports/okx-direct/OKX_DIRECT_2026-03-14_QUALITY_REPLAY.md/.json`
- `reports/okx-direct/OKX_DIRECT_MARCH_2026_FINAL_REPORT.md`  (this file)
- `scripts/okx-direct/build_inventory_and_audit_march_2026.py`
- `scripts/okx-direct/quality_replay_2026_03_14.py`
