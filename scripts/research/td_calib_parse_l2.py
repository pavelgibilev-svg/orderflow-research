"""TASK1 / B — L2 normalizer for TREND_DOWN calibration v1.

Reconstructs the order book from Bybit ob200 (JSONL snapshot+delta) and OKX 400lv (JSONL snapshot/update),
emits a UNIFIED per-second L2 summary per day:
  exchange, ts_sec, best_bid, best_ask, mid, spread_bps, top_bid_size, top_ask_size,
  bid_depth_top10, ask_depth_top10, depth_imbalance, update_count
Does not modify source files. Trade-flow fields are NOT here (no in-window trades) -> handled as N/A downstream.
"""
from __future__ import annotations
import csv, gzip, io, json, sys, tarfile, zipfile, datetime as dt
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
SRC = ROOT / "data/11.06.2026"
OUTDIR = ROOT / "reports/trend_down_calibration_v1/_normalized"
TOPN = 10


def emit_row(ex, sec, bids, asks, upd):
    if not bids or not asks: return None
    bb = max(bids); ba = min(asks)
    if ba <= bb: return None
    mid = (bb + ba) / 2
    bk = sorted(bids.keys(), reverse=True)[:TOPN]; ak = sorted(asks.keys())[:TOPN]
    bd = sum(bids[k] for k in bk); ad = sum(asks[k] for k in ak)
    di = round((bd - ad) / (bd + ad), 4) if (bd + ad) else None
    return [ex, sec, round(bb, 2), round(ba, 2), round(mid, 2), round((ba - bb) / mid * 1e4, 3),
            round(bids[bb], 4), round(asks[ba], 4), round(bd, 4), round(ad, 4), di, upd]


def iter_lines_zip(path):
    with zipfile.ZipFile(path) as z:
        name = z.namelist()[0]
        with z.open(name) as fh:
            for line in io.TextIOWrapper(fh, encoding="utf-8"):
                yield line


def iter_lines_tar(path):
    with tarfile.open(path, "r:gz") as t:
        m = next(x for x in t.getmembers() if x.isfile())
        fh = t.extractfile(m)
        for line in io.TextIOWrapper(fh, encoding="utf-8"):
            yield line


def parse(path, exchange):
    bids = {}; asks = {}; cur = None; upd = 0; rows = []
    it = iter_lines_zip(path) if path.suffix == ".zip" else iter_lines_tar(path)
    for line in it:
        line = line.strip()
        if not line: continue
        try: ev = json.loads(line)
        except json.JSONDecodeError: continue
        if exchange == "Bybit":
            ts = ev.get("ts"); typ = ev.get("type"); d = ev.get("data") or {}
            b = d.get("b"); a = d.get("a"); reset = (typ == "snapshot")
        else:  # OKX
            try: ts = int(ev.get("ts"))
            except (TypeError, ValueError): continue
            typ = ev.get("action"); b = ev.get("bids"); a = ev.get("asks"); reset = (typ == "snapshot")
        if ts is None: continue
        sec = int(ts) // 1000
        if cur is None: cur = sec
        if sec != cur:
            r = emit_row(exchange, cur, bids, asks, upd)
            if r: rows.append(r)
            cur = sec; upd = 0
        if reset: bids.clear(); asks.clear()
        if b:
            for lv in b:
                px = float(lv[0]); sz = float(lv[1])
                if sz == 0: bids.pop(px, None)
                else: bids[px] = sz
        if a:
            for lv in a:
                px = float(lv[0]); sz = float(lv[1])
                if sz == 0: asks.pop(px, None)
                else: asks[px] = sz
        upd += 1
    r = emit_row(exchange, cur, bids, asks, upd)
    if r: rows.append(r)
    return rows


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    jobs = []
    for p in sorted(SRC.iterdir()):
        n = p.name
        if n.endswith("_BTCUSDT_ob200.data.zip"):
            jobs.append((p, "Bybit", "BTCUSDT", n[:10]))
        elif n.startswith("BTC-USDT-SWAP-L2orderbook-400lv-") and n.endswith(".tar.gz"):
            jobs.append((p, "OKX", "BTC-USDT-SWAP", n.split("-")[-3] + "-" + n.split("-")[-2] + "-" + n.split("-")[-1].replace(".tar.gz", "")))
    print(f"{len(jobs)} L2 files to parse")
    cols = ["exchange", "ts_sec", "best_bid", "best_ask", "mid", "spread_bps", "top_bid_size", "top_ask_size", "bid_depth_top10", "ask_depth_top10", "depth_imbalance", "update_count"]
    for i, (path, ex, sym, date) in enumerate(jobs, 1):
        outp = OUTDIR / f"{ex}_{sym}_{date}_l2_1s.csv.gz"
        if outp.exists():
            print(f"[{i}/{len(jobs)}] skip (exists) {outp.name}"); continue
        t0 = dt.datetime.now()
        rows = parse(path, ex)
        with gzip.open(outp, "wt", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh); w.writerow(cols); w.writerows(rows)
        dtsec = (dt.datetime.now() - t0).total_seconds()
        mids = [r[4] for r in rows]
        print(f"[{i}/{len(jobs)}] {ex} {date}: {len(rows)} sec-rows, mid {min(mids):.0f}-{max(mids):.0f}, {dtsec:.0f}s -> {outp.name}", flush=True)
    print("L2 NORMALIZE DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
