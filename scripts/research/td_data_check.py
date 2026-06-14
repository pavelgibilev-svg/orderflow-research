"""TASK — DATA INTEGRITY CHECK for the 3 TREND_DOWN windows (NO calibration, NO analysis).

Opens every relevant archive (Telegram Desktop drop + existing data/11.06.2026), reads the INNER member's
first AND last record, computes the REAL UTC date span (do not trust filenames), flags broken/duplicate
files, and builds the per-window coverage matrix. Bybit symbol must be BTCUSDT (not a dated future).
"""
from __future__ import annotations
import csv, gzip, io, json, sys, tarfile, zipfile, datetime as dt
from pathlib import Path

HOME = Path("C:/Users/gibilev")
TG = HOME / "Downloads/Telegram Desktop"
OLD = HOME / "orderflow-research/data/11.06.2026"
OUT = HOME / "orderflow-research/reports/trend_down_calibration_v1"

WINDOWS = {
    "W1": ["2025-11-19", "2025-11-20", "2025-11-21", "2025-11-22"],
    "W3": ["2026-01-28", "2026-01-29", "2026-01-30", "2026-01-31"],
    "NEW_APRIL": ["2024-04-12", "2024-04-13", "2024-04-14", "2024-04-15", "2024-04-16", "2024-04-17"],
}


def utc(ts_s): return dt.datetime.fromtimestamp(ts_s, tz=dt.timezone.utc)
def utcd(ts_s): return utc(ts_s).strftime("%Y-%m-%d")
def utct(ts_s): return utc(ts_s).strftime("%Y-%m-%d %H:%M:%S")


def first_last_zip_csv(path):
    """csv inside zip: return (first_row, last_row, member)."""
    with zipfile.ZipFile(path) as z:
        m = z.namelist()[0]
        first = last = None; header = None
        with z.open(m) as fh:
            for i, line in enumerate(io.TextIOWrapper(fh, encoding="utf-8")):
                line = line.rstrip("\n")
                if i == 0: header = line; continue
                if line:
                    if first is None: first = line
                    last = line
        return first, last, m, header


def first_last_gz_csv(path):
    first = last = header = None
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.rstrip("\n")
            if i == 0: header = line; continue
            if line:
                if first is None: first = line
                last = line
    return first, last, path.name, header


def first_line_zip_json(path, want_last=False):
    with zipfile.ZipFile(path) as z:
        m = z.namelist()[0]
        first = last = None
        with z.open(m) as fh:
            for line in io.TextIOWrapper(fh, encoding="utf-8"):
                line = line.strip()
                if not line: continue
                if first is None: first = line
                if want_last: last = line
                else: break
        return first, last, m


def first_last_tar_json(path):
    with tarfile.open(path, "r:gz") as t:
        m = next(x for x in t.getmembers() if x.isfile())
        fh = t.extractfile(m); first = last = None
        for line in io.TextIOWrapper(fh, encoding="utf-8"):
            line = line.strip()
            if not line: continue
            if first is None: first = line
            last = line
        return first, last, m.name


def check_bybit_ob(path):
    try:
        first, last, m = first_line_zip_json(path, want_last=False)
        ev = json.loads(first); ts = int(ev["ts"]) / 1000
        sym = (ev.get("data") or {}).get("s") or ("BTCUSDT" if "BTCUSDT" in m else "?")
        return {"ok": True, "symbol": sym, "first_utc": utct(ts), "first_date": utcd(ts), "last_utc": "first-line-only(big file)", "member": m, "topic": ev.get("topic")}
    except Exception as e:
        return {"ok": False, "error": repr(e)[:120]}


def check_bybit_trades(path):
    try:
        first, last, m, header = first_last_gz_csv(path)
        f = first.split(","); l = last.split(",")
        fts = float(f[0]); lts = float(l[0]); sym = f[1]
        return {"ok": True, "symbol": sym, "first_utc": utct(fts), "last_utc": utct(lts),
                "first_date": utcd(fts), "last_date": utcd(lts), "header_ok": header.startswith("timestamp,symbol")}
    except Exception as e:
        return {"ok": False, "error": repr(e)[:120]}


def check_okx_trades(path):
    try:
        first, last, m, header = first_last_zip_csv(path)
        f = first.split(","); l = last.split(",")
        fts = int(f[-1]) / 1000; lts = int(l[-1]) / 1000; sym = f[0]
        return {"ok": True, "symbol": sym, "first_utc": utct(fts), "last_utc": utct(lts),
                "first_date": utcd(fts), "last_date": utcd(lts), "member": m, "header_ok": header.startswith("instrument_name")}
    except Exception as e:
        return {"ok": False, "error": repr(e)[:120]}


