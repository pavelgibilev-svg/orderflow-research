"""Re-convert ONLY incremental_book_L2.csv.gz for Binance OOS days 2026-05-21..30
using the fixed convert_raw_depth_to_l2 (per-second re-seed from
orderbook_snapshots_1s.jsonl, interleaved with raw_depth_events diffs).

Why a focused driver: the original convert_oos_0521_30.py skips days that already
have output, and would also rewrite the (already correct) trades/book_ticker/
derivative_ticker/liquidations streams. Only the L2 book was corrupted by the
single-stale-seed bug, so we regenerate just that stream.

Streams the two needed JSONL members straight out of each OFFRW/<date>.zip (the
raw_depth_events member is ~1.9 GB uncompressed; we never extract it to disk).
Writes to a .tmp file then os.replace() so a crash never leaves a truncated L2.
Raw archives are untouched.

Usage:
  python reconvert_l2_0521_30.py --date 2026-05-23     # one day
  python reconvert_l2_0521_30.py --all                 # all of 21..30
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventory_audit_normalize_convert as conv

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
STAGE = ROOT / "data/binance-live-archives/staging/OFFRW_0521_30/OFFRW"
TARDIS_OUT = ROOT / "data/binance-historical/BTCUSDT"
OUT = ROOT / "reports/binance-oos"
OUT.mkdir(parents=True, exist_ok=True)
DATES = [f"2026-05-{d:02d}" for d in range(21, 31)]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def reconvert_one(date: str) -> dict:
    zpath = STAGE / f"{date}.zip"
    if not zpath.exists():
        return {"date": date, "status": "MISSING_ZIP"}
    snap_member = f"{date}/orderbook_snapshots_1s.jsonl"
    raw_member = f"{date}/raw_depth_events.jsonl"
    out = TARDIS_OUT / date / "incremental_book_L2.csv.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")

    print(f"[{date}] re-converting L2 from {zpath.name} ...", file=sys.stderr)
    t0 = time.time()
    # Open the zip twice so the two ZipExtFile streams have independent file
    # handles (concurrent reads from one ZipFile are not safe). heapq.merge inside
    # _emit_l2 pulls from both as it interleaves by timestamp.
    z_snap = zipfile.ZipFile(zpath)
    z_raw = zipfile.ZipFile(zpath)
    try:
        names = set(z_raw.namelist())
        if snap_member not in names or raw_member not in names:
            return {"date": date, "status": "MISSING_STREAMS",
                    "have_snap": snap_member in names, "have_raw": raw_member in names}
        with z_snap.open(snap_member) as sf, z_raw.open(raw_member) as rf:
            rep = conv._emit_l2(sf, rf, tmp)
    finally:
        z_snap.close()
        z_raw.close()

    os.replace(tmp, out)  # atomic swap over the old corrupted file
    rep["out_path"] = str(out)
    rep["out_size_bytes"] = out.stat().st_size
    rep["date"] = date
    rep["status"] = "RECONVERTED"
    rep["wall_s"] = round(time.time() - t0, 1)
    print(f"[{date}] done in {rep['wall_s']}s: {rep['snapshots_seeded']:,} snaps, "
          f"{rep['events_in']:,} diffs, {rep['rows_out']:,} rows, "
          f"{rep['out_size_bytes']/1e6:.0f}MB", file=sys.stderr)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="single date YYYY-MM-DD")
    ap.add_argument("--all", action="store_true", help="all of 2026-05-21..30")
    args = ap.parse_args()

    if args.date:
        targets = [args.date]
    elif args.all:
        targets = DATES
    else:
        print("ERROR: pass --date <YYYY-MM-DD> or --all", file=sys.stderr)
        return 2

    report = {"build_time_utc": now_iso(), "fix": "per-second re-seed from orderbook_snapshots_1s",
              "days": []}
    for d in targets:
        rep = reconvert_one(d)
        report["days"].append(rep)
        (OUT / "BINANCE_L2_RECONVERT_0521_30.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8")

    ok = [d for d in report["days"] if d.get("status") == "RECONVERTED"]
    report["flags"] = {
        "L2_RECONVERT_DONE": "YES" if ok else "NO",
        "DAYS_RECONVERTED": [d["date"] for d in ok],
        "ERRORS": [d for d in report["days"] if d.get("status") != "RECONVERTED"],
    }
    (OUT / "BINANCE_L2_RECONVERT_0521_30.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("RECONVERT DONE:", report["flags"]["DAYS_RECONVERTED"], file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
