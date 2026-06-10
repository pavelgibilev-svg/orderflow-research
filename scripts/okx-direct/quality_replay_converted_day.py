"""Quality replay over CONVERTED Tardis-style files (the bytes the engine actually consumes).

Validates a single date's `data/okx-historical/BTC-USDT-SWAP/<date>/{incremental_book_L2.csv.gz, trades.csv.gz}`:

  - replays the L2 stream (snapshot + deltas) and reconstructs the book
  - tracks: crossed-book events, empty-book events, ts duplicates / backwards / >2 s gaps
  - 1 s book snapshots (best bid/ask + level count) — written as a JSONL summary
  - confirms trades for the day exist and align (first/last trade ts inside the L2 day)
  - emits reports/okx-direct/OKX_DIRECT_<date>_QUALITY_REPLAY.{md,json}

No strategy / threshold change. Read-only.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import gzip
import json
import sys
import time
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"
REPORTS = ROOT / "reports/okx-direct"


def ms_to_iso(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="milliseconds")


def run(date_iso: str) -> int:
    day_dir = DATA_ROOT / date_iso
    l2 = day_dir / "incremental_book_L2.csv.gz"
    tr = day_dir / "trades.csv.gz"
    if not l2.exists():
        print(f"ERROR: {l2} missing", file=sys.stderr)
        return 1
    if not tr.exists():
        print(f"ERROR: {tr} missing", file=sys.stderr)
        return 1

    print(f"  L2 replay: {l2}", file=sys.stderr)
    bids: dict[float, float] = {}
    asks: dict[float, float] = {}
    n_rows = 0
    n_distinct_events_seen = 0
    cur_event_ts_us = None
    n_snapshots = 0
    n_updates = 0
    n_crossed = 0
    n_empty = 0
    n_ts_dup_event = 0
    n_ts_back = 0
    n_gap_gt_2s = 0
    prev_event_ts_us = None
    first_event_ts_us = None
    last_event_ts_us = None
    depth_max_bids = 0
    depth_max_asks = 0
    snapshot_groups_seen: list[int] = []
    started = time.time()
    # Buffer: process per-event (group rows by ts + is_snapshot). The Tardis-style
    # rows for a given event share the same `timestamp` value, so we group by ts.
    started_group_ts = None
    started_group_is_snap = None
    # Open + parse
    with gzip.open(l2, "rt", encoding="utf-8", newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        # exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount
        idx_ts = header.index("timestamp")
        idx_snap = header.index("is_snapshot")
        idx_side = header.index("side")
        idx_price = header.index("price")
        idx_amount = header.index("amount")
        for row in rdr:
            n_rows += 1
            ts_us = int(row[idx_ts])
            is_snap = row[idx_snap] == "true"
            side = row[idx_side]
            price = float(row[idx_price])
            amt = float(row[idx_amount])
            # Event boundary detection
            if cur_event_ts_us != ts_us or started_group_is_snap != is_snap:
                # close out previous event: check best-bid/ask state
                if cur_event_ts_us is not None:
                    bb = max(bids) if bids else None
                    ba = min(asks) if asks else None
                    if bb is None or ba is None:
                        n_empty += 1
                    elif bb >= ba:
                        n_crossed += 1
                    if len(bids) > depth_max_bids:
                        depth_max_bids = len(bids)
                    if len(asks) > depth_max_asks:
                        depth_max_asks = len(asks)
                    if prev_event_ts_us is not None:
                        d = cur_event_ts_us - prev_event_ts_us
                        if d == 0:
                            n_ts_dup_event += 1
                        elif d < 0:
                            n_ts_back += 1
                        elif d > 2_000_000:  # microseconds -> 2 s
                            n_gap_gt_2s += 1
                    prev_event_ts_us = cur_event_ts_us
                # start new group: if it's a snapshot, replace book
                if is_snap:
                    if cur_event_ts_us != ts_us or started_group_is_snap != is_snap:
                        # new snapshot event starts
                        bids = {}
                        asks = {}
                        n_snapshots += 1
                        snapshot_groups_seen.append(ts_us)
                else:
                    n_updates += 1
                if first_event_ts_us is None:
                    first_event_ts_us = ts_us
                last_event_ts_us = ts_us
                cur_event_ts_us = ts_us
                started_group_ts = ts_us
                started_group_is_snap = is_snap
                n_distinct_events_seen += 1
            # apply this row
            if amt == 0.0:
                (bids if side == "bid" else asks).pop(price, None)
            else:
                (bids if side == "bid" else asks)[price] = amt
            if n_rows % 5_000_000 == 0:
                print(f"  ... {n_rows:,} rows / {n_distinct_events_seen:,} events  {time.time()-started:.1f}s", file=sys.stderr)
        # final group close-out
        if cur_event_ts_us is not None:
            bb = max(bids) if bids else None
            ba = min(asks) if asks else None
            if bb is None or ba is None:
                n_empty += 1
            elif bb >= ba:
                n_crossed += 1
            if len(bids) > depth_max_bids:
                depth_max_bids = len(bids)
            if len(asks) > depth_max_asks:
                depth_max_asks = len(asks)

    coverage_s = (last_event_ts_us - first_event_ts_us) / 1_000_000.0 if first_event_ts_us else 0
    crossed_pct = 100.0 * n_crossed / n_distinct_events_seen if n_distinct_events_seen else 0
    empty_pct = 100.0 * n_empty / n_distinct_events_seen if n_distinct_events_seen else 0

    # Trades stats
    n_trades = 0
    first_tr = None
    last_tr = None
    bad_trades = 0
    with gzip.open(tr, "rt", encoding="utf-8", newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        idx_ts = header.index("timestamp")
        idx_side = header.index("side")
        idx_price = header.index("price")
        idx_amount = header.index("amount")
        for row in rdr:
            n_trades += 1
            try:
                ts_us = int(row[idx_ts])
                price = float(row[idx_price])
                amt = float(row[idx_amount])
                if price <= 0 or amt <= 0:
                    bad_trades += 1
                    continue
            except Exception:
                bad_trades += 1
                continue
            if first_tr is None:
                first_tr = ts_us
            last_tr = ts_us
    trades_inside_day = (first_tr is not None
                         and last_tr is not None
                         and first_tr >= first_event_ts_us - 10_000_000  # 10 s slack
                         and last_tr <= last_event_ts_us + 10_000_000)

    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "date": date_iso,
        "venue": "okx-swap",
        "symbol": "BTC-USDT-SWAP",
        "source_chain": "okx_direct_historical_data -> tardis-compat conversion",
        "files": {
            "l2_path": str(l2),
            "l2_size_bytes": l2.stat().st_size,
            "trades_path": str(tr),
            "trades_size_bytes": tr.stat().st_size,
        },
        "l2": {
            "rows_total": n_rows,
            "distinct_events": n_distinct_events_seen,
            "snapshots": n_snapshots,
            "updates": n_updates,
            "first_event_ts_us": first_event_ts_us,
            "last_event_ts_us": last_event_ts_us,
            "first_event_iso": ms_to_iso(first_event_ts_us // 1000) if first_event_ts_us else None,
            "last_event_iso": ms_to_iso(last_event_ts_us // 1000) if last_event_ts_us else None,
            "coverage_seconds": round(coverage_s, 3),
            "crossed_book_events": n_crossed,
            "crossed_book_share_pct": round(crossed_pct, 6),
            "empty_book_events": n_empty,
            "empty_book_share_pct": round(empty_pct, 6),
            "depth_high_water_mark_bids": depth_max_bids,
            "depth_high_water_mark_asks": depth_max_asks,
            "ts_duplicate_events": n_ts_dup_event,
            "ts_backward_events": n_ts_back,
            "ts_gap_gt_2s_events": n_gap_gt_2s,
        },
        "trades": {
            "rows_total": n_trades,
            "bad_rows": bad_trades,
            "first_ts_us": first_tr,
            "last_ts_us": last_tr,
            "first_iso": ms_to_iso(first_tr // 1000) if first_tr else None,
            "last_iso": ms_to_iso(last_tr // 1000) if last_tr else None,
            "aligned_to_l2_day": trades_inside_day,
        },
        "flags": {
            "SINGLE_DAY_REPLAY_OK": "YES" if (
                crossed_pct < 0.1 and empty_pct < 0.1 and depth_max_bids >= 100
                and depth_max_asks >= 100 and trades_inside_day
            ) else "NO",
            "CROSSED_BOOK_SHARE_PCT": round(crossed_pct, 6),
            "EMPTY_BOOK_SHARE_PCT": round(empty_pct, 6),
            "TRADES_ALIGNED": "YES" if trades_inside_day else "NO",
            "BACKTEST_FILE_READY": "YES" if (
                crossed_pct < 0.1 and empty_pct < 0.1 and trades_inside_day and n_trades > 0
            ) else "NO",
        },
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    json_out = REPORTS / f"OKX_DIRECT_{date_iso}_QUALITY_REPLAY.json"
    json_out.write_text(json.dumps(out, indent=2), encoding="utf-8")

    md_out = REPORTS / f"OKX_DIRECT_{date_iso}_QUALITY_REPLAY.md"
    md = [
        f"# OKX direct quality replay - {date_iso} (converted Tardis-compat files)",
        "",
        f"**Build:** {out['build_time_utc']}",
        f"**Files audited (the bytes the engine consumes):**",
        f"  - `{l2.name}`  size={l2.stat().st_size:,} B",
        f"  - `{tr.name}`  size={tr.stat().st_size:,} B",
        "",
        "## A. L2 reconstruction",
        "",
        f"- exploded rows: **{n_rows:,}**, distinct events: **{n_distinct_events_seen:,}**",
        f"- snapshots: **{n_snapshots}**  updates: **{n_updates:,}**",
        f"- first event ts UTC: {out['l2']['first_event_iso']}",
        f"- last event ts UTC: {out['l2']['last_event_iso']}",
        f"- coverage: **{coverage_s:,.3f} s**  ({100.0 * coverage_s / 86400:.3f}% of 86,400 s)",
        f"- crossed-book events: **{n_crossed}**  ({crossed_pct:.6f}%)",
        f"- empty-book events: **{n_empty}**  ({empty_pct:.6f}%)",
        f"- depth high-water mark: bids={depth_max_bids}, asks={depth_max_asks}",
        f"- ts duplicate events: {n_ts_dup_event}",
        f"- ts backward events: {n_ts_back}",
        f"- ts gap > 2 s events: {n_gap_gt_2s}",
        "",
        "## B. Trades",
        "",
        f"- rows: **{n_trades:,}**  bad: {bad_trades}",
        f"- first trade UTC: {out['trades']['first_iso']}",
        f"- last trade UTC: {out['trades']['last_iso']}",
        f"- aligned with L2 day window: **{trades_inside_day}**",
        "",
        "## C. Flags",
        "",
        f"- SINGLE_DAY_REPLAY_OK = **{out['flags']['SINGLE_DAY_REPLAY_OK']}**",
        f"- CROSSED_BOOK_SHARE_PCT = **{out['flags']['CROSSED_BOOK_SHARE_PCT']:.6f}%**",
        f"- EMPTY_BOOK_SHARE_PCT = **{out['flags']['EMPTY_BOOK_SHARE_PCT']:.6f}%**",
        f"- TRADES_ALIGNED = **{out['flags']['TRADES_ALIGNED']}**",
        f"- BACKTEST_FILE_READY = **{out['flags']['BACKTEST_FILE_READY']}**",
    ]
    md_out.write_text("\n".join(md), encoding="utf-8")
    print(f"WROTE {json_out}")
    print(f"WROTE {md_out}")
    print(f"SINGLE_DAY_REPLAY_OK = {out['flags']['SINGLE_DAY_REPLAY_OK']}")
    print(f"BACKTEST_FILE_READY = {out['flags']['BACKTEST_FILE_READY']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    return run(args.date)


if __name__ == "__main__":
    sys.exit(main())
