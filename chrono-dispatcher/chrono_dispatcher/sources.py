"""Source layer: event producers + the per-source jitter watermark buffer.

A ``BaseSource`` produces ``Event``s in *file order* with a LOCAL monotonic ``seq``.
``_JitterSource`` wraps one source and:
  * buffers events in a tiny min-heap keyed by (timestamp, seq),
  * releases an event T to the global merge ONLY once the source has read past
    ``T + tolerance_us`` (watermark), so jitter (locally swapped near-equal timestamps)
    is re-sorted and nothing is emitted before it is safe (no look-ahead),
  * AGGRESSIVELY refills: it keeps pulling rows while the oldest buffered event is not
    yet safe, until either the window closes or EOF — a sparse source with a long pause
    in the file can never deadlock the merge,
  * drains fully on EOF (tail preserved),
  * raises ``ChronologyViolationError`` on a hard backward jump beyond tolerance.

The parser is format-specific (Tardis gzip-CSV here) and isolated from the merge core.
"""
from __future__ import annotations

import abc
import heapq
import sys
from collections.abc import Iterable, Iterator
from typing import Optional

from .config import SourceConfig
from .errors import ChronologyViolationError
from .events import (
    Event,
    OrderBookPayload,
    Payload,
    SourceType,
    TickerPayload,
    TradePayload,
)


def _intern(value: object) -> object:
    """Intern repeated short strings (symbol/side) so 100M rows share one instance."""
    return sys.intern(value) if type(value) is str else value


class BaseSource(abc.ABC):
    """A producer of events in file order. Subclasses assign a LOCAL monotonic ``seq``."""

    source_id: int
    symbol: str
    source_type: SourceType

    @abc.abstractmethod
    def iter_events(self) -> Iterator[Event]:
        """Yield events in the order they appear in the underlying file/stream."""

    def close(self) -> None:  # pragma: no cover - default no-op
        """Release any held resource (file handles). Must be idempotent."""


class MemorySource(BaseSource):
    """In-memory source for tests/benchmarks. ``rows`` is an iterable of
    ``(timestamp:int, payload)``; ``seq`` is assigned as the local row index."""

    def __init__(
        self,
        source_id: int,
        symbol: str,
        source_type: SourceType,
        rows: Iterable[tuple[int, Payload]],
    ) -> None:
        self.source_id = source_id
        self.symbol = sys.intern(symbol)
        self.source_type = source_type
        self._rows = list(rows)
        self.close_calls = 0  # spy hook for the early-break test

    def iter_events(self) -> Iterator[Event]:
        st = self.source_type
        sid = self.source_id
        sym = self.symbol
        for seq, (ts, payload) in enumerate(self._rows):
            yield Event(int(ts), sym, st, sid, seq, payload)

    def close(self) -> None:
        self.close_calls += 1


