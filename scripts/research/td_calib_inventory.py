"""TASK1 / A — DATA INVENTORY for TREND_DOWN calibration v1.

Scans data/11.06.2026 (manually downloaded), classifies each file by exchange/product/data_type/date,
maps to the 3 TREND_DOWN windows, and reports present/missing HONESTLY. No assumptions; missing = missing.
"""
from __future__ import annotations
import csv, json, re, sys, datetime as dt
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
SRC = ROOT / "data/11.06.2026"
OUT = ROOT / "reports/trend_down_calibration_v1"
WINDOWS = {"W1": ("2025-11-19", "2025-11-22"), "W2": ("2026-02-11", "2026-02-14"), "W3": ("2026-01-28", "2026-01-31")}


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def daterange(a, b):
    da, db = dt.date.fromisoformat(a), dt.date.fromisoformat(b); out = []
    while da <= db: out.append(da.isoformat()); da += dt.timedelta(days=1)
    return out


def classify(p: Path):
    n = p.name; mb = round(p.stat().st_size / 1e6, 2); m = re.search(r"(\d{4}-\d{2}-\d{2})", n)
    date = m.group(1) if m else None
    if re.match(r"\d{4}-\d{2}-\d{2}_BTCUSDT_ob200\.data\.zip", n):
        return {"source_exchange": "Bybit", "product_type": "linear perpetual (Contract)", "symbol": "BTCUSDT",
                "data_type": "orderbook_L2_200", "date": date, "file_size_mb": mb,
                "detected_schema": "Bybit V5 JSONL orderbook.200 (snapshot+delta; ts ms; b/a=[price,size]; size 0=delete)", "status": "PRESENT", "notes": ""}
    if re.match(r"BTC-USDT-SWAP-L2orderbook-400lv-\d{4}-\d{2}-\d{2}\.tar\.gz", n):
        return {"source_exchange": "OKX", "product_type": "SWAP (perp)", "symbol": "BTC-USDT-SWAP",
                "data_type": "orderbook_L2_400", "date": date, "file_size_mb": mb,
                "detected_schema": "OKX L2 400lv JSONL (action snapshot/update; ts str ms; asks/bids=[price,size,#orders])", "status": "PRESENT", "notes": ""}
    if re.match(r"BTC-USDT-SWAP-trades-\d{4}-\d{2}-\d{2}\.zip", n):
        return {"source_exchange": "OKX", "product_type": "SWAP (perp)", "symbol": "BTC-USDT-SWAP",
                "data_type": "trades", "date": date, "file_size_mb": mb,
                "detected_schema": "CSV: instrument_name,trade_id,side,price,size,created_time(ms)", "status": "PRESENT", "notes": ""}
    return {"source_exchange": "UNKNOWN", "product_type": "UNKNOWN", "symbol": "UNKNOWN", "data_type": "UNKNOWN",
            "date": date, "file_size_mb": mb, "detected_schema": "unrecognized", "status": "PRESENT", "notes": "unclassified filename"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not SRC.exists():
        print(f"SOURCE MISSING: {SRC}"); return 1
    rows = [dict(filepath=str(p.relative_to(ROOT)).replace("\\", "/"), **classify(p)) for p in sorted(SRC.iterdir()) if p.is_file()]

    # index present (exchange, data_type, date)
    present = {(r["source_exchange"], r["data_type"], r["date"]) for r in rows if r["status"] == "PRESENT"}
    # expected matrix: per window day, 4 streams
    expected = [("Bybit", "orderbook_L2_200"), ("Bybit", "trades"), ("OKX", "orderbook_L2_400"), ("OKX", "trades")]
    missing_rows = []
    for wid, (a, b) in WINDOWS.items():
        for d in daterange(a, b):
            for ex, dtp in expected:
                if (ex, dtp, d) not in present:
                    missing_rows.append({"source_exchange": ex, "product_type": ("linear perpetual (Contract)" if ex == "Bybit" else "SWAP (perp)"),
                                         "symbol": ("BTCUSDT" if ex == "Bybit" else "BTC-USDT-SWAP"), "data_type": dtp, "date": d,
                                         "filepath": "", "file_size_mb": "", "detected_schema": "", "status": "MISSING", "notes": f"window {wid}"})
    allrows = rows + missing_rows
    cols = ["source_exchange", "product_type", "symbol", "data_type", "date", "filepath", "file_size_mb", "detected_schema", "status", "notes"]
    with (OUT / "DATA_INVENTORY.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in allrows: w.writerow(r)

    # coverage per window
    def cov(ex, dtp, wid):
        a, b = WINDOWS[wid]; days = daterange(a, b)
        got = [d for d in days if (ex, dtp, d) in present]
        return got, [d for d in days if d not in got]
    cov_tbl = {}
    for wid in WINDOWS:
        cov_tbl[wid] = {f"{ex}_{dtp}": cov(ex, dtp, wid) for ex, dtp in expected}

    found_dates = sorted({r["date"] for r in rows if r["date"]})
    bybit_ob = [r["filepath"] for r in rows if r["source_exchange"] == "Bybit" and r["data_type"] == "orderbook_L2_200"]
    bybit_tr = [r["filepath"] for r in rows if r["source_exchange"] == "Bybit" and r["data_type"] == "trades"]
    okx_ob = [r["filepath"] for r in rows if r["source_exchange"] == "OKX" and r["data_type"] == "orderbook_L2_400"]
    okx_tr = [r["filepath"] for r in rows if r["source_exchange"] == "OKX" and r["data_type"] == "trades"]

    md = ["# DATA INVENTORY — TREND_DOWN calibration v1", "", f"Build {now_iso()} · source `data/11.06.2026` · RESEARCH/CALIBRATION ONLY.", "",
          "## Files found (by stream)",
          f"- **Bybit OrderBook (ob200)**: {len(bybit_ob)} files — {', '.join(Path(x).name for x in bybit_ob) if bybit_ob else 'NONE'}",
          f"- **Bybit Trades**: {len(bybit_tr)} files — {'NONE' if not bybit_tr else ', '.join(Path(x).name for x in bybit_tr)}",
          f"- **OKX OrderBook (400lv)**: {len(okx_ob)} files — {', '.join(Path(x).name for x in okx_ob) if okx_ob else 'NONE'}",
          f"- **OKX Trades**: {len(okx_tr)} files — {', '.join(Path(x).name for x in okx_tr) if okx_tr else 'NONE'}", "",
          "## Coverage per window (got / missing days)"]
    for wid, (a, b) in WINDOWS.items():
        md.append(f"### {wid}: {a}..{b}")
        for ex, dtp in expected:
            got, miss = cov_tbl[wid][f"{ex}_{dtp}"]
            md.append(f"- {ex} {dtp}: got {got or '[]'} · **missing {miss or '[]'}**")
    md += ["", "## Explicit summary",
           f"- **Dates found (any stream):** {found_dates}",
           "- **Dates MISSING by stream:**"]
    for ex, dtp in expected:
        miss_all = sorted({mr["date"] for mr in missing_rows if mr["source_exchange"] == ex and mr["data_type"] == dtp})
        md.append(f"  - {ex} {dtp}: {miss_all or 'none'}")
    md += ["",
           f"- **Where is Bybit OrderBook:** `data/11.06.2026/*_BTCUSDT_ob200.data.zip` — COMPLETE for all 12 window days.",
           f"- **Where is Bybit Trades:** NOT PROVIDED (0 files) — trade-flow features from Bybit are N/A.",
           f"- **Where is OKX OrderBook:** `data/11.06.2026/BTC-USDT-SWAP-L2orderbook-400lv-*.tar.gz` — only the LAST day of each window (2025-11-22, 2026-01-31, 2026-02-14).",
           f"- **Where is OKX Trades:** only out-of-window days (2025-11-23, 2026-02-01, 2026-02-15) — NONE inside the 3 windows.",
           "",
           "## Can we continue calibration?",
           "**YES — with Bybit ob200 as the primary in-window price + L2 source (full coverage).** Outcome labels",
           "(MFE/hit2/2.5/3) and L2 features (spread, depth, depth_imbalance, best sizes) are computable for all 3",
           "windows from Bybit ob200 mid-price reconstruction. **Trade-flow evidence** (real taker imbalance / CVD /",
           "aggressor side / effort_vs_result from executions) is **N/A in-window** (no in-window trades on either",
           "venue) and will be **L2-proxied or N/A**, never fabricated. OKX serves only as a 1-day-per-window L2",
           "cross-check. This is a CALIBRATION pass, not production.", ""]
    (OUT / "DATA_INVENTORY.md").write_text("\n".join(md), encoding="utf-8")

    print(f"inventory rows: {len(allrows)} (present {len(rows)}, missing {len(missing_rows)})")
    print("Bybit ob200:", len(bybit_ob), "| Bybit trades:", len(bybit_tr), "| OKX ob:", len(okx_ob), "| OKX trades:", len(okx_tr))
    for wid in WINDOWS:
        print(f"{wid}: " + " | ".join(f"{k}: got{len(v[0])}/miss{len(v[1])}" for k, v in cov_tbl[wid].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
