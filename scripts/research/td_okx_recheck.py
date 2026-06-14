"""OKX RE-CHECK + quarantine old OKX (NO calibration / NO analysis).

Verifies the freshly-dropped OKX BTC-USDT-SWAP files for NOVEMBER/JANUARY/APRIL sessions by opening each
archive and reading real inner timestamps (OB = UTC-day; trades = UTC+8 day boundary -> compute true UTC
span and check full coverage with no gaps). Then MOVES the old partial OKX (raw + normalized caches) into a
quarantine folder so it can't mix. Bybit is not touched.
"""
from __future__ import annotations
import csv, io, json, shutil, sys, tarfile, zipfile, datetime as dt
from pathlib import Path

HOME = Path("C:/Users/gibilev")
TG = HOME / "Downloads/Telegram Desktop"
PROJ = HOME / "orderflow-research"
OLD = PROJ / "data/11.06.2026"
NORM = PROJ / "reports/trend_down_calibration_v1/_normalized"
QUAR_RAW = PROJ / "data/_quarantine_old_okx_replaced"
QUAR_NORM = NORM / "_quarantine_old_okx_replaced"
OUT = PROJ / "reports/trend_down_calibration_v1"

OB_DATES = {
    "NOVEMBER": ["2025-11-19", "2025-11-20", "2025-11-21", "2025-11-22"],
    "JANUARY": ["2026-01-28", "2026-01-29", "2026-01-30", "2026-01-31"],
    "APRIL": ["2024-04-12", "2024-04-13", "2024-04-14", "2024-04-15", "2024-04-16", "2024-04-17"],
}
# OKX trades use UTC+8 day boundary: label D covers UTC [(D-1) 16:00, D 16:00). To cover UTC day D need labels D and D+1.
TRADE_LABELS = {
    "NOVEMBER": ["2025-11-19", "2025-11-20", "2025-11-21", "2025-11-22", "2025-11-23"],
    "JANUARY": ["2026-01-28", "2026-01-29", "2026-01-30", "2026-01-31", "2026-02-01"],
    "APRIL": ["2024-04-12", "2024-04-13", "2024-04-14", "2024-04-15", "2024-04-16", "2024-04-17", "2024-04-18"],
}


def utc(ts_s): return dt.datetime.fromtimestamp(ts_s, tz=dt.timezone.utc)
def utct(ts_s): return utc(ts_s).strftime("%Y-%m-%d %H:%M:%S")
def utcd(ts_s): return utc(ts_s).strftime("%Y-%m-%d")


def tar_first_ts(path):
    with tarfile.open(path, "r:gz") as t:
        m = next(x for x in t.getmembers() if x.isfile())
        fh = t.extractfile(m)
        for line in io.TextIOWrapper(fh, encoding="utf-8"):
            line = line.strip()
            if line:
                ev = json.loads(line)
                return int(ev["ts"]) / 1000, ev.get("instId"), m.name
    return None, None, None


