"""Compute intraday regime + target feasibility for every OKX first-of-month
sample we have on disk. Reads ONLY trades.csv.gz (no L2). Fast.

For each date:
  - first_price, last_price, day_return_pct
  - intraday high/low, range_pct
  - max forward up/down move within rolling 4h / 8h / 24h windows
  - feasible_target_pct[0.5, 1.0, 1.5, 2.0]: was a >=X% one-directional
    forward move ever reached over the day, in any direction?
  - regime label:
      "bullish"   if day_return_pct >= +1.0
      "bearish"   if day_return_pct <= -1.0
      "high_vol"  if range_pct >= 4.0 and |day_return_pct| < 1.0
      "choppy"    otherwise

Writes:
  reports/OKX_REGIME_TABLE.json
  reports/OKX_REGIME_TABLE.md
"""
from __future__ import annotations
import csv
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path("C:/Users/gibilev/orderflow-research")
DATA_ROOT = ROOT / "data" / "okx-historical" / "BTC-USDT-SWAP"
REPORTS = ROOT / "reports"
HORIZONS_MS = {"4h": 4 * 3_600_000, "8h": 8 * 3_600_000, "24h": 24 * 3_600_000}
FEASIBILITY_TARGETS = [0.5, 1.0, 1.5, 2.0]


