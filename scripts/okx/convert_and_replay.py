"""
Converter + parser-correctness replay for OKX-swap CSV.

Implements the OKX `books-l2-tbt` resync protocol correctly:
  - Discard any deltas that appear BEFORE the first snapshot chunk
    (Tardis records them in arrival order; per OKX protocol they must
    not be applied to the post-snapshot book).
  - On every snapshot chunk (consecutive `is_snapshot=true` rows sharing
    one timestamp): reset the book and rebuild from those rows.
  - Apply subsequent `is_snapshot=false` rows as deltas.

Writes the file-recording JSONL layout to
  data/file-recordings-from-okx/okx-swap/BTC-USDT-SWAP/2026-04-01/
and emits a 3-hour parser-correctness summary to metadata.json.

Strategy engine is NOT invoked — venue mismatch (OKX != Binance).
"""

from __future__ import annotations
import csv
import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from sortedcontainers import SortedDict

SRC = Path("data/okx-historical/BTC-USDT-SWAP/2026-04-01")
DEST = Path("data/file-recordings-from-okx/okx-swap/BTC-USDT-SWAP/2026-04-01")
DEST.mkdir(parents=True, exist_ok=True)

# 3-hour parser-correctness window
WINDOW_START_US = int(datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000)
WINDOW_END_US = int(datetime(2026, 4, 1, 3, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def stream_csv(path: Path) -> Iterator[dict[str, str]]:
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            yield row


def main() -> int:
    raw_path = DEST / "raw_depth_events.jsonl"
    snap_path = DEST / "orderbook_snapshots_1s.jsonl"
    trades_path = DEST / "trades.jsonl"
    health_path = DEST / "health.jsonl"
    meta_path = DEST / "metadata.json"

    bids: SortedDict = SortedDict()
    asks: SortedDict = SortedDict()

    n_l2 = 0
    n_l2_in_window_emitted = 0
    n_pre_snapshot_deltas_dropped = 0
    n_snapshot_rows_seen = 0
    n_delta_rows_applied = 0
    n_deletes = 0
    n_sets = 0
    snapshot_chunks: list[dict[str, int]] = []  # one entry per re-anchor

    last_emitted_second = -1
    n_snapshots_emitted = 0
    n_crossed_seconds = 0
    n_empty_seconds = 0
    n_normal_seconds = 0
    spread_min = float("inf")
    spread_max = 0.0
    spread_total = 0.0
    book_size_max = 0

    # State machine
    state = "pre_snapshot"  # pre_snapshot | in_snapshot | deltas
    current_snap_ts: int | None = None
    current_snap_rows = 0

    log(f"streaming L2 from {SRC/'incremental_book_L2.csv.gz'}")
    fraw = raw_path.open("w", encoding="utf-8")
    fsnap = snap_path.open("w", encoding="utf-8")
    try:
        for row in stream_csv(SRC / "incremental_book_L2.csv.gz"):
            n_l2 += 1
            ts = int(row["timestamp"])
            if ts > WINDOW_END_US:
                break
            in_window = WINDOW_START_US <= ts <= WINDOW_END_US
            is_snap = row["is_snapshot"] == "true"
            side = row["side"]
            price = float(row["price"])
            amount = float(row["amount"])

            # State transitions per OKX books-l2-tbt resync protocol
            if is_snap:
                if state != "in_snapshot" or ts != current_snap_ts:
                    # Start of a new snapshot chunk -> reset the book
                    if state == "pre_snapshot":
                        log(f"  first snapshot anchor at ts_us={ts} (dropped {n_pre_snapshot_deltas_dropped} pre-snap deltas)")
                    else:
                        log(f"  re-anchor at ts_us={ts} (chunk #{len(snapshot_chunks) + 1})")
                    bids.clear(); asks.clear()
                    current_snap_ts = ts
                    current_snap_rows = 0
                    snapshot_chunks.append({"ts_us": ts, "rows": 0})
                state = "in_snapshot"
                n_snapshot_rows_seen += 1
                current_snap_rows += 1
                snapshot_chunks[-1]["rows"] += 1
                # Populate the level
                if side == "bid":
                    if amount > 0:
                        bids[-price] = amount
                else:
                    if amount > 0:
                        asks[price] = amount
            else:
                # Delta row
                if state == "pre_snapshot":
                    # OKX protocol: discard deltas that pre-date the first snapshot
                    n_pre_snapshot_deltas_dropped += 1
                    continue
                # Transition out of in_snapshot
                state = "deltas"
                n_delta_rows_applied += 1
                if side == "bid":
                    if amount == 0:
                        bids.pop(-price, None); n_deletes += 1
                    else:
                        bids[-price] = amount; n_sets += 1
                else:
                    if amount == 0:
                        asks.pop(price, None); n_deletes += 1
                    else:
                        asks[price] = amount; n_sets += 1

            book_size_max = max(book_size_max, len(bids) + len(asks))

            if in_window:
                # Emit raw_depth_event in our recording format
                fraw.write(json.dumps({
                    "ts_us": ts,
                    "ingest_ts_us": int(row["local_timestamp"]),
                    "exchange": row["exchange"],
                    "symbol": row["symbol"],
                    "is_snapshot": is_snap,
                    "side": "BID" if side == "bid" else "ASK",
                    "price": price,
                    "amount": amount,
                }, separators=(",", ":")) + "\n")
                n_l2_in_window_emitted += 1

                # Emit 1s snapshots once the book is past its pre_snapshot phase
                if state != "pre_snapshot":
                    sec = ts // 1_000_000
                    if sec != last_emitted_second:
                        last_emitted_second = sec
                        bb = -bids.peekitem(0)[0] if bids else None
                        ba = asks.peekitem(0)[0] if asks else None
                        if bb is None or ba is None:
                            flags = ["EMPTY"]
                            n_empty_seconds += 1
                            snap = {
                                "ts_us": sec * 1_000_000,
                                "best_bid": None, "best_ask": None,
                                "mid": None, "spread": None,
                                "bid_levels": len(bids), "ask_levels": len(asks),
                                "quality_flags": flags,
                            }
                        else:
                            spread = ba - bb
                            flags: list[str] = []
                            if spread < 0:
                                flags.append("CROSSED")
                                n_crossed_seconds += 1
                            else:
                                spread_total += spread
                                spread_min = min(spread_min, spread)
                                spread_max = max(spread_max, spread)
                                n_normal_seconds += 1
                            snap = {
                                "ts_us": sec * 1_000_000,
                                "best_bid": bb, "best_ask": ba,
                                "mid": (bb + ba) / 2,
                                "spread": spread,
                                "bid_levels": len(bids), "ask_levels": len(asks),
                                "quality_flags": flags,
                            }
                        fsnap.write(json.dumps(snap, separators=(",", ":")) + "\n")
                        n_snapshots_emitted += 1
    finally:
        fraw.close(); fsnap.close()

    log(f"L2 done: rows_seen={n_l2:,} emitted_in_window={n_l2_in_window_emitted:,}")
    log(f"  pre_snapshot_deltas_dropped={n_pre_snapshot_deltas_dropped}")
    log(f"  snapshot_chunks={len(snapshot_chunks)}  snapshot_rows={n_snapshot_rows_seen}")
    log(f"  delta_rows_applied={n_delta_rows_applied}  deletes={n_deletes} sets={n_sets}")
    log(f"  seconds_emitted={n_snapshots_emitted}  normal={n_normal_seconds} crossed={n_crossed_seconds} empty={n_empty_seconds}")
    log(f"  book_size_max_levels={book_size_max}")

    # ---- 2) Trades CSV -> trades.jsonl ----
    log("streaming trades")
    n_trades = 0
    n_trades_window = 0
    n_taker_buy = 0
    n_taker_sell = 0
    qty_total = 0.0
    notional_total = 0.0
    with trades_path.open("w", encoding="utf-8") as ftr:
        for row in stream_csv(SRC / "trades.csv.gz"):
            n_trades += 1
            ts = int(row["timestamp"])
            if ts > WINDOW_END_US:
                break
            if WINDOW_START_US <= ts <= WINDOW_END_US:
                n_trades_window += 1
                taker_side = "BUY" if row["side"] == "buy" else "SELL"
                if taker_side == "BUY":
                    n_taker_buy += 1
                else:
                    n_taker_sell += 1
                price = float(row["price"])
                amount = float(row["amount"])
                qty_total += amount
                notional_total += price * amount
                ftr.write(json.dumps({
                    "ts_us": ts,
                    "ingest_ts_us": int(row["local_timestamp"]),
                    "exchange": row["exchange"],
                    "symbol": row["symbol"],
                    "trade_id": int(row["id"]) if row["id"] else None,
                    "side": taker_side,
                    "price": price,
                    "amount": amount,
                }, separators=(",", ":")) + "\n")
    log(f"trades done: in_window={n_trades_window:,}")

    # ---- 3) health.jsonl ----
    with health_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts_us": WINDOW_END_US,
            "status": "OK_IMPORTED_FROM_OKX_HISTORICAL",
            "source": "tardis-okex-swap-csv",
            "sequence_gap_count": 0,
            "reconnect_count": max(0, len(snapshot_chunks) - 1),
            "db_queue_size": 0,
            "spool_queue_size": 0,
            "note": "imported from OKX historical CSV via Tardis CDN; no live recorder run.",
        }, separators=(",", ":")) + "\n")

    # ---- 4) metadata.json ----
    meta = {
        "schema_version": 1,
        "exchange": "okex-swap",
        "venue_display": "OKX",
        "instrument": "BTC-USDT-SWAP",
        "instrument_kind": "perpetual_swap",
        "is_binance_futures": False,
        "is_directly_equivalent_to_binance_usdsm_futures": False,
        "source": {
            "provider": "Tardis",
            "channel": "datasets.tardis.dev/v1/okex-swap",
            "data_types_present": ["incremental_book_L2", "trades", "book_ticker", "derivative_ticker", "liquidations"],
            "original_files_dir": str(SRC),
        },
        "window": {
            "start_utc": datetime.fromtimestamp(WINDOW_START_US / 1_000_000, tz=timezone.utc).isoformat(),
            "end_utc":   datetime.fromtimestamp(WINDOW_END_US   / 1_000_000, tz=timezone.utc).isoformat(),
            "duration_hours": (WINDOW_END_US - WINDOW_START_US) / 3_600_000_000,
        },
        "l2_stream": {
            "rows_seen_until_window_end": n_l2,
            "rows_emitted_in_window": n_l2_in_window_emitted,
            "pre_snapshot_deltas_dropped": n_pre_snapshot_deltas_dropped,
            "snapshot_anchors": len(snapshot_chunks),
            "snapshot_chunks_detail": snapshot_chunks,
            "snapshot_rows_total": n_snapshot_rows_seen,
            "delta_rows_applied": n_delta_rows_applied,
            "level_deletes_applied": n_deletes,
            "level_sets_applied": n_sets,
            "book_size_max_levels_total": book_size_max,
        },
        "snapshots_1s": {
            "rows_emitted": n_snapshots_emitted,
            "normal_seconds": n_normal_seconds,
            "crossed_seconds": n_crossed_seconds,
            "empty_seconds": n_empty_seconds,
            "spread_min_usd": spread_min if spread_min != float("inf") else None,
            "spread_max_usd": spread_max,
            "spread_avg_usd": (spread_total / n_normal_seconds) if n_normal_seconds else None,
        },
        "trades": {
            "rows_seen_until_window_end": n_trades,
            "rows_in_window": n_trades_window,
            "taker_buy_count": n_taker_buy,
            "taker_sell_count": n_taker_sell,
            "taker_buy_share": (n_taker_buy / n_trades_window) if n_trades_window else None,
            "qty_total_contracts": qty_total,
            "notional_total_usd": notional_total,
            "vwap_usd": (notional_total / qty_total) if qty_total else None,
        },
        "strategy_engine_invoked": False,
        "strategy_skip_reason": "OKX != Binance. Strategy is calibrated for Binance USDS-M Futures BTCUSDT; running futures-tuned engine on OKX swap data without recalibration would conflate parser correctness with venue-regime mismatch. Per user instructions (no threshold changes, no curve-fitting, no winrate claim), engine is not invoked.",
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    log(f"wrote metadata to {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
