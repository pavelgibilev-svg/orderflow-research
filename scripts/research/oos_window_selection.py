"""OOS WINDOW SELECTION for frozen March filters (section D + E).

Data-driven: reads the NEXT_WINDOWS scanner output (monthly regime view from first-of-month snapshots +
day-level windows from local trades) and proposes non-March OOS windows per regime, preferring different
months/years. Writes OOS_WINDOWS_TO_DOWNLOAD_BY_REGIME.{csv,md} + FROZEN_FILTER_VALIDATION_PLAN.md.
RESEARCH ONLY. Do not tune frozen filters on these windows.
"""
from __future__ import annotations
import csv, json, sys, datetime as dt
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
SCAN = ROOT / "reports/strategy-calibration/NEXT_WINDOWS_TO_DOWNLOAD.json"
SWAP = ROOT / "data/okx-historical/BTC-USDT-SWAP"
OUT = ROOT / "reports/filter-calibration"


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def have_local(date10): return (SWAP / date10 / "trades.csv.gz").exists()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scan = json.loads(SCAN.read_text())
    mv = scan["monthly_view"]; windows = scan.get("top20_windows", [])

    rows = []
    # --- trend regimes from monthly view (true non-March OOS) ---
    def trend_months(sign, want):
        cands = [m for m in mv if (m["mom_return_pct"] >= 7 if sign > 0 else m["mom_return_pct"] <= -7)
                 and not m["month_start"].startswith("2026-03")]
        cands.sort(key=lambda m: -abs(m["mom_return_pct"]))
        # prefer year diversity
        seen_years = set(); picked = []
        for m in cands:
            yr = m["month_start"][:4]
            picked.append(m)
            seen_years.add(yr)
            if len(picked) >= want: break
        return picked
    for reg, sign in (("TREND_UP", 1), ("TREND_DOWN", -1)):
        for m in trend_months(sign, 3):
            ms = m["month_start"]
            rows.append({"regime": reg, "start_date": ms, "end_date": _plus(ms, 9), "span_net_pct_month": m["mom_return_pct"],
                         "median_daily_range_pct": "download_to_measure", "max_daily_range_pct": "download_to_measure",
                         "why_selected": f"month {ms[:7]} MoM {m['mom_return_pct']}% = strong {reg}", "tests_pattern": ("TU-long / trend-continuation" if sign > 0 else "TD-short / trend-continuation"),
                         "local": "NO", "files_to_download": f"OKX BTC-USDT-SWAP L2+trades for {ms[:7]} (>=5-10 contiguous UTC days); then re-scan daily to pick exact window", "priority": "HIGH" if abs(m["mom_return_pct"]) >= 13 else "MED"})
    # --- range/highvol/lowvol/breakout/sweep: prefer local non-March (May) as secondary sanity + a RANGE month to download ---
    def local_day_windows(reg):
        return [w for w in windows if w["regime"] == reg and not w["start_date"].startswith("2026-03") and w.get("have_locally")]
    for reg in ("RANGE", "HIGH_VOL", "LOW_VOL", "BREAKOUT", "REVERSAL_SWEEP"):
        ws = local_day_windows(reg)[:2]
        for w in ws:
            rows.append({"regime": reg, "start_date": w["start_date"], "end_date": w["end_date"], "span_net_pct_month": w["net_pct_span"],
                         "median_daily_range_pct": w["median_daily_range_pct"], "max_daily_range_pct": w["max_daily_range_pct"],
                         "why_selected": f"local non-March {reg} window (secondary sanity, May)", "tests_pattern": w["research_purpose"],
                         "local": "YES (May 2026 — secondary sanity only, overlaps mining month)", "files_to_download": "none (already local)", "priority": "LOW"})
        # one fresh download target: a RANGE month from monthly view
        if reg == "RANGE":
            rm = [m for m in mv if m["month_regime"] == "RANGE" and not m["month_start"].startswith("2026-03")]
            for m in rm[:2]:
                ms = m["month_start"]
                rows.append({"regime": reg, "start_date": ms, "end_date": _plus(ms, 9), "span_net_pct_month": m["mom_return_pct"],
                             "median_daily_range_pct": "download_to_measure", "max_daily_range_pct": "download_to_measure",
                             "why_selected": f"month {ms[:7]} flat MoM {m['mom_return_pct']}% = RANGE OOS (fresh)", "tests_pattern": "range-fade / accumulation-distribution",
                             "local": "NO", "files_to_download": f"OKX L2+trades for {ms[:7]} (>=7 days)", "priority": "MED"})

    # write CSV + MD
    cols = ["regime", "start_date", "end_date", "span_net_pct_month", "median_daily_range_pct", "max_daily_range_pct", "why_selected", "tests_pattern", "local", "priority", "files_to_download"]
    with (OUT / "OOS_WINDOWS_TO_DOWNLOAD_BY_REGIME.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in rows: w.writerow(r)
    md = ["# OOS WINDOWS TO DOWNLOAD — BY REGIME (for frozen March filters)", "", f"Build {now_iso()} · RESEARCH ONLY · do not tune filters on these.", "",
          "Trend windows are true non-March OOS chosen from monthly first-of-month returns; range/vol/sweep use local",
          "May windows for *secondary* sanity (they overlap the mining month) plus a fresh RANGE month to download.", "",
          "| regime | start | end | month net% | medRange% | why | local | prio |", "|---|---|---|--:|--:|---|:--:|:--:|"]
    for r in rows:
        md.append(f"| {r['regime']} | {r['start_date']} | {r['end_date']} | {r['span_net_pct_month']} | {r['median_daily_range_pct']} | {r['why_selected']} | {r['local'].split(' ')[0]} | {r['priority']} |")
    md += ["", "## Download priority (true OOS first)",
           "1. **TREND_DOWN**: " + ", ".join(sorted({r['start_date'][:7] for r in rows if r['regime'] == 'TREND_DOWN' and r['local'] == 'NO'})),
           "2. **TREND_UP**: " + ", ".join(sorted({r['start_date'][:7] for r in rows if r['regime'] == 'TREND_UP' and r['local'] == 'NO'})),
           "3. **RANGE (fresh)**: " + ", ".join(sorted({r['start_date'][:7] for r in rows if r['regime'] == 'RANGE' and r['local'] == 'NO'})),
           "4. HIGH_VOL/SWEEP/LOW_VOL: validate on local May first; download a dedicated month only if filters survive trend OOS.", "",
           "## Minimum data per window", "- OKX L2 (book deltas + snapshots) + trades.csv.gz for each UTC day, >=5 contiguous days.",
           "- For cross-venue: add Binance recorder L2 same days (only local overlap is 2026-05-21..30).", "- No Tardis."]
    (OUT / "OOS_WINDOWS_TO_DOWNLOAD_BY_REGIME.md").write_text("\n".join(md), encoding="utf-8")

    plan = ["# FROZEN FILTER VALIDATION PLAN", "", f"Build {now_iso()} · RESEARCH ONLY — no production, no Telegram.", "",
            "## Protocol",
            "1. **March 2026 = calibration only.** Thresholds frozen in FROZEN_FILTER_SET_MARCH_V1.json. Do NOT change after seeing OOS.",
            "2. **May 2026 existing artifacts = sanity-check, not proof** (overlaps the mining month; treat as in-sample-ish).",
            "3. **Non-March windows = true OOS** (download per OOS_WINDOWS_TO_DOWNLOAD_BY_REGIME).",
            "4. Apply each frozen filter **as-is**; one trade per unique move cluster; TP=2%; 2.5/3% labels only; decisions <= confirmedTs.",
            "5. Per regime report: signals, hit2 rate, W/L/TO, PF, expectancy, coverage (active days), date stability, survive/die.",
            "6. **If a filter fails OOS -> mark DEAD, do not tune it.**",
            "7. **If a filter survives OOS -> mark SHADOW_CANDIDATE (not production).**", "",
            "## Survive / die thresholds (declare before running OOS)",
            "- SURVIVE: winrate within ~10 pts of March AND PF>=1.0 AND n>=8 AND date_stability>=0.5 across >=2 OOS windows.",
            "- DEAD: winrate drops >15 pts OR PF<0.9 OR n<4 OR signals concentrate on a single day.",
            "- INCONCLUSIVE: n in [4,8) -> keep frozen, gather more OOS, no verdict.", "",
            "## Order of validation",
            "1. **F1_TD_SHORT** first — only filter with a prior robust signal; validate on TREND_DOWN OOS months.",
            "2. **F2_SWEEP_REVERSAL** + **F5_SIXBLOCK_4of6** on HIGH_VOL / mixed OOS.",
            "3. **F3_ACCUMULATION / F4_DISTRIBUTION** on RANGE OOS month.", "",
            "## What to ignore",
            "- Any March winrate >70% at n<6 — overfit, not evidence.",
            "- L2-dependent sub-features absent on March (book_entropy, thin-path, top-depth) until a full-schema cache is rebuilt.",
            "- Single-day spikes; only cross-date stable behaviour counts."]
    (OUT / "FROZEN_FILTER_VALIDATION_PLAN.md").write_text("\n".join(plan), encoding="utf-8")

    print(f"OOS rows {len(rows)}")
    for r in rows: print(f"  {r['regime']:<14} {r['start_date']}..{r['end_date']} net {r['span_net_pct_month']} local={r['local'].split(' ')[0]} prio {r['priority']}")
    return 0


def _plus(date10, days):
    return (dt.date.fromisoformat(date10) + dt.timedelta(days=days)).isoformat()


if __name__ == "__main__":
    sys.exit(main())
