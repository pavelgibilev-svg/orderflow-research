"""NEXT WINDOWS SCANNER — pick dates/pools to download next, from DAILY OHLCV.

Data-driven (no hand-picked dates). Classifies calendar windows into 7 regimes:
TREND_UP, TREND_DOWN, RANGE, HIGH_VOL, LOW_VOL, REVERSAL_SWEEP, BREAKOUT.

Input priority:
  1) --daily <csv> or env BTC_DAILY_CSV  (preferred: a full BTC 1d OHLCV history)
  2) fallback: build a sparse daily series from LOCAL trades archives under
     data/okx-historical/BTC-USDT-SWAP/<YYYY-MM-DD>/trades.csv.gz
If no daily CSV is supplied, an expected-schema template is written to data/daily/BTC_USDT_1d.SCHEMA.csv.

Outputs: reports/strategy-calibration/NEXT_WINDOWS_TO_DOWNLOAD.{md,json,csv}
Note: a freely downloadable Binance/OKX 1d klines CSV (NOT Tardis) is the recommended `--daily` input.
"""
from __future__ import annotations
import argparse, csv, gzip, json, os, statistics as st, sys, datetime as dt
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
SWAP = ROOT / "data/okx-historical/BTC-USDT-SWAP"
OUTDIR = ROOT / "reports/strategy-calibration"
DAILY_DEFAULT = ROOT / "data/daily/BTC_USDT_1d.csv"
SCHEMA = ROOT / "data/daily/BTC_USDT_1d.SCHEMA.csv"


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def d2(s): y, m, dd = s.split("-"); return dt.date(int(y), int(m), int(dd))


def write_schema():
    SCHEMA.parent.mkdir(parents=True, exist_ok=True)
    with SCHEMA.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        w.writerow(["2026-01-01", "92000", "94000", "91000", "93500", "12345.6"])
        w.writerow(["# one row per UTC day; date=YYYY-MM-DD; prices in USD; volume in BTC (optional)"])
    return SCHEMA


