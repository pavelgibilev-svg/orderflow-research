"""Convert OKX direct Historical Market Data into Tardis-style CSV.gz files
that the existing engine (`backtestDay.ts` / `backtest:okx-technical`) consumes.

Reads:
    data/okx-direct/BTC-USDT-SWAP/2026-03/raw/orderbook/BTC-USDT-SWAP-L2orderbook-400lv-<DATE>.tar.gz
    data/okx-direct/BTC-USDT-SWAP/2026-03/raw/trades/BTC-USDT-SWAP-trades-2026-03.zip
                                                  (or -2026-04.zip if needed)

Writes:
    data/okx-historical/BTC-USDT-SWAP/<DATE>/incremental_book_L2.csv.gz
    data/okx-historical/BTC-USDT-SWAP/<DATE>/trades.csv.gz

Schema produced (exact format already in the repo from prior Tardis-first-of-month runs):

    incremental_book_L2.csv.gz:
        exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount
        - exchange='okex-swap', symbol='BTC-USDT-SWAP'
        - timestamp = OKX direct ts_ms * 1000  (= microseconds, Tardis convention)
        - local_timestamp = same (we have no separate local arrival; using exchange ts)
        - is_snapshot = 'true' if event action=='snapshot' else 'false'
        - side = 'ask' or 'bid'
        - price, amount = decimal strings (amount=='0' => delete that level)

    trades.csv.gz:
        exchange,symbol,timestamp,local_timestamp,id,side,price,amount
        - exchange='okex-swap', symbol='BTC-USDT-SWAP'
        - timestamp = OKX direct created_time_ms * 1000 (microseconds)
        - local_timestamp = same
        - id = trade_id
        - side = 'buy' or 'sell'  (taker/aggressor side)
        - price, amount = decimal strings (amount field renamed from OKX 'size')
        - Filter rows where created_time is in [date 00:00 UTC, date+1 00:00 UTC)

This script is strict-sequential per date. Do not parallelise without separate
output dirs. No strategy / threshold change. Same upstream books-l2-tbt channel
that Tardis re-publishes, so the converted output is byte-compatible with the
Tardis OKX format the engine already supports.
"""
from __future__ import annotations
import argparse
import datetime as dt
import gzip
import io
import json
import re
import sys
import tarfile
import time
import zipfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
OB_RAW = ROOT / "data/okx-direct/BTC-USDT-SWAP/2026-03/raw/orderbook"
TR_RAW = ROOT / "data/okx-direct/BTC-USDT-SWAP/2026-03/raw/trades"
OUT_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"
EXCH = "okex-swap"
SYM = "BTC-USDT-SWAP"


def utc_day_window_ms(date_iso: str) -> tuple[int, int]:
    """[start_ms, end_ms) covering the full UTC day."""
    d = dt.datetime.fromisoformat(date_iso).replace(tzinfo=dt.timezone.utc)
    start = int(d.timestamp() * 1000)
    end = start + 86_400_000
    return start, end


def pick_trades_zip(date_iso: str) -> Path:
    """Asia-bucketing: trades-YYYY-MM.zip covers UTC [prev_month_28 16:00, this_month_31 16:00).

    For dates 2026-03-01..2026-03-31 UTC:
      - 2026-03-01 .. 2026-03-31 00:00..16:00 UTC is in trades-2026-03.zip
      - 2026-03-31 16:00 .. 2026-04-30 16:00 UTC is in trades-2026-04.zip
    For our scope (full UTC days, 2026-03-02..2026-03-15) the 2026-03 file
    fully covers everything.
    """
    return TR_RAW / "BTC-USDT-SWAP-trades-2026-03.zip"


def convert_orderbook(date_iso: str, out_path: Path, summary: dict) -> None:
    src = OB_RAW / f"BTC-USDT-SWAP-L2orderbook-400lv-{date_iso}.tar.gz"
    if not src.exists():
        raise FileNotFoundError(src)
    print(f"  [ob] reading {src.name}", file=sys.stderr)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    n_events = 0
    n_snap_events = 0
    n_update_events = 0
    n_rows_written = 0
    first_ts_ms = None
    last_ts_ms = None
    # gzip text writer, modest compression for speed
    with gzip.open(out_path, mode="wt", encoding="utf-8", newline="\n", compresslevel=5) as gz:
        gz.write("exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount\n")
        with tarfile.open(src, "r:gz") as tf:
            m = tf.getmembers()[0]
            fp = tf.extractfile(m)
            if fp is None:
                raise RuntimeError("cannot open inner data file")
            for raw in fp:
                n_events += 1
                d = json.loads(raw)
                ts_ms = int(d["ts"])
                ts_us = ts_ms * 1000
                if first_ts_ms is None:
                    first_ts_ms = ts_ms
                last_ts_ms = ts_ms
                is_snap = d["action"] == "snapshot"
                snap_str = "true" if is_snap else "false"
                if is_snap:
                    n_snap_events += 1
                else:
                    n_update_events += 1
                # OKX direct tuple: [price, size, ordersCount] — Tardis style needs amount only.
                # Output ask rows then bid rows; preserve order so updates apply correctly.
                lines: list[str] = []
                for p, s, _ in d.get("asks", ()):
                    lines.append(f"{EXCH},{SYM},{ts_us},{ts_us},{snap_str},ask,{p},{s}\n")
                for p, s, _ in d.get("bids", ()):
                    lines.append(f"{EXCH},{SYM},{ts_us},{ts_us},{snap_str},bid,{p},{s}\n")
                if lines:
                    gz.write("".join(lines))
                    n_rows_written += len(lines)
                if n_events % 500_000 == 0:
                    dt_s = time.time() - started
                    print(f"  [ob] {n_events:,} events  {n_rows_written:,} rows  {dt_s:.1f}s", file=sys.stderr)
    dur = time.time() - started
    print(f"  [ob] done {n_events:,} events  {n_rows_written:,} rows  {dur:.1f}s -> {out_path.name}",
          file=sys.stderr)
    summary["orderbook"] = {
        "src_archive": src.name,
        "events_total": n_events,
        "snapshot_events": n_snap_events,
        "update_events": n_update_events,
        "rows_written": n_rows_written,
        "first_ts_ms": first_ts_ms,
        "last_ts_ms": last_ts_ms,
        "duration_s": round(dur, 1),
        "out_path": str(out_path),
        "out_size_bytes": out_path.stat().st_size,
    }


