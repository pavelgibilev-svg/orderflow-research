"""Standalone benchmark (NOT pytest): Mode A vs Mode B updates/sec + peak RSS.

Generates 1 snapshot + N deltas per symbol and replays through a BookManager in each
storage mode. Two workloads:
  * apply-only        — pure update throughput;
  * apply + top-N read — every K updates read the top-N (copy, and view in Mode B) to
    show the incremental numpy cache's read advantage while the FULL book stays the
    source of truth under the hood.

Run:  python -m benchmarks.bench_orderbook --updates 2_000_000 --symbols BTCUSDT,ETHUSDT --top-n 25
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
import time

from orderbook import BookManager, OrderBookPayload, OrderSide, StorageMode

# The hot path warns on missing-level deletes / crossed books; logging is far too slow to
# leave on inside a multi-million-update benchmark (and would dwarf the real work).
logging.getLogger("orderbook").setLevel(logging.ERROR)

BID = OrderSide.BID
ASK = OrderSide.ASK


def peak_rss_bytes() -> int:
    """Cross-platform peak RSS (best effort)."""
    try:
        import resource

        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return ru * 1024 if sys.platform == "linux" else ru
    except ImportError:
        pass
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        k32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        c = PMC()
        c.cb = ctypes.sizeof(c)
        if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return int(c.PeakWorkingSetSize)
    return 0


def build_stream(symbols, n_updates, depth, seed):
    """Pre-build (symbol, payload) tuples: a snapshot per symbol then random deltas.
    Built once and shared by both modes so generation cost is out of the timed loop."""
    rng = random.Random(seed)
    stream = []
    mid = 1_000_000
    for sym in symbols:
        for i in range(depth):  # snapshot bids below mid, asks above mid
            stream.append((sym, OrderBookPayload(mid - 1 - i, rng.randint(1, 500), BID, True)))
            stream.append((sym, OrderBookPayload(mid + 1 + i, rng.randint(1, 500), ASK, True)))
    per = max(1, n_updates // len(symbols))
    for sym in symbols:
        for _ in range(per):
            if rng.random() < 0.5:
                price = mid - 1 - rng.randint(0, depth + 50)
                side = BID
            else:
                price = mid + 1 + rng.randint(0, depth + 50)
                side = ASK
            amount = 0 if rng.random() < 0.3 else rng.randint(1, 500)
            stream.append((sym, OrderBookPayload(price, amount, side, False)))
    return stream


def run(stream, mode, top_n, reads_per_update):
    """reads_per_update == 0 -> apply-only. Else each update is followed by R top-N reads:
    Mode B uses the O(1) view path, Mode A must copy (O(n))."""
    mgr = BookManager(mode=mode, top_n=top_n)
    n = top_n
    use_view = mode == StorageMode.TOPN_CACHE
    t0 = time.perf_counter()
    if reads_per_update == 0:
        for sym, pl in stream:
            mgr.apply_payload(sym, pl)
    else:
        for sym, pl in stream:
            st = mgr.apply_payload(sym, pl)
            for _ in range(reads_per_update):
                if use_view:
                    st.get_top_bids_view(n)   # O(1) zero-copy view
                    st.get_top_asks_view(n)
                else:
                    st.get_top_bids(n)        # O(n) deep copy
                    st.get_top_asks(n)
    elapsed = time.perf_counter() - t0
    return len(stream), elapsed


def fmt_mb(b: int) -> str:
    return f"{b / (1024 * 1024):.0f} MB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--updates", type=lambda s: int(s.replace("_", "")), default=2_000_000)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument("--top-n", type=int, default=25)
    ap.add_argument("--depth", type=int, default=500)
    ap.add_argument("--reads-per-update", type=int, default=8,
                    help="top-N reads after each update in the read-heavy workload")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    print(f"Building stream: ~{args.updates:,} deltas, {len(symbols)} symbols, depth={args.depth}, top_n={args.top_n}")
    stream = build_stream(symbols, args.updates, args.depth, seed=7)
    print(f"Total events (snapshot + deltas): {len(stream):,}\n")

    workloads = [("apply-only", 0),
                 (f"apply + {args.reads_per_update} top-N reads/update (view vs copy)", args.reads_per_update)]
    for label, rpu in workloads:
        print(f"--- workload: {label} ---")
        res = {}
        for mode in (StorageMode.FULL, StorageMode.TOPN_CACHE):
            events, elapsed = run(stream, mode, args.top_n, rpu)
            ups = events / elapsed if elapsed else 0.0
            res[mode] = ups
            print(f"  [{mode.name:11}] {events:,} events  {elapsed:.2f}s  {ups:,.0f} updates/sec")
        a = res[StorageMode.FULL]
        b = res[StorageMode.TOPN_CACHE]
        if a and b:
            faster = "TOPN_CACHE" if b >= a else "FULL"
            print(f"  -> {faster} faster by {max(a, b) / min(a, b):.2f}x\n")

    print(f"Peak RSS: {fmt_mb(peak_rss_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
