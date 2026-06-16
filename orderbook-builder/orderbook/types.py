"""Seam types for the L2 order-book builder.

These are the MINIMAL coupling types the builder depends on. The real dispatcher
substitutes its own ``Event`` / ``OrderBookPayload`` later — the builder only relies on
the attribute names declared by the Protocols below (structural typing), so no concrete
import of the dispatcher is needed.

Confirmed wire contract (scaled-int):
    price:  int  (real_price / tick_size)
    amount: int  (real_qty   / qty_step), amount == 0 => remove the level
    side:   OrderSide (BID=0, ASK=1)
    is_snapshot: bool
No update_id / seq on the payload (gap/STALE handling is a disabled hook, see state.py).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class OrderSide(enum.IntEnum):
    """Book side. Integer values match the wire contract."""

    BID = 0
    ASK = 1


class StorageMode(enum.IntEnum):
    """Storage backend selector (fixed in tests / chosen at BookManager init)."""

    FULL = 0  # Mode A: SortedDict only — correctness baseline.
    TOPN_CACHE = 1  # Mode B: SortedDict source-of-truth + synchronised numpy top-N cache.


@runtime_checkable
class OrderBookPayloadLike(Protocol):
    """Structural shape the builder consumes (scaled-int contract)."""

    price: int
    amount: int
    side: OrderSide
    is_snapshot: bool


@runtime_checkable
class EventLike(Protocol):
    """The builder only needs the symbol and the order-book payload off an Event."""

    symbol: str
    payload: OrderBookPayloadLike


# --- Concrete stubs (used by tests; real types come from the dispatcher) ---


@dataclass(frozen=True, slots=True)
class OrderBookPayload:
    """Stub payload matching the dispatcher contract (frozen + slots)."""

    price: int
    amount: int
    side: OrderSide
    is_snapshot: bool


@dataclass(frozen=True, slots=True)
class Event:
    """Stub Event: symbol + order-book payload."""

    symbol: str
    payload: OrderBookPayload


class CrossedBookError(RuntimeError):
    """Raised in strict mode when best_bid >= best_ask after an update."""

    def __init__(self, symbol: str, best_bid: int, best_ask: int) -> None:
        self.symbol = symbol
        self.best_bid = best_bid
        self.best_ask = best_ask
        super().__init__(
            f"Crossed book {symbol}: best_bid={best_bid} >= best_ask={best_ask}"
        )