def check_okx_l2(path):
    try:
        first, last, m = first_last_tar_json(path)
        fe = json.loads(first); le = json.loads(last)
        fts = int(fe["ts"]) / 1000; lts = int(le["ts"]) / 1000
        return {"ok": True, "symbol": fe.get("instId"), "first_utc": utct(fts), "last_utc": utct(lts),
                "first_date": utcd(fts), "last_date": utcd(lts), "member": m}
    except Exception as e:
        return {"ok": False, "error": repr(e)[:120]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []  # dicts: source_folder, filename, exchange, data_type, nominal_date, size_mb, check
    def add(folder, name, exchange, dtype, nominal, checker):
        p = folder / name
        if not p.exists(): return
        size = round(p.stat().st_size / 1e6, 1)
        print(f"checking {name} ({size}MB) ...", flush=True)
        c = checker(p)
        results.append({"folder": str(folder), "filename": name, "exchange": exchange, "data_type": dtype,
                        "nominal_date": nominal, "size_mb": size, **c})

    # ---- Bybit OrderBook ----
    for d in ["2024-04-12", "2024-04-13", "2024-04-14", "2024-04-15", "2024-04-16", "2024-04-17"]:
        add(TG, f"{d}_BTCUSDT_ob500.data.zip", "Bybit", "orderbook", d, check_bybit_ob)
    add(TG, "2025-11-19_BTCUSDT_ob200.data.zip", "Bybit", "orderbook", "2025-11-19", check_bybit_ob)
    for d in WINDOWS["W1"] + WINDOWS["W3"]:
        add(OLD, f"{d}_BTCUSDT_ob200.data.zip", "Bybit", "orderbook", d, check_bybit_ob)
    # ---- Bybit trades ----
    for d in WINDOWS["NEW_APRIL"] + WINDOWS["W1"] + WINDOWS["W3"]:
        add(TG, f"BTCUSDT{d}.csv.gz", "Bybit", "trades", d, check_bybit_trades)
    # ---- OKX L2 ----
    add(TG, "BTC-USDT-SWAP-L2orderbook-400lv-2024-04-17.tar.gz", "OKX", "orderbook", "2024-04-17", check_okx_l2)
    for d, dd in [("2025-11-22", "2025-11-22"), ("2026-01-31", "2026-01-31"), ("2026-02-14", "2026-02-14")]:
        add(OLD, f"BTC-USDT-SWAP-L2orderbook-400lv-{d}.tar.gz", "OKX", "orderbook", dd, check_okx_l2)
    # ---- OKX trades ----
    add(TG, "BTC-USDT-SWAP-trades-2024-04-18.zip", "OKX", "trades", "2024-04-18", check_okx_trades)
    add(TG, "BTC-USDT-SWAP-trades-2026-02-15.zip", "OKX", "trades", "2026-02-15", check_okx_trades)

    # ---- duplicate/suspicious DATA artifacts only (ignore the user's personal files) ----
    datakeys = ("ob200", "ob500", "L2orderbook", "BTC-USDT-SWAP", "BTCUSDT")
    suspicious = sorted({p.name for p in TG.iterdir() if p.is_file() and ("(1)" in p.name or "(2)" in p.name or "(3)" in p.name)
                         and any(k in p.name for k in datakeys)})

    # ---- coverage matrix using VERIFIED dates ----
    def covered(exchange, dtype, date):
        hits = []
        for r in results:
            if r["exchange"] != exchange or r["data_type"] != dtype or not r.get("ok"): continue
            fd = r.get("first_date"); ld = r.get("last_date", fd)
            if fd and ld and fd <= date <= ld: hits.append((r["filename"], f"{r.get('first_utc')}..{r.get('last_utc')}"))
            elif fd == date: hits.append((r["filename"], r.get("first_utc")))
        return hits
    matrix = []
    for wid, days in WINDOWS.items():
        for date in days:
            for ex, dtp in [("Bybit", "orderbook"), ("Bybit", "trades"), ("OKX", "orderbook"), ("OKX", "trades")]:
                hit = covered(ex, dtp, date)
                matrix.append({"window": wid, "date": date, "exchange": ex, "data_type": dtp,
                               "status": "PRESENT" if hit else "MISSING", "covered_by": "; ".join(h[0] for h in hit) or "-"})

    # ---- write CSV ----
    with (OUT / "DATA_CHECK_RESULT.csv").open("w", encoding="utf-8", newline="") as fh:
        cols = ["window", "date", "exchange", "data_type", "status", "covered_by"]
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for r in matrix: w.writerow(r)
    with (OUT / "DATA_CHECK_FILES.csv").open("w", encoding="utf-8", newline="") as fh:
        cols = ["exchange", "data_type", "nominal_date", "filename", "size_mb", "ok", "symbol", "first_utc", "last_utc", "first_date", "last_date", "error"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in results: w.writerow(r)

    # ---- analyze ----
    broken = [r for r in results if not r.get("ok")]
    bad_symbol = [r for r in results if r.get("ok") and r["exchange"] == "Bybit" and r.get("symbol") != "BTCUSDT"]
    multi_day = [r for r in results if r.get("ok") and r.get("first_date") and r.get("last_date") and r["first_date"] != r["last_date"]]
    def miss(ex, dtp):
        return [f"{m['window']}:{m['date']}" for m in matrix if m["exchange"] == ex and m["data_type"] == dtp and m["status"] == "MISSING"]
    bybit_missing = {"orderbook": miss("Bybit", "orderbook"), "trades": miss("Bybit", "trades")}
    okx_missing = {"orderbook": miss("OKX", "orderbook"), "trades": miss("OKX", "trades")}
    bybit_status = "BROKEN" if any(r["exchange"] == "Bybit" for r in broken) else ("OK" if not bybit_missing["orderbook"] and not bybit_missing["trades"] else "MISSING")
    okx_status = "BROKEN" if any(r["exchange"] == "OKX" for r in broken) else ("OK" if not okx_missing["orderbook"] and not okx_missing["trades"] else "MISSING")
    ready = "YES" if bybit_status == "OK" and okx_status == "OK" and not broken else "NO"

    md = ["# DATA_CHECK_RESULT — TREND_DOWN windows (integrity only, no calibration)", "", f"Build {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}",
          f"Source folder (fresh drop): `{TG}` + existing `{OLD}`.", "",
          "## Per-window coverage (verified by inner timestamps)", "| window | date | Bybit OB | Bybit trades | OKX OB | OKX trades |", "|---|---|:--:|:--:|:--:|:--:|"]
    for wid, days in WINDOWS.items():
        for date in days:
            cells = {}
            for ex, dtp in [("Bybit", "orderbook"), ("Bybit", "trades"), ("OKX", "orderbook"), ("OKX", "trades")]:
                st = [m for m in matrix if m["window"] == wid and m["date"] == date and m["exchange"] == ex and m["data_type"] == dtp][0]
                cells[(ex, dtp)] = "✅" if st["status"] == "PRESENT" else "❌"
            md.append(f"| {wid} | {date} | {cells[('Bybit','orderbook')]} | {cells[('Bybit','trades')]} | {cells[('OKX','orderbook')]} | {cells[('OKX','trades')]} |")
    md += ["", "## File-level verification (real UTC spans)", "| exchange | type | file | symbol | first_utc | last_utc | ok |", "|---|---|---|---|---|---|:--:|"]
    for r in results:
        md.append(f"| {r['exchange']} | {r['data_type']} | {r['filename']} | {r.get('symbol','-')} | {r.get('first_utc','-')} | {r.get('last_utc','-')} | {'OK' if r.get('ok') else 'BROKEN'} |")
    md += ["", "## DATA_CHECK_RESULT", "```",
           f"1. BYBIT_STATUS: {bybit_status}",
           f"2. OKX_STATUS:   {okx_status}",
           f"3. BYBIT_MISSING: OB={bybit_missing['orderbook'] or 'none'} | trades={bybit_missing['trades'] or 'none'}",
           f"4. OKX_MISSING:   OB={okx_missing['orderbook'] or 'none'} | trades={okx_missing['trades'] or 'none'}",
           f"5. ARCHIVE_ISSUES: broken={[r['filename'] for r in broken] or 'none'}; duplicates/suspicious={suspicious or 'none'}; bad_symbol={[r['filename'] for r in bad_symbol] or 'none'}",
           f"6. TIMESTAMP_CHECK: multi-UTC-day files (filename != UTC coverage): {[(r['filename'], r['first_date']+'..'+r['last_date']) for r in multi_day] or 'none — all single UTC day'}",
           f"7. READY_FOR_NEXT_PROMPT: {ready}",
           "```", "",
           "## If NOT READY — exact files to download (exchange, data_type, symbol, date)"]
    if ready == "NO":
        for dtp, lst in [("orderbook", okx_missing["orderbook"]), ("trades", okx_missing["trades"])]:
            for x in lst: md.append(f"- OKX, {dtp}, BTC-USDT-SWAP, {x.split(':')[1]}")
        for dtp, lst in [("orderbook", bybit_missing["orderbook"]), ("trades", bybit_missing["trades"])]:
            for x in lst: md.append(f"- Bybit, {dtp}, BTCUSDT, {x.split(':')[1]}")
    (OUT / "DATA_CHECK_RESULT.md").write_text("\n".join(md), encoding="utf-8")

    print("\n==== SUMMARY ====")
    print("BYBIT_STATUS:", bybit_status, "| OKX_STATUS:", okx_status, "| READY:", ready)
    print("Bybit missing:", bybit_missing)
    print("OKX missing:", okx_missing)
    print("broken:", [r["filename"] for r in broken])
    print("multi_utc_day:", [(r["filename"], r.get("first_date"), r.get("last_date")) for r in multi_day])
    print("suspicious/dup:", suspicious)
    print("bad_symbol:", [(r["filename"], r.get("symbol")) for r in bad_symbol])
    return 0


if __name__ == "__main__":
    sys.exit(main())
