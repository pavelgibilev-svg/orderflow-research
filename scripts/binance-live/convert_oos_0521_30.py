"""Stage B: normalize+convert Binance OOS days 2026-05-21..30 to Tardis CSV.gz.

Per day: extract inner zip -> NORM/<date>/*.jsonl -> convert_day -> Tardis CSV.gz
-> delete extracted jsonl (disk hygiene). Reuses convert functions from
inventory_audit_normalize_convert.py. Raw archives untouched.
"""
from __future__ import annotations
import json, shutil, sys, time, zipfile, datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventory_audit_normalize_convert as conv

ROOT = Path("C:/Users/gibilev/orderflow-research")
STAGE = ROOT / "data/binance-live-archives/staging/OFFRW_0521_30/OFFRW"
NORM = ROOT / "data/binance-live-normalized/binance-futures/BTCUSDT"
TARDIS_OUT = ROOT / "data/binance-historical/BTCUSDT"
OUT = ROOT / "reports/binance-oos"
OUT.mkdir(parents=True, exist_ok=True)
DATES = [f"2026-05-{d:02d}" for d in range(21, 31)]


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def main():
    norm_report = {"build_time_utc": now_iso(), "days": []}
    for d in DATES:
        t0 = time.time()
        zpath = STAGE / f"{d}.zip"
        if not zpath.exists():
            print(f"[{d}] MISSING zip", file=sys.stderr)
            norm_report["days"].append({"date": d, "status": "MISSING_ZIP"}); continue
        # already converted?
        l2 = TARDIS_OUT / d / "incremental_book_L2.csv.gz"
        tr = TARDIS_OUT / d / "trades.csv.gz"
        if l2.exists() and tr.exists() and l2.stat().st_size > 1e6 and tr.stat().st_size > 1e5:
            print(f"[{d}] already converted, skip", file=sys.stderr)
            norm_report["days"].append({"date": d, "status": "EXISTS"}); continue
        # 1) extract inner zip into NORM (zip has 2026-05-DD/ prefix)
        print(f"[{d}] extracting ...", file=sys.stderr)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(NORM)   # creates NORM/2026-05-DD/*.jsonl
        src = NORM / d
        if not (src / "raw_depth_events.jsonl").exists():
            print(f"[{d}] no raw_depth after extract", file=sys.stderr)
            norm_report["days"].append({"date": d, "status": "NO_STREAMS"}); continue
        # 2) convert
        print(f"[{d}] converting ...", file=sys.stderr)
        rep = conv.convert_day(d)
        # 3) cleanup jsonl to free disk
        try:
            shutil.rmtree(src)
        except Exception as e:
            print(f"[{d}] cleanup warn: {e}", file=sys.stderr)
        dur = round(time.time() - t0, 1)
        streams = {k: {"rows_out": v.get("rows_out") or v.get("n_rows"),
                       "size_mb": round((v.get("out_size_bytes") or 0)/1e6, 1),
                       "first_ts_ms": v.get("first_ts_ms"), "last_ts_ms": v.get("last_ts_ms")}
                   for k, v in rep["streams"].items()}
        norm_report["days"].append({"date": d, "status": "CONVERTED", "duration_s": dur, "streams": streams})
        print(f"[{d}] done in {dur}s: " +
              ", ".join(f"{k}={v['rows_out']}r/{v['size_mb']}MB" for k, v in streams.items()), file=sys.stderr)
        # checkpoint after each day
        (OUT / "BINANCE_2026_05_21_30_NORMALIZATION_REPORT.json").write_text(
            json.dumps(norm_report, indent=2, default=str), encoding="utf-8")

    # final report
    converted = [x for x in norm_report["days"] if x["status"] in ("CONVERTED", "EXISTS")]
    norm_report["flags"] = {
        "BINANCE_NORMALIZATION_DONE": "YES" if converted else "NO",
        "BINANCE_DAYS_NORMALIZED": len(converted),
        "BINANCE_PARTIAL_DAYS": [], "BINANCE_MERGED_DAYS": [],
        "BINANCE_CONVERSION_ERRORS": [x["date"] for x in norm_report["days"] if x["status"] not in ("CONVERTED", "EXISTS")]}
    (OUT / "BINANCE_2026_05_21_30_NORMALIZATION_REPORT.json").write_text(
        json.dumps(norm_report, indent=2, default=str), encoding="utf-8")
    md = ["# Binance OOS normalization+convert (2026-05-21..30)", "", f"**Build:** {now_iso()}",
          f"**Days converted:** {len(converted)}/{len(DATES)}", "",
          "| date | status | book rows | trades rows | deriv rows | liq rows | dur s |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for x in norm_report["days"]:
        s = x.get("streams", {})
        md.append(f"| {x['date']} | {x['status']} | "
                  f"{s.get('incremental_book_L2',{}).get('rows_out','-')} | "
                  f"{s.get('trades',{}).get('rows_out','-')} | "
                  f"{s.get('derivative_ticker',{}).get('rows_out','-')} | "
                  f"{s.get('liquidations',{}).get('rows_out','-')} | {x.get('duration_s','-')} |")
    (OUT / "BINANCE_2026_05_21_30_NORMALIZATION_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print("NORMALIZATION DONE:", norm_report["flags"], file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
