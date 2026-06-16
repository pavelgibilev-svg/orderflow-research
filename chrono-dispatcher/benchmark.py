"""Standalone benchmark (NOT a pytest test).

Generates synthetic Tardis-style gzip-CSV for several sources/symbols, replays them
through the dispatcher, and reports events/sec, peak RSS and GC pause stats. Crucially
it runs BOTH heap-key strategies (tuple key vs Event.__lt__ wrapper) so the choice in
the spec is decided by measurement, not assumption.

Usage:
    python benchmark.py --rows 5_000_000 --symbols BTCUSDT,ETHUSDT --tolerance-us 2000
"""
from __future__ import annotations

import argparse
import gc
import gzip
import os
import random
import sys
import tempfile
import time
from collections.abc import Sequence

from chrono_dispatcher import EventDispatcher, SourceConfig, SourceType


# --------------------------------------------------------------------------- memory


def peak_rss_bytes() -> int:
    """Cross-platform peak resident set size (best effort)."""
    try:
        import resource  # Unix only

        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return ru * 1024 if sys.platform == "linux" else ru  # Linux KB, macOS bytes
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

        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        # GetCurrentProcess returns a 64-bit pseudo-handle (-1); without an explicit
        # restype ctypes truncates it to 32 bits and the call silently fails -> 0.
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        c = PMC()
        c.cb = ctypes.sizeof(c)
        if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return int(c.PeakWorkingSetSize)
        return 0
    return 0


# --------------------------------------------------------------------------- gc probe


class GCProbe:
    """Accumulate GC pause durations via gc.callbacks."""

    def __init__(self) -> None:
        self.pauses: list[float] = []
        self._t0: float | None = None

    def _cb(self, phase: str, info: dict) -> None:
        if phase == "start":
            self._t0 = time.perf_counter()
        elif self._t0 is not None:
            self.pauses.append(time.perf_counter() - self._t0)
            self._t0 = None

    def __enter__(self) -> "GCProbe":
        gc.callbacks.append(self._cb)
        return self

    def __exit__(self, *exc: object) -> None:
        gc.callbacks.remove(self._cb)


# --------------------------------------------------------------------------- synthetic data


def _gen_file(path: str, stype: SourceType, symbol: str, n: int, jitter_us: int, seed: int) -> None:
    rng = random.Random(seed)
    ts = 1_700_000_000_000_000  # microseconds
    with gzip.open(path, "wt", newline="") as fh:
        if stype is SourceType.ORDER_BOOK:
            fh.write("exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount\n")
        elif stype is SourceType.TRADES:
            fh.write("exchange,symbol,timestamp,local_timestamp,id,side,price,amount\n")
        else:
            fh.write("exchange,symbol,timestamp,local_timestamp,funding_timestamp,funding_rate,"
                     "predicted_funding_rate,open_interest,last_price,index_price,mark_price\n")
        for i in range(n):
            ts += rng.randint(1, 50)
            lt = ts + (rng.randint(-jitter_us, jitter_us) if jitter_us else 0)
            px = 43000 + rng.uniform(-50, 50)
            amt = rng.uniform(0.001, 5.0)
            if stype is SourceType.ORDER_BOOK:
                side = "bid" if i & 1 else "ask"
                snap = "false"
                fh.write(f"bybit,{symbol},{ts},{lt},{snap},{side},{px:.1f},{amt:.3f}\n")
            elif stype is SourceType.TRADES:
                side = "buy" if i & 1 else "sell"
                fh.write(f"bybit,{symbol},{ts},{lt},id{i},{side},{px:.1f},{amt:.3f}\n")
            else:
                fh.write(f"bybit,{symbol},{ts},{lt},{ts},0.0001,0.0001,{1e6+i},{px:.1f},{px:.1f},{px:.1f}\n")


