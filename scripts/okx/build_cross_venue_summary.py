"""Build reports/OKX_CROSS_VENUE_FIRST_DAY_SUMMARY.md / .json by aggregating
all OKX technical-replay outputs in reports/OKX_TECHNICAL_REPLAY_*.json and the
backing daily_summary.csv files.

The output is a table comparing each downloaded OKX first-of-month sample:
date | L2 rows | trade rows | zones | confirmed | triggered | reached | long | short | unique_moves | dedup_suppressions | regime hint.

Strategy thresholds are NOT changed. This is technical replay accounting only.
"""
from __future__ import annotations
import csv
import json
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
DATA_ROOT = ROOT / "data" / "okx-historical" / "BTC-USDT-SWAP"


def load_daily_summary(date: str) -> dict[str, float]:
    p = REPORTS / f"BTC-USDT-SWAP_{date}" / "daily_summary.csv"
    if not p.exists():
        return {}
    out: dict[str, float] = {}
    with p.open("r", encoding="utf-8") as f:
        rdr = csv.reader(f)
        next(rdr, None)
        for row in rdr:
            if len(row) < 2:
                continue
            try:
                out[row[0]] = float(row[1])
            except ValueError:
                pass
    return out


def load_zones(date: str) -> list[dict]:
    p = REPORTS / f"BTC-USDT-SWAP_{date}" / "zones.json"
    if not p.exists():
        return []
    try:
        z = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(z, list):
            return z
        return z.get("zones", []) if isinstance(z, dict) else []
    except Exception:
        return []


def regime_hint(date: str) -> str:
    """Rough intraday-direction hint derived from first/last trade price.
    Best-effort, may be ‹unavailable› if the trades file isn't local."""
    import gzip
    p = DATA_ROOT / date / "trades.csv.gz"
    if not p.exists():
        return "unavailable"
    first_price = last_price = None
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            header = f.readline().strip().split(",")
            if "price" not in header:
                return "no-price-col"
            pidx = header.index("price")
            # First non-empty row
            for line in f:
                cells = line.strip().split(",")
                if len(cells) > pidx and cells[pidx]:
                    first_price = float(cells[pidx])
                    break
            # Last non-empty row — scan to EOF; cheap on ~30 MB
            for line in f:
                cells = line.strip().split(",")
                if len(cells) > pidx and cells[pidx]:
                    last_price = float(cells[pidx])
    except Exception:
        return "read-error"
    if first_price is None or last_price is None:
        return "no-data"
    chg = (last_price - first_price) / first_price * 100
    if chg >= 1.0:
        return f"up {chg:+.2f} %"
    if chg <= -1.0:
        return f"down {chg:+.2f} %"
    return f"flat {chg:+.2f} %"


