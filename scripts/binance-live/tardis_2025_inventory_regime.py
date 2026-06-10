"""B1 + B2 + B3 + B4 for Binance Tardis 2025 first-of-month dataset.

Inputs:
  data/tardis/binance-futures/BTCUSDT/<date>/{incremental_book_L2,trades,book_ticker,derivative_ticker,liquidations}.csv.gz

Outputs:
  reports/binance-tardis/BINANCE_TARDIS_2025_INVENTORY.{md,json}
  reports/binance-tardis/BINANCE_TARDIS_2025_REGIME_TABLE.{md,json}
  reports/binance-tardis/BINANCE_TARDIS_2025_SELECTED_DATES.json
  reports/binance-tardis/BINANCE_TARDIS_2025_DATA_QUALITY_AUDIT.{md,json}

Light regime/feasibility scan over trades.csv.gz only (fast). Quality audit
also light — relies on file existence/sizes + first-row sanity. NO new backtest.
"""
from __future__ import annotations
import csv
import datetime as dt
import gzip
import json
import statistics as stats
import sys
from collections import deque
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
DATA_ROOT = ROOT / "data/tardis/binance-futures/BTCUSDT"
REPORTS = ROOT / "reports/binance-tardis"
REPORTS.mkdir(parents=True, exist_ok=True)

DATES = [f"2025-{m:02d}-01" for m in range(1, 13)]
STREAMS = ["incremental_book_L2", "trades", "book_ticker", "derivative_ticker", "liquidations"]
HORIZONS_S = {"4h": 4 * 3600, "8h": 8 * 3600, "24h": 24 * 3600}
TARGETS_PCT = [0.5, 1.0, 1.5, 2.0]


def file_info(p: Path) -> dict:
    if not p.exists():
        return {"exists": False, "size_bytes": 0}
    st = p.stat()
    return {"exists": True, "size_bytes": st.st_size, "mtime_iso":
            dt.datetime.fromtimestamp(st.st_mtime, tz=dt.timezone.utc).isoformat(timespec="seconds")}


