"""
Parser-correctness test replay for the Kaggle BTCUSDT (SPOT) L2 sample.

Window: 2026-04-18 06:00:00 -> 09:00:00 UTC (3 hours).

Per-minute re-anchoring: for each snapshot in the window we initialize a
fresh book, apply diffs until the next snapshot, and generate 1-second
samples within that segment. This avoids the staleness drift that affects
naive single-anchor replays (Binance only sends deltas for levels that
changed, so an old snapshot's tail levels can ghost-cross when price moves).
"""

from __future__ import annotations
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from sortedcontainers import SortedDict

import pyarrow.parquet as pq
import pyarrow.compute as pc
import pyarrow as pa

DATA = Path("data/kaggle/binance-btcusdt-l3")
DIFFS = DATA / "orderbook_diffs_20260418.parquet"
SNAPS = DATA / "orderbook_snapshots_20260418.parquet"
TRADES = DATA / "trades_20260418.parquet"
OUT_JSON = DATA / "_replay_raw.json"

WINDOW_START = datetime(2026, 4, 18, 6, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 4, 18, 9, 0, 0, tzinfo=timezone.utc)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def load_snapshots_in_range(t0: datetime, t1: datetime) -> list[dict[str, Any]]:
    """Return all snapshots whose time is in [t0, t1], sorted ascending."""
    pf = pq.ParquetFile(SNAPS)
    out: list[dict[str, Any]] = []
    for batch in pf.iter_batches(batch_size=200_000):
        for r in batch.to_pylist():
            if t0 <= r["time"] <= t1:
                out.append(r)
    out.sort(key=lambda r: r["time"])
    return out


def init_book(snap: dict[str, Any]) -> tuple[SortedDict, SortedDict, int]:
    bids = SortedDict()
    asks = SortedDict()
    for p_str, q_str in json.loads(snap["bids"]):
        p, q = float(p_str), float(q_str)
        if q > 0:
            bids[-p] = q
    for p_str, q_str in json.loads(snap["asks"]):
        p, q = float(p_str), float(q_str)
        if q > 0:
            asks[p] = q
    return bids, asks, int(snap["last_update_id"])


def best_bid_ask(bids: SortedDict, asks: SortedDict) -> tuple[float | None, float | None]:
    bid = -bids.peekitem(0)[0] if bids else None
    ask = asks.peekitem(0)[0] if asks else None
    return bid, ask


def replay_segment(snap: dict[str, Any], t_end: datetime, all_diffs_table: pa.Table) -> dict[str, Any]:
    """Replay one segment: from snap.time to t_end. Returns stats."""
    bids, asks, anchor_id = init_book(snap)
    bid_changes = ask_changes = deletes = sets = 0
    seq_pairs = seq_gaps = 0
    prev_lu = None
    crossed = empty = 0
    spread_total = 0.0
    spread_min = float("inf")
    spread_max = 0.0
    spread_samples = 0
    last_emitted_second: datetime | None = None
    diff_rows = 0

    # Filter diffs in [snap.time, t_end] AND with final_update_id > anchor_id
    ts_col = all_diffs_table.column("time")
    snap_ts_pa = pa.scalar(snap["time"], type=ts_col.type)
    end_ts_pa = pa.scalar(t_end, type=ts_col.type)
    mask_t = pc.and_(pc.greater_equal(ts_col, snap_ts_pa), pc.less(ts_col, end_ts_pa))
    fu = all_diffs_table.column("final_update_id")
    anchor_pa = pa.scalar(anchor_id, type=fu.type)
    mask_seq = pc.greater(fu, anchor_pa)
    mask = pc.and_(mask_t, mask_seq)
    seg = all_diffs_table.filter(mask)

    rows = seg.to_pylist()
    for r in rows:
        diff_rows += 1
        ts = r["time"]
        first_id = int(r["first_update_id"])
        final_id = int(r["final_update_id"])
        if prev_lu is not None:
            seq_pairs += 1
            if first_id != prev_lu + 1:
                seq_gaps += 1
        prev_lu = final_id

        try:
            blvls = json.loads(r["bids"])
        except Exception:
            blvls = []
        for p_s, q_s in blvls:
            p = float(p_s); q = float(q_s)
            bid_changes += 1
            if q == 0:
                bids.pop(-p, None); deletes += 1
            else:
                bids[-p] = q; sets += 1

        try:
            alvls = json.loads(r["asks"])
        except Exception:
            alvls = []
        for p_s, q_s in alvls:
            p = float(p_s); q = float(q_s)
            ask_changes += 1
            if q == 0:
                asks.pop(p, None); deletes += 1
            else:
                asks[p] = q; sets += 1

        cur_sec = ts.replace(microsecond=0)
        if last_emitted_second is None or cur_sec != last_emitted_second:
            bb, ba = best_bid_ask(bids, asks)
            if bb is None or ba is None:
                empty += 1
            else:
                sp = ba - bb
                if sp < 0:
                    crossed += 1
                else:
                    spread_total += sp
                    spread_min = min(spread_min, sp)
                    spread_max = max(spread_max, sp)
                    spread_samples += 1
            last_emitted_second = cur_sec

    return {
        "anchor_time": str(snap["time"]),
        "anchor_last_update_id": anchor_id,
        "segment_end": t_end.isoformat(),
        "diff_rows_applied": diff_rows,
        "bid_level_changes": bid_changes,
        "ask_level_changes": ask_changes,
        "level_deletes": deletes,
        "level_sets": sets,
        "sequence_pairs_checked": seq_pairs,
        "sequence_gaps": seq_gaps,
        "second_samples_emitted": spread_samples + crossed + empty,
        "second_crossed": crossed,
        "second_empty": empty,
        "second_normal_samples": spread_samples,
        "spread_min_usd": spread_min if spread_min != float("inf") else None,
        "spread_max_usd": spread_max,
        "spread_avg_usd": (spread_total / spread_samples) if spread_samples else None,
        "final_bid_levels": len(bids),
        "final_ask_levels": len(asks),
        "final_best_bid": -bids.peekitem(0)[0] if bids else None,
        "final_best_ask": asks.peekitem(0)[0] if asks else None,
    }


