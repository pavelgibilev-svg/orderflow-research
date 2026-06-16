"""OrderBookState + storage backends (Mode A full / Mode B top-N numpy cache).

Source of truth in BOTH modes is the FULL book (one SortedDict per side, key=price int
-> value=amount int, natural ascending order). Mode B adds a fixed-length numpy cache of
the top-N levels per side that is kept in sync INCREMENTALLY (no full rebuild on deltas;
rebuild is allowed only when a snapshot block ends).

Complexity:
  - update: O(log L) into the SortedDict + O(N) worst-case in-place numpy shift (Mode B);
    the common "deep" update is an O(log N) early-skip that never touches the cache.
  - top read (copy): O(n) in both modes (allocates).
  - top read (view): O(1) in Mode B (read-only numpy view, valid until next apply_update).
"""
from __future__ import annotations

import logging
from itertools import islice
from typing import Optional

import numpy as np
from sortedcontainers import SortedDict

from .config import SymbolConfig
from .types import CrossedBookError, OrderBookPayloadLike, OrderSide, StorageMode

logger = logging.getLogger("orderbook")


class _Stats:
    """Lightweight counters for tests/observability (not in the hot path's inner loop)."""

    __slots__ = ("cache_rebuilds", "promotes", "missing_deletes", "crossed_count")

    def __init__(self) -> None:
        self.cache_rebuilds = 0
        self.promotes = 0
        self.missing_deletes = 0
        self.crossed_count = 0