def iter_trades(date_dir: Path) -> Iterable[tuple[int, float]]:
    p = date_dir / "trades.csv.gz"
    if not p.exists():
        return
    with gzip.open(p, "rt", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                ts_us = int(r["timestamp"])
                price = float(r["price"])
                yield ts_us, price
            except Exception:
                continue


def analyze_date(date: str) -> dict:
    date_dir = DATA_ROOT / date
    trades = list(iter_trades(date_dir))
    if not trades:
        return {"date": date, "status": "no_trades_file"}
    n = len(trades)
    first_ts, first_price = trades[0]
    last_ts, last_price = trades[-1]
    # min / max across the day
    hi = max(p for _, p in trades)
    lo = min(p for _, p in trades)
    day_return = (last_price - first_price) / first_price * 100.0
    range_pct = (hi - lo) / first_price * 100.0

    # Build a minute-grid for rolling-horizon analysis (downsample to last
    # trade per minute to keep the sweep cheap on millions of trades).
    minute_grid: dict[int, float] = {}
    for ts_us, p in trades:
        m = ts_us // 60_000_000  # minute index
        minute_grid[m] = p  # later trades overwrite earlier within the minute
    minutes = sorted(minute_grid.keys())
    prices = [minute_grid[m] for m in minutes]
    times_ms = [m * 60_000 for m in minutes]

    def max_forward_move_pct(window_ms: int) -> tuple[float, float]:
        """Return (best_up_pct, best_down_pct) over the full day, scanning
        every minute as a starting point and looking forward `window_ms`."""
        best_up = 0.0
        best_down = 0.0
        # Two-pointer rolling: for each i, slide j while within window
        j_max = 0
        running_max = -1.0
        running_min = 1e18
        # Reset per-i; cheap on 1440 points
        N = len(times_ms)
        for i in range(N):
            t0 = times_ms[i]
            p0 = prices[i]
            # Scan forward
            for j in range(i, N):
                if times_ms[j] - t0 > window_ms:
                    break
                pj = prices[j]
                up = (pj - p0) / p0 * 100.0
                dn = (p0 - pj) / p0 * 100.0
                if up > best_up:
                    best_up = up
                if dn > best_down:
                    best_down = dn
        return best_up, best_down

    horizons: dict[str, dict] = {}
    for label, window_ms in HORIZONS_MS.items():
        up, dn = max_forward_move_pct(window_ms)
        horizons[label] = {
            "max_up_pct": round(up, 3),
            "max_down_pct": round(dn, 3),
        }

    # Feasibility flags
    max_up_24h = horizons["24h"]["max_up_pct"]
    max_down_24h = horizons["24h"]["max_down_pct"]
    max_either_24h = max(max_up_24h, max_down_24h)
    feasibility: dict[str, bool] = {}
    for t in FEASIBILITY_TARGETS:
        feasibility[f"{t}pct"] = max_either_24h >= t

    abs_return = abs(day_return)
    if day_return >= 1.0:
        regime = "bullish"
    elif day_return <= -1.0:
        regime = "bearish"
    elif range_pct >= 4.0:
        regime = "high_vol"
    else:
        regime = "choppy"

    return {
        "date": date,
        "status": "ok",
        "trades_n": n,
        "first_price": first_price,
        "last_price": last_price,
        "intraday_high": hi,
        "intraday_low": lo,
        "day_return_pct": round(day_return, 3),
        "range_pct": round(range_pct, 3),
        "horizons": horizons,
        "feasibility": feasibility,
        "regime": regime,
    }


def main() -> int:
    if not DATA_ROOT.exists():
        print(f"{DATA_ROOT} does not exist")
        return 1
    dates = sorted(p.name for p in DATA_ROOT.iterdir() if p.is_dir())
    results = []
    for d in dates:
        print(f"analyzing {d} ...", file=sys.stderr, flush=True)
        r = analyze_date(d)
        results.append(r)

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "OKX_REGIME_TABLE.json").write_text(
        json.dumps({"dates": results}, indent=2), encoding="utf-8"
    )

    # Build MD
    md = [
        "# OKX BTC-USDT-SWAP — first-day regime + target-feasibility table",
        "",
        "**Venue:** OKX `okex-swap` BTC-USDT-SWAP (perpetual)",
        "**Source:** Tardis CDN free first-of-month samples (trades.csv.gz)",
        "**Computed from trades only** — no L2 reconstruction.",
        "",
        "Regime label:",
        "  - `bullish` if day_return >= +1.0 %",
        "  - `bearish` if day_return <= -1.0 %",
        "  - `high_vol` if range >= 4 % and |day_return| < 1 %",
        "  - `choppy` otherwise.",
        "",
        "Feasibility flags = whether the day's 24 h max forward move (up or down) was >= the listed target.",
        "",
        "| date       | regime  | day Δ %   | range % | 4h up | 4h dn | 8h up | 8h dn | 24h up | 24h dn | 0.5% | 1% | 1.5% | 2% | trades |",
        "|------------|---------|----------:|--------:|------:|------:|------:|------:|-------:|-------:|:----:|:--:|:----:|:--:|------:|",
    ]
    for r in results:
        if r.get("status") != "ok":
            md.append(f"| {r['date']} | (no trades file) |   |   |   |   |   |   |   |   |   |   |   |   |   |")
            continue
        h = r["horizons"]
        f = r["feasibility"]
        md.append(
            f"| {r['date']} | {r['regime']:<7s} | {r['day_return_pct']:+6.2f}   | "
            f"{r['range_pct']:6.2f} | {h['4h']['max_up_pct']:5.2f} | {h['4h']['max_down_pct']:5.2f} | "
            f"{h['8h']['max_up_pct']:5.2f} | {h['8h']['max_down_pct']:5.2f} | "
            f"{h['24h']['max_up_pct']:6.2f} | {h['24h']['max_down_pct']:6.2f} | "
            f"{'✓' if f['0.5pct'] else '·':^4s} | {'✓' if f['1.0pct'] else '·':^2s} | "
            f"{'✓' if f['1.5pct'] else '·':^4s} | {'✓' if f['2.0pct'] else '·':^2s} | "
            f"{r['trades_n']:>6,d} |"
        )
    md.append("")
    md.append("Companion JSON: `reports/OKX_REGIME_TABLE.json`.")
    (REPORTS / "OKX_REGIME_TABLE.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORTS/'OKX_REGIME_TABLE.json'}")
    print(f"wrote {REPORTS/'OKX_REGIME_TABLE.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
