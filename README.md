# Orderflow L2 Strategy — Research / Backtest Module

Stage 1 deliverable for the *Orderflow L2 Strategy* spec
(`TZ_orderflow_L2_strategy_module.docx`, version 1.0).

This is **not** a trading bot. It is an autonomous CLI research module that:

1. Streams Tardis CSV gzip files (`incremental_book_L2`, `trades`,
   `derivative_ticker`, `liquidations`, `book_ticker`) without loading
   them fully into RAM.
2. Reconstructs the L2 order book event by event (snapshot rows reset the
   side, `amount = 0` deletes the level).
3. Computes orderflow features on a 1-second feature grid (configurable):
   imbalance buckets, buy/sell pressure windows, absorption score, liquidity
   void score, add/remove/cancel rates, realised volatility / range.
4. Runs a Zone Detector as a state machine
   `Candidate → Confirmed → Triggered → Resolved | Expired | Invalidated`
   for both **Long Accumulation** and **Short Distribution** patterns.
5. For each Triggered zone runs a Target Checker that scans forward through
   trades on horizons (default `4h, 8h, 24h`) to record:
   * outcome (`reached` / `failed_by_timeout` / `invalid_data` /
     `no_trigger` / `invalidated_before_trigger`),
   * `timeToTargetMin`, `MFE`, `MAE`, `maxDrawdownBeforeTarget`.
6. **Saves all zones** — including failed, no-trigger, and invalidated —
   in `zones.csv`, `zones.json`, plus a daily summary, a markdown report
   and chart annotations.

There is **no web UI**, **no live recorder**, and **no exchange API** —
those are explicitly out of scope per the spec.

---

## AdShort — orderflow / liquidity strategy research

**AdShort** is the umbrella research project this repo backs: a study of whether
order-flow + liquidity structure can identify zones with positive expectancy on a
**clean 2–3 % move**. It is *research*, **not a production trading system**. Nothing
here is live, and no trading is performed.

### Target architecture (capital-state router)

```
Market background        →  Capital state / zone features  →  Zone expectancy   →  Entry / execution
(trend / range / vol)       (accumulation, distribution,       (does this zone      (timing inside a
                             absorption, markdown, chop)        beat a coin flip?)    permitted zone)
```

Zones already exist and are detected (the TypeScript engine above + the Python
research layer). The open question being researched is **zone expectancy**: given a
detected zone in a given market background and capital state, does it actually have
edge on a clean 2–3 % move — and only then, what entry/execution times it.

### Python research layer

The deeper statistical research lives in `scripts/research/` (causal, no-lookahead,
frozen gates) and writes artifacts to `reports/<branch>/`. Run e.g.:

```bash
python scripts/research/td_v9_phase.py        # phase-separation audit
python scripts/research/td_v10_blocker.py     # absorption/accumulation blocker
python scripts/research/td_v11_absorption.py  # forward-validated absorption labels (trades-only)
python scripts/research/td_v11b_build_l2.py   # reconstruct per-minute L2 book features (needs local data/)
python scripts/research/td_v11b_l2.py         # L2-aware absorption validation
```

These read **local** per-minute caches / raw market data under `data/` and
`reports/**/_series|_l2cache` (all gitignored — see below). They do not download data.

### Research branches (chronological)