def convert_trades(date_iso: str, out_path: Path, summary: dict) -> None:
    src = pick_trades_zip(date_iso)
    start_ms, end_ms = utc_day_window_ms(date_iso)
    print(f"  [tr] reading {src.name} -> slice [{start_ms}, {end_ms})", file=sys.stderr)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    n_rows_in = 0
    n_rows_out = 0
    first_kept_ts_ms = None
    last_kept_ts_ms = None
    bad_rows = 0
    with gzip.open(out_path, mode="wt", encoding="utf-8", newline="\n", compresslevel=5) as gz:
        gz.write("exchange,symbol,timestamp,local_timestamp,id,side,price,amount\n")
        with zipfile.ZipFile(src) as zf:
            inner = zf.infolist()[0].filename
            with zf.open(inner, "r") as fp:
                _header = fp.readline()
                buf = io.TextIOWrapper(fp, encoding="utf-8", newline="")
                for line in buf:
                    n_rows_in += 1
                    line = line.rstrip("\r\n")
                    if not line:
                        continue
                    # instrument_name,trade_id,side,price,size,created_time
                    try:
                        inst, tid, side, price, size, ct = line.split(",")
                        ts_ms = int(ct)
                    except Exception:
                        bad_rows += 1
                        continue
                    if ts_ms < start_ms:
                        # we are streaming the whole month chronologically; we can break early once we pass the window
                        continue
                    if ts_ms >= end_ms:
                        # safely break: monthly file is monotonic
                        break
                    if first_kept_ts_ms is None:
                        first_kept_ts_ms = ts_ms
                    last_kept_ts_ms = ts_ms
                    ts_us = ts_ms * 1000
                    gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},{tid},{side},{price},{size}\n")
                    n_rows_out += 1
                    if n_rows_out % 1_000_000 == 0:
                        dt_s = time.time() - started
                        print(f"  [tr] kept {n_rows_out:,}  scanned {n_rows_in:,}  {dt_s:.1f}s", file=sys.stderr)
    dur = time.time() - started
    print(f"  [tr] done kept {n_rows_out:,}  scanned {n_rows_in:,}  bad={bad_rows}  {dur:.1f}s -> {out_path.name}",
          file=sys.stderr)
    summary["trades"] = {
        "src_archive": src.name,
        "rows_scanned": n_rows_in,
        "rows_kept": n_rows_out,
        "bad_rows": bad_rows,
        "first_kept_ts_ms": first_kept_ts_ms,
        "last_kept_ts_ms": last_kept_ts_ms,
        "duration_s": round(dur, 1),
        "out_path": str(out_path),
        "out_size_bytes": out_path.stat().st_size,
    }


def run_one(date_iso: str) -> dict:
    summary: dict = {
        "date": date_iso,
        "exchange": EXCH,
        "symbol": SYM,
        "source": "okx_direct_historical_data",
        "depth": 400,
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    out_dir = OUT_ROOT / date_iso
    out_dir.mkdir(parents=True, exist_ok=True)
    ob_out = out_dir / "incremental_book_L2.csv.gz"
    tr_out = out_dir / "trades.csv.gz"

    if ob_out.exists():
        print(f"  [ob] {ob_out} already exists -- skipping orderbook conversion", file=sys.stderr)
        summary["orderbook"] = {"reused_existing": str(ob_out), "out_size_bytes": ob_out.stat().st_size}
    else:
        convert_orderbook(date_iso, ob_out, summary)

    if tr_out.exists():
        print(f"  [tr] {tr_out} already exists -- skipping trades conversion", file=sys.stderr)
        summary["trades"] = {"reused_existing": str(tr_out), "out_size_bytes": tr_out.stat().st_size}
    else:
        convert_trades(date_iso, tr_out, summary)

    summary["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD (single date) or comma-separated list")
    args = ap.parse_args()
    dates = [d.strip() for d in args.date.split(",") if d.strip()]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", dates[0]):
        raise SystemExit(f"bad --date: {args.date}")
    all_summaries: list[dict] = []
    for d in dates:
        print(f"=== convert {d} ===", file=sys.stderr)
        s = run_one(d)
        all_summaries.append(s)
    # Write a JSON manifest per invocation
    manifest = ROOT / "reports/okx-direct/_convert_log.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a", encoding="utf-8") as f:
        for s in all_summaries:
            f.write(json.dumps(s, separators=(",", ":")) + "\n")
    print(f"manifest appended to {manifest}", file=sys.stderr)
    for s in all_summaries:
        print(json.dumps(s, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
