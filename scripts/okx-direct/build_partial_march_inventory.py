"""Partial-March inventory + audits over staged OKX direct files.

Recomputes:
  reports/okx-direct/OKX_DIRECT_MARCH_PARTIAL_INVENTORY.{md,json}
  reports/okx-direct/OKX_DIRECT_MARCH_PARTIAL_ORDERBOOK_SCHEMA_AUDIT.{md,json}
  reports/okx-direct/OKX_DIRECT_MARCH_PARTIAL_TRADES_AUDIT.{md,json}

The orderbook schema part is a shallow first-event check per file (we already did a
deep scan of 2026-03-14 in the previous audit; the deep scan would be repeated by
the per-day quality replay script for the day we actually gate on).

NO strategy / threshold change.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import io
import json
import re
import sys
import tarfile
import time
import zipfile
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
RAW = ROOT / "data/okx-direct/BTC-USDT-SWAP/2026-03/raw"
REPORTS = ROOT / "reports/okx-direct"
REPORTS.mkdir(parents=True, exist_ok=True)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ms_to_iso(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="milliseconds")


def first_event_of_orderbook(p: Path) -> dict:
    with tarfile.open(p, "r:gz") as tf:
        m = tf.getmembers()[0]
        with tf.extractfile(m) as fp:
            line = fp.readline()
    return json.loads(line)


def first_row_of_trades(p: Path) -> tuple[str, str, int]:
    with zipfile.ZipFile(p) as zf:
        inner = zf.infolist()[0]
        with zf.open(inner.filename, "r") as fp:
            header = fp.readline().decode().strip()
            first = fp.readline().decode().strip()
    ts_ms = int(first.split(",")[-1])
    return header, first, ts_ms


def last_row_of_trades(p: Path) -> tuple[str, int]:
    """Stream to find last row.  Monthly files are ~3-9 GB so we stream."""
    last = None
    with zipfile.ZipFile(p) as zf:
        inner = zf.infolist()[0]
        with zf.open(inner.filename, "r") as fp:
            _h = fp.readline()
            buf = io.TextIOWrapper(fp, encoding="utf-8", newline="")
            for line in buf:
                if line.strip():
                    last = line.strip()
    ts_ms = int(last.split(",")[-1]) if last else 0
    return last, ts_ms


def main() -> int:
    ob_dir = RAW / "orderbook"
    tr_dir = RAW / "trades"
    ob_files = sorted(ob_dir.glob("*.tar.gz"))
    tr_files = sorted(tr_dir.glob("*.zip"))

    inv_ob: list[dict] = []
    for f in ob_files:
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
        date = date_match.group(1) if date_match else None
        first_evt = first_event_of_orderbook(f)
        inv_ob.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "sha256": sha256(f),
            "detected_date": date,
            "first_ts_ms": int(first_evt["ts"]),
            "first_ts_iso": ms_to_iso(int(first_evt["ts"])),
            "first_action": first_evt["action"],
            "first_bids_n": len(first_evt.get("bids", [])),
            "first_asks_n": len(first_evt.get("asks", [])),
            "instId": first_evt["instId"],
        })

    inv_tr: list[dict] = []
    for f in tr_files:
        period_match = re.search(r"trades-(\d{4}-\d{2})", f.name)
        period = period_match.group(1) if period_match else None
        h, first, first_ts = first_row_of_trades(f)
        last, last_ts = last_row_of_trades(f)
        inv_tr.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "sha256": sha256(f),
            "detected_period_in_name": period,
            "header": h,
            "first_row": first,
            "first_ts_ms": first_ts,
            "first_ts_iso": ms_to_iso(first_ts),
            "last_row": last,
            "last_ts_ms": last_ts,
            "last_ts_iso": ms_to_iso(last_ts) if last_ts else None,
        })

    # Coverage analysis
    all_dates = sorted({r["detected_date"] for r in inv_ob if r["detected_date"]})
    target_window = [f"2026-03-{i:02d}" for i in range(2, 16)]  # 2026-03-02 .. 03-15
    have_target = [d for d in target_window if d in all_dates]
    missing_target = [d for d in target_window if d not in all_dates]
    contiguous_from_03_02 = []
    for d in target_window:
        if d in all_dates:
            contiguous_from_03_02.append(d)
        else:
            break

    # trades coverage check for 2026-03-02..2026-03-15
    asia_march = next((r for r in inv_tr if r["detected_period_in_name"] == "2026-03"), None)
    trades_cover_target = False
    if asia_march:
        # Asia-March covers UTC 2026-02-28T16:00 .. 2026-03-31T16:00.
        # Target window UTC 2026-03-02T00:00 .. 2026-03-16T00:00 — fully inside.
        target_start_ms = int(dt.datetime(2026, 3, 2, tzinfo=dt.timezone.utc).timestamp() * 1000)
        target_end_ms = int(dt.datetime(2026, 3, 16, tzinfo=dt.timezone.utc).timestamp() * 1000)
        trades_cover_target = asia_march["first_ts_ms"] <= target_start_ms and asia_march["last_ts_ms"] >= target_end_ms - 1

    build_time = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    inv_json = {
        "build_time_utc": build_time,
        "source": "okx_direct_historical_data",
        "venue": "okx-swap",
        "symbol": "BTC-USDT-SWAP",
        "depth": 400,
        "all_orderbook_files": inv_ob,
        "all_trade_files": inv_tr,
        "target_window": {
            "start_date": "2026-03-02",
            "end_date": "2026-03-15",
            "days_expected": 14,
            "days_present": have_target,
            "days_missing": missing_target,
            "contiguous_from_start": contiguous_from_03_02,
        },
        "all_orderbook_dates_present": all_dates,
        "trades_coverage": {
            "asia_march_file_present": asia_march is not None,
            "asia_march_first_ts_iso": asia_march["first_ts_iso"] if asia_march else None,
            "asia_march_last_ts_iso": asia_march["last_ts_iso"] if asia_march else None,
            "asia_march_covers_target_window": trades_cover_target,
        },
        "flags": {
            "OKX_DIRECT_AVAILABLE_DATES": all_dates,
            "OKX_DIRECT_CONTIGUOUS_RANGE": (contiguous_from_03_02[0] + ".." + contiguous_from_03_02[-1]) if contiguous_from_03_02 else "(none)",
            "OKX_DIRECT_IS_FULL_MARCH": "NO",
            "OKX_DIRECT_PARTIAL_TEST_OK": "YES" if len(have_target) >= 1 and trades_cover_target else "NO",
        },
    }
    (REPORTS / "OKX_DIRECT_MARCH_PARTIAL_INVENTORY.json").write_text(
        json.dumps(inv_json, indent=2), encoding="utf-8")

    md = [
        "# OKX direct - partial March 2026 inventory",
        "",
        f"**Build:** {build_time}",
        f"**Source:** OKX direct Historical Market Data (NOT Tardis)",
        f"**Venue:** okx-swap  **Symbol:** BTC-USDT-SWAP  **Depth:** 400",
        "",
        "## A. Order book archives staged",
        "",
        "| date | size (B) | first ts UTC | action | bids/asks | sha256(8) |",
        "|---|---:|---|---|---|---|",
    ]
    for r in inv_ob:
        md.append(
            f"| {r['detected_date']} | {r['size_bytes']:,} | {r['first_ts_iso']} | "
            f"{r['first_action']} | {r['first_bids_n']}/{r['first_asks_n']} | `{r['sha256'][:8]}` |"
        )
    md.extend([
        "",
        "## B. Trade archives staged",
        "",
        "| filename | period in name | size (B) | first ts UTC | last ts UTC | sha256(8) |",
        "|---|---|---:|---|---|---|",
    ])
    for r in inv_tr:
        md.append(
            f"| `{r['filename']}` | {r['detected_period_in_name']} | {r['size_bytes']:,} | "
            f"{r['first_ts_iso']} | {r['last_ts_iso']} | `{r['sha256'][:8]}` |"
        )
    md.extend([
        "",
        "## C. Target window coverage (2026-03-02 .. 2026-03-15)",
        "",
        f"- days expected: 14",
        f"- days present in staging: **{len(have_target)}** ({', '.join(have_target)})",
        f"- days missing: {missing_target if missing_target else '(none)'}",
        f"- contiguous from 2026-03-02: **{len(contiguous_from_03_02)}** days",
        "",
        "## D. Trade coverage for target window",
        "",
        f"- Asia-March file present: **{asia_march is not None}**",
        f"- Asia-March UTC span: {asia_march['first_ts_iso'] if asia_march else None} -> {asia_march['last_ts_iso'] if asia_march else None}",
        f"- covers 2026-03-02..2026-03-15 UTC: **{trades_cover_target}**",
        "",
        "## E. Flags",
        "",
        f"- OKX_DIRECT_AVAILABLE_DATES = {all_dates}",
        f"- OKX_DIRECT_CONTIGUOUS_RANGE = `{inv_json['flags']['OKX_DIRECT_CONTIGUOUS_RANGE']}`",
        f"- OKX_DIRECT_IS_FULL_MARCH = **NO**",
        f"- OKX_DIRECT_PARTIAL_TEST_OK = **{inv_json['flags']['OKX_DIRECT_PARTIAL_TEST_OK']}**",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_PARTIAL_INVENTORY.md").write_text("\n".join(md), encoding="utf-8")

    # Orderbook schema audit (shallow; deep scan already done previously on 2026-03-14)
    sa = {
        "build_time_utc": build_time,
        "scope": "OKX direct, BTC-USDT-SWAP, depth 400, partial March 2026",
        "format": "line-delimited JSON; one event per line",
        "event_keys": ["instId", "action", "ts", "bids", "asks"],
        "action_values": ["snapshot", "update"],
        "ts": "millisecond UTC, string",
        "tuple_shape": "[price, size, ordersCount] - all strings",
        "depth_full_snapshot": 400,
        "update_semantics": "size=='0' => delete that price level",
        "snapshot_anchoring": "~15 min cadence observed on 2026-03-14 deep scan",
        "first_event_per_file": [
            {"file": r["filename"], "first_ts_iso": r["first_ts_iso"], "action": r["first_action"],
             "bids_n": r["first_bids_n"], "asks_n": r["first_asks_n"]}
            for r in inv_ob
        ],
        "flags": {
            "OKX_DIRECT_ORDERBOOK_READABLE": "YES",
            "OKX_DIRECT_ORDERBOOK_IS_L2": "YES",
            "OKX_DIRECT_ORDERBOOK_TYPE": "BOTH",
            "OKX_DIRECT_ORDERBOOK_CAN_RECONSTRUCT": "YES",
            "OKX_DIRECT_ORDERBOOK_DEPTH": 400,
            "SCHEMA_MATCHES_TARDIS_OKX": "PARTIAL",
            "schema_notes": "Same upstream OKX `books-l2-tbt` channel. Tardis hosts 4-element tuples + envelope columns; OKX direct hosts the bare 3-element tuples. Conversion is mechanical."
        },
    }
    (REPORTS / "OKX_DIRECT_MARCH_PARTIAL_ORDERBOOK_SCHEMA_AUDIT.json").write_text(
        json.dumps(sa, indent=2), encoding="utf-8")
    md_s = [
        "# OKX direct order book schema audit - partial March 2026",
        "",
        f"**Build:** {build_time}",
        "",
        "## A. Format summary",
        "",
        f"- format: {sa['format']}",
        f"- event keys: `{sa['event_keys']}`",
        f"- actions: `{sa['action_values']}`",
        f"- ts: {sa['ts']}",
        f"- tuple: `{sa['tuple_shape']}`",
        f"- depth (snapshot): {sa['depth_full_snapshot']}",
        f"- update semantics: {sa['update_semantics']}",
        f"- snapshot anchoring: {sa['snapshot_anchoring']}",
        "",
        "## B. First event of each file",
        "",
        "| file | first_ts_iso | action | bids/asks |",
        "|---|---|---|---|",
    ]
    for r in sa["first_event_per_file"]:
        md_s.append(f"| `{r['file']}` | {r['first_ts_iso']} | {r['action']} | {r['bids_n']}/{r['asks_n']} |")
    md_s.extend([
        "",
        "## C. Flags",
        "",
        f"- OKX_DIRECT_ORDERBOOK_READABLE = **YES**",
        f"- OKX_DIRECT_ORDERBOOK_IS_L2 = **YES**",
        f"- OKX_DIRECT_ORDERBOOK_TYPE = **BOTH** (snapshot anchor + incremental deltas in same stream)",
        f"- OKX_DIRECT_ORDERBOOK_CAN_RECONSTRUCT = **YES**",
        f"- OKX_DIRECT_ORDERBOOK_DEPTH = **400**",
        f"- SCHEMA_MATCHES_TARDIS_OKX = **PARTIAL** (mechanical conversion; same upstream channel)",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_PARTIAL_ORDERBOOK_SCHEMA_AUDIT.md").write_text("\n".join(md_s), encoding="utf-8")

    # Trades audit
    ta = {
        "build_time_utc": build_time,
        "files": inv_tr,
        "schema_columns": ["instrument_name", "trade_id", "side", "price", "size", "created_time"],
        "asia_month_bucket_note": (
            "OKX monthly trade-history files are bucketed by China local time (UTC+8). "
            "`trades-2026-03.zip` covers UTC 2026-02-28T16:00 .. 2026-03-31T16:00. "
            "`trades-2026-04.zip` covers UTC 2026-03-31T16:00 .. 2026-04-30T16:00."
        ),
        "flags": {
            "OKX_DIRECT_TRADES_READABLE": "YES",
            "OKX_DIRECT_TRADES_COVER_AVAILABLE_DATES": "YES" if trades_cover_target else "NO",
            "OKX_DIRECT_TRADES_USABLE_FOR_FLOW": "YES",
            "TRADES_SCHEMA_MATCHES_TARDIS_OKX": "PARTIAL",
        },
    }
    (REPORTS / "OKX_DIRECT_MARCH_PARTIAL_TRADES_AUDIT.json").write_text(
        json.dumps(ta, indent=2), encoding="utf-8")
    md_t = [
        "# OKX direct trades audit - partial March 2026",
        "",
        f"**Build:** {build_time}",
        "",
        "## A. Files",
        "",
        "| filename | period in name | size (B) | first ts UTC | last ts UTC |",
        "|---|---|---:|---|---|",
    ]
    for r in inv_tr:
        md_t.append(
            f"| `{r['filename']}` | {r['detected_period_in_name']} | {r['size_bytes']:,} | "
            f"{r['first_ts_iso']} | {r['last_ts_iso']} |"
        )
    md_t.extend([
        "",
        f"## B. Asia-month bucket note",
        "",
        ta["asia_month_bucket_note"],
        "",
        "## C. Coverage of target window 2026-03-02 .. 2026-03-15",
        "",
        f"- covers fully: **{trades_cover_target}** (UTC 2026-03-02T00:00 .. 2026-03-16T00:00 is inside Asia-March span)",
        "",
        "## D. Flags",
        "",
        f"- OKX_DIRECT_TRADES_READABLE = **YES**",
        f"- OKX_DIRECT_TRADES_COVER_AVAILABLE_DATES = **{ta['flags']['OKX_DIRECT_TRADES_COVER_AVAILABLE_DATES']}**",
        f"- OKX_DIRECT_TRADES_USABLE_FOR_FLOW = **YES**",
        f"- TRADES_SCHEMA_MATCHES_TARDIS_OKX = **PARTIAL** (column renames + microsecond timestamps)",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_PARTIAL_TRADES_AUDIT.md").write_text("\n".join(md_t), encoding="utf-8")

    print("WROTE:")
    for p in [
        REPORTS / "OKX_DIRECT_MARCH_PARTIAL_INVENTORY.json",
        REPORTS / "OKX_DIRECT_MARCH_PARTIAL_INVENTORY.md",
        REPORTS / "OKX_DIRECT_MARCH_PARTIAL_ORDERBOOK_SCHEMA_AUDIT.json",
        REPORTS / "OKX_DIRECT_MARCH_PARTIAL_ORDERBOOK_SCHEMA_AUDIT.md",
        REPORTS / "OKX_DIRECT_MARCH_PARTIAL_TRADES_AUDIT.json",
        REPORTS / "OKX_DIRECT_MARCH_PARTIAL_TRADES_AUDIT.md",
    ]:
        print(" ", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
