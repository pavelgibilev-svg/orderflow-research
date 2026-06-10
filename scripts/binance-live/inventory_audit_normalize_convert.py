"""End-to-end pipeline for Binance live-recorder archives:
  1. Inventory + SHA256 of raw archives.
  2. Audit per-day coverage (first/last event_time from each JSONL stream).
  3. Normalize 4 days into data/binance-live-normalized/binance-futures/BTCUSDT/<date>/
     - merge 2026-05-18 part1 (before 16:13:35.858Z) + part2 (from 16:13:35.858Z)
     - copy 17/19/20 from their single source.
  4. Convert each day to Tardis CSV.gz under data/binance-historical/BTCUSDT/<date>/
     so `npm run backtest:day --exchange binance-futures` consumes them unchanged.

NO strategy / threshold / engine change. NO new backtest spawned here.
Raw archives in data/binance-live-archives/raw/ are preserved untouched.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import heapq
import io
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
STAGING = ROOT / "data/binance-live-archives/staging"
RAW = ROOT / "data/binance-live-archives/raw"
NORM = ROOT / "data/binance-live-normalized/binance-futures/BTCUSDT"
TARDIS_OUT = ROOT / "data/binance-historical/BTCUSDT"
REPORTS = ROOT / "reports/binance-live"
REPORTS.mkdir(parents=True, exist_ok=True)

# Stream files (always present)
JSONL_STREAMS = [
    "raw_depth_events.jsonl",
    "trades.jsonl",
    "book_ticker.jsonl",
    "mark_price.jsonl",
    "liquidations.jsonl",
    "orderbook_snapshots_1s.jsonl",
    "health.jsonl",
]

DATES = ["2026-05-17", "2026-05-18", "2026-05-19", "2026-05-20"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ms_to_iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="milliseconds")


def stream_first_last(path: Path, ts_field: str = "event_time") -> tuple[int | None, int | None, int]:
    """Return (first_ts_ms, last_ts_ms, line_count). Streams the file once."""
    first = None
    last = None
    n = 0
    if not path.exists() or path.stat().st_size == 0:
        return None, None, 0
    with path.open("rb") as f:
        for line in f:
            n += 1
            if not line.strip():
                continue
            try:
                j = json.loads(line)
            except Exception:
                continue
            v = j.get(ts_field) or j.get("ts")
            if v is None:
                continue
            if first is None:
                first = int(v)
            last = int(v)
    return first, last, n


def stream_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    n = 0
    with path.open("rb") as f:
        for _ in f:
            n += 1
    return n


# ---------- A. inventory + audit ----------

def inventory() -> dict:
    archives = sorted(RAW.glob("*.zip")) + sorted(RAW.glob("*.tar*"))
    inv = []
    for a in archives:
        st = a.stat()
        inv.append({
            "filename": a.name,
            "path": str(a),
            "size_bytes": st.st_size,
            "sha256": sha256(a),
            "modified_iso": dt.datetime.fromtimestamp(st.st_mtime, tz=dt.timezone.utc).isoformat(timespec="seconds"),
        })
    return {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "archives_in_raw": inv,
        "n_archives_raw": len(inv),
    }


def audit_one_day_dir(day_dir: Path, label: str) -> dict:
    out: dict[str, Any] = {"source_label": label, "path": str(day_dir)}
    if not day_dir.exists():
        out["exists"] = False
        return out
    out["exists"] = True
    metadata = None
    md_path = day_dir / "metadata.json"
    if md_path.exists():
        try:
            metadata = json.loads(md_path.read_text(encoding="utf-8"))
        except Exception as e:
            metadata = {"_parse_error": str(e)}
    out["metadata"] = metadata
    streams: dict[str, dict] = {}
    # raw_depth_events / trades / liquidations / book_ticker / mark_price use event_time
    for name in JSONL_STREAMS:
        p = day_dir / name
        if not p.exists():
            streams[name] = {"exists": False}
            continue
        sz = p.stat().st_size
        first, last, n = stream_first_last(p, ts_field="event_time" if name != "health.jsonl" and name != "orderbook_snapshots_1s.jsonl" else "ts")
        streams[name] = {
            "exists": True,
            "size_bytes": sz,
            "first_ts_ms": first,
            "first_ts_iso": ms_to_iso(first),
            "last_ts_ms": last,
            "last_ts_iso": ms_to_iso(last),
            "approx_line_count": n,
        }
    out["streams"] = streams
    return out


def audit_all() -> dict:
    """Build audit per (source, date)."""
    audit: dict[str, Any] = {"build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    part1_dir = STAGING / "part1"
    part2_dir = STAGING / "part2"
    by_date: dict[str, dict] = {}
    for d in DATES:
        by_date[d] = {
            "part1": audit_one_day_dir(part1_dir / d, label=f"part1/{d}"),
            "part2": audit_one_day_dir(part2_dir / d, label=f"part2/{d}"),
        }
    audit["by_date"] = by_date
    # also check 2026-05-21 to confirm absence
    has_2026_05_21 = (part1_dir / "2026-05-21").exists() or (part2_dir / "2026-05-21").exists()
    audit["had_2026_05_21"] = has_2026_05_21
    return audit


# ---------- B. normalize ----------

CUTOVER_TS_MS = 1779120815858   # = part2/2026-05-18 trades first event_time = 2026-05-18T16:13:35.858Z UTC


def merge_jsonl_with_cutover(part1_path: Path, part2_path: Path, dest: Path,
                             cutover_ts_ms: int, ts_field: str = "event_time") -> dict:
    """Merge two JSONL files into dest by taking
       part1[ts < cutover] + part2[ts >= cutover].
    No content reordering inside each side.
    Returns counts and time span.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    n_p1_kept = 0
    n_p2_kept = 0
    n_p1_skipped_after = 0
    n_p2_skipped_before = 0
    first = None
    last = None
    with dest.open("wb") as out:
        if part1_path.exists() and part1_path.stat().st_size > 0:
            with part1_path.open("rb") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        j = json.loads(line)
                    except Exception:
                        continue
                    v = j.get(ts_field) or j.get("ts")
                    if v is None or int(v) < cutover_ts_ms:
                        out.write(line if line.endswith(b"\n") else line + b"\n")
                        n_p1_kept += 1
                        if first is None:
                            first = int(v) if v is not None else None
                        if v is not None:
                            last = int(v)
                    else:
                        n_p1_skipped_after += 1
        if part2_path.exists() and part2_path.stat().st_size > 0:
            with part2_path.open("rb") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        j = json.loads(line)
                    except Exception:
                        continue
                    v = j.get(ts_field) or j.get("ts")
                    if v is None or int(v) >= cutover_ts_ms:
                        out.write(line if line.endswith(b"\n") else line + b"\n")
                        n_p2_kept += 1
                        if first is None:
                            first = int(v) if v is not None else None
                        if v is not None:
                            last = int(v)
                    else:
                        n_p2_skipped_before += 1
    return {
        "dest": str(dest),
        "size_bytes": dest.stat().st_size if dest.exists() else 0,
        "from_part1_kept": n_p1_kept,
        "from_part2_kept": n_p2_kept,
        "from_part1_skipped_ge_cutover": n_p1_skipped_after,
        "from_part2_skipped_lt_cutover": n_p2_skipped_before,
        "first_ts_ms": first,
        "first_ts_iso": ms_to_iso(first),
        "last_ts_ms": last,
        "last_ts_iso": ms_to_iso(last),
    }


