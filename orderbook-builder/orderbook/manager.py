"""BookManager: routes dispatcher events to per-symbol OrderBookState instances."""
from __future__ import annotations

from typing import Optional

from .config import SymbolConfig
from .state import OrderBookState
from .types import EventLike, OrderBookPayloadLike, StorageMode


class BookManager:
    """One book per symbol, routed by ``Event.symbol``. Symbols are fully isolated.

    Consume the dispatcher's ``replay()`` and feed order-book events here::

        mgr = BookManager(mode=StorageMode.TOPN_CACHE, top_n=25,
                          configs={"BTCUSDT": SymbolConfig(tick_size=0.1, qty_step=0.001)})
        for event in dispatcher.replay():
            if event.source_type is SourceType.ORDER_BOOK:   # caller filters book events
                mgr.apply(event)
        book = mgr.get_state("BTCUSDT")

    Per the confirmed contract price/amount arrive already scaled (int), so ``apply`` does
    no scaling on the hot path; ``configs`` is used only for the read side (e.g. get_mid).
    """

    __slots__ = ("_states", "_configs", "mode", "top_n", "crossed_strict")

    def __init__(
        self,
        configs: Optional[dict[str, SymbolConfig]] = None,
        mode: StorageMode = StorageMode.FULL,
        top_n: int = 25,
        crossed_strict: bool = False,
    ) -> None:
        self._states: dict[str, OrderBookState] = {}
        self._configs: dict[str, SymbolConfig] = dict(configs) if configs else {}
        self.mode = mode
        self.top_n = top_n
        self.crossed_strict = crossed_strict

    def _state_for(self, symbol: str) -> OrderBookState:
        state = self._states.get(symbol)
        if state is None:
            state = OrderBookState(
                symbol,
                mode=self.mode,
                top_n=self.top_n,
                config=self._configs.get(symbol),
                crossed_strict=self.crossed_strict,
            )
            self._states[symbol] = state
        return state

    def apply(self, event: EventLike) -> OrderBookState:
        """Route one order-book event to its symbol's book and apply it. Returns the book."""
        state = self._state_for(event.symbol)
        state.apply_update(event.payload)
        return state

    def apply_payload(self, symbol: str, payload: OrderBookPayloadLike) -> OrderBookState:
        """Lower-level entry point when you already have (symbol, payload) split out."""
        state = self._state_for(symbol)
        state.apply_update(payload)
        return state

    def get_state(self, symbol: str) -> Optional[OrderBookState]:
        return self._states.get(symbol)

    def symbols(self) -> list[str]:
        return list(self._states)
