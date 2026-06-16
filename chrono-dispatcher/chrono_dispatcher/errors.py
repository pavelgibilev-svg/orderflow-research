"""Error types raised by the dispatcher."""
from __future__ import annotations

from .events import SourceType


class ChronologyViolationError(RuntimeError):
    """Raised when a source emits a timestamp that is older than something already
    released, i.e. out of order beyond ``tolerance_us`` — an unrecoverable look-ahead
    risk. Includes the offending source, row index and the backward delta.
    """

    def __init__(
        self,
        *,
        source_id: int,
        symbol: str,
        source_type: SourceType,
        row_index: int,
        last_released_ts: int,
        timestamp: int,
        tolerance_us: int,
    ) -> None:
        self.source_id = source_id
        self.symbol = symbol
        self.source_type = source_type
        self.row_index = row_index
        self.last_released_ts = last_released_ts
        self.timestamp = timestamp
        self.tolerance_us = tolerance_us
        self.delta = last_released_ts - timestamp
        super().__init__(
            f"Chronology violation in source_id={source_id} symbol={symbol} "
            f"type={source_type.name} at row {row_index}: timestamp={timestamp} is "
            f"{self.delta}us older than already-released {last_released_ts} "
            f"(tolerance_us={tolerance_us}). Out-of-order beyond tolerance."
        )
