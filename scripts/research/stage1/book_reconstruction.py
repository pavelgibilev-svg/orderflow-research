#!/usr/bin/env python3
"""
book_reconstruction.py  --  Stage 1: Bybit orderbook.200 snapshot+delta replay.

Reconstructs the full L2 book from a Bybit V5 `orderbook.200.<SYMBOL>` NDJSON
recorder dump and emits ONE reconstructed book slice per fixed interval
(default 1 s). The emitted slices are the exact input contract consumed by
features_geometry.book_geometry_* (same [price, size] rows).

Pure stdlib + NumPy for the engine (pandas only to write the CSV at the end).
No new runtime dependency beyond what is already in requirements.txt.

DATA FORMAT  (verified on disk; this recorder is NOT Tardis)
-----------------------------------------------------------
Each NDJSON line is one Bybit WS message:

    {"topic":"orderbook.200.BTCUSDT", "type":"snapshot"|"delta",
     "ts": <int ms>, "cts": <int ms>,
     "data": {"s":"BTCUSDT",
              "b": [["price","size"], ...],   # bids
              "a": [["price","size"], ...],   # asks
              "u": <updateId>, "seq": <int>}}

- type "snapshot": REPLACE the whole book with data.b / data.a.
- type "delta"   : per [price, size] -> size == 0  DELETE that level,
                                        else        SET   that level.
- ts is MILLISECONDS. Size is in BTC for Bybit BTCUSDT (perp AND spot)
  -> size_multiplier = 1.0.
- perp file: "<date>_BTCUSDT_ob200.data.zip"
  spot file: "<date>_BTCUSDT_ob200.data (1).zip"   ("(1)" == spot)
- tick size: BTCUSDT perp = 0.1, spot = 0.01.

RECONSTRUCTION STATE MACHINE  (THIS is what a TS port must mirror byte-for-byte)
-------------------------------------------------------------------------------
    state: bids: Map<priceKey, size>, asks: Map<priceKey, size>
    for each message in arrival (ts) order:
        if type == "snapshot":  bids.clear(); asks.clear()
        for [p, s] in data.b:   s == 0 ? bids.delete(p) : bids.set(p, s)
        for [p, s] in data.a:   s == 0 ? asks.delete(p) : asks.set(p, s)
        bucket = floor(ts / interval_ms)
        on bucket advance -> EMIT the book held at the END of the previous
                             bucket (end-of-interval sampling).
    best_bid = max(bids.keys); best_ask = min(asks.keys); mid = (bb+ba)/2.

priceKey here is float(price): one source string maps deterministically to one
float, and Bybit formats prices consistently per instrument, so float keys are
exact for set/delete. A TS port may key by the raw price string for the same
result (JS numbers are IEEE-754 doubles too, so float keys also match).

ZERO-LOOKAHEAD: an emitted slice uses only messages with ts <= bucket_end.
Deltas seen before the first snapshot are skipped (book not yet initialised).

OUTPUT  (reports/stage1/, gitignored)
-------------------------------------
Per emitted second: best_bid/ask, mid, spread_ticks, the geometry moments from
features_geometry (mass / com / variance / imbalance per side) and the
per-second deformation vs the previous second. CSV + a .summary.json that also
records the batch-vs-reference parity max-diff measured on real data.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import numpy as np

# Repo root (auto-detected, per DATA_HANDOVER: no hard-coded paths). Used only
# for the OUTPUT location; the external dataset is passed via --input.
ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "package.json").exists() and (p / "scripts").exists())
sys.path.insert(0, str(Path(__file__).resolve().parent))
import features_geometry as geo  # noqa: E402

SYMBOL = "BTCUSDT"
DEFAULT_TICK = {"perp": 0.1, "spot": 0.01}


# --------------------------------------------------------------------------- #
# File resolution                                                             #
# --------------------------------------------------------------------------- #

def resolve_zip(input_dir: Path, date: str, market: str) -> Path:
    """perp -> '<date>_BTCUSDT_ob200.data.zip'; spot -> '..ob200.data (1).zip'."""
    if market == "perp":
        name = f"{date}_{SYMBOL}_ob200.data.zip"
    elif market == "spot":
        name = f"{date}_{SYMBOL}_ob200.data (1).zip"
    else:
        raise ValueError(f"market must be 'perp' or 'spot', got {market!r}")
    p = input_dir / name
    if not p.exists():
        raise FileNotFoundError(f"ob200 file not found: {p}")
    return p


# --------------------------------------------------------------------------- #
# Order-book state machine                                                    #
# --------------------------------------------------------------------------- #

class OrderBook:
    """Bybit orderbook.200 state. Keys are float prices (exact per instrument)."""

    __slots__ = ("bids", "asks")

    def __init__(self) -> None:
        self.bids: dict[float, float] = {}
        self.asks: dict[float, float] = {}

    def apply(self, msg: dict) -> None:
        if msg["type"] == "snapshot":
            self.bids.clear()
            self.asks.clear()
        d = msg["data"]
        b = self.bids
        a = self.asks
        for p, s in d.get("b", ()):
            sf = float(s)
            if sf == 0.0:
                b.pop(float(p), None)
            else:
                b[float(p)] = sf
        for p, s in d.get("a", ()):
            sf = float(s)
            if sf == 0.0:
                a.pop(float(p), None)
            else:
                a[float(p)] = sf

    def best_bid(self) -> float:
        return max(self.bids) if self.bids else float("nan")

    def best_ask(self) -> float:
        return min(self.asks) if self.asks else float("nan")


# --------------------------------------------------------------------------- #
# Streaming replay -> 1-second snapshots                                      #
# --------------------------------------------------------------------------- #

def iter_messages(zip_path: Path):
    """Stream-decode NDJSON lines from the single-entry zip. Bounded memory."""
    with zipfile.ZipFile(zip_path) as zf:
        inner = zf.namelist()[0]
        with zf.open(inner) as raw:
            for line in io.TextIOWrapper(raw, encoding="utf-8"):
                line = line.strip()
                if line:
                    yield json.loads(line)


def _emit(ob: OrderBook, bucket_ts: int, n_msgs: int):
    """Materialise the current book as (ts, bb, ba, bid_p, bid_s, ask_p, ask_s, n).

    Empty sides are padded with a single (0.0, 0.0) sentinel: price 0 is always
    out-of-window (|0-mid|/mid > any depth pct for mid>0) and size 0 adds no
    weight, so geometry sees mass 0 / NaN moments (== the reference's empty case)
    while every reduceat segment keeps >= 1 row (well-formed segments).
    """
    bb = ob.best_bid()
    ba = ob.best_ask()
    if ob.bids:
        bid_p = np.fromiter(ob.bids.keys(), np.float64, len(ob.bids))
        bid_s = np.fromiter(ob.bids.values(), np.float64, len(ob.bids))
    else:
        bid_p, bid_s = np.zeros(1), np.zeros(1)
    if ob.asks:
        ask_p = np.fromiter(ob.asks.keys(), np.float64, len(ob.asks))
        ask_s = np.fromiter(ob.asks.values(), np.float64, len(ob.asks))
    else:
        ask_p, ask_s = np.zeros(1), np.zeros(1)
    return bucket_ts, bb, ba, bid_p, bid_s, ask_p, ask_s, n_msgs


def replay(zip_path: Path, interval_ms: int = 1000, max_seconds: int | None = None):
    """Yield one end-of-bucket snapshot per `interval_ms` (see module docstring)."""
    ob = OrderBook()
    have_snapshot = False
    cur_bucket: int | None = None
    start_bucket: int | None = None
    msgs_in_bucket = 0
    for msg in iter_messages(zip_path):
        if not have_snapshot:
            if msg["type"] != "snapshot":
                continue  # cannot trust deltas before the first full snapshot
            have_snapshot = True
        bucket = msg["ts"] // interval_ms
        if cur_bucket is None:
            cur_bucket = start_bucket = bucket
        elif bucket > cur_bucket:
            yield _emit(ob, cur_bucket * interval_ms, msgs_in_bucket)
            msgs_in_bucket = 0
            cur_bucket = bucket
            if max_seconds is not None and (bucket - start_bucket) >= max_seconds:
                return
        ob.apply(msg)
        msgs_in_bucket += 1
    if cur_bucket is not None and msgs_in_bucket:
        yield _emit(ob, cur_bucket * interval_ms, msgs_in_bucket)


# --------------------------------------------------------------------------- #
# Geometry over the replay (vectorized, chunked)                              #
# --------------------------------------------------------------------------- #

def _seg_starts(arrays: list[np.ndarray]) -> np.ndarray:
    """Exclusive-prefix offsets for a ragged list -> seg_starts for reduceat."""
    lengths = np.fromiter((a.size for a in arrays), np.int64, len(arrays))
    starts = np.zeros(len(arrays), np.int64)
    if len(arrays) > 1:
        np.cumsum(lengths[:-1], out=starts[1:])
    return starts


def _absdiff(a: float, b: float) -> float:
    """NaN-aware abs diff: NaN vs NaN -> 0 (both empty), else |a-b|."""
    if np.isnan(a) and np.isnan(b):
        return 0.0
    return abs(float(a) - float(b))


def run(
    zip_path: Path,
    *,
    tick_size: float,
    interval_ms: int = 1000,
    max_seconds: int | None = None,
    chunk: int = 3600,
    max_depth_pct: float = geo.DEFAULT_MAX_DEPTH_PCT,
    exp_lambda: float = geo.DEFAULT_EXP_LAMBDA,
    size_multiplier: float = 1.0,
    crosscheck_n: int = 25,
) -> dict:
    """Reconstruct + compute per-second geometry. Returns dict of column arrays."""
    cols: dict[str, list] = {k: [] for k in (
        "ts", "best_bid", "best_ask", "mid", "spread_ticks", "n_msgs",
        "mass_bid", "com_bid", "var_bid", "n_bid",
        "mass_ask", "com_ask", "var_ask", "n_ask",
        "imbalance_inv", "imbalance_exp", "crossed", "empty_bid", "empty_ask",
    )}
    state = {"maxdiff": 0.0, "checked": 0}

    buf: dict[str, list] = {k: [] for k in
                            ("ts", "bb", "ba", "nm", "bp", "bs", "ap", "as_", "mid")}

    def geom_side(bp, bs, seg, mids):
        return geo.book_geometry_batch(
            np.concatenate(bp), np.concatenate(bs), seg, mids,
            tick_size=tick_size, max_depth_pct=max_depth_pct,
            exp_lambda=exp_lambda, size_multiplier=size_multiplier)

    def flush():
        if not buf["ts"]:
            return
        mids = np.asarray(buf["mid"], np.float64)
        bseg = _seg_starts(buf["bp"])
        aseg = _seg_starts(buf["ap"])
        b = geom_side(buf["bp"], buf["bs"], bseg, mids)
        a = geom_side(buf["ap"], buf["as_"], aseg, mids)

        denom_inv = b["w_inv"] + a["w_inv"]
        denom_exp = b["w_exp"] + a["w_exp"]
        with np.errstate(invalid="ignore", divide="ignore"):
            imb_inv = np.where(denom_inv > geo.EPS,
                               (b["w_inv"] - a["w_inv"]) / denom_inv, np.nan)
            imb_exp = np.where(denom_exp > geo.EPS,
                               (b["w_exp"] - a["w_exp"]) / denom_exp, np.nan)

        bb = np.asarray(buf["bb"], np.float64)
        ba = np.asarray(buf["ba"], np.float64)
        cols["ts"].extend(buf["ts"])
        cols["best_bid"].extend(bb.tolist())
        cols["best_ask"].extend(ba.tolist())
        cols["mid"].extend(mids.tolist())
        cols["spread_ticks"].extend(((ba - bb) / tick_size).tolist())
        cols["n_msgs"].extend(buf["nm"])
        cols["mass_bid"].extend(b["mass"].tolist())
        cols["com_bid"].extend(b["com_ticks"].tolist())
        cols["var_bid"].extend(b["variance"].tolist())
        cols["n_bid"].extend(b["n_levels"].tolist())
        cols["mass_ask"].extend(a["mass"].tolist())
        cols["com_ask"].extend(a["com_ticks"].tolist())
        cols["var_ask"].extend(a["variance"].tolist())
        cols["n_ask"].extend(a["n_levels"].tolist())
        cols["imbalance_inv"].extend(imb_inv.tolist())
        cols["imbalance_exp"].extend(imb_exp.tolist())
        cols["crossed"].extend((bb >= ba).tolist())
        cols["empty_bid"].extend((b["mass"] <= geo.EPS).tolist())
        cols["empty_ask"].extend((a["mass"] <= geo.EPS).tolist())

        # Real-data parity: batch (reduceat) must equal the single-snapshot
        # reference. Extends the synthetic <1e-11 invariant to live books.
        i = 0
        while state["checked"] < crosscheck_n and i < len(buf["ts"]):
            ref = geo.book_geometry_snapshot(
                np.column_stack([buf["bp"][i], buf["bs"][i]]),
                np.column_stack([buf["ap"][i], buf["as_"][i]]),
                tick_size=tick_size, ts=buf["ts"][i],
                max_depth_pct=max_depth_pct, exp_lambda=exp_lambda,
                size_multiplier=size_multiplier)
            for rv, bv in ((ref.bid.mass, b["mass"][i]),
                           (ref.bid.com_ticks, b["com_ticks"][i]),
                           (ref.bid.variance, b["variance"][i]),
                           (ref.ask.mass, a["mass"][i]),
                           (ref.ask.com_ticks, a["com_ticks"][i]),
                           (ref.ask.variance, a["variance"][i]),
                           (ref.imbalance_inv, imb_inv[i]),
                           (ref.imbalance_exp, imb_exp[i])):
                state["maxdiff"] = max(state["maxdiff"], _absdiff(rv, bv))
            state["checked"] += 1
            i += 1

        for v in buf.values():
            v.clear()

    t0 = time.perf_counter()
    total_msgs = 0
    for ts, bb, ba, bid_p, bid_s, ask_p, ask_s, n in replay(
            zip_path, interval_ms=interval_ms, max_seconds=max_seconds):
        buf["ts"].append(ts)
        buf["bb"].append(bb)
        buf["ba"].append(ba)
        buf["nm"].append(n)
        buf["bp"].append(bid_p)
        buf["bs"].append(bid_s)
        buf["ap"].append(ask_p)
        buf["as_"].append(ask_s)
        buf["mid"].append((bb + ba) / 2.0)
        total_msgs += n
        if len(buf["ts"]) >= chunk:
            flush()
    flush()

    out = {k: np.asarray(v) for k, v in cols.items()}
    out.update(_deformation(out["ts"], out))
    out["_meta"] = {
        "rows": int(out["ts"].size),
        "total_messages": int(total_msgs),
        "wall_seconds": round(time.perf_counter() - t0, 2),
        "batch_vs_reference_maxdiff": float(state["maxdiff"]),
        "crosschecked_snapshots": int(state["checked"]),
    }
    return out


def _deformation(ts: np.ndarray, cols: dict) -> dict:
    """Per-second rates (#4). dt from real ts gaps; row 0 is NaN."""
    ts_s = ts.astype(np.float64) / 1000.0
    dt = np.diff(ts_s)

    def rate(name: str) -> np.ndarray:
        x = cols[name].astype(np.float64)
        r = np.full(x.size, np.nan)
        if x.size > 1:
            with np.errstate(invalid="ignore", divide="ignore"):
                r[1:] = np.where(dt > 0, np.diff(x) / dt, np.nan)
        return r

    dcb = rate("com_bid")
    dca = rate("com_ask")
    speed = np.full(ts.size, np.nan)
    if ts.size > 1:
        speed[1:] = np.hypot(dcb[1:], dca[1:])
    return {
        "dmass_bid_dt": rate("mass_bid"), "dmass_ask_dt": rate("mass_ask"),
        "dcom_bid_dt": dcb, "dcom_ask_dt": dca,
        "dvar_bid_dt": rate("var_bid"), "dvar_ask_dt": rate("var_ask"),
        "deformation_speed": speed,
    }


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

CSV_COLUMNS = [
    "ts", "best_bid", "best_ask", "mid", "spread_ticks", "n_msgs",
    "mass_bid", "com_bid", "var_bid", "n_bid",
    "mass_ask", "com_ask", "var_ask", "n_ask",
    "imbalance_inv", "imbalance_exp",
    "dmass_bid_dt", "dmass_ask_dt", "dcom_bid_dt", "dcom_ask_dt",
    "dvar_bid_dt", "dvar_ask_dt", "deformation_speed",
    "crossed", "empty_bid", "empty_ask",
]


def _summary(out: dict, *, date: str, market: str, tick_size: float,
             interval_ms: int) -> dict:
    ts = out["ts"]
    mid = out["mid"]
    finite_mid = mid[np.isfinite(mid)]
    gaps = int(np.count_nonzero(np.diff(ts) > interval_ms)) if ts.size > 1 else 0
    return {
        "symbol": SYMBOL, "market": market, "date": date,
        "tick_size": tick_size, "interval_ms": interval_ms,
        "rows": out["_meta"]["rows"],
        "total_messages": out["_meta"]["total_messages"],
        "wall_seconds": out["_meta"]["wall_seconds"],
        "batch_vs_reference_maxdiff": out["_meta"]["batch_vs_reference_maxdiff"],
        "crosschecked_snapshots": out["_meta"]["crosschecked_snapshots"],
        "ts_first": int(ts[0]) if ts.size else None,
        "ts_last": int(ts[-1]) if ts.size else None,
        "mid_min": float(finite_mid.min()) if finite_mid.size else None,
        "mid_median": float(np.median(finite_mid)) if finite_mid.size else None,
        "mid_max": float(finite_mid.max()) if finite_mid.size else None,
        "n_bid_median": float(np.median(out["n_bid"])) if ts.size else None,
        "n_ask_median": float(np.median(out["n_ask"])) if ts.size else None,
        "pct_crossed": round(100 * float(np.mean(out["crossed"])), 4) if ts.size else None,
        "pct_empty_bid": round(100 * float(np.mean(out["empty_bid"])), 4) if ts.size else None,
        "pct_empty_ask": round(100 * float(np.mean(out["empty_ask"])), 4) if ts.size else None,
        "missing_second_gaps": gaps,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Bybit ob200 reconstruction -> 1s book geometry (Stage 1).")
    ap.add_argument("--input", required=True,
                    help="dir holding <date>_BTCUSDT_ob200.data*.zip")
    ap.add_argument("--date", required=True, help="e.g. 2026-06-02")
    ap.add_argument("--market", choices=["perp", "spot"], default="perp")
    ap.add_argument("--tick-size", type=float, default=None,
                    help="default 0.1 (perp) / 0.01 (spot)")
    ap.add_argument("--interval-ms", type=int, default=1000)
    ap.add_argument("--max-seconds", type=int, default=None,
                    help="stop after N seconds of book time (smoke runs)")
    ap.add_argument("--chunk", type=int, default=3600,
                    help="snapshots per vectorized batch flush")
    ap.add_argument("--out", default=None, help="output dir (default reports/stage1)")
    args = ap.parse_args(argv)

    tick = args.tick_size if args.tick_size is not None else DEFAULT_TICK[args.market]
    zip_path = resolve_zip(Path(args.input), args.date, args.market)
    out_dir = Path(args.out) if args.out else (ROOT / "reports" / "stage1")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[ob200] {args.market} {SYMBOL} {args.date} tick={tick} "
          f"src={zip_path.name}", file=sys.stderr)
    out = run(zip_path, tick_size=tick, interval_ms=args.interval_ms,
              max_seconds=args.max_seconds, chunk=args.chunk)

    summary = _summary(out, date=args.date, market=args.market,
                       tick_size=tick, interval_ms=args.interval_ms)

    import pandas as pd  # local import: engine stays numpy-only
    df = pd.DataFrame({c: out[c] for c in CSV_COLUMNS})
    stem = f"geometry_{args.market}_{SYMBOL}_{args.date}"
    csv_path = out_dir / f"{stem}.csv"
    sum_path = out_dir / f"{stem}.summary.json"
    df.to_csv(csv_path, index=False)
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[ob200] rows={summary['rows']} msgs={summary['total_messages']:,} "
          f"wall={summary['wall_seconds']}s "
          f"parity_maxdiff={summary['batch_vs_reference_maxdiff']:.2e}", file=sys.stderr)
    print(f"[ob200] mid {summary['mid_min']}..{summary['mid_max']} "
          f"(med {summary['mid_median']}) crossed={summary['pct_crossed']}% "
          f"gaps={summary['missing_second_gaps']}", file=sys.stderr)
    print(f"[ob200] -> {csv_path}", file=sys.stderr)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
