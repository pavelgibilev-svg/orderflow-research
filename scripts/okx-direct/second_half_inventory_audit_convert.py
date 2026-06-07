"""Inventory + audit + convert for OKX direct March SECOND HALF (2026-03-16..03-31).

NEW vs original convert_okx_direct_to_tardis.py:
  - For 2026-03-31 UTC, trades must come from BOTH trades-2026-03.zip (UTC 03-31 00:00-16:00)
    AND trades-2026-04.zip (UTC 03-31 16:00-24:00). Handled automatically.
  - 03-17 is missing in the source; documented as such.
  - Other days (03-16, 03-18..03-30) use trades-2026-03.zip only.

Inputs:
  data/okx-direct/BTC-USDT-SWAP/2026-03/raw/orderbook/BTC-USDT-SWAP-L2orderbook-400lv-2026-03-DD.tar.gz
  data/okx-direct/BTC-USDT-SWAP/2026-03/raw/trades/BTC-USDT-SWAP-trades-2026-03.zip
  data/okx-direct/BTC-USDT-SWAP/2026-03/raw/trades/BTC-USDT-SWAP-trades-2026-04.zip

Outputs:
  data/okx-historical/BTC-USDT-SWAP/2026-03-DD/incremental_book_L2.csv.gz
  data/okx-historical/BTC-USDT-SWAP/2026-03-DD/trades.csv.gz
  reports/okx-direct/OKX_DIRECT_MARCH_SECOND_HALF_INVENTORY.{md,json}
  reports/okx-direct/OKX_DIRECT_MARCH_SECOND_HALF_QUALITY_AUDIT.{md,json}

NO strategy change. NO new backtest spawned here.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import sys
import tarfile
import time
import zipfile
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
RAW_OB = ROOT / "data/okx-direct/BTC-USDT-SWAP/2026-03/raw/orderbook"
RAW_TR = ROOT / "data/okx-direct/BTC-USDT-SWAP/2026-03/raw/trades"
OUT_TARDIS = ROOT / "data/okx-historical/BTC-USDT-SWAP"
REPORTS = ROOT / "reports/okx-direct"
REPORTS.mkdir(parents=True, exist_ok=True)

SECOND_HALF_DATES = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]
# 03-17 is missing in the source folder.
EXCH = "okex-swap"
SYM = "BTC-USDT-SWAP"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ms_to_iso(ms: int | None) -> str | None:
    if ms is None: return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="milliseconds")


def utc_day_window_ms(date_iso: str) -> tuple[int, int]:
    d = dt.datetime.fromisoformat(date_iso).replace(tzinfo=dt.timezone.utc)
    start = int(d.timestamp() * 1000)
    return start, start + 86_400_000


# ---------- orderbook conversion ----------

def convert_orderbook(date_iso: str, summary: dict) -> None:
    src = RAW_OB / f"BTC-USDT-SWAP-L2orderbook-400lv-{date_iso}.tar.gz"
    if not src.exists():
        summary["orderbook"] = {"missing_src": str(src)}
        return
    out_dir = OUT_TARDIS / date_iso
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "incremental_book_L2.csv.gz"
    if out_path.exists() and out_path.stat().st_size > 0:
        summary["orderbook"] = {"reused_existing": str(out_path),
                                 "out_size_bytes": out_path.stat().st_size}
        print(f"  [ob] reuse {out_path.name}", file=sys.stderr)
        return
    started = time.time()
    n_events = 0; n_snap = 0; n_upd = 0; n_rows = 0
    first_ts = None; last_ts = None
    with gzip.open(out_path, "wt", encoding="utf-8", newline="\n", compresslevel=5) as gz:
        gz.write("exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount\n")
        with tarfile.open(src, "r:gz") as tf:
            m = tf.getmembers()[0]
            fp = tf.extractfile(m)
            if fp is None:
                summary["orderbook"] = {"error": "cannot open inner data file"}
                return
            for raw in fp:
                n_events += 1
                try:
                    d = json.loads(raw)
                except Exception:
                    continue
                ts_ms = int(d["ts"]); ts_us = ts_ms * 1000
                if first_ts is None: first_ts = ts_ms
                last_ts = ts_ms
                is_snap = d["action"] == "snapshot"
                snap = "true" if is_snap else "false"
                if is_snap: n_snap += 1
                else: n_upd += 1
                lines: list[str] = []
                for p, s, _ in d.get("asks", ()):
                    lines.append(f"{EXCH},{SYM},{ts_us},{ts_us},{snap},ask,{p},{s}\n")
                for p, s, _ in d.get("bids", ()):
                    lines.append(f"{EXCH},{SYM},{ts_us},{ts_us},{snap},bid,{p},{s}\n")
                if lines:
                    gz.write("".join(lines))
                    n_rows += len(lines)
                if n_events % 500_000 == 0:
                    print(f"  [ob] {n_events:,} events  {n_rows:,} rows  {time.time()-started:.1f}s",
                          file=sys.stderr)
    dur = time.time() - started
    summary["orderbook"] = {
        "src_archive": src.name, "events_total": n_events,
        "snapshot_events": n_snap, "update_events": n_upd, "rows_written": n_rows,
        "first_ts_ms": first_ts, "last_ts_ms": last_ts,
        "first_ts_iso": ms_to_iso(first_ts), "last_ts_iso": ms_to_iso(last_ts),
        "duration_s": round(dur, 1), "out_path": str(out_path),
        "out_size_bytes": out_path.stat().st_size,
    }


# ---------- trades conversion ----------

def stream_trades_zip(zip_path: Path, start_ms: int, end_ms: int):
    """Yield (ts_us_str, tid, side, price, qty) for rows within [start_ms, end_ms)."""
    with zipfile.ZipFile(zip_path) as zf:
        inner = zf.infolist()[0].filename
        with zf.open(inner, "r") as fp:
            _h = fp.readline()
            buf = io.TextIOWrapper(fp, encoding="utf-8", newline="")
            for line in buf:
                line = line.rstrip("\r\n")
                if not line: continue
                try:
                    inst, tid, side, price, size, ct = line.split(",")
                    ts_ms = int(ct)
                except Exception:
                    continue
                if ts_ms < start_ms:
                    continue
                if ts_ms >= end_ms:
                    break
                yield ts_ms * 1000, tid, side, price, size


def convert_trades_for_day(date_iso: str, summary: dict) -> None:
    """Handle 2026-03-31 split between trades-03 and trades-04."""
    out_dir = OUT_TARDIS / date_iso
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "trades.csv.gz"
    if out_path.exists() and out_path.stat().st_size > 0:
        summary["trades"] = {"reused_existing": str(out_path),
                              "out_size_bytes": out_path.stat().st_size}
        print(f"  [tr] reuse {out_path.name}", file=sys.stderr)
        return
    start_ms, end_ms = utc_day_window_ms(date_iso)
    asia_march_zip = RAW_TR / "BTC-USDT-SWAP-trades-2026-03.zip"
    asia_april_zip = RAW_TR / "BTC-USDT-SWAP-trades-2026-04.zip"
    # Asia-March covers UTC [2026-02-28T16:00, 2026-03-31T16:00)
    asia_march_end_utc_ms = int(dt.datetime(2026, 3, 31, 16, 0, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
    sources_used: list[str] = []
    started = time.time()
    n_in = 0; n_out = 0
    first_kept = None; last_kept = None
    with gzip.open(out_path, "wt", encoding="utf-8", newline="\n", compresslevel=5) as gz:
        gz.write("exchange,symbol,timestamp,local_timestamp,id,side,price,amount\n")
        # Part 1: from Asia-March file, up to min(end_ms, asia_march_end_utc_ms)
        p1_end = min(end_ms, asia_march_end_utc_ms)
        if start_ms < p1_end and asia_march_zip.exists():
            sources_used.append(asia_march_zip.name)
            for ts_us, tid, side, price, size in stream_trades_zip(asia_march_zip, start_ms, p1_end):
                gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},{tid},{side},{price},{size}\n")
                n_out += 1
                ts_ms = ts_us // 1000
                if first_kept is None: first_kept = ts_ms
                last_kept = ts_ms
                n_in += 1
        # Part 2: from Asia-April file, from max(start_ms, asia_march_end_utc_ms) to end_ms
        p2_start = max(start_ms, asia_march_end_utc_ms)
        if p2_start < end_ms and asia_april_zip.exists():
            sources_used.append(asia_april_zip.name)
            for ts_us, tid, side, price, size in stream_trades_zip(asia_april_zip, p2_start, end_ms):
                gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},{tid},{side},{price},{size}\n")
                n_out += 1
                ts_ms = ts_us // 1000
                if first_kept is None: first_kept = ts_ms
                last_kept = ts_ms
                n_in += 1
    summary["trades"] = {
        "sources_used": sources_used,
        "rows_kept": n_out,
        "first_kept_ts_ms": first_kept, "last_kept_ts_ms": last_kept,
        "first_kept_ts_iso": ms_to_iso(first_kept), "last_kept_ts_iso": ms_to_iso(last_kept),
        "duration_s": round(time.time() - started, 1),
        "out_path": str(out_path),
        "out_size_bytes": out_path.stat().st_size,
    }


# ---------- per-day pipeline ----------

def process_day(date_iso: str) -> dict:
    summary = {"date": date_iso, "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    print(f"=== {date_iso} ===", file=sys.stderr)
    convert_orderbook(date_iso, summary)
    convert_trades_for_day(date_iso, summary)
    summary["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return summary


# ---------- main ----------

def main() -> int:
    # ---------- A: inventory ----------
    ob_files: list[dict] = []
    for d in SECOND_HALF_DATES:
        p = RAW_OB / f"BTC-USDT-SWAP-L2orderbook-400lv-{d}.tar.gz"
        if p.exists():
            ob_files.append({"date": d, "path": str(p), "size": p.stat().st_size, "sha256_8": sha256(p)[:8]})
        else:
            ob_files.append({"date": d, "path": str(p), "missing": True})

    march_zip = RAW_TR / "BTC-USDT-SWAP-trades-2026-03.zip"
    april_zip = RAW_TR / "BTC-USDT-SWAP-trades-2026-04.zip"
    inv = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct March SECOND HALF inventory (2026-03-16..03-31)",
        "expected_days": [f"2026-03-{i:02d}" for i in range(16, 32)],
        "actual_orderbook_files": ob_files,
        "missing_orderbook_days": [d for d in (f"2026-03-{i:02d}" for i in range(16, 32))
                                    if not (RAW_OB / f"BTC-USDT-SWAP-L2orderbook-400lv-{d}.tar.gz").exists()],
        "trades_2026_03_zip_exists": march_zip.exists(),
        "trades_2026_04_zip_exists": april_zip.exists(),
        "trades_2026_03_size_bytes": march_zip.stat().st_size if march_zip.exists() else None,
        "trades_2026_04_size_bytes": april_zip.stat().st_size if april_zip.exists() else None,
        "asia_month_note": "OKX monthly trades bucketed by China local time (UTC+8). For 2026-03-31 UTC we use trades-03 (00:00-16:00 UTC) + trades-04 (16:00-24:00 UTC).",
    }
    inv["second_half_orderbook_days_found"] = sum(1 for r in ob_files if "missing" not in r)
    inv["second_half_ready"] = (
        inv["second_half_orderbook_days_found"] > 0
        and inv["trades_2026_03_zip_exists"]
        and inv["trades_2026_04_zip_exists"]
    )

    (REPORTS / "OKX_DIRECT_MARCH_SECOND_HALF_INVENTORY.json").write_text(
        json.dumps(inv, indent=2, default=str), encoding="utf-8")
    md = [
        "# OKX direct March SECOND HALF inventory (2026-03-16..03-31)",
        "",
        f"**Build:** {inv['build_time_utc']}",
        "",
        "## A. Order book archives",
        "",
        "| date | size (B) | sha256(8) | status |",
        "|---|---:|---|---|",
    ]
    for r in ob_files:
        if "missing" in r:
            md.append(f"| {r['date']} | — | — | **MISSING** |")
        else:
            md.append(f"| {r['date']} | {r['size']:,} | `{r['sha256_8']}` | ok |")
    md.extend([
        "",
        f"- order book days found: **{inv['second_half_orderbook_days_found']} / 16**",
        f"- missing days: {inv['missing_orderbook_days']}",
        "",
        "## B. Trade history archives",
        "",
        f"- `BTC-USDT-SWAP-trades-2026-03.zip`: {inv['trades_2026_03_zip_exists']} ({inv['trades_2026_03_size_bytes']} B)",
        f"- `BTC-USDT-SWAP-trades-2026-04.zip`: {inv['trades_2026_04_zip_exists']} ({inv['trades_2026_04_size_bytes']} B)",
        f"- Note: {inv['asia_month_note']}",
        "",
        "## C. Flags",
        "",
        f"- `OKX_SECOND_HALF_ORDERBOOK_DAYS_FOUND` = **{inv['second_half_orderbook_days_found']}**",
        f"- `OKX_SECOND_HALF_MISSING_DAYS` = `{inv['missing_orderbook_days']}`",
        f"- `OKX_TRADES_03_FOUND` = **{inv['trades_2026_03_zip_exists']}**",
        f"- `OKX_TRADES_04_FOUND` = **{inv['trades_2026_04_zip_exists']}**",
        f"- `OKX_SECOND_HALF_READY` = **{inv['second_half_ready']}**",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_SECOND_HALF_INVENTORY.md").write_text("\n".join(md), encoding="utf-8")
    print("[A] inventory written", file=sys.stderr)

    # ---------- B: convert + quality audit ----------
    convert_summaries: list[dict] = []
    quality_rows: list[dict] = []
    for d in SECOND_HALF_DATES:
        if not (RAW_OB / f"BTC-USDT-SWAP-L2orderbook-400lv-{d}.tar.gz").exists():
            quality_rows.append({"date": d, "verdict": "MISSING_SOURCE"})
            continue
        s = process_day(d)
        convert_summaries.append(s)
        # quick quality from summary
        ob = s.get("orderbook") or {}
        tr = s.get("trades") or {}
        first_ob = ob.get("first_ts_ms"); last_ob = ob.get("last_ts_ms")
        ob_coverage_h = (last_ob - first_ob) / 3_600_000.0 if first_ob and last_ob else None
        first_tr = tr.get("first_kept_ts_ms"); last_tr = tr.get("last_kept_ts_ms")
        tr_coverage_h = (last_tr - first_tr) / 3_600_000.0 if first_tr and last_tr else None
        verdict = "OK"
        if ob.get("missing_src"): verdict = "MISSING_OB"
        elif ob_coverage_h is not None and ob_coverage_h < 23.5: verdict = "PARTIAL_OB"
        elif tr_coverage_h is not None and tr_coverage_h < 23.5: verdict = "PARTIAL_TRADES"
        quality_rows.append({
            "date": d,
            "ob_events": ob.get("events_total"),
            "ob_snapshots": ob.get("snapshot_events"),
            "ob_first_ts": ob.get("first_ts_iso"), "ob_last_ts": ob.get("last_ts_iso"),
            "ob_coverage_h": round(ob_coverage_h, 3) if ob_coverage_h else None,
            "ob_out_size_mb": round((ob.get("out_size_bytes") or 0) / 1_048_576, 2),
            "trades_rows": tr.get("rows_kept"),
            "trades_first_ts": tr.get("first_kept_ts_iso"),
            "trades_last_ts": tr.get("last_kept_ts_iso"),
            "trades_coverage_h": round(tr_coverage_h, 3) if tr_coverage_h else None,
            "trades_sources_used": tr.get("sources_used"),
            "trades_out_size_mb": round((tr.get("out_size_bytes") or 0) / 1_048_576, 2),
            "verdict": verdict,
        })

    qa = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct March SECOND HALF quality audit + conversion summary",
        "per_day": quality_rows,
        "convert_summaries": convert_summaries,
        "pass_days": [r["date"] for r in quality_rows if r["verdict"] == "OK"],
        "bad_days": [r["date"] for r in quality_rows if r["verdict"] != "OK"],
    }
    (REPORTS / "OKX_DIRECT_MARCH_SECOND_HALF_QUALITY_AUDIT.json").write_text(
        json.dumps(qa, indent=2, default=str), encoding="utf-8")
    md_q = [
        "# OKX direct March SECOND HALF - quality audit + conversion",
        "",
        f"**Build:** {qa['build_time_utc']}",
        "",
        "| date | ob events | ob snaps | ob coverage h | ob out (MB) | trades rows | trades coverage h | trades sources | verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in quality_rows:
        if r["verdict"] == "MISSING_SOURCE":
            md_q.append(f"| {r['date']} | — | — | — | — | — | — | — | **MISSING_SOURCE** |")
            continue
        md_q.append(
            f"| {r['date']} | {r.get('ob_events'):,} | {r.get('ob_snapshots')} | "
            f"{r.get('ob_coverage_h')} | {r.get('ob_out_size_mb')} | "
            f"{r.get('trades_rows'):,} | {r.get('trades_coverage_h')} | "
            f"{','.join(r.get('trades_sources_used') or [])} | {r['verdict']} |"
        )
    md_q.extend([
        "",
        f"- pass days: **{len(qa['pass_days'])}** ({qa['pass_days']})",
        f"- bad days: **{len(qa['bad_days'])}** ({qa['bad_days']})",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_SECOND_HALF_QUALITY_AUDIT.md").write_text("\n".join(md_q), encoding="utf-8")
    print("[B] quality audit written", file=sys.stderr)

    print()
    print(f"OKX_SECOND_HALF_ORDERBOOK_DAYS_FOUND = {inv['second_half_orderbook_days_found']}")
    print(f"OKX_SECOND_HALF_MISSING_DAYS = {inv['missing_orderbook_days']}")
    print(f"OKX_TRADES_03_FOUND = {inv['trades_2026_03_zip_exists']}")
    print(f"OKX_TRADES_04_FOUND = {inv['trades_2026_04_zip_exists']}")
    print(f"OKX_SECOND_HALF_READY = {inv['second_half_ready']}")
    print(f"PASS_DAYS = {qa['pass_days']}")
    print(f"BAD_DAYS = {qa['bad_days']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