def replay_trades_vectorized() -> dict[str, Any]:
    pf = pq.ParquetFile(TRADES)
    start_pa = pa.scalar(WINDOW_START, type=pa.timestamp("ns", tz="UTC"))
    end_pa = pa.scalar(WINDOW_END, type=pa.timestamp("ns", tz="UTC"))
    n = 0
    taker_buy = taker_sell = 0
    vol_buy = vol_sell = 0.0
    notional_total = qty_total = 0.0
    p_min, p_max = float("inf"), 0.0

    for batch_idx, batch in enumerate(pf.iter_batches(
        columns=["time", "price", "qty", "is_buyer_maker"],
        batch_size=200_000,
    )):
        ts_col = batch.column("time")
        if pc.min(ts_col).as_py() is not None and pc.min(ts_col).as_py() > WINDOW_END:
            break
        if pc.max(ts_col).as_py() is not None and pc.max(ts_col).as_py() < WINDOW_START:
            continue
        mask = pc.and_(pc.greater_equal(ts_col, start_pa), pc.less_equal(ts_col, end_pa))
        f = batch.filter(mask)
        if f.num_rows == 0:
            continue
        n += f.num_rows
        price = f.column("price")
        qty = f.column("qty")
        bm = f.column("is_buyer_maker")
        p_min = min(p_min, pc.min(price).as_py())
        p_max = max(p_max, pc.max(price).as_py())
        qty_total += float(pc.sum(qty).as_py())
        notional_total += float(pc.sum(pc.multiply(price, qty)).as_py())
        sell_count = int(pc.sum(bm).as_py())
        taker_sell += sell_count
        taker_buy += f.num_rows - sell_count
        sell_qty = float(pc.sum(pc.multiply(qty, pc.cast(bm, pa.float64()))).as_py())
        vol_sell += sell_qty
        vol_buy += (float(pc.sum(qty).as_py()) - sell_qty)

    return {
        "rows_in_window": n,
        "taker_buy_count": taker_buy,
        "taker_sell_count": taker_sell,
        "taker_sell_share": (taker_sell / n) if n else None,
        "qty_total_btc": qty_total,
        "buy_qty_btc": vol_buy,
        "sell_qty_btc": vol_sell,
        "notional_usd": notional_total,
        "vwap_usd": (notional_total / qty_total) if qty_total else None,
        "price_min": p_min if p_min != float("inf") else None,
        "price_max": p_max,
    }


