"""chrono_dispatcher — deterministic K-way event replay for an HFT backtester."""
from __future__ import annotations

from .config import SourceConfig
from .dispatcher import EventDispatcher
from .errors import ChronologyViolationError
from .events import (
    Event,
    OrderBookPayload,
    Payload,
    SourceType,
    TickerPayload,
    TradePayload,
)
from .sources import BaseSource, MemorySource, TardisGzipSource

__all__ = [
    "EventDispatcher",
    "SourceConfig",
    "SourceType",
    "Event",
    "OrderBookPayload",
    "TradePayload",
    "TickerPayload",
    "Payload",
    "BaseSource",
    "MemorySource",
    "TardisGzipSource",
    "ChronologyViolationError",
]
