"""Source configuration. Extensible to N sources; priority is derived from type."""
from __future__ import annotations

from dataclasses import dataclass

from .events import SourceType


@dataclass(frozen=True, slots=True)
class SourceConfig:
    """One input file. ``source_id`` MUST be globally unique (it is the deterministic
    tie-break key between two files of equal type/priority — e.g. BTC-trades vs
    ETH-trades — so the heap never has to compare payloads)."""

    path: str
    source_type: SourceType
    source_id: int
    symbol: str

    @property
    def priority(self) -> int:
        """Tie-break priority at equal timestamps (lower wins). Derived from type."""
        return int(self.source_type)
