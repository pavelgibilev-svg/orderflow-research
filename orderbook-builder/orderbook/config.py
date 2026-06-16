"""Per-symbol scaling configuration."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SymbolConfig:
    """Scaling for one symbol.

    Under the confirmed contract price/amount already arrive as scaled ints, so the
    builder does NOT scale on the hot path. ``tick_size`` / ``qty_step`` are kept for the
    read side only: converting the (float) ``get_mid`` back to a real price, or any
    optional scaled<->real conversion a strategy wants. They are NEVER used as tree keys.
    """

    tick_size: float
    qty_step: float

    def price_to_real(self, scaled_price: int) -> float:
        """Scaled tick price -> real price (read side only)."""
        return scaled_price * self.tick_size

    def real_to_price(self, real_price: float) -> int:
        """Real price -> scaled tick price (only for an optional raw-ingest adapter)."""
        return round(real_price / self.tick_size)

    def qty_to_real(self, scaled_qty: int) -> float:
        """Scaled qty -> real qty (read side only)."""
        return scaled_qty * self.qty_step