def build_dataset(rows: int, symbols: Sequence[str], jitter_us: int, out_dir: str) -> list[SourceConfig]:
    types = [SourceType.ORDER_BOOK, SourceType.TRADES, SourceType.DERIVATIVE_TICKER]
    n_sources = len(symbols) * len(types)
    per = max(1, rows // n_sources)
    cfgs: list[SourceConfig] = []
    sid = 0
    for symbol in symbols:
        for stype in types:
            sid += 1
            # ticker is naturally sparse -> fewer rows
            n = per if stype is not SourceType.DERIVATIVE_TICKER else max(1, per // 20)
            path = os.path.join(out_dir, f"{symbol}_{stype.name.lower()}.csv.gz")
            _gen_file(path, stype, symbol, n, jitter_us, seed=sid)
            cfgs.append(SourceConfig(path, stype, sid, symbol))
    return cfgs


# --------------------------------------------------------------------------- run


def _run_once(cfgs: list[SourceConfig], tolerance_us: int, key_mode: str) -> tuple[int, float, GCProbe]:
    count = 0
    last_ts = -1
    probe = GCProbe()
    with probe:
        t0 = time.perf_counter()
        with EventDispatcher(cfgs, tolerance_us=tolerance_us, key_mode=key_mode) as d:
            for ev in d.replay():
                # minimal touch + cheap global-order assertion (no allocation)
                if ev.timestamp < last_ts:
                    raise AssertionError("global order violated")
                last_ts = ev.timestamp
                count += 1
        elapsed = time.perf_counter() - t0
    return count, elapsed, probe


def _fmt_mb(b: int) -> str:
    return f"{b / (1024 * 1024):.0f} MB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=lambda s: int(s.replace("_", "")), default=2_000_000)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument("--tolerance-us", type=int, default=2000)
    ap.add_argument("--jitter-us", type=int, default=500)
    ap.add_argument("--keep", action="store_true", help="keep generated data dir")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    tmp = tempfile.mkdtemp(prefix="chrono_bench_")
    print(f"Generating ~{args.rows:,} rows across {len(symbols)} symbols x 3 types -> {tmp}")
    cfgs = build_dataset(args.rows, symbols, args.jitter_us, tmp)
    total_bytes = sum(os.path.getsize(c.path) for c in cfgs)
    print(f"Sources: {len(cfgs)} files, {_fmt_mb(total_bytes)} gzip on disk")
    print(f"tolerance_us={args.tolerance_us}, jitter_us={args.jitter_us}\n")

    # Warm-up pass (discarded): equalises OS file cache + CPython allocator so neither
    # key mode gets an unfair advantage from running second.
    print("warm-up pass...")
    _run_once(cfgs, args.tolerance_us, "tuple")

    results = {}
    for key_mode in ("tuple", "event"):
        gc.collect()
        count, elapsed, probe = _run_once(cfgs, args.tolerance_us, key_mode)
        eps = count / elapsed if elapsed else 0.0
        results[key_mode] = (count, elapsed, eps, probe)
        print(f"[key_mode={key_mode:5}] events={count:,}  time={elapsed:.2f}s  "
              f"speed={eps:,.0f} ev/s  gc_pauses={len(probe.pauses)} "
              f"gc_total={sum(probe.pauses)*1000:.1f}ms gc_max={ (max(probe.pauses)*1000 if probe.pauses else 0):.2f}ms")

    print(f"\nPeak RSS: {_fmt_mb(peak_rss_bytes())}")

    t_eps = results["tuple"][2]
    e_eps = results["event"][2]
    if t_eps and e_eps:
        winner = "tuple" if t_eps >= e_eps else "event"
        ratio = max(t_eps, e_eps) / min(t_eps, e_eps)
        print(f"\nVERDICT: '{winner}' key is faster by {ratio:.2f}x "
              f"(tuple {t_eps:,.0f} vs event {e_eps:,.0f} ev/s). "
              f"Spec default is 'tuple'; switch only if 'event' wins materially here.")

    if not args.keep:
        for c in cfgs:
            try:
                os.remove(c.path)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