def normalize_all() -> dict:
    """Build data/binance-live-normalized/.../<date>/ with merged 05-18 and copied others."""
    NORM.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "cutover_ts_ms_2026_05_18": CUTOVER_TS_MS,
        "cutover_ts_iso_2026_05_18": ms_to_iso(CUTOVER_TS_MS),
        "days": {},
    }
    part1_dir = STAGING / "part1"
    part2_dir = STAGING / "part2"

    for d in DATES:
        dest_dir = NORM / d
        dest_dir.mkdir(parents=True, exist_ok=True)
        day_report: dict[str, Any] = {"streams": {}, "merge_source": None}
        src_dirs = []
        if d == "2026-05-18":
            day_report["merge_source"] = "merged from part1 + part2 by cutover"
            for name in JSONL_STREAMS:
                # merge stream by stream
                ts_field = "ts" if name in ("health.jsonl", "orderbook_snapshots_1s.jsonl") else "event_time"
                day_report["streams"][name] = merge_jsonl_with_cutover(
                    part1_dir / d / name,
                    part2_dir / d / name,
                    dest_dir / name,
                    CUTOVER_TS_MS,
                    ts_field=ts_field,
                )
            # also synthesize a merged metadata.json
            md1_path = part1_dir / d / "metadata.json"
            md2_path = part2_dir / d / "metadata.json"
            md1 = json.loads(md1_path.read_text(encoding="utf-8")) if md1_path.exists() else None
            md2 = json.loads(md2_path.read_text(encoding="utf-8")) if md2_path.exists() else None
            merged_md = {
                "exchange": "binance-futures",
                "symbol": "BTCUSDT",
                "day": d,
                "merged": True,
                "cutover_ts_ms": CUTOVER_TS_MS,
                "cutover_ts_iso": ms_to_iso(CUTOVER_TS_MS),
                "part1_metadata": md1,
                "part2_metadata": md2,
            }
            (dest_dir / "metadata.json").write_text(
                json.dumps(merged_md, indent=2), encoding="utf-8"
            )
        elif d == "2026-05-17":
            day_report["merge_source"] = "single part1"
            for name in JSONL_STREAMS:
                src = part1_dir / d / name
                dst = dest_dir / name
                if src.exists():
                    if not dst.exists() or src.stat().st_size != dst.stat().st_size:
                        shutil.copy2(src, dst)
                    day_report["streams"][name] = {"copied_from": str(src), "size_bytes": dst.stat().st_size}
                else:
                    day_report["streams"][name] = {"missing_source": str(src)}
            shutil.copy2(part1_dir / d / "metadata.json", dest_dir / "metadata.json")
        else:  # 05-19, 05-20 from part2
            day_report["merge_source"] = "single part2"
            for name in JSONL_STREAMS:
                src = part2_dir / d / name
                dst = dest_dir / name
                if src.exists():
                    if not dst.exists() or src.stat().st_size != dst.stat().st_size:
                        shutil.copy2(src, dst)
                    day_report["streams"][name] = {"copied_from": str(src), "size_bytes": dst.stat().st_size}
                else:
                    day_report["streams"][name] = {"missing_source": str(src)}
            shutil.copy2(part2_dir / d / "metadata.json", dest_dir / "metadata.json")

        report["days"][d] = day_report
    return report


