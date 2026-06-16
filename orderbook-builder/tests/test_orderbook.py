"""Deterministic unit tests for the L2 order-book builder (both storage modes)."""
from __future__ import annotations

import numpy as np
import pytest

from orderbook import (
    BookManager,
    CrossedBookError,
    Event,
    OrderBookPayload,
    OrderBookState,
    OrderSide,
    StorageMode,
    SymbolConfig,
)

BID = OrderSide.BID
ASK = OrderSide.ASK


# --------------------------------------------------------------------------- helpers


def P(price: int, amount: int, side: OrderSide, snap: bool = False) -> OrderBookPayload:
    return OrderBookPayload(price, amount, side, snap)


def feed(state: OrderBookState, payloads) -> None:
    for pl in payloads:
        state.apply_update(pl)


def snapshot(state: OrderBookState, bids, asks) -> None:
    """Send a snapshot block (is_snapshot=True) then one no-op-ish delta to close it."""
    rows = [P(p, a, BID, snap=True) for p, a in bids] + [P(p, a, ASK, snap=True) for p, a in asks]
    feed(state, rows)


BOTH_MODES = [StorageMode.FULL, StorageMode.TOPN_CACHE]


def new_state(mode=StorageMode.FULL, top_n=8, **kw) -> OrderBookState:
    return OrderBookState("BTCUSDT", mode=mode, top_n=top_n, **kw)


# --------------------------------------------------------------------------- snapshot


@pytest.mark.parametrize("mode", BOTH_MODES)
def test_snapshot_clears_and_rebuilds(mode):
    s = new_state(mode)
    feed(s, [P(100, 5, BID), P(101, 3, ASK)])  # pre-existing deltas
    # A fresh snapshot must wipe and replace the whole book.
    snapshot(s, bids=[(90, 1), (91, 2)], asks=[(95, 4), (96, 6)])
    assert s.get_best_bid() == (91, 2)
    assert s.get_best_ask() == (95, 4)
    assert s.get_top_bids(8) == [(91, 2), (90, 1)]
    assert s.get_top_asks(8) == [(95, 4), (96, 6)]
    assert 100 not in [p for p, _ in s.get_top_bids(8)]  # old level gone


# --------------------------------------------------------------------------- CRUD


@pytest.mark.parametrize("mode", BOTH_MODES)
def test_crud_add_update_delete(mode):
    s = new_state(mode)
    s.apply_update(P(100, 5, BID))            # add
    assert s.get_best_bid() == (100, 5)
    s.apply_update(P(100, 9, BID))            # update volume
    assert s.get_best_bid() == (100, 9)
    s.apply_update(P(100, 0, BID))            # delete
    assert s.get_best_bid() is None


@pytest.mark.parametrize("mode", BOTH_MODES)
def test_delete_missing_level_warns_not_crash(mode, caplog):
    s = new_state(mode)
    s.apply_update(P(100, 5, BID))
    with caplog.at_level("WARNING"):
        s.apply_update(P(555, 0, ASK))        # delete of a level that never existed
    assert s.stats.missing_deletes == 1
    assert s.get_best_bid() == (100, 5)        # book intact


# --------------------------------------------------------------------------- ordering / best


@pytest.mark.parametrize("mode", BOTH_MODES)
def test_side_sort_direction_and_best(mode):
    s = new_state(mode)
    feed(s, [P(100, 1, BID), P(102, 1, BID), P(101, 1, BID),
             P(110, 1, ASK), P(108, 1, ASK), P(109, 1, ASK)])
    assert s.get_top_bids(3) == [(102, 1), (101, 1), (100, 1)]   # descending
    assert s.get_top_asks(3) == [(108, 1), (109, 1), (110, 1)]   # ascending
    assert s.get_best_bid() == (102, 1)
    assert s.get_best_ask() == (108, 1)


# --------------------------------------------------------------------------- empty / one-sided reads