| Branch | Question | Honest outcome |
|---|---|---|
| v6 / v7 | strict short-permission gate (GATE_6A / GATE_6E) | gate adds edge as a *regime filter*, not entry alpha; frozen |
| v8 | 8A "failed VWAP reclaim" short entry | weak candidate; profit concentrated in TREND_DOWN; NEED_MORE_DATA |
| v9 | phase-separation audit (6 market phases) | phases distinguishable, but GATE_6A leaks into absorption/accumulation; NEED_MORE_DATA |
| v10 | absorption/accumulation blocker on top of the gate | accumulation partly blocked; absorption not solved; ex-post test failed; NEED_MORE_DATA |
| v11 | forward-validated absorption labels (trades-only evidence) | **TRADES_ONLY_FEATURES_REJECTED** — within-background AUC ≈ 0.50 (Simpson's-paradox guard) |
| v11b | L2-aware absorption validation (reconstructed order book) | **L2_ABSORPTION_EVIDENCE_REJECTED** at 1-min resolution — within-TREND_DOWN/RANGE AUC still ≈ 0.49–0.52 |

### Current honest status

- **Trades-only absorption: rejected.** Causal trades-only evidence does not separate
  "sell pressure that continues markdown" from "sell pressure that gets absorbed"
  *within* a market background (the cross-background signal is just trend, which the
  gate already encodes).
- **1-minute L2 absorption separation: not proven.** Full order-book reconstruction
  (depth / refill / microprice) did **not** beat the chance floor within
  TREND_DOWN / RANGE at 1-minute resolution. Open doors: sub-minute / per-event L2,
  liquidations, OI.
- **Next core step: zone-level L2 expectancy calibration** — move from minute-level
  absorption to zone-level expectancy on the clean 2–3 % move.
- **No production.** Nothing is deployed or traded unless explicitly approved.

### Data policy (important)

Raw market data is **NOT** stored in GitHub. All venue data (OKX / Binance / Bybit
trades, `incremental_book_L2`, order book tar/zip, reconstructed caches, March/May
windows) lives locally under `data/` and `reports/**/_series|_l2cache` and is
gitignored. To reproduce the research you must supply that data locally. See
[`DATA_MANIFEST_EXCLUDED.md`](DATA_MANIFEST_EXCLUDED.md) for exactly what is excluded,
where it lives locally, and which scripts read it.

What **is** in GitHub: all source code, research scripts, configs, docs, and the small
research artifacts (`reports/**/*.md` and small `reports/**/*.csv` scorecards / audits /
final decisions).

---

## Project layout

```
orderflow-research/
├── README.md
├── package.json
├── tsconfig.json
├── vitest.config.ts
├── config/
│   └── strategy.default.json     # all thresholds — no magic numbers in code
├── src/
│   ├── data/                     # CSV streaming, schema, file resolver, time
│   ├── replay/                   # OrderBook, marketReplayEngine, snapshots, data quality
│   ├── features/                 # FeatureEngine + imbalance / absorption / void / events / vol
│   ├── strategy/                 # Zone state machine, detector, target checker, baselines
│   ├── reports/                  # CSV / JSON / Markdown writers
│   └── cli/                      # inspectData, backtestDay, exportSnapshots
├── tests/                        # vitest unit tests
└── reports/                      # output goes here (gitignored)
```

## Install

```bash
cd orderflow-research
npm install
```

This pulls only `tsx`, `typescript`, `vitest` and `@types/node`. The
runtime code itself is dependency-free (uses only `node:fs`, `node:zlib`,
`node:stream`).

## Get sample data

The bundled Tardis downloader (`tardis_2026_day_downloader.zip`) pulls one
free day of `binance-futures BTCUSDT`:

```bash
unzip tardis_2026_day_downloader.zip -d ./data/sample
cd ./data/sample
bash ./download_tardis_day.sh 2026-05-01 BTCUSDT
cd ../..
```

The resulting layout:

```
data/sample/tardis_binance-futures_BTCUSDT_2026-05-01/
  BTCUSDT_incremental_book_L2_2026-05-01.csv.gz
  BTCUSDT_trades_2026-05-01.csv.gz
  BTCUSDT_derivative_ticker_2026-05-01.csv.gz
  BTCUSDT_liquidations_2026-05-01.csv.gz
  BTCUSDT_book_ticker_2026-05-01.csv.gz
```

The file resolver searches recursively under `--input` so you can either
point it at the parent `./data/sample` or directly at the dated folder.

## Launch

### 1. Inspect the data files

```bash
npm run inspect:data -- --input ./data/sample --symbol BTCUSDT --date 2026-05-01
```

Lists matched files, prints column headers and the first 3 parsed rows for
each data type.

### 2. Run the full backtest for one day

```bash
npm run backtest:day -- \
  --input ./data/sample \
  --exchange binance-futures \
  --symbol BTCUSDT \
  --date 2026-05-01 \
  --target-pct 2 \
  --horizons 4h,8h,24h
```

Outputs go to `reports/BTCUSDT_2026-05-01/`:

| File | Purpose |
|---|---|
| `zones.csv` | One row per zone, all metrics, all outcomes. **Bad zones included.** |
| `zones.json` | Full zone structure with reason chain for downstream visualisation |
| `daily_summary.csv` | Counts, hit rate among triggered, breakdown by status |
| `report.md` | Human-readable summary, top zones, baselines, warnings |
| `chart_annotations.json` | Rectangles + trigger lines + targets for any future chart UI |
| `config.echo.json` | The exact config used for this run (reproducibility) |

### 3. Export reconstructed book snapshots

```bash
npm run export:snapshots -- \
  --input ./data/sample \
  --symbol BTCUSDT --date 2026-05-01 \
  --interval 1s --depth 50
```

Produces `reports/BTCUSDT_2026-05-01_snapshots/snapshots_1s_d50.jsonl`.
Each line is one snapshot:
```json
{"ts": 1746057600000, "isoTs": "2026-05-01T00:00:00.000Z", "bestBid": 65123.5, "bestAsk": 65124.0, "mid": 65123.75, "bids":[[65123.5, 1.2], …], "asks":[[65124.0, 0.8], …]}
```

### 4. Range backtest (when paid data is available)

```bash
npm run backtest:range -- \
  --input ./data/tardis-paid \
  --symbol BTCUSDT --from 2024-04-01 --to 2024-04-30 \
  --target-pct 2
```

### 5. Validate Tardis files (compatibility / smoke check)

```bash
npm run validate:tardis -- \
  --input ./data/tardis/binance-futures/BTCUSDT \
  --symbol BTCUSDT --exchange binance-futures \
  --dates 2026-01-01,2026-02-01,2026-03-01,2026-04-01
```

For each date the validator checks: file presence, gzip integrity, expected
columns (incl. `timestamp` / `local_timestamp`), inferred data type, and the
parseability of the first 1000 rows. `incremental_book_L2` and `trades` are
treated as **mandatory**; `derivative_ticker`, `book_ticker`, `liquidations`
are optional and only emit `missing_optional`. Outputs:
* `reports/tardis_validation_2026_ytd_except_may.md`
* `reports/tardis_validation_2026_ytd_except_may.json`

### Live recorder — Binance USDS-M Futures public market data

A separate, optional module under `src/live-recorder/` that streams **public**
Binance Futures market data (no API key, no trading) into ClickHouse so the
strategy engine can later replay from your own database via the
`backtest:db` CLI.

**What gets recorded** per configured symbol:

| ClickHouse table | Contents |
|---|---|
| `raw_depth_events` | every L2 diff update (`<symbol>@depth@100ms`) with bids/asks arrays |
| `orderbook_snapshots_1s` | every 1s, top-50 reconstructed snapshot from the local order book + quality flags |
| `trades` | aggregate trades (`<symbol>@aggTrade`) with normalised buy/sell side |
| `book_ticker` | `<symbol>@bookTicker` best bid/ask |
| `mark_price` | `<symbol>@markPrice@1s` mark / index / funding |
| `liquidations` | `<symbol>@forceOrder` |
| `recorder_health` | one row per ~10s with rates, gap counts, reconnects, queue sizes |

**Local order book correctness.** The recorder follows Binance's official
[order-book management](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly):
buffer events → REST `GET /fapi/v1/depth?limit=1000` snapshot → drop events
with `u < lastUpdateId` → first applied event must satisfy
`U <= lastUpdateId+1 <= u` → on every subsequent event check
`pu == previous u`. A sequence gap is recorded in `recorder_health.sequence_gap_count`
and triggers a re-snapshot. The same `OrderBook` class that backs the
backtest is reused for the live reconstruction, so live = backtest byte-identical.

**Reliability.** A `BatchWriter` flushes rows to ClickHouse in batches; if
the database is unreachable, rows are appended to JSONL spool files at
`./data/live-spool/<table>-<YYYYMMDD>.jsonl` and re-inserted on the next
recovery pass. **No event is silently dropped.**

#### How to launch

```bash
# 1. Bring up ClickHouse
docker compose up -d clickhouse

# 2. Apply the schema (idempotent)
npm run db:migrate

# 3. Verify tables
npm run db:check

# 4. Start the recorder (foreground)
SYMBOLS=BTCUSDT npm run live:recorder

# 5. In another terminal: point-in-time health snapshot
npm run live:health
```

Configuration is via environment variables (see `.env.example`): `EXCHANGE`,
`SYMBOLS`, `DEPTH_STREAM_SPEED`, `SNAPSHOT_INTERVAL_MS`, `CLICKHOUSE_URL`,
`CLICKHOUSE_DB`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `RAW_SPOOL_DIR`,
`LOG_LEVEL`. None of those are credentials for trading — Binance Futures
public market-data streams require no API key.

To **add a new symbol**, set `SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT` and restart
the recorder. Per-symbol order books, REST snapshots and 1s emitter run
independently; ClickHouse partitioning is by `(exchange, symbol, event_time)`.

#### Verifying data is being written

```sql
-- 1-min depth event count
SELECT count() FROM orderflow.raw_depth_events
 WHERE event_time >= now() - INTERVAL 1 MINUTE;

-- 1-min trade count
SELECT count() FROM orderflow.trades
 WHERE event_time >= now() - INTERVAL 1 MINUTE;

-- Latest reconstructed snapshot
SELECT ts, best_bid, best_ask, mid, spread
  FROM orderflow.orderbook_snapshots_1s
 ORDER BY ts DESC
 LIMIT 1;

-- Sequence gap history
SELECT ts, symbol, sequence_gap_count, reconnect_count, status
  FROM orderflow.recorder_health
 ORDER BY ts DESC
 LIMIT 20;
```

#### Replaying recorded data through the strategy

```bash
npm run backtest:db -- --symbol BTCUSDT \
  --from 2026-05-09T00:00:00Z --to 2026-05-09T23:59:59Z \
  --target-pct 2 --horizons 4h,8h,24h
```

The `ClickHouseDataSource` adapter pulls `raw_depth_events`, `trades` and
`liquidations` from the database, merges them by event time, and feeds the
existing `FeatureEngine` + `ZoneDetector` + `TargetChecker` pipeline. Output
goes to `reports/db_<symbol>_<from-date>/` with the same `zones.csv /
zones.json / report.md` layout as `backtest:day`.

#### Stopping the recorder

`Ctrl-C` — the service handles `SIGINT`/`SIGTERM` and flushes any pending
batches before exiting. Spool files are kept on disk and recovered on next
start.

#### Safety guarantees

- **No API key** — the recorder uses only public REST `/fapi/v1/depth` and
  public WS `fstream.binance.com/stream`.
- **No trading endpoints** — the test `J. live-recorder source contains
  NO trading endpoints` greps `src/live-recorder/*.ts` for any trading
  pattern (`X-MBX-APIKEY`, `placeOrder`, `cancelOrder`, `/fapi/v1/order`,
  `HMAC-SHA256`, …) and fails the build if any is present.
- **Tardis CSV pipeline is untouched** — `backtest:day`, `backtest:sample-2026`,
  `validate:tardis` and every existing report keep working as before.

### 6. End-to-end smoke backtest on the Jan-Apr 2026 sample

```bash
# (optional) download the data first:
bash scripts/download-tardis-2026-ytd-except-may.sh
# or
powershell -ExecutionPolicy Bypass -File scripts/download-tardis-2026-ytd-except-may.ps1
# or
python scripts/download-tardis-2026-ytd-except-may.py

npm run backtest:sample-2026
```

This runs `validate -> export:snapshots (1s, depth 50) -> backtest:day` per day
for `2026-01-01, 2026-02-01, 2026-03-01, 2026-04-01`. **One bad day does not
abort the rest.** Outputs:
* `reports/sample_2026_ytd_except_may/summary.csv`
* `reports/sample_2026_ytd_except_may/summary.json`
* `reports/sample_2026_ytd_except_may/report.md` (per-day table with L2/trade
  rows, optional present/missing, quality flag tick count, snapshots, zones by
  state, ±2% reach by horizon, baseline 24h up/down, triggered hit rate)

The report explicitly states: *"This is a compatibility and smoke-test run,
not a proof of strategy profitability."* Failed / `no_trigger` / `invalidated`
zones are kept; thresholds in `config/strategy.default.json` are **not**
modified by this run.

## Configuration

All thresholds live in `config/strategy.default.json`. Override with
`--config path/to/your.json`. The most important knobs:

| Section | Field | Meaning |
|---|---|---|
| top-level | `targetPct` | Target move size in % (default 2) |
| top-level | `featureIntervalSec` | Feature tick rate. 1 = each second. |
| top-level | `tradeWindowsSec` | Rolling trade-aggregation windows (s) |
| top-level | `depthPctBuckets` | Order-book depth pct buckets used for imbalance |
| `zone.candidate` | `minSidedPressure` | Minimum buy/sell pressure to open a candidate (0..1) |
| `zone.candidate` | `minRefillScore` | Minimum bid/ask refill score |
| `zone.candidate` | `rangeCompressionPct` | 1m range cap to flag compression |
| `zone` | `minAbsorptionCycles` | Cycles required for confirmation |
| `zone.confirmed` | `minDefendedPersistenceSec` | Defended-side persistence threshold |
| `zone.trigger` | `minBreakDistancePct` | Break out of zone by this % |
| `zone.trigger` | `minAggressiveFlowMultiplier` | Trade flow burst at trigger vs baseline |
| `targetChecker` | `horizons` | Horizons to evaluate |
| `quality` | `maxSpreadPct` | Spread above which a tick is flagged |
| `quality` | `maxGapMs` | Time gap above which a tick is flagged |

## Tests

```bash
npm test
```

Adds the following vitest suites:

| File | Covers |
|---|---|
| `tests/orderBook.test.ts` | Snapshot reset, update / delete, `bestBid < bestAsk`, depth-around-mid |
| `tests/csvParser.test.ts` | Header detection, microsecond → ms, gzip streaming end-to-end |
| `tests/features.test.ts` | Trade aggregation across windows, no lookahead, imbalance math |
| `tests/targetChecker.test.ts` | LONG / SHORT 2% reach, timeout fail, no-lookahead from pre-trigger trades |
| `tests/absorption.test.ts` | Toy absorption scenario produces a Long candidate; debug reasons populated |

## Anti-self-deception guarantees

The spec (§13) is explicit and the code follows it:

1. Failed / `no_trigger` / `invalidated` zones are kept in `zones.csv`.
2. `report.md` reports the hit rate **only over triggered zones**; the
   raw counts are listed separately so you can see survivorship.
3. Every zone carries a `reasons` array with the conditions that fired at
   each transition (`candidate`, `confirmed`, `trigger`, `expire` …).
4. Tick-level quality flags (`EMPTY_BOOK`, `CROSSED`, `WIDE_SPREAD`,
   `NO_BBO`, `GAP`) are surfaced both per feature row and per zone, and
   summarised in `report.md`.
5. `probabilityBaseline.ts` provides the unconditional 2% hit rate from
   the day's price walk so you can tell whether the zone signal adds
   anything over a coin flip.

## Limitations of this stage

* Day-level only (range mode loops days; no cross-day state).
* Single-symbol (`BTCUSDT` is the default but anything works as long as
  files match).
* Zone scoring is intentionally simple and exposed as config — this is
  research scaffolding, not a tuned model.
* The order book uses linear scans for depth-around-mid (clear / robust;
  not nanosecond-fast). With 100 levels per side it's fine.
* `targetChecker` walks trades sequentially, not via a price index. For a
  single day this is millisecond-cheap; for multi-month runs you may want
  a pre-built `(ts, hi, lo)` ladder.

## What to verify when you provide a real backtest file

1. `npm run inspect:data` succeeds and lists at least
   `incremental_book_L2` and `trades` (warnings list any missing types).
2. The first lines printed by `inspect:data` show **microsecond
   timestamps** for `timestamp` and `local_timestamp` — the parser
   converts to ms automatically; if you see seconds or ms in the raw CSV
   the parser will silently produce wrong dates, so check.
3. `npm run export:snapshots --interval 1s` produces snapshots whose
   `mid` is in a reasonable range for the day (~$65k for BTCUSDT in
   2026-05-01). This validates the order-book reconstruction.
4. `npm run backtest:day` finishes without "WARN: missing required data
   types" and writes all 5 artefacts. Open `report.md` and check:
   * `Rows processed` is non-zero for `L2` and `trades`,
   * `Hit rate among triggered` is shown next to the unconditional
     baseline,
   * `Top zones by absorption × void score` actually has rows.
5. Open `zones.csv` in Excel / numbers / a notebook and check the
   `reasons` column has multi-stage chains
   (`candidate@... | confirmed@... | trigger@...`) and the
   `outcome_summary` column shows `4h:reached | 8h:reached | 24h:reached`
   patterns rather than all-`no_trigger`.
6. If everything looks empty, check `quality_flags`: a wide-spread or
   constantly-gappy day will skip ticks. Loosen
   `quality.maxSpreadPct` / `quality.maxGapMs` in the config and re-run.
7. If you see lots of zones but everything `failed_by_timeout`, the
   day may simply have been a slow chop. Compare to the unconditional
   baseline in `report.md` before drawing conclusions.