def main() -> int:
    log("loading diffs table (filtered to window)...")
    pf = pq.ParquetFile(DIFFS)
    start_pa = pa.scalar(WINDOW_START, type=pa.timestamp("ns", tz="UTC"))
    # Allow a 5-min margin before window_start so we can pre-load the snapshot's diff context
    pre_pa = pa.scalar(WINDOW_START.replace(minute=0, second=0, microsecond=0), type=pa.timestamp("ns", tz="UTC"))
    end_pa = pa.scalar(WINDOW_END, type=pa.timestamp("ns", tz="UTC"))
    tables: list[pa.Table] = []
    for batch in pf.iter_batches(batch_size=50_000):
        ts_col = batch.column("time")
        if pc.min(ts_col).as_py() is not None and pc.min(ts_col).as_py() > WINDOW_END:
            break
        if pc.max(ts_col).as_py() is not None and pc.max(ts_col).as_py() < WINDOW_START:
            continue
        mask = pc.and_(pc.greater_equal(ts_col, pre_pa), pc.less_equal(ts_col, end_pa))
        f = batch.filter(mask)
        if f.num_rows:
            tables.append(pa.Table.from_batches([f]))
    diffs_table = pa.concat_tables(tables) if tables else pa.table({})
    log(f"diffs in window: {diffs_table.num_rows}")

    log("loading snapshots in window...")
    snaps = load_snapshots_in_range(WINDOW_START, WINDOW_END)
    log(f"snapshots in window: {len(snaps)}")
    if not snaps:
        # fall back to last snapshot before window_start
        log("no snapshots in window; falling back to nearest pre-window snapshot")
        pf_s = pq.ParquetFile(SNAPS)
        last_pre = None
        for batch in pf_s.iter_batches(batch_size=200_000):
            for r in batch.to_pylist():
                if r["time"] <= WINDOW_START and (last_pre is None or r["time"] > last_pre["time"]):
                    last_pre = r
        if last_pre is None:
            raise RuntimeError("no anchor snapshot at all")
        snaps = [last_pre]

    # Replay segment-by-segment
    segments: list[dict[str, Any]] = []
    for i, snap in enumerate(snaps):
        t_end = snaps[i + 1]["time"] if i + 1 < len(snaps) else WINDOW_END
        if t_end > WINDOW_END:
            t_end = WINDOW_END
        seg = replay_segment(snap, t_end, diffs_table)
        segments.append(seg)
        log(f"  segment {i+1}/{len(snaps)} anchor={snap['time']} -> {t_end} | applied={seg['diff_rows_applied']} crossed_secs={seg['second_crossed']}")

    # Aggregate
    total_diff_rows = sum(s["diff_rows_applied"] for s in segments)
    total_levels_set = sum(s["level_sets"] for s in segments)
    total_levels_deleted = sum(s["level_deletes"] for s in segments)
    total_seq_pairs = sum(s["sequence_pairs_checked"] for s in segments)
    total_seq_gaps = sum(s["sequence_gaps"] for s in segments)
    total_seconds_emitted = sum(s["second_samples_emitted"] for s in segments)
    total_crossed = sum(s["second_crossed"] for s in segments)
    total_empty = sum(s["second_empty"] for s in segments)
    total_normal = sum(s["second_normal_samples"] for s in segments)
    spread_min_global = min((s["spread_min_usd"] for s in segments if s["spread_min_usd"] is not None), default=None)
    spread_max_global = max((s["spread_max_usd"] for s in segments if s["spread_max_usd"] is not None), default=None)
    spread_avg_weighted = (
        sum(s["spread_avg_usd"] * s["second_normal_samples"] for s in segments if s["spread_avg_usd"] is not None) / max(1, total_normal)
    ) if total_normal else None

    log("running trades replay...")
    trades = replay_trades_vectorized()
    log(f"trades window rows: {trades['rows_in_window']}")

    summary = {
        "window_start_utc": WINDOW_START.isoformat(),
        "window_end_utc": WINDOW_END.isoformat(),
        "diff_segments_count": len(segments),
        "totals": {
            "diff_rows_applied": total_diff_rows,
            "level_sets_applied": total_levels_set,
            "level_deletes_applied": total_levels_deleted,
            "sequence_pairs_checked": total_seq_pairs,
            "sequence_gaps": total_seq_gaps,
            "sequence_gap_share": (total_seq_gaps / total_seq_pairs) if total_seq_pairs else None,
            "seconds_emitted": total_seconds_emitted,
            "seconds_normal": total_normal,
            "seconds_crossed": total_crossed,
            "seconds_empty": total_empty,
            "spread_min_usd": spread_min_global,
            "spread_max_usd": spread_max_global,
            "spread_avg_usd_weighted": spread_avg_weighted,
        },
        "first_segment": segments[0] if segments else None,
        "last_segment": segments[-1] if segments else None,
        "trades": trades,
        "errors": [],
        "notes": [
            "Per-minute re-anchoring used. Each snapshot starts a fresh book; diffs are applied until the next snapshot.",
            "Strategy engine NOT invoked: this dataset is Binance SPOT, while our strategy is calibrated for USDS-M Futures. Running the futures-tuned engine on spot data would conflate parser correctness with venue-regime mismatch. See KAGGLE_BTCUSDT_L3_DATA_AUDIT.md Section B.",
        ],
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    log(f"wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
