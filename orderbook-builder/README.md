# orderbook-builder — Local L2 Order Book Builder

Consumes `Event`s from the existing `EventDispatcher` (each carries an `OrderBookPayload`)
and reconstructs the live L2 book per symbol. **Strict scaled-int** core: `price`/`amount`
are integers (real / `tick_size`, real / `qty_step`) — no float in storage keys, so tree
keys, `np.searchsorted` and the `amount == 0` delete check are exact.

Wire contract (confirmed): `price:int`, `amount:int`, `side:OrderSide(BID=0,ASK=1)`,
`is_snapshot:bool`; no `update_id`/`seq` on the payload (gap/STALE handling is a present-
but-disabled hook). `symbol` comes off the `Event`.

## Layout
```
orderbook/types.py     # OrderSide, StorageMode, OrderBookPayload/Event seam (Protocols + stubs), CrossedBookError
orderbook/config.py    # SymbolConfig(tick_size, qty_step) — read-side scaling only
orderbook/state.py     # OrderBookState + _Side backends (Mode A / Mode B)
orderbook/manager.py   # BookManager — routes Event.symbol -> OrderBookState
tests/test_orderbook.py
benchmarks/bench_orderbook.py
```

## Storage modes (source of truth = the FULL book in both)
- **Mode A — `StorageMode.FULL`** (correctness baseline): one `sortedcontainers.SortedDict`
  per side, `price(int) -> amount(int)`, natural ascending order. `best_ask = peekitem(0)`,
  `best_bid = peekitem(-1)`. Top-bids = tail of the tree, returned reversed.
- **Mode B — `StorageMode.TOPN_CACHE`**: the SortedDict stays the *only* source of truth;
  on top sits a synchronised fixed-length numpy cache (two `int64` arrays + a count per
  side). Search/insert/validate via `np.searchsorted` (C). Bids store `-price` so a single
  ascending searchsorted works for both sides (sign restored on read). **Never** keeps only
  top-N: deleting a cached top level **promotes** the (N+1)-th best from the SortedDict via
  O(log L) indexed access — no look-ahead, no blind top-N.

## apply_update state machine
1. `is_snapshot=True`: on the first row of a snapshot block, wipe both sides; fill the
   SortedDict; the (single) cache rebuild is deferred to end-of-block. Full cache rebuild is
   allowed **only** here.
2. `amount == 0`: delete; if the level was absent → warn `(symbol, price, side)` and
   continue (init jitter), never crash.
3. `amount > 0`: upsert.
4. Cache sync is **strictly incremental** (no per-delta rebuild): deep updates outside the
   top-N early-skip (O(log N)); in-window updates do an in-place numpy shift (O(N)); top
   deletes promote from depth (O(log L)).

Invariants: crossed-book check (`best_bid < best_ask`) after each update, `warn`/`strict`
flag; `BookManager` isolates symbols via `dict[str, OrderBookState]`.

## Read API (immutability & memory)
- `get_top_bids(n)` / `get_top_asks(n)` → `list[tuple[int,int]]` — **deep copy** (bids
  descending, asks ascending). O(n), allocates.
- `get_top_bids_view(n)` / `get_top_asks_view(n)` → read-only numpy views — **Mode B only**,
  O(1), valid only until the next `apply_update`. (For bids the price view holds `-price` —
  the one spot the sign isn't auto-restored, since a zero-copy view can't negate; use the
  copy API for ergonomic real prices.)
- `get_best_bid()/get_best_ask()` → `(price, amount) | None`.
- `get_mid()` → `float | None` — the ONLY sanctioned float (derived; never re-enters the
  book/keys/cache). Real price if a `SymbolConfig` is attached, else scaled. `None` if a
  side is empty.
- `get_mid_x2()` → `int | None` (best_bid + best_ask, half-ticks, float-free).
- `get_spread()` → `int | None`.

## Run
```bash
cd orderbook-builder
python -m pip install numpy sortedcontainers pytest

python -m pytest -q                                   # 22 tests (both modes)
python -m benchmarks.bench_orderbook --updates 2_000_000 --symbols BTCUSDT,ETHUSDT --top-n 25 --reads-per-update 8
```

## Usage
```python
from orderbook import BookManager, StorageMode, SymbolConfig
mgr = BookManager(mode=StorageMode.TOPN_CACHE, top_n=25,
                  configs={"BTCUSDT": SymbolConfig(tick_size=0.1, qty_step=0.001)})
for event in dispatcher.replay():
    if event.source_type is SourceType.ORDER_BOOK:   # caller filters book events
        mgr.apply(event)
book = mgr.get_state("BTCUSDT")
prices, amounts = book.get_top_asks_view(10)         # O(1) hot read
```

## Benchmark finding (honest tradeoff)
1M deltas, 2 symbols, top_n=25 (logging off in the hot path):
```
apply-only:                       FULL 439k upd/s   TOPN_CACHE 177k upd/s   -> FULL 2.49x
apply + 8 top-N reads/update:     FULL 6.1k upd/s    TOPN_CACHE 33.6k upd/s  -> TOPN_CACHE 5.51x
Peak RSS: 223 MB
```
- **Mode A** is faster on pure writes — it does no cache maintenance.
- **Mode B** pays a per-write cache cost but its **O(1) views** crush Mode A's O(n) copies
  on reads; with a realistic read-heavy strategy (top-N read many times per event) Mode B
  wins decisively, with the honest full book still underneath.
- Pick **Mode B** when reads dominate (the usual HFT feature-evaluation pattern); **Mode A**
  when you mostly apply and rarely read top-N.

## Complexity
- update: O(log L) SortedDict + O(N) in-place numpy shift (Mode B); common deep update is
  an O(log N) early-skip.
- top read: O(n) copy in both modes; O(1) via view in Mode B.