# ---------- C. JSONL -> Tardis CSV.gz converter ----------

EXCH = "binance-futures"
SYM = "BTCUSDT"


# Merge-stream record kinds. The sort key is (ts_ms, _KIND_*) so that when a
# 1-second snapshot shares a millisecond with a depth diff, the snapshot reset is
# emitted FIRST and the consumer (and the parity replay) clears the book before
# applying that millisecond's diff.
_KIND_SNAP = 0
_KIND_DIFF = 1


def _iter_snapshot_records(fp: Iterable[bytes]):
    """Yield (ts_ms, _KIND_SNAP, snapshot_dict) for each 1s book snapshot."""
    for line in fp:
        if not line.strip():
            continue
        try:
            s = json.loads(line)
        except Exception:
            continue
        ts_ms = int(s.get("ts") or 0)
        if ts_ms == 0:
            continue
        yield (ts_ms, _KIND_SNAP, s)


def _iter_depth_records(fp: Iterable[bytes]):
    """Yield (ts_ms, _KIND_DIFF, depth_event_dict) for each raw depth diff."""
    for line in fp:
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        ts_ms = int(ev.get("event_time") or 0)
        if ts_ms == 0:
            continue
        yield (ts_ms, _KIND_DIFF, ev)


def _emit_l2(snap_fp: Iterable[bytes] | None, raw_fp: Iterable[bytes] | None,
             out_path: Path) -> dict:
    """Write incremental_book_L2.csv.gz by interleaving the per-second snapshots
    (emitted as is_snapshot=true resets) with the raw depth diffs (is_snapshot=false),
    in timestamp order.

    Why re-seed every second instead of once: the depth diffs are depth-limited
    (only levels near the live price change), so a single stale seed leaves far
    levels that the diffs never revisit. Once the price drifts out of the seed
    window the reconstructed book crosses (best_bid >= best_ask) and stays crossed
    for the rest of the day. orderbook_snapshots_1s.jsonl carries a fresh 50-level
    book every second; re-seeding from it bounds any staleness to <1s and keeps the
    top of book correct. Consumers that honour Tardis snapshot semantics
    (src/replay/orderBook.ts, src/features/liquidityEvents.ts, and the parity
    replay) clear/re-baseline on each contiguous is_snapshot=true block, so the
    snapshot resets do not leak into the add/cancel flow features.

    Diffs before the first snapshot are dropped (no anchor book exists yet — the
    first snapshot supersedes them anyway).
    """
    started = time.time()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_events = 0          # depth diff events read
    n_rows = 0            # CSV data rows written
    n_snapshots_emitted = 0
    first_ts = None
    last_ts = None
    seeded = False        # have we emitted the first snapshot reset yet?

    snap_iter = _iter_snapshot_records(snap_fp) if snap_fp is not None else iter(())
    depth_iter = _iter_depth_records(raw_fp) if raw_fp is not None else iter(())
    # Both inputs are individually time-sorted, so heapq.merge yields a single
    # time-sorted stream; the (ts_ms, kind) key keeps snapshot-before-diff on ties.
    merged = heapq.merge(snap_iter, depth_iter, key=lambda r: (r[0], r[1]))

    with gzip.open(out_path, mode="wt", encoding="utf-8", newline="\n", compresslevel=5) as gz:
        gz.write("exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount\n")
        for ts_ms, kind, payload in merged:
            ts_us = ts_ms * 1000
            if kind == _KIND_SNAP:
                aps = payload.get("ask_prices") or []
                aqs = payload.get("ask_qty") or []
                bps = payload.get("bid_prices") or []
                bqs = payload.get("bid_qty") or []
                wrote = False
                for p, q in zip(aps, aqs):
                    if q is None or float(q) <= 0:
                        continue
                    gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},true,ask,{p},{q}\n")
                    n_rows += 1
                    wrote = True
                for p, q in zip(bps, bqs):
                    if q is None or float(q) <= 0:
                        continue
                    gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},true,bid,{p},{q}\n")
                    n_rows += 1
                    wrote = True
                if wrote:
                    n_snapshots_emitted += 1
                    seeded = True
                    if first_ts is None:
                        first_ts = ts_ms
                    last_ts = ts_ms
            else:  # _KIND_DIFF
                n_events += 1
                if not seeded:
                    continue  # drop diffs that precede the first snapshot anchor
                bids = payload.get("bids") or []
                asks = payload.get("asks") or []
                # Tardis amount=0 means "delete level" — Binance qty 0 has the same meaning.
                for p, q in asks:
                    gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},false,ask,{p},{q}\n")
                    n_rows += 1
                for p, q in bids:
                    gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},false,bid,{p},{q}\n")
                    n_rows += 1
                last_ts = ts_ms
                if n_events % 200_000 == 0:
                    print(f"    [depth] {n_events:,} events  {n_snapshots_emitted:,} snaps  "
                          f"{n_rows:,} rows  {time.time()-started:.1f}s", file=sys.stderr)

    dur = time.time() - started
    return {
        "out_path": str(out_path), "out_size_bytes": out_path.stat().st_size,
        "events_in": n_events, "rows_out": n_rows,
        "snapshots_seeded": n_snapshots_emitted,
        "first_ts_ms": first_ts, "last_ts_ms": last_ts,
        "duration_s": round(dur, 1),
    }


