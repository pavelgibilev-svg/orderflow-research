"""Immutable, GC-friendly event + payload types.

Design constraints (HFT replay at 100M+ events):
- Event and every payload are ``@dataclass(frozen=True, slots=True)``: no per-instance
  ``__dict__`` (slots) keeps memory low and access fast; ``frozen`` makes them
  immutable so a strategy cannot accidentally mutate replayed market data.
- ``order`` is left at its default (False), so accidentally comparing two payloads /
  events raises ``TypeError`` loudly instead of silently mis-ordering the stream. The
  heap key is a tuple whose unique prefix means the payload/event is *never* compared.
- ``SourceType`` is the single source of truth for both the type tag and the
  tie-break priority at equal timestamps (lower value wins).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Union


class SourceType(enum.IntEnum):
    """Event source kind. The integer value doubles as the heap tie-break priority.

    Priority order at equal timestamps: ORDER_BOOK (0) < TRADES (1) < DERIVATIVE_TICKER (2),
    i.e. a book update at T is delivered before a trade at the same T, before a ticker.
    """

    ORDER_BOOK = 0
    TRADES = 1
    DERIVATIVE_TICKER = 2


@dataclass(frozen=True, slots=True)
class OrderBookPayload:
    """One L2 increment row (Tardis ``incremental_book_L2``). ``amount`` is the absolute
    resting size at ``price``; ``amount == 0`` means the level was removed."""

    side: str  # interned "bid" / "ask"
    price: float
    amount: float
    is_snapshot: bool


@dataclass(frozen=True, slots=True)
class TradePayload:
    """One market trade (Tardis ``trades``)."""

    side: str  # interned "buy" / "sell"
    price: float
    amount: float
    trade_id: str  # high-cardinality -> NOT interned


@dataclass(frozen=True, slots=True)
class TickerPayload:
    """One derivative ticker row (Tardis ``derivative_ticker``): OI + funding + marks."""

    open_interest: float
    funding_rate: float
    predicted_funding_rate: float
    mark_price: float
    index_price: float
    last_price: float
    funding_timestamp: int


Payload = Union[OrderBookPayload, TradePayload, TickerPayload]


@dataclass(frozen=True, slots=True)
class Event:
    """A single replayable market event.

    ``timestamp`` is the authoritative ordering clock (``local_timestamp`` in
    microseconds — what the recorder/strategy actually observed). ``seq`` is a LOCAL
    monotonic row counter within its source (never global — global read order is
    non-deterministic). ``symbol`` isolates events when several pairs are merged.
    """

    timestamp: int
    symbol: str
    source_type: SourceType
    source_id: int
    seq: int
    payload: Payload