def load_daily_csv(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            try:
                if not r.get("date") or str(r["date"]).startswith("#"): continue
                rows.append({"date": r["date"][:10], "open": float(r["open"]), "high": float(r["high"]),
                             "low": float(r["low"]), "close": float(r["close"]),
                             "volume": float(r.get("volume") or 0)})
            except (ValueError, KeyError, TypeError):
                continue
    rows.sort(key=lambda x: x["date"])
    return rows


def build_daily_from_trades():
    rows = []
    if not SWAP.exists(): return rows
    for d in sorted(p.name for p in SWAP.iterdir() if p.is_dir() and len(p.name) == 10 and p.name[4] == "-"):
        f = SWAP / d / "trades.csv.gz"
        if not f.exists(): continue
        o = h = l = c = None; vol = 0.0
        try:
            with gzip.open(f, "rt") as fh:
                rd = csv.reader(fh); next(rd, None)
                for row in rd:
                    try: px = float(row[6]); am = float(row[7])
                    except (IndexError, ValueError): continue
                    if o is None: o = h = l = px
                    h = max(h, px); l = min(l, px); c = px; vol += am
        except OSError:
            continue
        if o is not None:
            rows.append({"date": d, "open": o, "high": h, "low": l, "close": c, "volume": round(vol, 2)})
    return rows


def enrich(rows):
    """add net%, range%, rolling 3d/7d returns (only within contiguous runs), prior-week range."""
    by = {r["date"]: r for r in rows}
    for r in rows:
        r["net_pct"] = round(100 * (r["close"] - r["open"]) / r["open"], 2)
        r["range_pct"] = round(100 * (r["high"] - r["low"]) / r["open"], 2)
        r["upper_wick_pct"] = round(100 * (r["high"] - max(r["open"], r["close"])) / r["open"], 2)
        r["lower_wick_pct"] = round(100 * (min(r["open"], r["close"]) - r["low"]) / r["open"], 2)
    for i, r in enumerate(rows):
        def back(n):
            dprev = (d2(r["date"]) - dt.timedelta(days=n)).isoformat()
            return by.get(dprev)
        for n in (3, 7, 14):
            p = back(n)
            r[f"ret_{n}d"] = (round(100 * (r["close"] - p["close"]) / p["close"], 2) if p else None)
        # prior 7d high/low (contiguous)
        prior = [by[(d2(r["date"]) - dt.timedelta(days=k)).isoformat()] for k in range(1, 8) if (d2(r["date"]) - dt.timedelta(days=k)).isoformat() in by]
        if len(prior) >= 5:
            r["prior7_high"] = max(p["high"] for p in prior); r["prior7_low"] = min(p["low"] for p in prior)
            r["prior7_med_range"] = round(st.median([p["range_pct"] for p in prior]), 2)
        else:
            r["prior7_high"] = r["prior7_low"] = r["prior7_med_range"] = None
    return rows


def classify_day(r):
    """return list of (regime, score, reason) tags for a single day given enriched fields."""
    tags = []
    r3, r7 = r.get("ret_3d"), r.get("ret_7d")
    rng, net = r["range_pct"], r["net_pct"]
    # TREND_UP
    if (r3 is not None and r3 > 3) or (r7 is not None and r7 > 5):
        tags.append(("TREND_UP", round((r3 or 0) + (r7 or 0) / 2 + rng, 2), f"3d {r3}% / 7d {r7}%"))
    # TREND_DOWN
    if (r3 is not None and r3 < -3) or (r7 is not None and r7 < -5):
        tags.append(("TREND_DOWN", round(-((r3 or 0) + (r7 or 0) / 2) + rng, 2), f"3d {r3}% / 7d {r7}%"))
    # RANGE (choppy but wide intraday, flat over week)
    if (r7 is not None and abs(r7) < 2 and rng >= 3):
        tags.append(("RANGE", round(rng - abs(r7), 2), f"7d {r7}% flat, intraday range {rng}%"))
    # HIGH_VOL
    if r.get("prior7_med_range") and rng > 3 and rng > 1.3 * r["prior7_med_range"]:
        tags.append(("HIGH_VOL", round(rng + (rng - r["prior7_med_range"]), 2), f"range {rng}% vs prior med {r['prior7_med_range']}%"))
    # LOW_VOL
    if rng < 1.7:
        tags.append(("LOW_VOL", round(-rng, 2), f"range only {rng}%"))
    # REVERSAL / SWEEP (large wick, close back inside, net not extreme)
    big_wick = max(r["upper_wick_pct"], r["lower_wick_pct"])
    if big_wick >= 1.5 and abs(net) < big_wick and rng >= 2.5:
        tags.append(("REVERSAL_SWEEP", round(big_wick + rng - abs(net), 2), f"wick {big_wick}% vs net {net}%"))
    # BREAKOUT (close outside prior 7d range after compression)
    if r.get("prior7_high") and r.get("prior7_med_range") is not None:
        if (r["close"] > r["prior7_high"] or r["close"] < r["prior7_low"]) and r["prior7_med_range"] < 3:
            tags.append(("BREAKOUT", round(abs(net) + (3 - r["prior7_med_range"]), 2), f"close breaks prior7 range after compression ({r['prior7_med_range']}%)"))
    return tags


def venue_for(date):
    # OKX+Binance L2 overlap window we have locally is 2026-05-21..30; recommend both there.
    if "2026-05-21" <= date <= "2026-05-30": return "both (OKX L2+trades AND Binance recorder — cross-venue overlap)"
    return "OKX L2+trades (download; add Binance recorder if you also want cross-venue)"


def make_windows(rows, tagged):
    """group consecutive same-regime days into windows."""
    windows = []
    for regime in ("TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOL", "LOW_VOL", "REVERSAL_SWEEP", "BREAKOUT"):
        days = sorted([(r["date"], sc, rs, r) for r in rows for (rg, sc, rs) in tagged.get(r["date"], []) if rg == regime])
        if not days: continue
        cur = []
        prev = None
        for dd, sc, rs, r in days:
            if prev is not None and (d2(dd) - d2(prev)).days > 2:
                windows.append((regime, cur)); cur = []
            cur.append((dd, sc, rs, r)); prev = dd
        if cur: windows.append((regime, cur))
    out = []
    for regime, grp in windows:
        ds = [g[0] for g in grp]; rs_all = [g[3] for g in grp]
        nets = [r["net_pct"] for r in rs_all]; ranges = [r["range_pct"] for r in rs_all]
        score = round(st.mean([g[1] for g in grp]) + len(grp) * 0.5, 2)
        out.append({"regime": regime, "start_date": ds[0], "end_date": ds[-1], "days": len(ds),
                    "score": score, "net_pct_sum": round(sum(nets), 2), "net_pct_span": round(rs_all[-1]["close"] / rs_all[0]["open"] * 100 - 100, 2),
                    "median_daily_range_pct": round(st.median(ranges), 2), "max_daily_range_pct": max(ranges),
                    "reason": grp[0][2], "venue_data_needed": venue_for(ds[0]),
                    "have_locally": all((SWAP / d / "trades.csv.gz").exists() for d in ds),
                    "research_purpose": {
                        "TREND_UP": "calibrate trend-continuation longs / TU module (missing in 05-03..20)",
                        "TREND_DOWN": "validate TD-short module out-of-sample",
                        "RANGE": "range-fade edge+reclaim positives (already have May; need variety)",
                        "HIGH_VOL": "stress strong-move separation; most 2%+ opportunities",
                        "LOW_VOL": "no-trade / false-positive control set",
                        "REVERSAL_SWEEP": "sweep-reversal + false-breakout reclaim setups",
                        "BREAKOUT": "breakout-continuation / retest setups"}[regime]})
    out.sort(key=lambda w: (-w["score"]))
    return out


def monthly_view(rows):
    """month-level regime from first-of-month snapshots (handles sparse 2024-2026 history)."""
    firsts = [r for r in rows if r["date"].endswith("-01")]
    firsts.sort(key=lambda r: r["date"])
    mv = []
    for i in range(1, len(firsts)):
        a, b = firsts[i - 1], firsts[i]
        ret = round(100 * (b["close"] - a["close"]) / a["close"], 2)
        reg = "TREND_UP" if ret > 6 else "TREND_DOWN" if ret < -6 else "RANGE"
        mv.append({"month_start": a["date"], "month_end": b["date"], "mom_return_pct": ret, "month_regime": reg})
    return mv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", default=os.environ.get("BTC_DAILY_CSV", str(DAILY_DEFAULT)))
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    src = Path(args.daily)
    provenance = ""
    if src.exists():
        rows = load_daily_csv(src); provenance = f"daily CSV: {src}"
    else:
        write_schema()
        rows = build_daily_from_trades()
        provenance = (f"NO daily CSV at {src} -> wrote schema template {SCHEMA} and built a SPARSE daily series "
                      f"from local trades ({len(rows)} days; mostly first-of-month snapshots + contiguous 2026-03 & 2026-05).")
    if not rows:
        (OUTDIR / "NEXT_WINDOWS_TO_DOWNLOAD.md").write_text("# NEXT WINDOWS\n\nNo daily data available. Provide a BTC 1d OHLCV CSV via --daily.\n", encoding="utf-8")
        print("no daily data"); return 0
    rows = enrich(rows)
    tagged = {r["date"]: classify_day(r) for r in rows}
    windows = make_windows(rows, tagged)
    mv = monthly_view(rows)

    per_regime_top5 = {}
    for regime in ("TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOL", "LOW_VOL", "REVERSAL_SWEEP", "BREAKOUT"):
        per_regime_top5[regime] = [w for w in windows if w["regime"] == regime][:5]
    top20 = windows[:20]

    min_reqs = {
        "per_window": "OKX L2 (book deltas + 3h/full-day snapshots) + trades.csv.gz for each UTC day in the window",
        "cross_venue": "for OKX+Binance comparison also capture Binance recorder L2 for the same UTC days (only overlap we have is 2026-05-21..30)",
        "minimum_window_length": ">=5 contiguous days per regime so 3d/7d context and >=3-5 unique strong moves can form",
        "no_tardis": "use OKX-open / Binance-recorder captures only; Tardis excluded by policy",
    }
    payload = {"build": now_iso(), "provenance": provenance, "n_daily_rows": len(rows),
               "monthly_view": mv, "top20_windows": top20, "top5_per_regime": per_regime_top5,
               "minimum_data_requirements": min_reqs,
               "flags": {"NEXT_WINDOWS_SCANNER_DONE": "YES", "NEXT_WINDOWS_TO_DOWNLOAD_READY": "YES" if windows else "NO",
                         "DAILY_CSV_PROVIDED": "YES" if src.exists() else "NO (sparse local fallback used)", "TARDIS_USED": "NO"}}
    (OUTDIR / "NEXT_WINDOWS_TO_DOWNLOAD.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    with (OUTDIR / "NEXT_WINDOWS_TO_DOWNLOAD.csv").open("w", encoding="utf-8", newline="") as fh:
        cols = ["regime", "start_date", "end_date", "days", "score", "net_pct_span", "median_daily_range_pct", "max_daily_range_pct", "have_locally", "venue_data_needed", "research_purpose", "reason"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for win in windows: w.writerow(win)
    md = ["# NEXT WINDOWS TO DOWNLOAD (data-driven from daily OHLCV)", "", f"**Build:** {now_iso()}", f"Provenance: {provenance}", "",
          "## Top 20 windows overall", "| # | regime | start | end | days | score | net% span | med range% | have? | venue |", "|--:|---|---|---|--:|--:|--:|--:|:--:|---|"]
    for i, w in enumerate(top20, 1):
        md.append(f"| {i} | {w['regime']} | {w['start_date']} | {w['end_date']} | {w['days']} | {w['score']} | {w['net_pct_span']} | {w['median_daily_range_pct']} | {'yes' if w['have_locally'] else 'NO'} | {w['venue_data_needed'].split(' (')[0]} |")
    md += ["", "## Top 5 per regime"]
    for regime, ws in per_regime_top5.items():
        md.append(f"### {regime}")
        if not ws: md.append("- (none found in available daily data)"); continue
        for w in ws: md.append(f"- {w['start_date']}..{w['end_date']} ({w['days']}d) score {w['score']} · net {w['net_pct_span']}% · medRange {w['median_daily_range_pct']}% · {w['research_purpose']} · {'HAVE' if w['have_locally'] else 'DOWNLOAD'}")
    md += ["", "## Month-level regime (from first-of-month snapshots, for picking months to fully download)", "| month start | month end | MoM ret% | regime |", "|---|---|--:|---|"]
    for m in mv: md.append(f"| {m['month_start']} | {m['month_end']} | {m['mom_return_pct']} | {m['month_regime']} |")
    md += ["", "## Minimum data requirements"] + [f"- **{k}**: {v}" for k, v in min_reqs.items()]
    (OUTDIR / "NEXT_WINDOWS_TO_DOWNLOAD.md").write_text("\n".join(md), encoding="utf-8")

    print(provenance)
    print(f"daily rows {len(rows)} | windows {len(windows)}")
    print("top 10 windows:")
    for w in windows[:10]:
        print(f"  {w['regime']:<14} {w['start_date']}..{w['end_date']} {w['days']}d score {w['score']} netspan {w['net_pct_span']}% medRange {w['median_daily_range_pct']}% have={w['have_locally']}")
    print("regimes with NO window:", [rg for rg, ws in per_regime_top5.items() if not ws])
    print("monthly view (last 8):")
    for m in mv[-8:]: print(f"  {m['month_start']}->{m['month_end']} {m['mom_return_pct']:>7}% {m['month_regime']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
