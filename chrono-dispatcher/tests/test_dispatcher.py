"""Deterministic, fast unit tests for the chronology dispatcher."""
from __future__ import annotations

import dataclasses
import gzip
import os

import pytest

from chrono_dispatcher import (
    ChronologyViolationError,
    EventDispatcher,
    Event,
    MemorySource,
    OrderBookPayload,
    SourceConfig,
    SourceType,
    TickerPayload,
    TradePayload,
)


# --------------------------------------------------------------------------- helpers


def trade(ts: int, price: float = 1.0) -> tuple[int, TradePayload]:
    return (ts, TradePayload("buy", price, 1.0, "t"))


def book(ts: int, price: float = 1.0) -> tuple[int, OrderBookPayload]:
    return (ts, OrderBookPayload("bid", price, 1.0, False))


def mem(source_id: int, symbol: str, stype: SourceType, rows) -> MemorySource:
    return MemorySource(source_id, symbol, stype, rows)


def run(sources, **kw) -> list[Event]:
    with EventDispatcher(sources, **kw) as d:
        return list(d.replay())


def assert_monotonic(events: list[Event]) -> None:
    last = None
    for ev in events:
        if last is not None:
            assert ev.timestamp >= last, f"out of order: {ev.timestamp} after {last}"
        last = ev.timestamp


# --------------------------------------------------------------------------- 1. order


def test_global_order_with_shuffled_timestamps_between_sources():
    a = mem(1, "BTCUSDT", SourceType.TRADES, [trade(100), trade(300), trade(500)])
    b = mem(2, "BTCUSDT", SourceType.ORDER_BOOK, [book(200), book(400), book(600)])
    out = run([a, b])
    assert [e.timestamp for e in out] == [100, 200, 300, 400, 500, 600]
    assert_monotonic(out)


# --------------------------------------------------------------------------- 2. tie-break


def test_priority_tiebreak_at_equal_timestamp():
    # order_book (prio 0) must come before trades (prio 1) at the same timestamp.
    ob = mem(1, "BTCUSDT", SourceType.ORDER_BOOK, [book(1000)])
    tr = mem(2, "BTCUSDT", SourceType.TRADES, [trade(1000)])
    out = run([tr, ob])  # registration order intentionally reversed
    assert [e.source_type for e in out] == [SourceType.ORDER_BOOK, SourceType.TRADES]


def test_equal_priority_and_seq_breaks_on_source_id_no_payload_compare():
    # Two files, equal priority (both TRADES) and equal local seq (both first row) and
    # equal timestamp -> must break on source_id WITHOUT ever comparing payloads.
    a = mem(10, "BTCUSDT", SourceType.TRADES, [trade(1000)])
    b = mem(20, "ETHUSDT", SourceType.TRADES, [trade(1000)])
    out = run([b, a])  # b registered first, but lower source_id (a=10) must win the tie
    assert [e.source_id for e in out] == [10, 20]


def test_payloads_are_fail_loud_when_compared():
    # Proves the tie-break above never relied on payload ordering: comparing payloads
    # raises (order=False), so if the heap ever reached the payload it would blow up.
    with pytest.raises(TypeError):
        _ = TradePayload("buy", 1.0, 1.0, "a") < TradePayload("buy", 1.0, 1.0, "b")
    with pytest.raises(TypeError):
        _ = OrderBookPayload("bid", 1, 1, False) < OrderBookPayload("ask", 1, 1, False)


# --------------------------------------------------------------------------- 3. jitter / watermark


def test_jitter_within_tolerance_is_reordered_without_lookahead():
    # Source A is locally swapped (100 then 90); B has 95. With tolerance the watermark
    # holds 100 until 90/95 are placed -> correct global order 90, 95, 100.
    a = mem(1, "BTCUSDT", SourceType.TRADES, [trade(100), trade(90), trade(300)])
    b = mem(2, "BTCUSDT", SourceType.TRADES, [trade(95), trade(200)])
    out = run([a, b], tolerance_us=100)
    assert [e.timestamp for e in out] == [90, 95, 100, 200, 300]
    assert_monotonic(out)