@pytest.mark.parametrize("mode", BOTH_MODES)
def test_reads_on_empty_or_one_sided_book(mode):
    s = new_state(mode)
    assert s.get_mid() is None and s.get_mid_x2() is None and s.get_spread() is None
    assert s.get_best_bid() is None and s.get_best_ask() is None
    s.apply_update(P(100, 1, BID))            # one-sided
    assert s.get_mid() is None and s.get_spread() is None and s.get_mid_x2() is None
    assert s.get_best_ask() is None
    s.apply_update(P(104, 1, ASK))
    assert s.get_mid_x2() == 204
    assert s.get_spread() == 4


def test_get_mid_uses_config_real_price():
    s = new_state(config=SymbolConfig(tick_size=0.5, qty_step=0.001))
    s.apply_update(P(100, 1, BID))
    s.apply_update(P(102, 1, ASK))
    assert s.get_mid() == pytest.approx(101 * 0.5)  # (100+102)/2 * tick_size


# --------------------------------------------------------------------------- Mode B promote


def test_mode_b_promote_on_delete_of_middle_and_best():
    # top_n=3; build 5 asks. Cache holds [100,101,102]; deeper [103,104].
    s = new_state(StorageMode.TOPN_CACHE, top_n=3)
    for p in (100, 101, 102, 103, 104):
        s.apply_update(P(p, 10 + p, ASK))
    assert s.get_top_asks(3) == [(100, 110), (101, 111), (102, 112)]
    # delete the MIDDLE cached level -> 103 must promote from depth.
    s.apply_update(P(101, 0, ASK))
    assert s.get_top_asks(3) == [(100, 110), (102, 112), (103, 113)]
    # delete the BEST cached level -> 104 must promote.
    s.apply_update(P(100, 0, ASK))
    assert s.get_top_asks(3) == [(102, 112), (103, 113), (104, 114)]
    assert s.stats.promotes == 2


def test_mode_b_promote_bids_side():
    s = new_state(StorageMode.TOPN_CACHE, top_n=3)
    for p in (100, 101, 102, 103, 104):
        s.apply_update(P(p, p, BID))
    assert s.get_top_bids(3) == [(104, 104), (103, 103), (102, 102)]
    s.apply_update(P(104, 0, BID))            # delete best bid -> 101 promotes from depth
    assert s.get_top_bids(3) == [(103, 103), (102, 102), (101, 101)]


# --------------------------------------------------------------------------- cache incrementality


def test_deep_update_does_not_rebuild_or_touch_cache():
    s = new_state(StorageMode.TOPN_CACHE, top_n=4)
    snapshot(s, bids=[(p, p) for p in range(90, 100)], asks=[(p, p) for p in range(100, 110)])
    s.apply_update(P(99, 99, BID))            # one delta to settle (rebuild #1)
    rebuilds_before = s.stats.cache_rebuilds
    pv, av = s.get_top_asks_view(4)
    snapshot_before = (pv.copy(), av.copy())
    # An update FAR below the top-N (deep ask) must early-skip the cache entirely.
    s.apply_update(P(5000, 7, ASK))
    assert s.stats.cache_rebuilds == rebuilds_before          # no rebuild
    pv2, av2 = s.get_top_asks_view(4)
    assert np.array_equal(pv2, snapshot_before[0])            # cache untouched
    assert np.array_equal(av2, snapshot_before[1])
    assert s.ask_depth() == 11                                # but the deep level IS stored


# --------------------------------------------------------------------------- slice immutability


@pytest.mark.parametrize("mode", BOTH_MODES)
def test_top_copy_is_immutable_snapshot(mode):
    s = new_state(mode)
    feed(s, [P(100, 1, BID), P(99, 1, BID)])
    copy = s.get_top_bids(2)
    s.apply_update(P(100, 999, BID))          # mutate best after copying
    assert copy == [(100, 1), (99, 1)]        # the earlier copy is unaffected