class TardisGzipSource(BaseSource):
    """Block-read + vectorised parse of a Tardis gzip-CSV file (one type per file).

    Ordering clock is ``local_timestamp`` (microseconds). Parsing reads ~``chunk_size``
    rows per block via pandas, extracts columns to flat lists with ``.tolist()`` and
    iterates them together with ``zip`` — never ``iterrows``/``iloc``/``to_dict``.
    """

    # Column maps. To adapt to a different header, change ONLY these.
    _TS_COL = "local_timestamp"

    def __init__(self, config: SourceConfig, chunk_size: int = 50_000) -> None:
        self.config = config
        self.source_id = config.source_id
        self.symbol = sys.intern(config.symbol)
        self.source_type = config.source_type
        self.chunk_size = chunk_size
        self._reader = None  # pandas TextFileReader (closeable)

    def iter_events(self) -> Iterator[Event]:
        import pandas as pd  # lazy: the merge core / memory tests need no pandas

        st = self.source_type
        if st is SourceType.ORDER_BOOK:
            usecols = [self._TS_COL, "side", "price", "amount", "is_snapshot"]
        elif st is SourceType.TRADES:
            usecols = [self._TS_COL, "side", "price", "amount", "id"]
        elif st is SourceType.DERIVATIVE_TICKER:
            usecols = [
                self._TS_COL, "funding_timestamp", "funding_rate", "predicted_funding_rate",
                "open_interest", "last_price", "index_price", "mark_price",
            ]
        else:  # pragma: no cover - defensive
            raise ValueError(f"unknown source_type {st!r}")

        reader = pd.read_csv(
            self.config.path, compression="gzip", usecols=usecols, chunksize=self.chunk_size,
        )
        self._reader = reader
        sid = self.source_id
        sym = self.symbol
        seq = 0
        for chunk in reader:
            ts_list = chunk[self._TS_COL].to_numpy().tolist()
            if st is SourceType.ORDER_BOOK:
                side_list = chunk["side"].tolist()
                price_list = chunk["price"].tolist()
                amount_list = chunk["amount"].tolist()
                # pandas may parse "true"/"false" as real bool OR keep them as strings;
                # normalise both in one pass.
                snap_list = [
                    v is True or (type(v) is str and v.lower() == "true")
                    for v in chunk["is_snapshot"].tolist()
                ]
                for ts_i, side_i, price_i, amount_i, snap_i in zip(
                    ts_list, side_list, price_list, amount_list, snap_list
                ):
                    payload = OrderBookPayload(_intern(side_i), price_i, amount_i, snap_i)
                    yield Event(ts_i, sym, st, sid, seq, payload)
                    seq += 1
            elif st is SourceType.TRADES:
                side_list = chunk["side"].tolist()
                price_list = chunk["price"].tolist()
                amount_list = chunk["amount"].tolist()
                id_list = chunk["id"].tolist()
                for ts_i, side_i, price_i, amount_i, id_i in zip(
                    ts_list, side_list, price_list, amount_list, id_list
                ):
                    payload = TradePayload(_intern(side_i), price_i, amount_i, id_i)
                    yield Event(ts_i, sym, st, sid, seq, payload)
                    seq += 1
            else:  # DERIVATIVE_TICKER
                ft_list = chunk["funding_timestamp"].tolist()
                fr_list = chunk["funding_rate"].tolist()
                pfr_list = chunk["predicted_funding_rate"].tolist()
                oi_list = chunk["open_interest"].tolist()
                lp_list = chunk["last_price"].tolist()
                ip_list = chunk["index_price"].tolist()
                mp_list = chunk["mark_price"].tolist()
                for ts_i, ft_i, fr_i, pfr_i, oi_i, lp_i, ip_i, mp_i in zip(
                    ts_list, ft_list, fr_list, pfr_list, oi_list, lp_list, ip_list, mp_list
                ):
                    ft = int(ft_i) if isinstance(ft_i, (int, float)) and ft_i == ft_i else 0
                    payload = TickerPayload(oi_i, fr_i, pfr_i, mp_i, ip_i, lp_i, ft)
                    yield Event(ts_i, sym, st, sid, seq, payload)
                    seq += 1

    def close(self) -> None:
        if self._reader is not None:
            try:
                self._reader.close()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
            self._reader = None


class _JitterSource:
    """Per-source watermark buffer. Hands ``next_releasable()`` to the global merge."""

    __slots__ = (
        "_source", "_it", "tolerance_us", "_buf",
        "_max_read_ts", "_eof", "_last_released", "_row_index",
    )

    def __init__(self, source: BaseSource, tolerance_us: int) -> None:
        self._source = source
        self._it = source.iter_events()
        self.tolerance_us = tolerance_us
        self._buf: list[tuple[int, int, Event]] = []  # min-heap by (timestamp, seq)
        self._max_read_ts = -1
        self._eof = False
        self._last_released: Optional[int] = None
        self._row_index = -1  # index of the last row pulled from the source

    def _pull_one(self) -> bool:
        """Pull one row into the buffer. Returns False at EOF. Raises on hard violation."""
        try:
            ev = next(self._it)
        except StopIteration:
            self._eof = True
            return False
        self._row_index += 1
        ts = ev.timestamp
        if self._last_released is not None and ts < self._last_released:
            raise ChronologyViolationError(
                source_id=self._source.source_id,
                symbol=self._source.symbol,
                source_type=self._source.source_type,
                row_index=self._row_index,
                last_released_ts=self._last_released,
                timestamp=ts,
                tolerance_us=self.tolerance_us,
            )
        if ts > self._max_read_ts:
            self._max_read_ts = ts
        heapq.heappush(self._buf, (ts, ev.seq, ev))
        return True

    def next_releasable(self) -> Optional[Event]:
        """Return the next safe-to-emit event, or None when the source is exhausted.

        Aggressively reads more rows while the oldest buffered event is still inside the
        jitter window (``max_read - min < tolerance``), until the window closes or EOF.
        """
        while True:
            if self._buf:
                min_ts = self._buf[0][0]
                if self._eof or (self._max_read_ts - min_ts) >= self.tolerance_us:
                    _ts, _seq, ev = heapq.heappop(self._buf)
                    self._last_released = ev.timestamp
                    return ev
                self._pull_one()  # window still open -> refill (may hit EOF; loop re-checks)
            else:
                if self._eof:
                    return None
                self._pull_one()