def test_watermark_does_not_release_before_window_closes():
    # With a single jittered source, 90 must be emitted before 100 even though 100 is
    # read first — i.e. the watermark re-sorts and never leaks 100 early.
    a = mem(1, "BTCUSDT", SourceType.TRADES, [trade(100), trade(90), trade(300)])
    out = run([a], tolerance_us=100)
    assert [e.timestamp for e in out] == [90, 100, 300]


# --------------------------------------------------------------------------- 4. deadlock


def test_sparse_source_does_not_deadlock_aggressive_refill():
    # Low-liquidity source: one early event then a huge pause in the file. A naive
    # "stop when chunk is full" reader would never close the jitter window and would
    # hang forever. Aggressive refill keeps reading until the window closes.
    low = mem(1, "BTCUSDT", SourceType.TRADES, [trade(100), trade(10_000_000)])
    high = mem(2, "BTCUSDT", SourceType.ORDER_BOOK, [book(t) for t in range(100, 2100, 100)])
    out = run([low, high], tolerance_us=1000)
    # Completes (no hang) and the low source's early 100 is placed before the dense run.
    assert out[0].timestamp == 100
    assert_monotonic(out)
    assert sorted(e.timestamp for e in out) == [e.timestamp for e in out]
    assert any(e.source_id == 1 and e.timestamp == 10_000_000 for e in out)


# --------------------------------------------------------------------------- 5. EOF drain


def test_eof_drains_buffer_tail_not_lost():
    # tolerance huge -> nothing releases until EOF, then the whole buffer drains sorted.
    a = mem(1, "BTCUSDT", SourceType.TRADES, [trade(100), trade(200), trade(150)])
    out = run([a], tolerance_us=10_000_000)
    assert [e.timestamp for e in out] == [100, 150, 200]  # tail (150) preserved + sorted


# --------------------------------------------------------------------------- 6. hard violation


def test_violation_beyond_tolerance_raises_clear_error():
    a = mem(1, "BTCUSDT", SourceType.TRADES,
            [trade(1000), trade(1100), trade(1200), trade(1300), trade(1400), trade(1500), trade(200)])
    with pytest.raises(ChronologyViolationError) as ei:
        run([a], tolerance_us=100)
    err = ei.value
    assert err.source_id == 1
    assert err.timestamp == 200
    assert err.delta > 100  # backward jump exceeds tolerance
    assert "row" in str(err)


# --------------------------------------------------------------------------- 7. early break closes files


def test_early_break_closes_all_sources():
    sources = [
        mem(1, "BTCUSDT", SourceType.TRADES, [trade(t) for t in range(100, 10000, 10)]),
        mem(2, "ETHUSDT", SourceType.TRADES, [trade(t) for t in range(105, 10000, 10)]),
    ]
    with EventDispatcher(sources, tolerance_us=0) as d:
        for i, _ev in enumerate(d.replay()):
            if i == 3:
                break  # early exit -> GeneratorExit + __exit__ must close everything
    assert all(s.close_calls >= 1 for s in sources)


def test_generator_finally_closes_on_explicit_close():
    sources = [mem(1, "BTCUSDT", SourceType.TRADES, [trade(t) for t in range(0, 1000)])]
    d = EventDispatcher(sources).__enter__()
    gen = d.replay()
    next(gen)
    gen.close()  # GeneratorExit -> finally -> close()
    assert sources[0].close_calls >= 1


# --------------------------------------------------------------------------- 8. multi-asset


def test_multiasset_symbols_isolated_global_chrono_order():
    btc = mem(1, "BTCUSDT", SourceType.TRADES, [trade(100), trade(300)])
    eth = mem(2, "ETHUSDT", SourceType.TRADES, [trade(150), trade(250)])
    out = run([btc, eth])
    assert [(e.timestamp, e.symbol) for e in out] == [
        (100, "BTCUSDT"), (150, "ETHUSDT"), (250, "ETHUSDT"), (300, "BTCUSDT")
    ]
    # symbol strings are interned: all BTC events share one str instance.
    btc_syms = {id(e.symbol) for e in out if e.source_id == 1}
    assert len(btc_syms) == 1