def convert_raw_depth_to_l2(raw_depth_path: Path, snapshots_path: Path, out_path: Path) -> dict:
    """Emit incremental_book_L2.csv.gz from raw_depth_events.jsonl, re-seeding the
    book from EVERY orderbook_snapshots_1s.jsonl entry (interleaved in timestamp
    order). See _emit_l2 for the rationale.
    """
    snap_fp = (snapshots_path.open("rb")
               if (snapshots_path.exists() and snapshots_path.stat().st_size > 0) else None)
    raw_fp = (raw_depth_path.open("rb")
              if (raw_depth_path.exists() and raw_depth_path.stat().st_size > 0) else None)
    try:
        return _emit_l2(snap_fp, raw_fp, out_path)
    finally:
        if snap_fp is not None:
            snap_fp.close()
        if raw_fp is not None:
            raw_fp.close()


def convert_trades(trades_path: Path, out_path: Path) -> dict:
    started = time.time()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_in = 0
    n_out = 0
    first_ts = None
    last_ts = None
    with gzip.open(out_path, mode="wt", encoding="utf-8", newline="\n", compresslevel=5) as gz:
        gz.write("exchange,symbol,timestamp,local_timestamp,id,side,price,amount\n")
        if trades_path.exists() and trades_path.stat().st_size > 0:
            with trades_path.open("rb") as fp:
                for line in fp:
                    if not line.strip():
                        continue
                    try:
                        t = json.loads(line)
                    except Exception:
                        continue
                    n_in += 1
                    ts_ms = int(t.get("event_time") or 0)
                    if ts_ms == 0:
                        continue
                    ts_us = ts_ms * 1000
                    if first_ts is None:
                        first_ts = ts_ms
                    last_ts = ts_ms
                    tid = t.get("trade_id") or t.get("agg_trade_id") or ""
                    side = t.get("side")
                    price = t.get("price")
                    qty = t.get("qty")
                    if price is None or qty is None or float(price) <= 0 or float(qty) <= 0:
                        continue
                    gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},{tid},{side},{price},{qty}\n")
                    n_out += 1
    return {
        "out_path": str(out_path), "out_size_bytes": out_path.stat().st_size,
        "rows_in": n_in, "rows_out": n_out,
        "first_ts_ms": first_ts, "last_ts_ms": last_ts,
        "duration_s": round(time.time() - started, 1),
    }


