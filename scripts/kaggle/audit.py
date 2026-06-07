"""
Audit the downloaded Kaggle BTCUSDT L3 dataset using vectorized pyarrow compute.

Writes streaming progress to stderr (flushed) so we can see it grow, and the
final JSON to stdout in one shot at the end.
"""

from __future__ import annotations
import json
import sys
import time
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pyarrow.compute as pc

DATA = Path("data/kaggle/binance-btcusdt-l3")
FILES = {
    "diffs": "orderbook_diffs_20260418.parquet",
    "snapshots": "orderbook_snapshots_20260418.parquet",
    "trades": "trades_20260418.parquet",
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def schema_to_dict(schema) -> list[dict[str, Any]]:
    return [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in schema]


def first_n_rows(path: Path, n: int = 3) -> list[dict[str, Any]]:
    pf = pq.ParquetFile(path)
    rows: list[dict[str, Any]] = []
    for batch in pf.iter_batches(batch_size=n):
        rows.extend(batch.to_pylist())
        if len(rows) >= n:
            break
    return rows[:n]


def detect_precision(t: str) -> str:
    if "timestamp[ns" in t:
        return "ns"
    if "timestamp[us" in t:
        return "us"
    if "timestamp[ms" in t:
        return "ms"
    if "timestamp[s" in t:
        return "s"
    if t in ("int64", "uint64"):
        return "epoch_int_unknown_unit"
    return "unknown"


def audit_basic(label: str, file: str) -> dict[str, Any]:
    path = DATA / file
    log(f"audit_basic: {file}")
    out: dict[str, Any] = {"file": file, "size_bytes": path.stat().st_size}
    pf = pq.ParquetFile(path)
    md = pf.metadata
    out["num_rows"] = md.num_rows
    out["num_row_groups"] = md.num_row_groups
    schema_fields = schema_to_dict(pf.schema_arrow)
    out["schema"] = schema_fields
    out["sample_rows"] = first_n_rows(path, 3)
    return out


def audit_diffs() -> dict[str, Any]:
    file = FILES["diffs"]
    path = DATA / file
    log(f"audit_diffs: {file}")
    pf = pq.ParquetFile(path)
    cols = ["time", "first_update_id", "final_update_id"]
    t_min, t_max = None, None
    fu_min, fu_max = None, None
    lu_min, lu_max = None, None
    seq_gaps = 0
    seq_pairs = 0
    prev_lu = None
    n = 0
    for batch in pf.iter_batches(columns=cols, batch_size=200_000):
        n += batch.num_rows
        log(f"  batch rows={batch.num_rows}, total={n}")
        # time min/max
        ts = batch.column("time")
        b_tmin = pc.min(ts).as_py()
        b_tmax = pc.max(ts).as_py()
        if b_tmin is not None and (t_min is None or b_tmin < t_min):
            t_min = b_tmin
        if b_tmax is not None and (t_max is None or b_tmax > t_max):
            t_max = b_tmax
        fu = batch.column("first_update_id")
        lu = batch.column("final_update_id")
        b_fmin = pc.min(fu).as_py(); b_fmax = pc.max(fu).as_py()
        b_lmin = pc.min(lu).as_py(); b_lmax = pc.max(lu).as_py()
        if b_fmin is not None and (fu_min is None or b_fmin < fu_min):
            fu_min = b_fmin
        if b_fmax is not None and (fu_max is None or b_fmax > fu_max):
            fu_max = b_fmax
        if b_lmin is not None and (lu_min is None or b_lmin < lu_min):
            lu_min = b_lmin
        if b_lmax is not None and (lu_max is None or b_lmax > lu_max):
            lu_max = b_lmax
        # Sequence-gap analysis: diffs[i].first_update_id should equal diffs[i-1].final_update_id + 1
        first_arr = fu.to_pylist()
        final_arr = lu.to_pylist()
        for i in range(len(first_arr)):
            if prev_lu is not None and first_arr[i] is not None:
                seq_pairs += 1
                if first_arr[i] != prev_lu + 1:
                    seq_gaps += 1
            prev_lu = final_arr[i] if final_arr[i] is not None else prev_lu
    out: dict[str, Any] = {
        "rows": n,
        "time_min": str(t_min),
        "time_max": str(t_max),
        "first_update_id_min": str(fu_min),
        "first_update_id_max": str(fu_max),
        "final_update_id_min": str(lu_min),
        "final_update_id_max": str(lu_max),
        "consecutive_pairs": seq_pairs,
        "sequence_gaps": seq_gaps,
        "sequence_gap_share": (seq_gaps / seq_pairs) if seq_pairs else None,
    }
    return out


def audit_diffs_levels_sample() -> dict[str, Any]:
    """Parse the JSON bids/asks columns on the first ~5k rows to understand
    the level-change shape and confirm qty=0 means delete.
    """
    file = FILES["diffs"]
    path = DATA / file
    log(f"audit_diffs_levels_sample: {file}")
    pf = pq.ParquetFile(path)
    bid_levels = 0
    ask_levels = 0
    bid_zero = 0
    ask_zero = 0
    bid_nonzero = 0
    ask_nonzero = 0
    rows_seen = 0
    examples_bid: list = []
    examples_ask: list = []
    for batch in pf.iter_batches(columns=["bids", "asks"], batch_size=2000):
        bids_arr = batch.column("bids").to_pylist()
        asks_arr = batch.column("asks").to_pylist()
        for b in bids_arr:
            if b is None:
                continue
            try:
                lvls = json.loads(b)
            except Exception:
                continue
            for lvl in lvls:
                bid_levels += 1
                try:
                    qf = float(lvl[1])
                    if qf == 0:
                        bid_zero += 1
                    else:
                        bid_nonzero += 1
                except Exception:
                    pass
            if len(examples_bid) < 3 and lvls:
                examples_bid.append(lvls[:3])
        for a in asks_arr:
            if a is None:
                continue
            try:
                lvls = json.loads(a)
            except Exception:
                continue
            for lvl in lvls:
                ask_levels += 1
                try:
                    qf = float(lvl[1])
                    if qf == 0:
                        ask_zero += 1
                    else:
                        ask_nonzero += 1
                except Exception:
                    pass
            if len(examples_ask) < 3 and lvls:
                examples_ask.append(lvls[:3])
        rows_seen += batch.num_rows
        if rows_seen >= 5000:
            break
    return {
        "rows_inspected": rows_seen,
        "bid_levels_total": bid_levels,
        "ask_levels_total": ask_levels,
        "bid_zero_qty": bid_zero,
        "bid_nonzero_qty": bid_nonzero,
        "ask_zero_qty": ask_zero,
        "ask_nonzero_qty": ask_nonzero,
        "example_bid_changes": examples_bid,
        "example_ask_changes": examples_ask,
    }


def audit_snapshots() -> dict[str, Any]:
    file = FILES["snapshots"]
    path = DATA / file
    log(f"audit_snapshots: {file}")
    pf = pq.ParquetFile(path)
    cols = ["time", "last_update_id"]
    n = 0
    t_min, t_max = None, None
    lu_min, lu_max = None, None
    for batch in pf.iter_batches(columns=cols, batch_size=200_000):
        n += batch.num_rows
        ts = batch.column("time")
        if (b_tmin := pc.min(ts).as_py()) is not None and (t_min is None or b_tmin < t_min):
            t_min = b_tmin
        if (b_tmax := pc.max(ts).as_py()) is not None and (t_max is None or b_tmax > t_max):
            t_max = b_tmax
        lu = batch.column("last_update_id")
        if (b := pc.min(lu).as_py()) is not None and (lu_min is None or b < lu_min):
            lu_min = b
        if (b := pc.max(lu).as_py()) is not None and (lu_max is None or b > lu_max):
            lu_max = b
    # Inspect first snapshot fully
    first_full = first_n_rows(path, 1)[0] if pf.metadata.num_rows > 0 else None
    bids_top = asks_top = None
    bids_count = asks_count = None
    if first_full is not None:
        try:
            bids_list = json.loads(first_full["bids"])
            asks_list = json.loads(first_full["asks"])
            bids_count = len(bids_list)
            asks_count = len(asks_list)
            bids_top = bids_list[:3]
            asks_top = asks_list[:3]
        except Exception as e:
            log(f"first_full parse error: {e}")
    return {
        "rows": n,
        "time_min": str(t_min),
        "time_max": str(t_max),
        "last_update_id_min": str(lu_min),
        "last_update_id_max": str(lu_max),
        "first_snapshot_bid_levels": bids_count,
        "first_snapshot_ask_levels": asks_count,
        "first_snapshot_top3_bids": bids_top,
        "first_snapshot_top3_asks": asks_top,
        "first_snapshot_time": str(first_full.get("time")) if first_full else None,
        "first_snapshot_last_update_id": str(first_full.get("last_update_id")) if first_full else None,
    }


def audit_trades() -> dict[str, Any]:
    file = FILES["trades"]
    path = DATA / file
    log(f"audit_trades: {file}")
    pf = pq.ParquetFile(path)
    cols = ["time", "trade_id", "price", "qty", "is_buyer_maker"]
    n = 0
    t_min, t_max = None, None
    p_min, p_max = None, None
    q_sum, q_zero = 0.0, 0
    tid_min, tid_max = None, None
    bm_true, bm_false = 0, 0
    for batch in pf.iter_batches(columns=cols, batch_size=200_000):
        n += batch.num_rows
        ts = batch.column("time")
        if (b := pc.min(ts).as_py()) is not None and (t_min is None or b < t_min):
            t_min = b
        if (b := pc.max(ts).as_py()) is not None and (t_max is None or b > t_max):
            t_max = b
        price = batch.column("price")
        qty = batch.column("qty")
        tid = batch.column("trade_id")
        bm = batch.column("is_buyer_maker")
        if (b := pc.min(price).as_py()) is not None and (p_min is None or b < p_min):
            p_min = b
        if (b := pc.max(price).as_py()) is not None and (p_max is None or b > p_max):
            p_max = b
        q_sum += float(pc.sum(qty).as_py() or 0)
        q_zero += int(pc.sum(pc.equal(qty, 0)).as_py() or 0)
        if (b := pc.min(tid).as_py()) is not None and (tid_min is None or b < tid_min):
            tid_min = b
        if (b := pc.max(tid).as_py()) is not None and (tid_max is None or b > tid_max):
            tid_max = b
        bm_true += int(pc.sum(bm).as_py() or 0)
        bm_false += batch.num_rows - int(pc.sum(bm).as_py() or 0)
    return {
        "rows": n,
        "time_min": str(t_min),
        "time_max": str(t_max),
        "price_min": p_min,
        "price_max": p_max,
        "qty_sum": q_sum,
        "qty_zero_rows": q_zero,
        "trade_id_min": str(tid_min),
        "trade_id_max": str(tid_max),
        "trade_id_span": (int(tid_max) - int(tid_min)) if (tid_min is not None and tid_max is not None) else None,
        "trade_id_density": (n / max(1, (int(tid_max) - int(tid_min)))) if (tid_min is not None and tid_max is not None) else None,
        "is_buyer_maker_true": bm_true,
        "is_buyer_maker_false": bm_false,
        "is_buyer_maker_true_share": bm_true / n if n else None,
    }


def main() -> int:
    out: dict[str, Any] = {}
    out["files"] = {label: audit_basic(label, fname) for label, fname in FILES.items()}
    out["diffs_deep"] = audit_diffs()
    out["diffs_levels_sample_first_5k_rows"] = audit_diffs_levels_sample()
    out["snapshots_deep"] = audit_snapshots()
    out["trades_deep"] = audit_trades()
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
