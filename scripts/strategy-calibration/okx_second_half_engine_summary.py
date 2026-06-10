"""Engine-level summary across OKX direct second-half March (15 days).

Reads from reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_*.json and assembles
per-day engine metrics + totals.

NO new backtest, NO engine change. Read-only.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REP_OKX = ROOT / "reports/okx-direct"
REP_OUT = ROOT / "reports/strategy-calibration"
REP_OUT.mkdir(parents=True, exist_ok=True)

OKX_DATES = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]


def _ds(d: str) -> dict:
    p = REP_OKX / f"OKX_DIRECT_TECHNICAL_REPLAY_{d}.json"
    if not p.exists():
        return None
    w = json.loads(p.read_text(encoding="utf-8"))
    return (w.get("underlying_backtest_summary") or {}).get("daily_summary") or {}


def main() -> int:
    per_day = []
    totals = defaultdict(int)
    mute_days = []
    days_with_2pct_potential = []
    for d in OKX_DATES:
        ds = _ds(d)
        if ds is None:
            per_day.append({"date": d, "missing": True})
            continue
        row = {
            "date": d,
            "zones": ds.get("zones_total", 0),
            "triggered": ds.get("zones_triggered", 0),
            "reached_raw": ds.get("reached_zones_raw", 0),
            "primary_unique_reached": ds.get("unique_reached_moves", 0),
            "duplicate_move_credits": ds.get("duplicate_move_credits", 0),
            "failed_triggered": ds.get("status_RESOLVED_FAILED", 0),
            "no_trigger": ds.get("status_NO_TRIGGER", 0),
            "invalidated": ds.get("status_INVALIDATED", 0),
            "expired": ds.get("status_EXPIRED", 0),
            "LONG": ds.get("direction_LONG", 0),
            "SHORT": ds.get("direction_SHORT", 0),
            "raw_hit_pct": round(100.0 * (ds.get("raw_triggered_hit_rate") or 0), 2),
            "unique_hit_pct": round(100.0 * (ds.get("unique_move_adjusted_hit_rate") or 0), 2),
            "dedup_supp": ds.get("duplicate_suppression_count", 0),
        }
        per_day.append(row)
        for k in ("zones", "triggered", "reached_raw", "primary_unique_reached",
                   "duplicate_move_credits", "failed_triggered", "no_trigger",
                   "invalidated", "expired", "LONG", "SHORT", "dedup_supp"):
            totals[k] += row[k]
        if row["reached_raw"] == 0:
            mute_days.append(d)
        else:
            days_with_2pct_potential.append(d)

    n_days = sum(1 for r in per_day if not r.get("missing"))
    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct second-half March engine-level summary",
        "dates_processed": [r["date"] for r in per_day if not r.get("missing")],
        "missing_dates": [r["date"] for r in per_day if r.get("missing")] + ["2026-03-17 (no source data)"],
        "n_days_processed": n_days,
        "per_day": per_day,
        "totals": {**totals,
                    "unique_per_day": round((totals["primary_unique_reached"] or 0) / max(n_days, 1), 3),
                    "triggered_per_day": round((totals["triggered"] or 0) / max(n_days, 1), 2)},
        "mute_days": mute_days,
        "days_with_reached_raw": days_with_2pct_potential,
    }
    (REP_OUT / "OKX_SECOND_HALF_ENGINE_SUMMARY.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")

    keys = list(per_day[0].keys()) if per_day else []
    with (REP_OUT / "OKX_SECOND_HALF_ENGINE_SUMMARY.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in per_day:
            if not r.get("missing"):
                w.writerow(r)

    md = [
        "# OKX direct SECOND HALF March 2026 - Engine-level summary (15 days)",
        "",
        f"**Build:** {out['build_time_utc']}",
        f"**Days processed:** {n_days}/15 (2026-03-16, 03-18..03-31)",
        f"**Missing:** 2026-03-17 (not in source archive)",
        "",
        "## Per-day metrics",
        "",
        "| date | zones | trig | reached | primary | dup | failed | no_trig | invalid | LONG | SHORT | raw_hit % | unique_hit % | dedup |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in per_day:
        if r.get("missing"):
            md.append(f"| {r['date']} | — | — | — | — | — | — | — | — | — | — | — | — | — |")
            continue
        md.append(f"| {r['date']} | {r['zones']} | {r['triggered']} | {r['reached_raw']} | "
                  f"{r['primary_unique_reached']} | {r['duplicate_move_credits']} | "
                  f"{r['failed_triggered']} | {r['no_trigger']} | {r['invalidated']} | "
                  f"{r['LONG']} | {r['SHORT']} | {r['raw_hit_pct']} | "
                  f"{r['unique_hit_pct']} | {r['dedup_supp']} |")
    md.extend([
        "",
        "## Totals",
        "",
        f"- zones: **{totals['zones']}**",
        f"- triggered: **{totals['triggered']}**  (~{round(totals['triggered']/max(n_days,1), 1)}/day)",
        f"- reached_raw: **{totals['reached_raw']}**",
        f"- primary unique reached moves: **{totals['primary_unique_reached']}**  (~{round(totals['primary_unique_reached']/max(n_days,1), 2)}/day)",
        f"- duplicate move credits: **{totals['duplicate_move_credits']}**",
        f"- failed triggered: **{totals['failed_triggered']}**",
        f"- LONG / SHORT (all classes): **{totals['LONG']} / {totals['SHORT']}**",
        f"- mute days (0 reached): **{len(mute_days)}** ({mute_days})",
        f"- days with reached_raw ≥ 1: **{len(days_with_2pct_potential)}**",
    ])
    (REP_OUT / "OKX_SECOND_HALF_ENGINE_SUMMARY.md").write_text("\n".join(md), encoding="utf-8")

    print(f"engine summary: {n_days} days, {totals['primary_unique_reached']} primaries, {totals['reached_raw']} reached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
