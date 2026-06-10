"""Convert OKX open early-May full days to engine-ready L2 + trades. No Tardis.

L2 available 05-02..; trades 05-03..  -> convert L2 for 05-02..10, trades for 05-03..10.
amount kept in CONTRACTS (March-compatible). Output: data/okx-historical/BTC-USDT-SWAP/<date>/.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import okx_may_full_convert as F   # reuse convert_l2 / convert_trades

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
RAW = ROOT / "data/okx may 2026"
OUT = ROOT / "data/okx-historical/BTC-USDT-SWAP"
REPORT = ROOT / "reports/okx-may-early"; REPORT.mkdir(parents=True, exist_ok=True)
DATES = [f"2026-05-{d:02d}" for d in range(2, 21)]   # 05-02..05-10


def main():
    rep = {"build": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "days": []}
    for d in DATES:
        tar = RAW / f"BTC-USDT-SWAP-L2orderbook-400lv-{d}.tar.gz"
        trz = RAW / f"BTC-USDT-SWAP-trades-{d}.zip"
        rec = {"date": d}
        l2o = OUT / d / "incremental_book_L2.csv.gz"; tro = OUT / d / "trades.csv.gz"
        if not tar.exists(): rec["l2_status"] = "MISSING"
        elif l2o.exists() and l2o.stat().st_size > 5e6: rec["l2_status"] = "EXISTS"
        else:
            t0 = time.time(); r = F.convert_l2(tar, l2o)
            rec.update({"l2_status": "CONVERTED", "l2_rows": r["rows"], "l2_snapshots": r["snapshots"], "l2_dur_s": round(time.time()-t0,1)})
            print(f"[{d}] L2 {rec['l2_dur_s']}s rows={r['rows']}", file=sys.stderr)
        if not trz.exists(): rec["tr_status"] = "MISSING"
        elif tro.exists() and tro.stat().st_size > 5e5: rec["tr_status"] = "EXISTS"
        else:
            t0 = time.time(); r = F.convert_trades(trz, tro)
            rec.update({"tr_status": "CONVERTED", "tr_rows": r["rows"], "tr_dur_s": round(time.time()-t0,1)})
            print(f"[{d}] trades {rec['tr_dur_s']}s rows={r['rows']}", file=sys.stderr)
        rep["days"].append(rec)
        (REPORT / "OKX_EARLY_CONVERSION_REPORT.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    nB = sum(1 for x in rep["days"] if x.get("l2_status") in ("CONVERTED","EXISTS") and x.get("tr_status") in ("CONVERTED","EXISTS"))
    print(f"OKX EARLY CONVERT DONE: {nB} days with both L2+trades", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
