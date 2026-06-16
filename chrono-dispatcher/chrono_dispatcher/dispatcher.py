"""EventDispatcher — deterministic K-way merge of many sources into one chrono stream.

K-way merge via a min-heap (``heapq``) holding exactly ONE head per source (K entries).
Default heap key is the tuple ``(timestamp, source_type, source_id, seq, event)``:
  * compared in C, fast for small K;
  * ``(source_id, seq)`` is globally unique AND each source has at most one head in the
    heap at a time, so two entries can never tie past ``source_id`` -> the ``event``
    (and its payload) is NEVER compared. ``Event``/payloads are ``order=False`` so any
    accidental comparison would raise ``TypeError`` (fail loud), not mis-order.

``key_mode="event"`` (a benchmark-only alternative) wraps events in ``_KeyedEvent`` with a
hand-written ``__lt__`` over the same chain — kept so the benchmark can prove which is
faster. Tuple key is the default per the spec; the benchmark decides empirically.
"""
from __future__ import annotations

import heapq
from collections.abc import Iterator, Sequence
from typing import Union

from .config import SourceConfig
from .events import Event
from .sources import BaseSource, TardisGzipSource, _JitterSource

SourceSpec = Union[SourceConfig, BaseSource]


class _KeyedEvent:
    """Heap wrapper for ``key_mode="event"``: manual ``__lt__`` over the tie-break chain."""

    __slots__ = ("event",)

    def __init__(self, event: Event) -> None:
        self.event = event

    def __lt__(self, other: "_KeyedEvent") -> bool:
        a = self.event
        b = other.event
        if a.timestamp != b.timestamp:
            return a.timestamp < b.timestamp
        if a.source_type != b.source_type:
            return a.source_type < b.source_type
        if a.source_id != b.source_id:
            return a.source_id < b.source_id
        return a.seq < b.seq


class EventDispatcher:
    """Merge multiple Tardis sources and replay events in strict chronological order.

    Usage::

        with EventDispatcher(sources_config, tolerance_us=2000) as d:
            for event in d.replay():
                ...

    ``sources_config`` items may be ``SourceConfig`` (file-backed, default) or already
    built ``BaseSource`` instances (used by tests). The dispatcher is a context manager
    and guarantees every file is closed on exit; ``replay()`` also closes on early break.
    """

    def __init__(
        self,
        sources_config: Sequence[SourceSpec],
        tolerance_us: int = 0,
        key_mode: str = "tuple",
        chunk_size: int = 50_000,
    ) -> None:
        if tolerance_us < 0:
            raise ValueError("tolerance_us must be >= 0")
        if key_mode not in ("tuple", "event"):
            raise ValueError("key_mode must be 'tuple' or 'event'")
        self.tolerance_us = tolerance_us
        self.key_mode = key_mode
        self.chunk_size = chunk_size
        self._specs = list(sources_config)
        self._sources: list[BaseSource] = []
        self._jitters: list[_JitterSource] = []
        self._jitter_by_id: dict[int, _JitterSource] = {}
        self._entered = False
        self._closed = False

    # ---- lifecycle ----

    def __enter__(self) -> "EventDispatcher":
        seen: set[int] = set()
        for spec in self._specs:
            if isinstance(spec, BaseSource):
                source: BaseSource = spec
            elif isinstance(spec, SourceConfig):
                source = TardisGzipSource(spec, chunk_size=self.chunk_size)
            else:  # pragma: no cover - defensive
                raise TypeError(f"source spec must be SourceConfig or BaseSource, got {type(spec)!r}")
            if source.source_id in seen:
                raise ValueError(f"duplicate source_id {source.source_id}")
            seen.add(source.source_id)
            self._sources.append(source)
            jitter = _JitterSource(source, self.tolerance_us)
            self._jitters.append(jitter)
            self._jitter_by_id[source.source_id] = jitter
        self._entered = True
        return self

    def __exit__(self, *exc_info: object) -> bool:
        self.close()
        return False

    def close(self) -> None:
        """Close every source exactly once (idempotent)."""
        if self._closed:
            return
        self._closed = True
        for source in self._sources:
            try:
                source.close()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass

    # ---- replay ----

    def replay(self) -> Iterator[Event]:
        """Yield events from all sources in strict chronological order."""
        if not self._entered:
            raise RuntimeError("EventDispatcher must be used as a context manager (use `with`)")
        if self.key_mode == "tuple":
            return self._replay_tuple()
        return self._replay_event()

    def _replay_tuple(self) -> Iterator[Event]:
        heap: list[tuple[int, int, int, int, Event]] = []
        jitter_by_id = self._jitter_by_id
        try:
            for jitter in self._jitters:
                ev = jitter.next_releasable()
                if ev is not None:
                    heap.append((ev.timestamp, ev.source_type, ev.source_id, ev.seq, ev))
            heapq.heapify(heap)
            while heap:
                _ts, _prio, _sid, _seq, ev = heapq.heappop(heap)
                yield ev
                nxt = jitter_by_id[ev.source_id].next_releasable()
                if nxt is not None:
                    heapq.heappush(
                        heap, (nxt.timestamp, nxt.source_type, nxt.source_id, nxt.seq, nxt)
                    )
        finally:
            self.close()

    def _replay_event(self) -> Iterator[Event]:
        heap: list[_KeyedEvent] = []
        jitter_by_id = self._jitter_by_id
        try:
            for jitter in self._jitters:
                ev = jitter.next_releasable()
                if ev is not None:
                    heap.append(_KeyedEvent(ev))
            heapq.heapify(heap)
            while heap:
                ev = heapq.heappop(heap).event
                yield ev
                nxt = jitter_by_id[ev.source_id].next_releasable()
                if nxt is not None:
                    heapq.heappush(heap, _KeyedEvent(nxt))
        finally:
            self.close()