# --------------------------------------------------------------------------- integer exactness


@pytest.mark.parametrize("mode", BOTH_MODES)
def test_integer_price_exactness(mode):
    # Prices that would collide/round under float are exact as int keys.
    s = new_state(mode)
    s.apply_update(P(100000000000001, 1, ASK))
    s.apply_update(P(100000000000002, 1, ASK))
    s.apply_update(P(100000000000001, 0, ASK))   # delete the exact level
    assert s.get_top_asks(2) == [(100000000000002, 1)]
    assert all(isinstance(p, int) for p, _ in s.get_top_asks(2))


# --------------------------------------------------------------------------- Mode A == Mode B


def test_mode_a_and_b_identical_topn_on_stream():
    rng = np.random.default_rng(1234)
    n = 6
    sa = new_state(StorageMode.FULL, top_n=n)
    sb = new_state(StorageMode.TOPN_CACHE, top_n=n)
    # snapshot
    bids = [(p, p) for p in range(900, 960)]
    asks = [(p, p) for p in range(1000, 1060)]
    for st in (sa, sb):
        snapshot(st, bids, asks)
    # random stream of deltas (upserts + deletes), same to both
    prices = list(range(880, 1080))
    for _ in range(4000):
        price = int(rng.choice(prices))
        side = BID if price < 980 else ASK
        amount = 0 if rng.random() < 0.35 else int(rng.integers(1, 50))
        pl = P(price, amount, side)
        sa.apply_update(pl)
        sb.apply_update(pl)
        if rng.random() < 0.05:  # spot-check during the stream
            assert sa.get_top_bids(n) == sb.get_top_bids(n)
            assert sa.get_top_asks(n) == sb.get_top_asks(n)
    assert sa.get_top_bids(n) == sb.get_top_bids(n)
    assert sa.get_top_asks(n) == sb.get_top_asks(n)


# --------------------------------------------------------------------------- crossed book


def test_crossed_book_warn_then_strict():
    warn = new_state(crossed_strict=False)
    warn.apply_update(P(100, 1, ASK))
    warn.apply_update(P(105, 1, BID))         # bid above ask -> crossed, but only warns
    assert warn.stats.crossed_count == 1
    strict = new_state(crossed_strict=True)
    strict.apply_update(P(100, 1, ASK))
    with pytest.raises(CrossedBookError):
        strict.apply_update(P(105, 1, BID))


# --------------------------------------------------------------------------- multi-symbol


def test_multisymbol_isolation():
    mgr = BookManager(mode=StorageMode.TOPN_CACHE, top_n=5)
    mgr.apply(Event("BTCUSDT", P(100, 1, BID)))
    mgr.apply(Event("ETHUSDT", P(50, 9, BID)))
    mgr.apply(Event("BTCUSDT", P(101, 2, ASK)))
    btc = mgr.get_state("BTCUSDT")
    eth = mgr.get_state("ETHUSDT")
    assert btc.get_best_bid() == (100, 1)
    assert btc.get_best_ask() == (101, 2)
    assert eth.get_best_bid() == (50, 9)
    assert eth.get_best_ask() is None         # ETH book unaffected by BTC asks
    assert set(mgr.symbols()) == {"BTCUSDT", "ETHUSDT"}


# --------------------------------------------------------------------------- view read-only


def test_view_is_readonly_mode_b_only():
    s = new_state(StorageMode.TOPN_CACHE, top_n=4)
    feed(s, [P(100, 1, ASK), P(101, 2, ASK)])
    prices, amounts = s.get_top_asks_view(4)
    assert not prices.flags.writeable and not amounts.flags.writeable
    with pytest.raises(ValueError):
        prices[0] = 0                          # read-only
    a = new_state(StorageMode.FULL)
    with pytest.raises(RuntimeError):
        a.get_top_asks_view(4)                 # views are Mode B only
