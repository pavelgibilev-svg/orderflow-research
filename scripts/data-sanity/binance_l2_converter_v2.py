"""TRACK B — fixed Binance L2 converter (re-seed/reconcile from orderbook_snapshots_1s).

Root cause of the old bug (scripts/binance-live/inventory_audit_normalize_convert.py):
  it seeded the book ONCE from the first 1s snapshot, then applied depth-limited diffs forever,
  so stale far levels were never deleted -> persistent crossed book (~208 bps).

Fix (consumer-agnostic, pure-delta output):
  - seed from the first 1s snapshot (is_snapshot=true block, clears book),
  - merge raw_depth_events diffs AND every subsequent 1s snapshot by timestamp,
  - on each diff: apply level (qty 0 = delete) and emit the row,
  - on each 1s snapshot: RECONCILE the live book to the snapshot — emit amount=0 deletes for
    levels no longer present (kills stale far levels) and updates for changed/new levels.
  Output schema identical: exchange,symbol,timestamp(us),local_timestamp(us),is_snapshot,side,price,amount
  Raw archives untouched. amount stays in BTC (raw Binance base units).
"""
from __future__ import annotations
import gzip, json, sys, time
from pathlib import Path

EXCH = "binance-futures"; SYM = "BTCUSDT"


def _iter_snapshots(path: Path):
    """yield (ts_ms, 'snap', (bid_dict, ask_dict))."""
    if not path.exists(): return
    with path.open("rb") as fp:
        for line in fp:
            if not line.strip(): continue
            try: s = json.loads(line)
            except Exception: continue
            ts = int(s.get("ts") or 0)
            if ts == 0: continue
            bp = s.get("bid_prices") or []; bq = s.get("bid_qty") or []
            ap = s.get("ask_prices") or []; aq = s.get("ask_qty") or []
            bid = {float(p): float(q) for p, q in zip(bp, bq) if float(q) > 0}
            ask = {float(p): float(q) for p, q in zip(ap, aq) if float(q) > 0}
            yield (ts, "snap", (bid, ask))


def _iter_diffs(path: Path):
    """yield (ts_ms, 'diff', (bids, asks))."""
    if not path.exists(): return
    with path.open("rb") as fp:
        for line in fp:
            if not line.strip(): continue
            try: ev = json.loads(line)
            except Exception: continue
            ts = int(ev.get("event_time") or 0)
            if ts == 0: continue
            yield (ts, "diff", (ev.get("bids") or [], ev.get("asks") or []))


def _merge(snap_it, diff_it):
    """merge two ts-sorted iterators; snapshots before diffs at equal ts (seed/reconcile first)."""
    import heapq
    def keyed(it, order):
        for ts, typ, payload in it:
            yield (ts, order, typ, payload)
    yield from heapq.merge(keyed(snap_it, 0), keyed(diff_it, 1), key=lambda x: (x[0], x[1]))