def convert_liquidations(liq_path: Path, out_path: Path) -> dict:
    started = time.time()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_in = 0
    n_out = 0
    with gzip.open(out_path, mode="wt", encoding="utf-8", newline="\n", compresslevel=5) as gz:
        gz.write("exchange,symbol,timestamp,local_timestamp,id,side,price,amount\n")
        if liq_path.exists() and liq_path.stat().st_size > 0:
            with liq_path.open("rb") as fp:
                for i, line in enumerate(fp):
                    if not line.strip():
                        continue
                    try:
                        t = json.loads(line)
                    except Exception:
                        continue
                    n_in += 1
                    ts_ms = int(t.get("event_time") or 0)
                    if ts_ms == 0:
                        continue
                    ts_us = ts_ms * 1000
                    side = t.get("side")
                    price = t.get("price")
                    qty = t.get("qty")
                    if price is None or qty is None:
                        continue
                    gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},liq{i},{side},{price},{qty}\n")
                    n_out += 1
    return {
        "out_path": str(out_path), "out_size_bytes": out_path.stat().st_size,
        "rows_in": n_in, "rows_out": n_out,
        "duration_s": round(time.time() - started, 1),
    }


def convert_book_ticker(bt_path: Path, out_path: Path) -> dict:
    started = time.time()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_in = 0
    n_out = 0
    with gzip.open(out_path, mode="wt", encoding="utf-8", newline="\n", compresslevel=5) as gz:
        gz.write("exchange,symbol,timestamp,local_timestamp,bid_price,bid_amount,ask_price,ask_amount\n")
        if bt_path.exists() and bt_path.stat().st_size > 0:
            with bt_path.open("rb") as fp:
                for line in fp:
                    if not line.strip():
                        continue
                    try:
                        b = json.loads(line)
                    except Exception:
                        continue
                    n_in += 1
                    ts_ms = int(b.get("event_time") or 0)
                    if ts_ms == 0:
                        continue
                    ts_us = ts_ms * 1000
                    gz.write(
                        f"{EXCH},{SYM},{ts_us},{ts_us},{b.get('bid_price')},{b.get('bid_qty')},"
                        f"{b.get('ask_price')},{b.get('ask_qty')}\n")
                    n_out += 1
    return {
        "out_path": str(out_path), "out_size_bytes": out_path.stat().st_size,
        "rows_in": n_in, "rows_out": n_out,
        "duration_s": round(time.time() - started, 1),
    }