class _Side:
    """One book side: a SortedDict (source of truth) + an optional numpy top-N cache.

    The cache stores a *searchsorted key* that is ascending for both sides: for asks the
    key is the price (ascending = best first); for bids the key is ``-price`` (ascending =
    highest price first). Index 0 is always the best level. On read the sign is restored.
    """

    __slots__ = ("side", "mode", "n", "sd", "_neg", "cache_key", "cache_amt", "count", "stats")

    def __init__(self, side: OrderSide, mode: StorageMode, n: int, stats: _Stats) -> None:
        self.side = side
        self.mode = mode
        self.n = n
        self.stats = stats
        self.sd: SortedDict = SortedDict()
        self._neg = side == OrderSide.BID
        if mode == StorageMode.TOPN_CACHE:
            self.cache_key = np.zeros(n, dtype=np.int64)
            self.cache_amt = np.zeros(n, dtype=np.int64)
        else:
            self.cache_key = None
            self.cache_amt = None
        self.count = 0

    # ---- key helpers ----
    def key_of(self, price: int) -> int:
        return -price if self._neg else price

    # ---- source-of-truth ops ----
    def clear(self) -> None:
        self.sd.clear()
        self.count = 0

    def best(self) -> Optional[tuple[int, int]]:
        """(price, amount) of the best level, or None. From the SortedDict (always correct)."""
        if not self.sd:
            return None
        return self.sd.peekitem(-1 if self._neg else 0)  # bid: highest=last, ask: lowest=first

    def level_at_rank(self, rank: int) -> tuple[int, int]:
        """rank-th best level (0=best) via O(log L) indexed access — no full scan."""
        if self._neg:
            return self.sd.peekitem(len(self.sd) - 1 - rank)
        return self.sd.peekitem(rank)

    # ---- cache maintenance (Mode B) ----
    def rebuild_cache(self) -> None:
        """Full rebuild of the top-N cache from the SortedDict. Allowed only after a
        snapshot block (counted in stats.cache_rebuilds)."""
        if self.mode != StorageMode.TOPN_CACHE:
            return
        sd = self.sd
        n = self.n
        length = len(sd)
        cnt = min(n, length)
        self.count = cnt
        ck = self.cache_key
        ca = self.cache_amt
        if self._neg:  # bids: top = highest prices (tail of the tree)
            for i in range(cnt):
                p, a = sd.peekitem(length - 1 - i)
                ck[i] = -p
                ca[i] = a
        else:  # asks: top = lowest prices (head of the tree)
            for i, (p, a) in enumerate(islice(sd.items(), cnt)):
                ck[i] = p
                ca[i] = a

    def cache_upsert(self, k: int, amount: int) -> None:
        """Incrementally reflect an upsert (price already in SortedDict) into the cache."""
        ck = self.cache_key
        ca = self.cache_amt
        n = self.n
        cnt = self.count
        pos = int(np.searchsorted(ck[:cnt], k)) if cnt else 0
        if pos < cnt and ck[pos] == k:
            ca[pos] = amount  # pure volume change at a cached level — O(1)
            return
        if cnt == n and pos >= n:
            return  # worse than the worst cached level and cache is full -> EARLY SKIP
        if cnt < n:  # room: shift [pos:cnt] right, insert
            if cnt > pos:
                ck[pos + 1 : cnt + 1] = ck[pos:cnt]
                ca[pos + 1 : cnt + 1] = ca[pos:cnt]
            ck[pos] = k
            ca[pos] = amount
            self.count = cnt + 1
        else:  # full: insert at pos, the old worst (index n-1) drops out of the window
            if pos < n - 1:
                ck[pos + 1 : n] = ck[pos : n - 1]
                ca[pos + 1 : n] = ca[pos : n - 1]
            ck[pos] = k
            ca[pos] = amount  # count stays n

    def cache_delete(self, k: int) -> None:
        """Incrementally reflect a delete (price already removed from SortedDict), promoting
        the next-best deep level into the freed top-N slot if the side has more depth."""
        ck = self.cache_key
        ca = self.cache_amt
        n = self.n
        cnt = self.count
        if cnt == 0:
            return
        pos = int(np.searchsorted(ck[:cnt], k))
        if not (pos < cnt and ck[pos] == k):
            return  # deeper than the cached window -> nothing cached to remove (EARLY SKIP)
        if pos < cnt - 1:  # close the gap
            ck[pos : cnt - 1] = ck[pos + 1 : cnt]
            ca[pos : cnt - 1] = ca[pos + 1 : cnt]
        self.count = cnt - 1
        length = len(self.sd)
        if self.count < n and length > self.count:  # PROMOTE the next-best uncached level
            p, a = self.level_at_rank(self.count)  # O(log L)
            ck[self.count] = self.key_of(p)
            ca[self.count] = a
            self.count += 1
            self.stats.promotes += 1

    # ---- reads ----
    def top_copy(self, requested: int) -> list[tuple[int, int]]:
        """Deep copy of the top levels (best first). Mode B reads the cache; Mode A the tree."""
        if self.mode == StorageMode.TOPN_CACHE:
            m = min(requested, self.count)
            ck = self.cache_key
            ca = self.cache_amt
            if self._neg:
                return [(int(-ck[i]), int(ca[i])) for i in range(m)]
            return [(int(ck[i]), int(ca[i])) for i in range(m)]
        # Mode A: from the SortedDict.
        sd = self.sd
        length = len(sd)
        m = min(requested, length)
        if self._neg:  # bids descending: highest first
            return [sd.peekitem(length - 1 - i) for i in range(m)]
        return list(islice(sd.items(), m))  # asks ascending: lowest first

    def top_view(self, requested: int) -> tuple[np.ndarray, np.ndarray]:
        """Read-only O(1) numpy views (Mode B only). Returns (prices_key, amounts).

        NOTE: for BIDS ``prices_key`` holds the cache key, i.e. ``-real_price`` (the only
        place the sign is not auto-restored, because a zero-copy view cannot negate).
        Negate it for real bid prices, or use ``top_copy`` for ergonomic real prices.
        Valid ONLY until the next apply_update on this side.
        """
        if self.mode != StorageMode.TOPN_CACHE:
            raise RuntimeError("views require StorageMode.TOPN_CACHE")
        m = min(requested, self.count)
        pv = self.cache_key[:m]
        av = self.cache_amt[:m]
        pv.flags.writeable = False
        av.flags.writeable = False
        return pv, av