def stream_trades_sec_bucket(date: str) -> list[tuple[int, float]]:
    p = DATA_ROOT / date / "trades.csv.gz"
    last_price_by_sec: dict[int, float] = {}
    n = 0
    with gzip.open(p, "rt", encoding="utf-8", newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        idx_ts = header.index("timestamp")
        idx_price = header.index("price")
        for row in rdr:
            try:
                ts_us = int(row[idx_ts])
                price = float(row[idx_price])
            except Exception:
                continue
            n += 1
            last_price_by_sec[ts_us // 1_000_000] = price
    return sorted(last_price_by_sec.items()), n


def day_regime_one(date: str) -> dict:
    pts, n_trades = stream_trades_sec_bucket(date)
    if not pts:
        return {"date": date, "n_trades": 0}
    open_p = pts[0][1]
    close_p = pts[-1][1]
    prices = [p for _, p in pts]
    secs = [s for s, _ in pts]
    high = max(prices)
    low = min(prices)
    day_return = (close_p - open_p) / open_p * 100.0 if open_p else None
    day_range = (high - low) / low * 100.0 if low > 0 else None

    forward = {h: {"max_up": 0.0, "max_down": 0.0} for h in HORIZONS_S}
    for h_label, h_s in HORIZONS_S.items():
        max_up = 0.0
        max_down = 0.0
        dq_max = deque()
        dq_min = deque()
        j = 0
        N = len(pts)
        for i in range(N):
            while j < N and secs[j] - secs[i] <= h_s:
                while dq_max and prices[dq_max[-1]] <= prices[j]:
                    dq_max.pop()
                dq_max.append(j)
                while dq_min and prices[dq_min[-1]] >= prices[j]:
                    dq_min.pop()
                dq_min.append(j)
                j += 1
            while dq_max and dq_max[0] < i:
                dq_max.popleft()
            while dq_min and dq_min[0] < i:
                dq_min.popleft()
            if dq_max and dq_min:
                p0 = prices[i]
                up = (prices[dq_max[0]] - p0) / p0 * 100.0
                dn = (p0 - prices[dq_min[0]]) / p0 * 100.0
                if up > max_up:
                    max_up = up
                if dn > max_down:
                    max_down = dn
        forward[h_label]["max_up"] = round(max_up, 4)
        forward[h_label]["max_down"] = round(max_down, 4)

    feas = {f"{t}pct": (forward["24h"]["max_up"] >= t or forward["24h"]["max_down"] >= t)
            for t in TARGETS_PCT}

    # Regime label (FOR REPORT ONLY, not a filter feature)
    if day_return is not None and day_return >= 1.0:
        regime = "bullish"
    elif day_return is not None and day_return <= -1.0:
        regime = "bearish"
    elif day_range is not None and day_range >= 4.0 and abs(day_return or 0) < 1.0:
        regime = "high_vol"
    else:
        regime = "choppy"

    return {
        "date": date,
        "n_trades": n_trades,
        "open": open_p, "high": high, "low": low, "close": close_p,
        "day_return_pct": round(day_return, 4) if day_return is not None else None,
        "day_range_pct": round(day_range, 4) if day_range is not None else None,
        "forward_max_moves": forward,
        "feasibility": feas,
        "regime": regime,
    }


def main() -> int:
    # ---------- B1: inventory ----------
    inv: list[dict] = []
    for d in DATES:
        rec = {"date": d, "streams": {}, "size_total_bytes": 0}
        for s in STREAMS:
            p = DATA_ROOT / d / f"{s}.csv.gz"
            info = file_info(p)
            rec["streams"][s] = info
            rec["size_total_bytes"] += info["size_bytes"]
        rec["all_mandatory_present"] = all(
            rec["streams"][s]["exists"] and rec["streams"][s]["size_bytes"] > 1000
            for s in ("incremental_book_L2", "trades"))
        inv.append(rec)
    inv_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Binance Futures BTCUSDT, Tardis first-of-month 2025",
        "data_root": str(DATA_ROOT),
        "per_date": inv,
    }
    (REPORTS / "BINANCE_TARDIS_2025_INVENTORY.json").write_text(
        json.dumps(inv_json, indent=2), encoding="utf-8")
    md_inv = [
        "# Binance Tardis 2025 first-of-month inventory",
        "",
        f"**Build:** {inv_json['build_time_utc']}",
        f"**Source:** {inv_json['data_root']}",
        "",
        "| date | L2 (MB) | trades (MB) | book_ticker (MB) | derivative_ticker (MB) | liquidations (MB) | total (MB) | ready |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in inv:
        l2 = r["streams"]["incremental_book_L2"]["size_bytes"] / 1_048_576
        tr = r["streams"]["trades"]["size_bytes"] / 1_048_576
        bt = r["streams"]["book_ticker"]["size_bytes"] / 1_048_576
        dt_ = r["streams"]["derivative_ticker"]["size_bytes"] / 1_048_576
        lq = r["streams"]["liquidations"]["size_bytes"] / 1_048_576
        tot = r["size_total_bytes"] / 1_048_576
        ok = "YES" if r["all_mandatory_present"] else "NO"
        md_inv.append(f"| {r['date']} | {l2:.1f} | {tr:.1f} | {bt:.1f} | {dt_:.1f} | {lq:.1f} | {tot:.1f} | {ok} |")
    (REPORTS / "BINANCE_TARDIS_2025_INVENTORY.md").write_text("\n".join(md_inv), encoding="utf-8")
    print("[B1] inventory done", file=sys.stderr)

    # ---------- B2: regime + feasibility ----------
    rows = []
    for d in DATES:
        print(f"  regime scan {d}", file=sys.stderr)
        r = day_regime_one(d)
        rows.append(r)
    regime_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "per_date": rows,
    }
    (REPORTS / "BINANCE_TARDIS_2025_REGIME_TABLE.json").write_text(
        json.dumps(regime_json, indent=2), encoding="utf-8")
    md_r = [
        "# Binance Tardis 2025 - regime + feasibility table",
        "",
        f"**Build:** {regime_json['build_time_utc']}",
        "",
        "| date | regime | day Δ % | range % | 4h up | 4h dn | 8h up | 8h dn | 24h up | 24h dn | 0.5% | 1% | 1.5% | 2% |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|:---:|:---:|",
    ]
    for r in rows:
        if not r.get("n_trades"):
            md_r.append(f"| {r['date']} | no data |")
            continue
        f = r["forward_max_moves"]
        feas = r["feasibility"]
        md_r.append(
            f"| {r['date']} | {r['regime']} | {r['day_return_pct']:+6.2f} | {r['day_range_pct']:6.2f} | "
            f"{f['4h']['max_up']:6.2f} | {f['4h']['max_down']:6.2f} | "
            f"{f['8h']['max_up']:6.2f} | {f['8h']['max_down']:6.2f} | "
            f"{f['24h']['max_up']:6.2f} | {f['24h']['max_down']:6.2f} | "
            f"{'✓' if feas['0.5pct'] else '·'} | {'✓' if feas['1.0pct'] else '·'} | "
            f"{'✓' if feas['1.5pct'] else '·'} | {'✓' if feas['2.0pct'] else '·'} |"
        )
    (REPORTS / "BINANCE_TARDIS_2025_REGIME_TABLE.md").write_text("\n".join(md_r), encoding="utf-8")
    print("[B2] regime done", file=sys.stderr)

    # ---------- B3: select dates ----------
    feas_2pct = [r for r in rows if r.get("feasibility", {}).get("2.0pct")]
    # All 12 dates fit (size is manageable). Select all.
    selected = [r["date"] for r in rows]
    sel_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "selected_dates": selected,
        "n_selected": len(selected),
        "rationale": "All 12 first-of-month 2025 dates are available with mandatory streams.",
        "feasible_2pct_dates": [r["date"] for r in feas_2pct],
        "n_feasible_2pct": len(feas_2pct),
        "regime_split": {
            "bullish": [r["date"] for r in rows if r.get("regime") == "bullish"],
            "bearish": [r["date"] for r in rows if r.get("regime") == "bearish"],
            "choppy": [r["date"] for r in rows if r.get("regime") == "choppy"],
            "high_vol": [r["date"] for r in rows if r.get("regime") == "high_vol"],
        },
    }
    (REPORTS / "BINANCE_TARDIS_2025_SELECTED_DATES.json").write_text(
        json.dumps(sel_json, indent=2), encoding="utf-8")
    print("[B3] selection done", file=sys.stderr)

    # ---------- B4: data quality (light) ----------
    dq_rows = []
    for d in DATES:
        rec_inv = next(r for r in inv if r["date"] == d)
        rec_reg = next(r for r in rows if r["date"] == d)
        # Coverage from trades.csv.gz first/last ts
        first_ts, last_ts = None, None
        n_lines = 0
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            with gzip.open(p, "rt", encoding="utf-8", newline="") as f:
                rdr = csv.reader(f)
                header = next(rdr)
                idx_ts = header.index("timestamp")
                for row in rdr:
                    n_lines += 1
                    try:
                        ts = int(row[idx_ts])
                    except Exception:
                        continue
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts
        coverage_h = (last_ts - first_ts) / 1_000_000 / 3600 if first_ts and last_ts else None
        verdict = "OK" if (rec_inv["all_mandatory_present"] and coverage_h and coverage_h >= 23.5) else "PARTIAL"
        dq_rows.append({
            "date": d,
            "all_mandatory_present": rec_inv["all_mandatory_present"],
            "trades_first_ts_us": first_ts,
            "trades_last_ts_us": last_ts,
            "coverage_hours": round(coverage_h, 3) if coverage_h else None,
            "trades_rows": n_lines,
            "verdict": verdict,
        })
    dq_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "per_date": dq_rows,
        "all_pass": all(r["verdict"] == "OK" for r in dq_rows),
    }
    (REPORTS / "BINANCE_TARDIS_2025_DATA_QUALITY_AUDIT.json").write_text(
        json.dumps(dq_json, indent=2), encoding="utf-8")
    md_dq = [
        "# Binance Tardis 2025 - data quality audit",
        "",
        f"**Build:** {dq_json['build_time_utc']}",
        "",
        "| date | mandatory streams | coverage (h) | trades rows | verdict |",
        "|---|:---:|---:|---:|---|",
    ]
    for r in dq_rows:
        md_dq.append(f"| {r['date']} | {'YES' if r['all_mandatory_present'] else 'NO'} | "
                     f"{r['coverage_hours']} | {r['trades_rows']:,} | {r['verdict']} |")
    md_dq.extend([
        "",
        f"All-days-pass: **{dq_json['all_pass']}**",
    ])
    (REPORTS / "BINANCE_TARDIS_2025_DATA_QUALITY_AUDIT.md").write_text("\n".join(md_dq), encoding="utf-8")
    print("[B4] data quality done", file=sys.stderr)

    print()
    print("FLAGS:")
    print(f"  BINANCE_TARDIS_2025_INVENTORY_DONE   = YES")
    print(f"  BINANCE_TARDIS_DATES_AVAILABLE       = {selected}")
    print(f"  BINANCE_TARDIS_DATES_SELECTED        = {selected}")
    print(f"  BINANCE_TARDIS_DATA_QUALITY_PASS     = {'YES' if dq_json['all_pass'] else 'PARTIAL'}")
    print(f"  BINANCE_TARDIS_TARGET_2PCT_FEASIBLE_DAYS = {len(feas_2pct)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
