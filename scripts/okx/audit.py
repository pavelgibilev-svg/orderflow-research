"""Audit OKX-swap BTC-USDT-SWAP 2026-04-01 sample.

Reads the gzipped CSVs streamingly, reports headers, sample rows, row counts,
time ranges, gap analysis on sequence ids if present, qty=0 semantics, and
crossed/empty book check based on the book_ticker stream.
"""
from __future__ import annotations
import csv
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA = Path("data/okx-historical/BTC-USDT-SWAP/2026-04-01")
FILES = {
    "incremental_book_L2": DATA / "incremental_book_L2.csv.gz",
    "trades": DATA / "trades.csv.gz",
    "book_ticker": DATA / "book_ticker.csv.gz",
    "derivative_ticker": DATA / "derivative_ticker.csv.gz",
    "liquidations": DATA / "liquidations.csv.gz",
}


def micros_to_dt(us: int) -> str:
    return datetime.fromtimestamp(us / 1_000_000, tz=timezone.utc).isoformat()


def audit_csv(path: Path, label: str, deep: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {"file": str(path), "size_bytes": path.stat().st_size}
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        out["columns"] = header
        # Read first 3 raw rows
        samples: list[list[str]] = []
        for _ in range(3):
            try:
                samples.append(next(rdr))
            except StopIteration:
                break
        out["sample_rows"] = [dict(zip(header, r)) for r in samples]
        if not deep:
            return out

    # Deep pass: count rows, time range, side breakdown, sequence integrity, etc.
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        col = {name: i for i, name in enumerate(header)}
        n = 0
        ts_idx = col.get("timestamp")
        local_ts_idx = col.get("local_timestamp")
        side_idx = col.get("side")
        is_snap_idx = col.get("is_snapshot")
        seq_idx = (
            col.get("sequence_id")
            or col.get("update_id")
            or col.get("seq_id")
            or col.get("id")
            or col.get("trade_id")
        )
        amount_idx = col.get("amount") or col.get("size") or col.get("qty")
        price_idx = col.get("price")

        ts_min, ts_max = None, None
        side_counter: dict[str, int] = {}
        is_snap_counter: dict[str, int] = {}
        amount_zero, amount_nonzero = 0, 0
        price_min, price_max = float("inf"), 0.0
        seq_prev: int | None = None
        seq_pairs = 0
        seq_gaps = 0
        seq_min, seq_max = None, None

        # For book_ticker: crossed / empty detection
        is_book_ticker = label == "book_ticker"
        bb_idx = col.get("bid_price") or col.get("best_bid_price")
        ba_idx = col.get("ask_price") or col.get("best_ask_price")
        bbq_idx = col.get("bid_amount") or col.get("best_bid_amount") or col.get("bid_size")
        baq_idx = col.get("ask_amount") or col.get("best_ask_amount") or col.get("ask_size")
        crossed = 0
        empty = 0
        per_second_count: dict[int, int] = {}

        for row in rdr:
            n += 1
            if ts_idx is not None:
                try:
                    v = int(row[ts_idx])
                    if ts_min is None or v < ts_min:
                        ts_min = v
                    if ts_max is None or v > ts_max:
                        ts_max = v
                    # Bucket per second
                    sec = v // 1_000_000
                    per_second_count[sec] = per_second_count.get(sec, 0) + 1
                except Exception:
                    pass
            if side_idx is not None:
                s = row[side_idx]
                side_counter[s] = side_counter.get(s, 0) + 1
            if is_snap_idx is not None:
                s = row[is_snap_idx]
                is_snap_counter[s] = is_snap_counter.get(s, 0) + 1
            if amount_idx is not None:
                try:
                    a = float(row[amount_idx])
                    if a == 0:
                        amount_zero += 1
                    else:
                        amount_nonzero += 1
                except Exception:
                    pass
            if price_idx is not None:
                try:
                    p = float(row[price_idx])
                    if 100 < p < 10_000_000:  # sanity filter
                        if p < price_min:
                            price_min = p
                        if p > price_max:
                            price_max = p
                except Exception:
                    pass
            if seq_idx is not None:
                try:
                    sv = int(row[seq_idx])
                    if seq_min is None or sv < seq_min:
                        seq_min = sv
                    if seq_max is None or sv > seq_max:
                        seq_max = sv
                    if seq_prev is not None:
                        seq_pairs += 1
                        if sv != seq_prev + 1:
                            seq_gaps += 1
                    seq_prev = sv
                except Exception:
                    pass
            if is_book_ticker and bb_idx is not None and ba_idx is not None:
                try:
                    bb = float(row[bb_idx])
                    ba = float(row[ba_idx])
                    if bb == 0 or ba == 0:
                        empty += 1
                    elif bb >= ba:
                        crossed += 1
                except Exception:
                    pass

        out["row_count"] = n
        if ts_min is not None:
            out["time_min_utc"] = micros_to_dt(ts_min)
            out["time_max_utc"] = micros_to_dt(ts_max)
            out["duration_seconds"] = (ts_max - ts_min) / 1_000_000.0
            out["distinct_seconds_with_events"] = len(per_second_count)
            counts = sorted(per_second_count.values())
            if counts:
                out["events_per_second"] = {
                    "min": counts[0],
                    "p50": counts[len(counts) // 2],
                    "p95": counts[int(len(counts) * 0.95)],
                    "max": counts[-1],
                    "mean": sum(counts) / len(counts),
                }
        if side_counter:
            out["side_distribution"] = side_counter
        if is_snap_counter:
            out["is_snapshot_distribution"] = is_snap_counter
        if amount_idx is not None:
            out["amount_zero_rows"] = amount_zero
            out["amount_nonzero_rows"] = amount_nonzero
            total = amount_zero + amount_nonzero
            if total:
                out["amount_zero_share"] = amount_zero / total
        if price_idx is not None and price_min != float("inf"):
            out["price_min"] = price_min
            out["price_max"] = price_max
        if seq_idx is not None and seq_min is not None:
            out["sequence_id_min"] = seq_min
            out["sequence_id_max"] = seq_max
            out["sequence_pairs_checked"] = seq_pairs
            out["sequence_gaps"] = seq_gaps
            out["sequence_gap_share"] = (seq_gaps / seq_pairs) if seq_pairs else None
        if is_book_ticker:
            out["book_ticker_crossed_rows"] = crossed
            out["book_ticker_empty_rows"] = empty
    return out


def main() -> int:
    result: dict[str, Any] = {}
    for label, path in FILES.items():
        print(f"=== {label} ===", file=sys.stderr, flush=True)
        result[label] = audit_csv(path, label, deep=True)
    Path("data/okx-historical/_audit_raw.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
