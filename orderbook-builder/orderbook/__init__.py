"""orderbook — local L2 order-book builder (consumer of EventDispatcher events)."""
from __future__ import annotations

from .config import SymbolConfig
from .manager import BookManager
from .state import OrderBookState
from .types import (
    CrossedBookError,
    Event,
    EventLike,
    OrderBookPayload,
    OrderBookPayloadLike,
    OrderSide,
    StorageMode,
)

__all__ = [
    "BookManager",
    "OrderBookState",
    "SymbolConfig",
    "OrderSide",
    "StorageMode",
    "OrderBookPayload",
    "Event",
    "OrderBookPayloadLike",
    "EventLike",
    "CrossedBookError",
]