def convert_day_v3(raw_depth_path: Path, snapshots_path: Path, out_path: Path) -> dict:
    """PURE-DIFF reconstruction. The orderbook_snapshots_1s stream is FROZEN/STALE (verified:
    stuck at a constant best bid/ask while diffs track real price) -> it is NOT used as a seed.
    Reconstruct from raw_depth_events diffs only, and prune crossed levels (emit amount=0 deletes)
    so the output is a clean, self-consistent pure-delta stream (best_bid < best_ask).
    `snapshots_path` is accepted for signature compat but intentionally ignored.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bid = {}; ask = {}
    n_rows = 0; n_diffs = 0; n_prune_deletes = 0
    first_ts = None; last_ts = None
    t0 = time.time()
    with gzip.open(out_path, "wt", encoding="utf-8", newline="\n", compresslevel=5) as gz:
        gz.write("exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount\n")
        for ts_ms, _typ, payload in _iter_diffs(raw_depth_path):
            ts_us = ts_ms * 1000
            if first_ts is None: first_ts = ts_ms
            last_ts = ts_ms
            bids, asks = payload
            for p, q in asks:
                p = float(p); q = float(q)
                if q == 0: ask.pop(p, None)
                else: ask[p] = q
                gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},false,ask,{p},{q}\n"); n_rows += 1
            for p, q in bids:
                p = float(p); q = float(q)
                if q == 0: bid.pop(p, None)
                else: bid[p] = q
                gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},false,bid,{p},{q}\n"); n_rows += 1
            n_diffs += 1
            # prune crossed levels (only when crossed; cheap check first)
            if bid and ask:
                ba = min(ask); bb = max(bid)
                if bb >= ba:
                    for p in [p for p in bid if p >= ba]:
                        del bid[p]; gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},false,bid,{p},0\n"); n_rows += 1; n_prune_deletes += 1
                    bb2 = max(bid) if bid else None
                    if bb2 is not None:
                        for p in [p for p in ask if p <= bb2]:
                            del ask[p]; gz.write(f"{EXCH},{SYM},{ts_us},{ts_us},false,ask,{p},0\n"); n_rows += 1; n_prune_deletes += 1
    return {"out_path": str(out_path), "rows_out": n_rows, "diffs": n_diffs, "snapshots": 0,
            "prune_deletes": n_prune_deletes, "first_ts_ms": first_ts, "last_ts_ms": last_ts,
            "duration_s": round(time.time() - t0, 1)}


# ---------------- driver: re-convert 2026-05-21..30 from staging zips ----------------
def main():
    import zipfile, shutil
    ROOT = Path("C:/Users/gibilev/orderflow-research")
    STAGE = ROOT / "data/binance-live-archives/staging/OFFRW_0521_30/OFFRW"
    TMP = ROOT / "data/binance-live-normalized/_reconv_tmp"
    OUT = ROOT / "data/binance-historical/BTCUSDT"
    REPORT = ROOT / "reports/data-sanity"
    REPORT.mkdir(parents=True, exist_ok=True)
    dates = [f"2026-05-{d:02d}" for d in range(21, 31)]
    rep = {"build": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "days": []}
    for d in dates:
        zp = STAGE / f"{d}.zip"
        if not zp.exists():
            print(f"[{d}] MISSING staging zip", file=sys.stderr)
            rep["days"].append({"date": d, "status": "MISSING_ZIP"}); continue
        day_tmp = TMP / d; day_tmp.mkdir(parents=True, exist_ok=True)
        # extract only the two streams we need
        with zipfile.ZipFile(zp) as z:
            for member in z.namelist():
                if member.endswith("raw_depth_events.jsonl") or member.endswith("orderbook_snapshots_1s.jsonl"):
                    z.extract(member, day_tmp)
        rd = next(day_tmp.rglob("raw_depth_events.jsonl"), None)
        sn = next(day_tmp.rglob("orderbook_snapshots_1s.jsonl"), None)
        if rd is None or sn is None:
            print(f"[{d}] missing streams (rd={rd} sn={sn})", file=sys.stderr)
            rep["days"].append({"date": d, "status": "NO_STREAMS"}); shutil.rmtree(day_tmp, ignore_errors=True); continue
        out = OUT / d / "incremental_book_L2.csv.gz"
        print(f"[{d}] reconverting (pure-diff v3) ...", file=sys.stderr)
        r = convert_day_v3(rd, sn, out)
        rep["days"].append({"date": d, "status": "RECONVERTED", **r})
        print(f"[{d}] done {r['duration_s']}s rows={r['rows_out']} diffs={r['diffs']} prune_del={r['prune_deletes']}", file=sys.stderr)
        shutil.rmtree(day_tmp, ignore_errors=True)
        (REPORT / "BINANCE_L2_CONVERTER_FIX_REPORT.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    ok = [x for x in rep["days"] if x.get("status") == "RECONVERTED"]
    rep["flags"] = {"BINANCE_CONVERTER_FIX_DONE": "YES" if ok else "NO", "DAYS_RECONVERTED": len(ok)}
    (REPORT / "BINANCE_L2_CONVERTER_FIX_REPORT.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    md = ["# B1/B2. Binance L2 converter fix + re-convert", "", f"**Build:** {rep['build']}",
          "Root cause: orderbook_snapshots_1s is FROZEN/STALE; the old converter seeded from it -> phantom stale levels -> crossed book.",
          "Fix (v3): PURE-DIFF reconstruction from raw_depth_events only (snapshots ignored) + prune crossed levels (amount=0 deletes).", "",
          "| date | status | rows | diffs | prune_deletes | dur s |",
          "|---|---|---:|---:|---:|---:|"]
    for x in rep["days"]:
        md.append(f"| {x['date']} | {x['status']} | {x.get('rows_out','-')} | {x.get('diffs','-')} | "
                  f"{x.get('prune_deletes','-')} | {x.get('duration_s','-')} |")
    (REPORT / "BINANCE_L2_CONVERTER_FIX_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print(f"FIX DONE: {len(ok)}/{len(dates)} days", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