# --------------------------------------------------------------------------- 9. immutability


def test_event_and_payload_are_immutable():
    ev = Event(1, "BTCUSDT", SourceType.TRADES, 1, 0, TradePayload("buy", 1.0, 1.0, "x"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.timestamp = 5  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.payload.price = 9.0  # type: ignore[misc]


# --------------------------------------------------------------------------- 10. uneven / empty


def test_uneven_exhaustion_and_empty_sources():
    a = mem(1, "BTCUSDT", SourceType.TRADES, [trade(100), trade(110), trade(120)])
    b = mem(2, "BTCUSDT", SourceType.ORDER_BOOK, [book(105)])  # exhausts early
    empty = mem(3, "ETHUSDT", SourceType.TRADES, [])  # never contributes
    out = run([a, b, empty])
    assert [e.timestamp for e in out] == [100, 105, 110, 120]
    assert_monotonic(out)


def test_duplicate_source_id_rejected():
    a = mem(1, "BTCUSDT", SourceType.TRADES, [trade(1)])
    b = mem(1, "ETHUSDT", SourceType.TRADES, [trade(2)])
    with pytest.raises(ValueError):
        run([a, b])


# --------------------------------------------------------------------------- key-mode parity


def test_tuple_and_event_key_modes_agree():
    rows_a = [trade(t) for t in (100, 90, 300, 305, 700)]
    rows_b = [book(t) for t in (95, 200, 305, 650)]
    a1 = mem(1, "BTCUSDT", SourceType.TRADES, rows_a)
    b1 = mem(2, "BTCUSDT", SourceType.ORDER_BOOK, rows_b)
    out_tuple = run([a1, b1], tolerance_us=100, key_mode="tuple")
    a2 = mem(1, "BTCUSDT", SourceType.TRADES, rows_a)
    b2 = mem(2, "BTCUSDT", SourceType.ORDER_BOOK, rows_b)
    out_event = run([a2, b2], tolerance_us=100, key_mode="event")
    key = lambda e: (e.timestamp, int(e.source_type), e.source_id, e.seq)
    assert [key(e) for e in out_tuple] == [key(e) for e in out_event]
    assert_monotonic(out_tuple)


# --------------------------------------------------------------------------- file parser (needs pandas)


def _write_gz(path: str, header: str, rows: list[str]) -> None:
    with gzip.open(path, "wt", newline="") as fh:
        fh.write(header + "\n")
        for r in rows:
            fh.write(r + "\n")


def test_tardis_gzip_parser_roundtrip(tmp_path):
    pytest.importorskip("pandas")
    ob = os.path.join(tmp_path, "ob.csv.gz")
    tr = os.path.join(tmp_path, "tr.csv.gz")
    _write_gz(
        ob,
        "exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount",
        [
            "bybit,BTCUSDT,1000,1000,true,bid,100.5,2.0",
            "bybit,BTCUSDT,1300,1300,false,ask,101.0,0.0",
        ],
    )
    _write_gz(
        tr,
        "exchange,symbol,timestamp,local_timestamp,id,side,price,amount",
        [
            "bybit,BTCUSDT,1100,1100,abc,buy,100.7,0.5",
            "bybit,BTCUSDT,1400,1400,def,sell,100.9,1.5",
        ],
    )
    cfg = [
        SourceConfig(ob, SourceType.ORDER_BOOK, 1, "BTCUSDT"),
        SourceConfig(tr, SourceType.TRADES, 2, "BTCUSDT"),
    ]
    with EventDispatcher(cfg, tolerance_us=0, chunk_size=8) as d:
        out = list(d.replay())
    assert [e.timestamp for e in out] == [1000, 1100, 1300, 1400]
    assert isinstance(out[0].payload, OrderBookPayload)
    assert out[0].payload.is_snapshot is True
    assert out[1].payload.trade_id == "abc"
    assert_monotonic(out)