class OrderBookState:
    """Mutable per-symbol L2 book. All updates are strictly in-place."""

    __slots__ = (
        "symbol", "mode", "n", "config", "crossed_strict",
        "_bid", "_ask", "_prev_was_snapshot", "_cache_dirty", "stale", "stats",
    )

    def __init__(
        self,
        symbol: str,
        mode: StorageMode = StorageMode.FULL,
        top_n: int = 25,
        config: Optional[SymbolConfig] = None,
        crossed_strict: bool = False,
    ) -> None:
        self.symbol = symbol
        self.mode = mode
        self.n = top_n
        self.config = config
        self.crossed_strict = crossed_strict
        self.stats = _Stats()
        self._bid = _Side(OrderSide.BID, mode, top_n, self.stats)
        self._ask = _Side(OrderSide.ASK, mode, top_n, self.stats)
        self._prev_was_snapshot = False
        self._cache_dirty = False
        self.stale = False

    # ------------------------------------------------------------------ write

    def apply_update(self, payload: OrderBookPayloadLike) -> None:
        """Deterministic state machine for one L2 increment (scaled-int contract)."""
        side = self._bid if payload.side == OrderSide.BID else self._ask
        price = payload.price
        amount = payload.amount

        if payload.is_snapshot:
            if not self._prev_was_snapshot:  # first row of a new snapshot block -> reset
                self._bid.clear()
                self._ask.clear()
                self.stale = False
            self._prev_was_snapshot = True
            # Fill the SortedDict; defer the (single) cache rebuild to end-of-block.
            if amount == 0:
                side.sd.pop(price, None)
            else:
                side.sd[price] = amount
            self._cache_dirty = True
            return

        # First non-snapshot row after a snapshot block closes the block: rebuild once.
        if self._prev_was_snapshot:
            self._prev_was_snapshot = False
            self._ensure_cache_synced()

        # Gap/STALE hook (disabled: payload carries no update_id/seq). When seq is added,
        # check monotonicity here and call self._mark_stale() on a gap.

        if amount == 0:  # delete
            if price in side.sd:
                del side.sd[price]
                if self.mode == StorageMode.TOPN_CACHE:
                    side.cache_delete(side.key_of(price))
            else:
                self.stats.missing_deletes += 1
                logger.warning(
                    "delete of missing level symbol=%s price=%d side=%s",
                    self.symbol, price, payload.side.name,
                )
                return  # nothing changed -> no crossed-check needed
        else:  # upsert
            side.sd[price] = amount
            if self.mode == StorageMode.TOPN_CACHE:
                side.cache_upsert(side.key_of(price), amount)

        self._check_crossed()

    def _ensure_cache_synced(self) -> None:
        """Rebuild the top-N cache from the SortedDict if it was left dirty by a snapshot."""
        if self._cache_dirty and self.mode == StorageMode.TOPN_CACHE:
            self._bid.rebuild_cache()
            self._ask.rebuild_cache()
            self.stats.cache_rebuilds += 1
        self._cache_dirty = False

    def _check_crossed(self) -> None:
        bb = self._bid.best()
        ba = self._ask.best()
        if bb is None or ba is None:
            return
        if bb[0] >= ba[0]:
            self.stats.crossed_count += 1
            if self.crossed_strict:
                raise CrossedBookError(self.symbol, bb[0], ba[0])
            logger.warning(
                "crossed book symbol=%s best_bid=%d best_ask=%d", self.symbol, bb[0], ba[0]
            )

    # ------------------------------------------------------------------ read

    def get_top_bids(self, n: int) -> list[tuple[int, int]]:
        """Deep copy of the top ``n`` bids, descending. O(n)."""
        if self.mode == StorageMode.TOPN_CACHE:
            self._ensure_cache_synced()
        return self._bid.top_copy(n)

    def get_top_asks(self, n: int) -> list[tuple[int, int]]:
        """Deep copy of the top ``n`` asks, ascending. O(n)."""
        if self.mode == StorageMode.TOPN_CACHE:
            self._ensure_cache_synced()
        return self._ask.top_copy(n)

    def get_top_bids_view(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Read-only numpy views of the top ``n`` bids (Mode B only). O(1). See _Side.top_view."""
        self._ensure_cache_synced()
        return self._bid.top_view(n)

    def get_top_asks_view(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Read-only numpy views of the top ``n`` asks (Mode B only). O(1)."""
        self._ensure_cache_synced()
        return self._ask.top_view(n)

    def get_best_bid(self) -> Optional[tuple[int, int]]:
        return self._bid.best()

    def get_best_ask(self) -> Optional[tuple[int, int]]:
        return self._ask.best()

    def get_mid(self) -> Optional[float]:
        """Mid price as float — the ONLY sanctioned float (derived, never re-enters the book).
        Real price if a SymbolConfig is attached, else scaled (tick units). None if a side is empty."""
        bb = self._bid.best()
        ba = self._ask.best()
        if bb is None or ba is None:
            return None
        half = (bb[0] + ba[0]) / 2.0
        return half * self.config.tick_size if self.config is not None else half

    def get_mid_x2(self) -> Optional[int]:
        """best_bid + best_ask (scaled int, no float). None if a side is empty."""
        bb = self._bid.best()
        ba = self._ask.best()
        if bb is None or ba is None:
            return None
        return bb[0] + ba[0]

    def get_spread(self) -> Optional[int]:
        """best_ask - best_bid (scaled int). None if a side is empty."""
        bb = self._bid.best()
        ba = self._ask.best()
        if bb is None or ba is None:
            return None
        return ba[0] - bb[0]

    # ------------------------------------------------------------------ depth helpers

    def bid_depth(self) -> int:
        return len(self._bid.sd)

    def ask_depth(self) -> int:
        return len(self._ask.sd)