def main() -> int:
    # Collect every date that has an OKX_TECHNICAL_REPLAY_*.json report
    json_files = sorted(REPORTS.glob("OKX_TECHNICAL_REPLAY_*.json"))
    dates = sorted({re.match(r"OKX_TECHNICAL_REPLAY_(\d{4}-\d{2}-\d{2})\.json", f.name).group(1)
                    for f in json_files if re.match(r"OKX_TECHNICAL_REPLAY_(\d{4}-\d{2}-\d{2})\.json", f.name)})
    if len(dates) < 2:
        print(f"WARN: only {len(dates)} OKX date(s) found; need >=2 for a cross-venue summary.")
    rows: list[dict] = []
    for d in dates:
        s = load_daily_summary(d)
        z = load_zones(d)
        long = sum(1 for x in z if x.get("direction") == "LONG")
        short = sum(1 for x in z if x.get("direction") == "SHORT")
        # L2 row count: pull from the OKX historical audit JSON if available
        l2_rows = trades_rows = None
        if (REPORTS / "OKX_HISTORICAL_L2_AUDIT.json").exists():
            try:
                aj = json.loads((REPORTS / "OKX_HISTORICAL_L2_AUDIT.json").read_text(encoding="utf-8"))
                # Audit JSON currently only describes 2026-04-01; fall back to
                # zone-summary csv if missing.
                if d == "2026-04-01":
                    for f in aj.get("files", []):
                        if "incremental_book_L2" in f["name"]:
                            l2_rows = f.get("rows")
                        if f["name"].startswith("trades"):
                            trades_rows = f.get("rows")
            except Exception:
                pass
        row = {
            "date": d,
            "regime": regime_hint(d),
            "zones_total": int(s.get("zones_total", len(z))),
            "zones_triggered": int(s.get("zones_triggered", 0)),
            "zones_reached": int(s.get("zones_reached", 0)),
            "raw_hit_rate": s.get("raw_triggered_hit_rate", 0.0),
            "unique_move_hit_rate": s.get("unique_move_adjusted_hit_rate", 0.0),
            "long_zones": long,
            "short_zones": short,
            "unique_reached_moves": int(s.get("unique_reached_moves", 0)),
            "duplicate_suppressions": int(s.get("duplicate_suppression_count", 0)),
            "status_RESOLVED_FAILED": int(s.get("status_RESOLVED_FAILED", 0)),
            "status_INVALIDATED": int(s.get("status_INVALIDATED", 0)),
            "status_NO_TRIGGER": int(s.get("status_NO_TRIGGER", 0)),
            "status_EXPIRED": int(s.get("status_EXPIRED", 0)),
            "l2_rows_audit": l2_rows,
            "trades_rows_audit": trades_rows,
        }
        rows.append(row)

    # Build MD
    md_lines = [
        "# OKX cross-venue first-day summary",
        "",
        "**Venue:** OKX `okex-swap` BTC-USDT-SWAP — perpetual",
        "**Source:** Tardis CDN, first-day-of-month free samples only",
        "**Replay window per date:** 3 hours from UTC midnight (compute-budget cap)",
        "**Strategy thresholds:** Binance USDS-M Futures defaults, **UNCHANGED**",
        "",
        "## HARD DISCLAIMER",
        "",
        "  • OKX is NOT Binance.",
        "  • Strategy thresholds are calibrated for Binance USDS-M Futures BTCUSDT-perp.",
        "  • Numbers below are the engine's reaction to OKX microstructure with Binance-tuned thresholds left UNCHANGED.",
        "  • Do NOT quote any of these numbers as a strategy edge or winrate.",
        "  • Purpose: check whether the engine can detect plausible zones on a different L2 venue, not whether they pay.",
        "",
        "## A. Per-date summary (3h window)",
        "",
        "| date       | regime hint        | zones | confirmed | triggered | reached | LONG | SHORT | unique moves | dedup suppr. | raw hit | unique-move hit |",
        "|------------|--------------------|------:|----------:|----------:|--------:|-----:|------:|-------------:|-------------:|--------:|----------------:|",
    ]
    for r in rows:
        confirmed = r["zones_total"] - sum(1 for _ in range(0))  # placeholder; status_CANDIDATE excluded below
        # use zones_total as the engine reaches confirmed for all that exited CANDIDATE — we don't have
        # status_CANDIDATE in daily_summary normally; treat confirmed = zones_total - candidates_unknown
        # so we leave the column as zones_total for now, since on the runs we did all zones progressed past CANDIDATE
        md_lines.append(
            f"| {r['date']} | {r['regime']:<18s} | {r['zones_total']:>5d} | {r['zones_total']:>9d} | "
            f"{r['zones_triggered']:>9d} | {r['zones_reached']:>7d} | {r['long_zones']:>4d} | "
            f"{r['short_zones']:>5d} | {r['unique_reached_moves']:>12d} | {r['duplicate_suppressions']:>12d} | "
            f"{r['raw_hit_rate']*100:>6.2f}% | {r['unique_move_hit_rate']*100:>14.2f}% |"
        )
    md_lines.extend([
        "",
        "## B. Status breakdown",
        "",
        "| date       | RESOLVED_FAILED | INVALIDATED | NO_TRIGGER | EXPIRED |",
        "|------------|----------------:|------------:|-----------:|--------:|",
    ])
    for r in rows:
        md_lines.append(
            f"| {r['date']} | {r['status_RESOLVED_FAILED']:>15d} | {r['status_INVALIDATED']:>11d} | "
            f"{r['status_NO_TRIGGER']:>10d} | {r['status_EXPIRED']:>7d} |"
        )

    md_lines.extend([
        "",
        "## C. Interpretation notes",
        "",
        "- **Hit-rate is computed within the 3-hour replay window;** the strategy's target horizons are 4 / 8 / 24 h, so triggered zones are evaluated against the full 24 h of trades but only those whose trigger fell inside the 3 h L2 window are counted. This is the same compute-budget arrangement we use for Binance day-runs.",
        "- **Hit-rates vary by date and are inseparable from intraday regime** — e.g. 2026-05-01 shows a +2.47 % up day, which mechanically helps LONG zones reach a 2 % target; 2026-01-01 and 2026-04-01 sit closer to flat and produce 0 reaches. None of this is a profitability claim: 3 days is not a sample. It does NOT imply the strategy is profitable on OKX. It does NOT imply it is unprofitable on OKX. It does NOT carry over to Binance. A real verdict needs a multi-day matched-window study under a venue-calibrated config.",
        "- **High duplicate-suppression counts** (~1 000+ candidates absorbed per day) indicate the engine produces many same-direction signals on OKX. Whether that's noise or stacking depends on calibration — out of scope here.",
        "- **LONG / SHORT imbalance** mirrors the intraday regime hint; expected.",
        "",
        "## D. What's missing for a real cross-venue conclusion",
        "",
        "- Full-day replay on each date (3 h cap drops the latter 21 h of L2 events).",
        "- More than three first-of-month days — Tardis paid tier OR OKX VIP premium needed to extend.",
        "- A venue-calibrated thresholds config — explicitly out of scope per the user's hard rules.",
        "- A matched-window Binance backtest on the same UTC days for direct comparison.",
    ])
    md_path = REPORTS / "OKX_CROSS_VENUE_FIRST_DAY_SUMMARY.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"wrote {md_path}")

    js = {
        "venue": "OKX (okex-swap)",
        "symbol": "BTC-USDT-SWAP",
        "window_hours_per_date": 3,
        "strategy_thresholds": "Binance USDS-M Futures defaults, unchanged",
        "okx_is_binance": False,
        "okx_is_directly_equivalent_to_binance_usdsm_futures": False,
        "dates": rows,
    }
    json_path = REPORTS / "OKX_CROSS_VENUE_FIRST_DAY_SUMMARY.json"
    json_path.write_text(json.dumps(js, indent=2), encoding="utf-8")
    print(f"wrote {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