def convert_mark_price(mp_path: Path, out_path: Path) -> dict:
    started = time.time()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_in = 0
    n_out = 0
    with gzip.open(out_path, mode="wt", encoding="utf-8", newline="\n", compresslevel=5) as gz:
        gz.write("exchange,symbol,timestamp,local_timestamp,funding_rate,index_price,mark_price,last_price\n")
        if mp_path.exists() and mp_path.stat().st_size > 0:
            with mp_path.open("rb") as fp:
                for line in fp:
                    if not line.strip():
                        continue
                    try:
                        m = json.loads(line)
                    except Exception:
                        continue
                    n_in += 1
                    ts_ms = int(m.get("event_time") or 0)
                    if ts_ms == 0:
                        continue
                    ts_us = ts_ms * 1000
                    gz.write(
                        f"{EXCH},{SYM},{ts_us},{ts_us},{m.get('funding_rate', '')},"
                        f"{m.get('index_price', '')},{m.get('mark_price', '')},\n")
                    n_out += 1
    return {
        "out_path": str(out_path), "out_size_bytes": out_path.stat().st_size,
        "rows_in": n_in, "rows_out": n_out,
        "duration_s": round(time.time() - started, 1),
    }


def convert_day(date: str) -> dict:
    """Convert one normalized day (JSONL) to Tardis CSV.gz files."""
    src = NORM / date
    dst = TARDIS_OUT / date
    dst.mkdir(parents=True, exist_ok=True)
    print(f"  [{date}] converting under {dst}", file=sys.stderr)
    rep: dict[str, Any] = {"date": date, "src": str(src), "dst": str(dst), "streams": {}}
    rep["streams"]["incremental_book_L2"] = convert_raw_depth_to_l2(
        src / "raw_depth_events.jsonl",
        src / "orderbook_snapshots_1s.jsonl",
        dst / "incremental_book_L2.csv.gz",
    )
    rep["streams"]["trades"] = convert_trades(
        src / "trades.jsonl", dst / "trades.csv.gz")
    rep["streams"]["liquidations"] = convert_liquidations(
        src / "liquidations.jsonl", dst / "liquidations.csv.gz")
    rep["streams"]["book_ticker"] = convert_book_ticker(
        src / "book_ticker.jsonl", dst / "book_ticker.csv.gz")
    rep["streams"]["derivative_ticker"] = convert_mark_price(
        src / "mark_price.jsonl", dst / "derivative_ticker.csv.gz")
    return rep


# ---------- writers ----------

def write_inventory_report(inv: dict, audit: dict) -> None:
    (REPORTS / "BINANCE_LIVE_ARCHIVE_INVENTORY.json").write_text(
        json.dumps({"inventory": inv, "audit": audit}, indent=2, default=str), encoding="utf-8")

    md = [
        "# Binance live-recorder archive inventory + audit",
        "",
        f"**Build:** {inv['build_time_utc']}",
        "",
        "## A. Raw archives staged",
        "",
        "| filename | size (B) | modified UTC | sha256(8) |",
        "|---|---:|---|---|",
    ]
    for a in inv["archives_in_raw"]:
        md.append(f"| `{a['filename']}` | {a['size_bytes']:,} | {a['modified_iso']} | `{a['sha256'][:8]}` |")
    md.extend([
        "",
        "## B. Per-day audit (first/last event_time + line counts)",
        "",
        "| date | source | stream | first ts UTC | last ts UTC | lines | size (B) |",
        "|---|---|---|---|---|---:|---:|",
    ])
    for d, srcs in audit["by_date"].items():
        for src_label, payload in srcs.items():
            if not payload.get("exists"):
                continue
            for sn, info in payload["streams"].items():
                if not info.get("exists"):
                    continue
                md.append(
                    f"| {d} | {src_label} | `{sn}` | {info['first_ts_iso']} | "
                    f"{info['last_ts_iso']} | {info['approx_line_count']} | {info['size_bytes']:,} |"
                )
    md.extend([
        "",
        f"## C. 2026-05-21 presence: **{audit['had_2026_05_21']}** (must be NO per scope)",
        "",
    ])
    (REPORTS / "BINANCE_LIVE_ARCHIVE_INVENTORY.md").write_text("\n".join(md), encoding="utf-8")


