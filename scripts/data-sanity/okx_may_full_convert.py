"""TRACK A — convert OKX open May full days to engine-ready Tardis-compat L2 + trades.

Source: data/okx may 2026/BTC-USDT-SWAP-L2orderbook-400lv-YYYY-MM-DD.tar.gz  (NDJSON books, OKX public)
        data/okx may 2026/BTC-USDT-SWAP-trades-YYYY-MM-DD.zip
Output: data/okx-historical/BTC-USDT-SWAP/YYYY-MM-DD/incremental_book_L2.csv.gz + trades.csv.gz
amount kept in CONTRACTS (raw OKX), consistent with OKX March data. No Tardis.
"""
from __future__ import annotations
import csv, gzip, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import okx_open_converter as okc

ROOT = Path("C:/Users/gibilev/orderflow-research")
RAW = ROOT / "data/okx may 2026"
OUT = ROOT / "data/okx-historical/BTC-USDT-SWAP"
REPORT = ROOT / "reports/okx-may"; REPORT.mkdir(parents=True, exist_ok=True)
DATES = [f"2026-05-{d:02d}" for d in range(21, 31)]


def convert_l2(tar_path, out_path):
    rows = 0; first = None; last = None; snaps = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8", newline="\n", compresslevel=5) as out:
        out.write("exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount\n")
        for obj in okc.iter_book_objs(tar_path):
            ts = int(obj.get("ts", 0))
            if ts == 0: continue
            ts_us = ts * 1000
            snap = obj.get("action") == "snapshot"
            if snap: snaps += 1
            for side, key in (("ask", "asks"), ("bid", "bids")):
                for lvl in obj.get(key, []):
                    try: price = float(lvl[0]); amt = float(lvl[1])
                    except Exception: continue
                    out.write(f"{okc.EXCH},BTC-USDT-SWAP,{ts_us},{ts_us},{'true' if snap else 'false'},{side},{price},{amt}\n")
                    rows += 1
                    if first is None: first = ts
                    last = ts
    return {"rows": rows, "snapshots": snaps, "first_ts_ms": first, "last_ts_ms": last}


def convert_trades(zip_path, out_path):
    rows = 0; first = None; last = None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8", newline="\n", compresslevel=5) as out:
        out.write("exchange,symbol,timestamp,local_timestamp,id,side,price,amount\n")
        for (ex, sym, ts_us, lt, tid, side, price, size) in okc.iter_trades(zip_path):
            out.write(f"{ex},BTC-USDT-SWAP,{ts_us},{lt},{tid},{side},{price},{size}\n"); rows += 1
            ms = ts_us // 1000
            if first is None: first = ms
            last = ms
    return {"rows": rows, "first_ts_ms": first, "last_ts_ms": last}


def main():
    rep = {"build": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "days": []}
    for d in DATES:
        tar = RAW / f"BTC-USDT-SWAP-L2orderbook-400lv-{d}.tar.gz"
        trz = RAW / f"BTC-USDT-SWAP-trades-{d}.zip"
        rec = {"date": d}
        l2_out = OUT / d / "incremental_book_L2.csv.gz"
        tr_out = OUT / d / "trades.csv.gz"
        # L2
        if not tar.exists():
            rec["l2_status"] = "MISSING"
        elif l2_out.exists() and l2_out.stat().st_size > 5e6:
            rec["l2_status"] = "EXISTS"
        else:
            t0 = time.time(); r = convert_l2(tar, l2_out)
            rec.update({"l2_status": "CONVERTED", "l2_rows": r["rows"], "l2_snapshots": r["snapshots"],
                        "l2_first_ms": r["first_ts_ms"], "l2_last_ms": r["last_ts_ms"], "l2_dur_s": round(time.time()-t0,1)})
            print(f"[{d}] L2 {rec['l2_dur_s']}s rows={r['rows']} snaps={r['snapshots']}", file=sys.stderr)
        # trades
        if not trz.exists():
            rec["tr_status"] = "MISSING"
        elif tr_out.exists() and tr_out.stat().st_size > 5e5:
            rec["tr_status"] = "EXISTS"
        else:
            t0 = time.time(); r = convert_trades(trz, tr_out)
            rec.update({"tr_status": "CONVERTED", "tr_rows": r["rows"], "tr_first_ms": r["first_ts_ms"],
                        "tr_last_ms": r["last_ts_ms"], "tr_dur_s": round(time.time()-t0,1)})
            print(f"[{d}] trades {rec['tr_dur_s']}s rows={r['rows']}", file=sys.stderr)
        rep["days"].append(rec)
        (REPORT / "OKX_MAY_CONVERSION_REPORT.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    nL2 = sum(1 for x in rep["days"] if x.get("l2_status") in ("CONVERTED","EXISTS"))
    nTr = sum(1 for x in rep["days"] if x.get("tr_status") in ("CONVERTED","EXISTS"))
    rep["flags"] = {"OKX_MAY_L2_CONVERTED_DAYS": nL2, "OKX_MAY_TRADES_CONVERTED_DAYS": nTr, "TARDIS_USED": "NO"}
    (REPORT / "OKX_MAY_CONVERSION_REPORT.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(f"OKX MAY CONVERT DONE: L2 {nL2}/10, trades {nTr}/10", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
