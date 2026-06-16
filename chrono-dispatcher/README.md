# chrono-dispatcher — Deterministic Event Replay (HFT backtester core)

Merges events from many Tardis (Bybit) gzip-CSV files and replays them in **strict
chronological order** (`local_timestamp`, microseconds, `int`). Any out-of-order delivery
is a look-ahead bias; replay here is deterministic and bit-for-bit repeatable.

## Confirmed inputs
- Format: **tardis.dev gzip-CSV**, one file per `source_type` × symbol.
- Ordering clock: **`local_timestamp`** (µs) — what the recorder/strategy actually saw.
- order_book source: **`incremental_book_L2`** (per-level deltas, `is_snapshot` column;
  `amount` is absolute, `amount == 0` removes a level).
- Vectorised parsing: **pandas** (`read_csv(compression="gzip", chunksize=50_000)`).

## Architecture
```
files ──▶ TardisGzipSource (block read + vectorised parse) ──▶ Event(seq local)
                                   │
                                   ▼
                        _JitterSource (watermark buffer + aggressive refill)
                                   │ next_releasable()  (one safe head per source)
                                   ▼
            EventDispatcher  K-way min-heap merge  ──▶ replay() ──▶ Iterator[Event]
```
- **K-way merge**: `heapq` with one head per source (K entries). Key tuple
  `(timestamp, source_type, source_id, seq, event)` — compared in C. `(source_id, seq)`
  is globally unique and each source has ≤1 head in the heap, so the comparison never
  reaches `event`/payload. `Event`/payloads are `order=False` → any accidental compare
  raises `TypeError` (fail-loud), never mis-orders.
- **Jitter watermark** (`tolerance_us`): an event `T` is released only once the source
  has read past `T + tolerance_us`, so locally-swapped near-equal timestamps are
  re-sorted and nothing leaks early. **Aggressive refill** keeps reading rows while the
  oldest buffered event is still inside the window — a sparse source with a long pause
  can never deadlock the merge. On **EOF** the buffer drains fully (tail preserved). A
  backward jump beyond tolerance raises `ChronologyViolationError` (source + row + delta).
- **Memory/immutability**: `Event` and `OrderBookPayload`/`TradePayload`/`TickerPayload`
  are `@dataclass(frozen=True, slots=True)` (no per-instance dict, no `MappingProxyType`,
  no `dict` payloads). `symbol`/`side` are `sys.intern`-ed (one instance for 100M rows).
- **Resources**: `EventDispatcher` is a context manager; `replay()` wraps the merge in
  `try/finally` so an early `break` (`GeneratorExit`) still closes every file. No
  `OSError: Too many open files` under mass parameter sweeps.

`SourceType` (IntEnum) is the single source of truth for type **and** priority:
`ORDER_BOOK(0) < TRADES(1) < DERIVATIVE_TICKER(2)` at equal timestamps.

## Install / test / benchmark
```bash
cd chrono-dispatcher
python -m pip install pytest pandas        # merge core needs neither; parsers+bench need pandas

python -m pytest -q                        # 17 deterministic tests

python benchmark.py --rows 2_000_000 --symbols BTCUSDT,ETHUSDT --tolerance-us 2000
```

## Interface
```python
from chrono_dispatcher import EventDispatcher, SourceConfig, SourceType

sources = [
    SourceConfig("BTCUSDT_book.csv.gz",   SourceType.ORDER_BOOK,        1, "BTCUSDT"),
    SourceConfig("BTCUSDT_trades.csv.gz", SourceType.TRADES,            2, "BTCUSDT"),
    SourceConfig("ETHUSDT_trades.csv.gz", SourceType.TRADES,            3, "ETHUSDT"),
]
with EventDispatcher(sources, tolerance_us=2000) as d:
    for event in d.replay():
        ...   # Event(timestamp, symbol, source_type, source_id, seq, payload)
```
Tests inject `MemorySource` instances in place of `SourceConfig` (same `replay()` path),
so the merge core is exercised without files.

## Benchmark finding (heap key: tuple vs Event.__lt__)
The spec leaves the choice to measurement. A *fair* run (warm-up pass first, so neither
mode benefits from a warm file cache by running second):

```
[key_mode=tuple] 1,366,664 events  7.12s  192,035 ev/s  gc_pauses=3  gc_total=8.5ms
[key_mode=event] 1,366,664 events  9.47s  144,337 ev/s  gc_pauses=3  gc_total=10.8ms
Peak RSS: 179 MB
VERDICT: 'tuple' key is faster by 1.33x.
```
→ **Tuple key stays the default**, confirming the spec's reasoning: at small K the native
C tuple comparison beats a Python `__lt__`. (Note: an earlier *unfair* run where `event`
ran second on a warm cache made `event` look 1.05× faster — hence the warm-up pass.)

## Complexity
- Time: **O(N log K)** — N events, heap of K source heads.
- Memory: **O(K · (chunk + jitter_window))** — one decode chunk + one jitter buffer per
  source live at a time; events are streamed, never materialised.