def write_normalization_report(rep: dict) -> None:
    (REPORTS / "BINANCE_LIVE_NORMALIZATION_REPORT.json").write_text(
        json.dumps(rep, indent=2, default=str), encoding="utf-8")
    md = [
        "# Binance live-recorder normalization report",
        "",
        f"**Build:** {rep['build_time_utc']}",
        f"**Cutover for 2026-05-18 merge:** `event_time >= {rep['cutover_ts_ms_2026_05_18']}` "
        f"(= {rep['cutover_ts_iso_2026_05_18']}) goes to part2; everything earlier stays from part1.",
        "",
        "## Per-day normalization",
        "",
    ]
    for d, day in rep["days"].items():
        md.append(f"### {d}  ({day['merge_source']})")
        md.append("")
        md.append("| stream | first ts UTC | last ts UTC | rows | source split (p1/p2) |")
        md.append("|---|---|---|---:|---|")
        for sn, info in day["streams"].items():
            if "from_part1_kept" in info:
                first = info.get("first_ts_iso")
                last = info.get("last_ts_iso")
                rows = info["from_part1_kept"] + info["from_part2_kept"]
                split = f"{info['from_part1_kept']}/{info['from_part2_kept']}"
                md.append(f"| `{sn}` | {first} | {last} | {rows} | {split} |")
            elif info.get("size_bytes"):
                md.append(f"| `{sn}` | (copy) | (copy) | — | {info.get('copied_from', '')} |")
        md.append("")
    (REPORTS / "BINANCE_LIVE_NORMALIZATION_REPORT.md").write_text("\n".join(md), encoding="utf-8")


