#!/usr/bin/env python3
"""
emit_snapshots_jsonl.py  --  Stage 1 bridge: 1-second L2 snapshots as JSONL.

Reconstructs the Bybit ob200 PERP book (reusing book_reconstruction.replay,
READ-ONLY — this script does NOT modify book_reconstruction.py) and writes one
JSON object per second in the SAME shape the TS engine's exportSnapshots.ts
emits. With this, Participant A can add a minimal JSONL loader and run
exportZoneFeatures on our 8 Bybit days without a native Bybit ob200 loader.

Line format (top-`depth` levels per side):
  {"ts": <ms>, "isoTs": "...Z", "bestBid": .., "bestAsk": .., "mid": ..,
   "bids": [[price, size], ... desc], "asks": [[price, size], ... asc]}

Output: <DATA_BYBIT>/derived/snapshots_jsonl/snapshots_BTCUSDT_<date>.jsonl
        (<DATA_BYBIT> = DATA_BYBIT_DIR env, default external data dir; not in repo)

Deps: numpy + book_reconstruction (stdlib json). No new dependency.

Run:  python emit_snapshots_jsonl.py
      python emit_snapshots_jsonl.py --depth 50 --dates 2025-10-10,2025-10-11
      python emit_snapshots_jsonl.py --output-dir DIR --max-seconds 120   (smoke)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import book_reconstruction as br  # noqa: E402  (read-only reuse of replay/resolve_zip)

DATA_BYBIT_ROOT = Path(os.environ.get("DATA_BYBIT_DIR", r"C:\orderflow-recoder module\data_bybit"))

CONFIG = {
    "INPUT_DIR_ENV": "DATA_BYBIT_DIR",
    "INPUT_DIR": str(DATA_BYBIT_ROOT),                       # dir holding <date>_BTCUSDT_ob200.data.zip
    "OUTPUT_DIR": str(DATA_BYBIT_ROOT / "derived" / "snapshots_jsonl"),
    "SYMBOL": "BTCUSDT",
    "DATE_LIST": ["2025-10-10", "2025-10-11", "2025-10-12",
                  "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06"],
    "GRID_SECONDS": 1,
    "DEPTH": 50,
}


def _iso(ts_ms: int) -> str:
    return (datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            .isoformat(timespec="milliseconds").replace("+00:00", "Z"))


def _side_levels(prices: np.ndarray, sizes: np.ndarray, depth: int, descending: bool):
    """Top-`depth` [price, size] pairs (size > 0), sorted by price."""
    order = np.argsort(prices, kind="stable")
    if descending:
        order = order[::-1]
    out = []
    for i in order:
        s = float(sizes[i])
        if s > 0.0:
            out.append([float(prices[i]), s])
            if len(out) >= depth:
                break
    return out


def emit_snapshots_for_day(date_str: str, input_dir: str, output_dir: str,
                           depth: int, grid_sec: int, max_seconds=None):
    try:
        zip_path = br.resolve_zip(Path(input_dir), date_str, "perp")
    except FileNotFoundError:
        print(f"[emit_jsonl] WARNING: no perp ob200 for {date_str} -> skipped", file=sys.stderr)
        return None

    out_dir = Path(output_dir); out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"snapshots_{CONFIG['SYMBOL']}_{date_str}.jsonl"

    n = skipped = 0
    first_ts = last_ts = None
    with out_path.open("w", encoding="utf-8") as fh:
        for ts, bb, ba, bid_p, bid_s, ask_p, ask_s, _ in br.replay(
                zip_path, interval_ms=grid_sec * 1000, max_seconds=max_seconds):
            if not (np.isfinite(bb) and np.isfinite(ba)):
                skipped += 1                                  # empty / one-sided book
                continue
            if not (bb < ba):
                print(f"[emit_jsonl] ERROR: crossed book at ts={ts} ({_iso(ts)}): "
                      f"bestBid {bb} >= bestAsk {ba}", file=sys.stderr)
                raise ValueError(f"crossed book at ts={ts}")
            bids = _side_levels(bid_p, bid_s, depth, descending=True)
            asks = _side_levels(ask_p, ask_s, depth, descending=False)
            if not bids or not asks:
                skipped += 1
                continue
            if bids[0][0] != bb or asks[0][0] != ba:
                print(f"[emit_jsonl] ERROR: top-level mismatch at ts={ts}: "
                      f"bids[0]={bids[0][0]} vs bestBid {bb}; asks[0]={asks[0][0]} vs bestAsk {ba}",
                      file=sys.stderr)
                raise ValueError(f"top-level mismatch at ts={ts}")
            obj = {"ts": int(ts), "isoTs": _iso(ts),
                   "bestBid": float(bb), "bestAsk": float(ba), "mid": float((bb + ba) / 2.0),
                   "bids": bids, "asks": asks}
            fh.write(json.dumps(obj) + "\n")
            n += 1
            if first_ts is None:
                first_ts = int(ts)
            last_ts = int(ts)

    if skipped:
        print(f"[emit_jsonl]   {date_str}: skipped {skipped} empty/one-sided snapshots", file=sys.stderr)
    size = out_path.stat().st_size
    print(f"[emit_jsonl] Processing {date_str}... {n} snapshots -> {size / 1e6:.1f} MB", file=sys.stderr)
    return {"date": date_str, "n_snapshots": n, "file_size_bytes": size,
            "first_ts": first_ts, "last_ts": last_ts, "path": str(out_path)}


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Emit 1s L2 snapshots as JSONL (exportSnapshots.ts format).")
    ap.add_argument("--depth", type=int, default=CONFIG["DEPTH"])
    ap.add_argument("--dates", default=None, help="comma list; default = all 8 CONFIG dates")
    ap.add_argument("--input-dir", default=CONFIG["INPUT_DIR"])
    ap.add_argument("--output-dir", default=CONFIG["OUTPUT_DIR"])
    ap.add_argument("--max-seconds", type=int, default=None, help="cap per day (smoke runs)")
    args = ap.parse_args(argv)
    dates = [d.strip() for d in args.dates.split(",")] if args.dates else CONFIG["DATE_LIST"]

    print(f"[emit_jsonl] Symbol: {CONFIG['SYMBOL']}, depth={args.depth}, grid={CONFIG['GRID_SECONDS']}s", file=sys.stderr)
    print(f"[emit_jsonl] Input dir:  {args.input_dir}", file=sys.stderr)
    print(f"[emit_jsonl] Output dir: {args.output_dir}", file=sys.stderr)

    results = []
    for d in dates:
        r = emit_snapshots_for_day(d, args.input_dir, args.output_dir, args.depth,
                                   CONFIG["GRID_SECONDS"], args.max_seconds)
        if r:
            results.append(r)

    total_snaps = sum(r["n_snapshots"] for r in results)
    total_bytes = sum(r["file_size_bytes"] for r in results)
    avg = total_snaps / len(results) if results else 0
    print(f"\n[emit_jsonl] DONE. {len(results)} dates, {total_snaps} snapshots total, "
          f"~{total_bytes / 1e9:.2f} GB on disk (avg {avg:.0f}/day).", file=sys.stderr)
    print(json.dumps({"dates": len(results), "total_snapshots": total_snaps,
                      "total_bytes": total_bytes, "avg_per_day": round(avg, 1)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