def zip_csv_first_last(path):
    with zipfile.ZipFile(path) as z:
        m = z.namelist()[0]
        first = last = None
        with z.open(m) as fh:
            for i, line in enumerate(io.TextIOWrapper(fh, encoding="utf-8")):
                if i == 0: continue
                line = line.rstrip("\n")
                if line:
                    if first is None: first = line
                    last = line
        f = first.split(","); l = last.split(",")
        return int(f[-1]) / 1000, int(l[-1]) / 1000, f[0], m


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = {"ob": [], "trades": []}

    # ---- scan + verify OKX OrderBook (relevant dates only) ----
    needed_ob = {d for ds in OB_DATES.values() for d in ds}
    ob_files = sorted(TG.glob("BTC-USDT-SWAP-L2orderbook-400lv-*.tar*"))
    seen_ob = {}
    for p in ob_files:
        # date from name only to filter scope; verify by content
        import re
        m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
        nd = m.group(1) if m else None
        if nd not in needed_ob: continue
        try:
            fts, sym, member = tar_first_ts(p)
            rd = utcd(fts)
            dup = "DUP" if (rd in seen_ob) else ""
            seen_ob.setdefault(rd, []).append(p.name)
            results["ob"].append({"file": p.name, "nominal_date": nd, "verified_utc_date": rd, "first_utc": utct(fts),
                                  "symbol": sym, "ok": sym == "BTC-USDT-SWAP" and rd == nd, "dup": dup})
        except Exception as e:
            results["ob"].append({"file": p.name, "nominal_date": nd, "ok": False, "error": repr(e)[:120]})

    # ---- scan + verify OKX trades (UTC+8) ----
    needed_labels = {d for ds in TRADE_LABELS.values() for d in ds}
    tr_files = sorted(TG.glob("BTC-USDT-SWAP-trades-*.zip"))
    seen_tr = {}; spans = []
    for p in tr_files:
        import re
        m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
        nd = m.group(1) if m else None
        if nd not in needed_labels: continue
        try:
            fts, lts, sym, member = zip_csv_first_last(p)
            dup = "DUP" if (nd in seen_tr) else ""
            seen_tr.setdefault(nd, []).append(p.name)
            if not dup: spans.append((fts, lts))
            results["trades"].append({"file": p.name, "label_date": nd, "first_utc": utct(fts), "last_utc": utct(lts),
                                      "utc_span": f"{utcd(fts)}..{utcd(lts)}", "symbol": sym, "ok": sym == "BTC-USDT-SWAP", "dup": dup})
        except Exception as e:
            results["trades"].append({"file": p.name, "label_date": nd, "ok": False, "error": repr(e)[:120]})

    # ---- OB coverage ----
    ob_have = {r["verified_utc_date"] for r in results["ob"] if r.get("ok")}
    ob_missing = {s: [d for d in ds if d not in ob_have] for s, ds in OB_DATES.items()}

    # ---- trades coverage: union of UTC spans, check each required UTC day fully covered ----
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1] + 1: merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else: merged.append((s, e))
    GAP_TOL_S = 120  # sub-2min holes at file boundaries are no-trade intervals, not missing data
    def covered_day(d):
        d0 = dt.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp()
        d1 = d0 + 86400
        gaps = []; cur = d0
        for s, e in merged:
            if e < cur: continue
            if s > cur and s < d1:
                gaps.append((cur, min(s, d1)))
            cur = max(cur, e)
            if cur >= d1: break
        if cur < d1: gaps.append((cur, d1))
        real = [(utct(a), utct(b), round(b - a)) for a, b in gaps if (b - a) > GAP_TOL_S]
        return (len(real) == 0), real
    tr_missing = {}; tr_gaps = {}
    for s, ds in OB_DATES.items():
        miss = []; gaps = {}
        for d in ds:
            ok, g = covered_day(d)
            if not ok: miss.append(d); gaps[d] = g
        tr_missing[s] = miss; tr_gaps[s] = gaps
    # which trade LABELS are missing
    label_have = {r["label_date"] for r in results["trades"] if r.get("ok")}
    label_missing = {s: [d for d in ds if d not in label_have] for s, ds in TRADE_LABELS.items()}

    # ---- duplicates / old files ----
    dup_ob = [r["file"] for r in results["ob"] if r.get("dup") == "DUP"]
    dup_tr = [r["file"] for r in results["trades"] if r.get("dup") == "DUP"]

    # ---- QUARANTINE old OKX (move, not delete) ----
    QUAR_RAW.mkdir(parents=True, exist_ok=True); QUAR_NORM.mkdir(parents=True, exist_ok=True)
    moved = []
    old_raw = ["BTC-USDT-SWAP-L2orderbook-400lv-2025-11-22.tar.gz", "BTC-USDT-SWAP-L2orderbook-400lv-2026-01-31.tar.gz",
               "BTC-USDT-SWAP-L2orderbook-400lv-2026-02-14.tar.gz", "BTC-USDT-SWAP-trades-2025-11-23.zip",
               "BTC-USDT-SWAP-trades-2026-02-01.zip", "BTC-USDT-SWAP-trades-2026-02-15.zip"]
    for n in old_raw:
        src = OLD / n
        if src.exists():
            shutil.move(str(src), str(QUAR_RAW / n)); moved.append(f"data/11.06.2026/{n}")
    for p in list(NORM.glob("OKX_*_l2_1s.csv.gz")):
        shutil.move(str(p), str(QUAR_NORM / p.name)); moved.append(f"_normalized/{p.name}")
    already_quar = [p.name for p in QUAR_RAW.glob("*") if p.is_file()] + [p.name for p in QUAR_NORM.glob("*") if p.is_file()]

    old_removed = "YES" if (moved or already_quar) else "NO(none-present)"
    okx_ob_status = "BROKEN" if any(not r.get("ok") and r.get("error") for r in results["ob"]) else ("OK" if not any(ob_missing.values()) else "MISSING")
    okx_tr_status = "BROKEN" if any(not r.get("ok") and r.get("error") for r in results["trades"]) else ("OK" if not any(tr_missing.values()) else "MISSING")
    ts_cov = "OK" if not any(tr_missing.values()) else "GAPS_FOUND"
    dups_in_scope = (dup_ob + dup_tr)
    ready = "YES" if okx_ob_status == "OK" and okx_tr_status == "OK" and ts_cov == "OK" else "NO"

    # ---- write report ----
    def w(line): md.append(line)
    md = ["# OKX_RECHECK_RESULT — TREND_DOWN sessions (verify + quarantine, NO calibration)", "",
          f"Build {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} · new OKX from `{TG}`; Bybit untouched.", "",
          "## OKX OrderBook (verified UTC date == required)", "| session | date | file | verified UTC | symbol | ok |", "|---|---|---|---|---|:--:|"]
    for s, ds in OB_DATES.items():
        for d in ds:
            r = next((x for x in results["ob"] if x.get("verified_utc_date") == d and x.get("ok")), None)
            if r: w(f"| {s} | {d} | {r['file']} | {r['verified_utc_date']} | {r['symbol']} | OK |")
            else: w(f"| {s} | {d} | — | — | — | ❌ MISSING |")
    md += ["", "## OKX Trades (UTC+8 labels -> real UTC span)", "| session | label | file | real UTC span | symbol | dup |", "|---|---|---|---|---|:--:|"]
    for s, ds in TRADE_LABELS.items():
        for d in ds:
            r = next((x for x in results["trades"] if x.get("label_date") == d and not x.get("dup")), None)
            rd = next((x for x in results["trades"] if x.get("label_date") == d and x.get("dup")), None)
            if r: w(f"| {s} | {d} | {r['file']} | {r['first_utc']} .. {r['last_utc']} | {r['symbol']} | {'(dup also present)' if rd else ''} |")
            else: w(f"| {s} | {d} | — | — | — | ❌ MISSING LABEL |")
    md += ["", "## UTC-day trade coverage (gaps)"]
    for s, ds in OB_DATES.items():
        for d in ds:
            ok, g = covered_day(d)
            w(f"- {s} {d}: {'FULL' if ok else 'GAP ' + str(g)}")
    md += ["", "## Quarantine (old OKX moved, not deleted)"] + [f"- {m} -> _quarantine_old_okx_replaced/" for m in moved]
    md += ["", "## OKX_RECHECK_RESULT", "```",
           f"1. OLD_OKX_REMOVED_FROM_WORKSET: {old_removed}",
           f"2. OKX_ORDERBOOK_STATUS: {okx_ob_status}",
           f"3. OKX_TRADES_STATUS: {okx_tr_status}",
           f"4. MISSING_FILES: OB={ {k:v for k,v in ob_missing.items() if v} or 'none'} | trade_labels={ {k:v for k,v in label_missing.items() if v} or 'none'}",
           f"5. TIMESTAMP_COVERAGE: {ts_cov}" + ("" if ts_cov == "OK" else f"  gaps={ {k:v for k,v in tr_missing.items() if v} }"),
           f"6. DUPLICATES_OR_OLD_FILES_IN_SCOPE: {'YES, ' + str(dups_in_scope) if dups_in_scope else 'NO'}",
           f"7. READY_FOR_NEXT_PROMPT: {ready}",
           "```"]
    if ready == "NO":
        md += ["", "## Exact files to download (exchange, data_type, symbol, date/label)"]
        for s, v in ob_missing.items():
            for d in v: md.append(f"- OKX, orderbook, BTC-USDT-SWAP, {d}")
        for s, v in label_missing.items():
            for d in v: md.append(f"- OKX, trades, BTC-USDT-SWAP, label {d} (UTC+8 file)")
    (OUT / "OKX_RECHECK_RESULT.md").write_text("\n".join(md), encoding="utf-8")
    with (OUT / "OKX_RECHECK_FILES.csv").open("w", encoding="utf-8", newline="") as fh:
        rows = [{"type": "orderbook", **r} for r in results["ob"]] + [{"type": "trades", **r} for r in results["trades"]]
        cols = sorted({k for r in rows for k in r})
        wcsv = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); wcsv.writeheader()
        for r in rows: wcsv.writerow(r)

    print("OLD_OKX_REMOVED:", old_removed, "moved", len(moved))
    print("OKX_OB:", okx_ob_status, "| OKX_TRADES:", okx_tr_status, "| TS_COVERAGE:", ts_cov, "| READY:", ready)
    print("OB missing:", {k: v for k, v in ob_missing.items() if v})
    print("trade-label missing:", {k: v for k, v in label_missing.items() if v})
    print("trade UTC-day gaps:", {k: v for k, v in tr_missing.items() if v})
    print("dups in scope:", dups_in_scope)
    print("moved:", moved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