def write_data_quality_audit(audit: dict, normalization_report: dict) -> dict:
    """Synthesize the data quality report and return flags."""
    flags: dict[str, Any] = {
        "BINANCE_LIVE_DATA_AUDIT_DONE": "YES",
        "BACKTEST_READY_DAYS": [],
        "PARTIAL_DAYS": [],
        "BLOCKED_DAYS": [],
        "LIQUIDATIONS_AVAILABLE": "PARTIAL",  # 17/18-part1 had none; 18-part2/19/20 have
    }
    rows = []
    by_date = audit["by_date"]
    for d in DATES:
        # Aggregate first/last from merged normalized data if 05-18 (merged), else single source
        norm_streams = normalization_report["days"][d]["streams"]
        # Use trades.jsonl as canonical
        trades_info = norm_streams.get("trades.jsonl") or {}
        if "from_part1_kept" in trades_info:
            first = trades_info.get("first_ts_ms")
            last = trades_info.get("last_ts_ms")
        else:
            # copy case — read from the single source audit
            src_label = "part2" if d in ("2026-05-19", "2026-05-20") else "part1"
            s = by_date[d].get(src_label, {}).get("streams", {}).get("trades.jsonl", {})
            first = s.get("first_ts_ms")
            last = s.get("last_ts_ms")
        if first is None or last is None:
            verdict = "BLOCKED"
            flags["BLOCKED_DAYS"].append(d)
        else:
            duration_s = (last - first) / 1000.0
            duration_h = duration_s / 3600.0
            if d == "2026-05-18" and duration_h >= 23.5:
                verdict = "FULL"
                flags["BACKTEST_READY_DAYS"].append(d)
            elif duration_h < 0.5:
                verdict = "TOO_SHORT_SKIP"
                flags["BLOCKED_DAYS"].append(d)
            elif duration_h < 23.0:
                verdict = "PARTIAL"
                flags["PARTIAL_DAYS"].append(d)
            else:
                verdict = "FULL"
                flags["BACKTEST_READY_DAYS"].append(d)
        rows.append({
            "date": d,
            "first_ts_iso": ms_to_iso(first),
            "last_ts_iso": ms_to_iso(last),
            "duration_h": round((last - first) / 3_600_000.0, 3) if first and last else None,
            "verdict": verdict,
        })

    audit_out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Binance live-recorder, BTCUSDT Futures, days 2026-05-17..2026-05-20",
        "per_day": rows,
        "flags": flags,
    }
    (REPORTS / "BINANCE_LIVE_DATA_QUALITY_AUDIT.json").write_text(
        json.dumps(audit_out, indent=2, default=str), encoding="utf-8")
    md = [
        "# Binance live-recorder data quality audit",
        "",
        f"**Build:** {audit_out['build_time_utc']}",
        "",
        "## Per-day coverage (from normalized JSONL trade stream)",
        "",
        "| date | first ts UTC | last ts UTC | duration (h) | verdict |",
        "|---|---|---|---:|---|",
    ]
    for r in rows:
        md.append(f"| {r['date']} | {r['first_ts_iso']} | {r['last_ts_iso']} | {r['duration_h']} | {r['verdict']} |")
    md.extend([
        "",
        "## Flags",
        "",
        f"- BINANCE_LIVE_DATA_AUDIT_DONE = **{flags['BINANCE_LIVE_DATA_AUDIT_DONE']}**",
        f"- BACKTEST_READY_DAYS = `{flags['BACKTEST_READY_DAYS']}`",
        f"- PARTIAL_DAYS = `{flags['PARTIAL_DAYS']}`",
        f"- BLOCKED_DAYS = `{flags['BLOCKED_DAYS']}`",
        f"- LIQUIDATIONS_AVAILABLE = **{flags['LIQUIDATIONS_AVAILABLE']}**  "
        "(part1 streams have empty liquidations; part2 streams + 19/20 carry liquidations)",
        "",
        "## Hard rules honored",
        "",
        "- no engine / threshold change",
        "- recorder not restarted; raw archives preserved",
        "- no API keys touched",
    ])
    (REPORTS / "BINANCE_LIVE_DATA_QUALITY_AUDIT.md").write_text("\n".join(md), encoding="utf-8")
    return audit_out


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="all",
                    choices=["all", "inventory", "audit", "normalize", "convert", "convert-single"])
    ap.add_argument("--date", default=None)
    args = ap.parse_args()

    if args.phase in ("all", "inventory"):
        print("[phase] inventory", file=sys.stderr)
        inv = inventory()
    else:
        inv = None
    if args.phase in ("all", "audit", "inventory"):
        print("[phase] audit", file=sys.stderr)
        audit = audit_all()
        if inv is not None:
            write_inventory_report(inv, audit)
    else:
        audit = None

    if args.phase in ("all", "normalize"):
        print("[phase] normalize", file=sys.stderr)
        norm_rep = normalize_all()
        write_normalization_report(norm_rep)
        if audit is None:
            audit = audit_all()
        dq = write_data_quality_audit(audit, norm_rep)
        print("BACKTEST_READY_DAYS:", dq["flags"]["BACKTEST_READY_DAYS"])
        print("PARTIAL_DAYS:", dq["flags"]["PARTIAL_DAYS"])
        print("BLOCKED_DAYS:", dq["flags"]["BLOCKED_DAYS"])

    if args.phase == "convert-single":
        if not args.date:
            print("ERROR: --date required for convert-single", file=sys.stderr)
            return 2
        rep = convert_day(args.date)
        log = REPORTS / "_convert_log.jsonl"
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rep, default=str) + "\n")
        print(json.dumps(rep, indent=2, default=str))

    if args.phase == "convert":
        # Convert all 4 days
        all_rep = {}
        for d in DATES:
            rep = convert_day(d)
            all_rep[d] = rep
            print(f"  [{d}] done", file=sys.stderr)
        (REPORTS / "BINANCE_LIVE_CONVERSION_LOG.json").write_text(
            json.dumps(all_rep, indent=2, default=str), encoding="utf-8")

    if args.phase == "all":
        print("[phase] (NOT auto-converting in 'all'; run --phase convert-single per date)",
              file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
