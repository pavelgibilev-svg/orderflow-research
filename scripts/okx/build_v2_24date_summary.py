"""Build the combined 24-date OKX full-day summary across three rounds:
  - 6 calibration dates (v1 weight derivation)
  - 6 OOS dates (v1 OOS test)
  - 12 v2 candidate dates (this round)
  -> 24 dates total

For each date pulls metrics from the per-date OKX_*_TECHNICAL_REPLAY_<date>_fullday.json
(joined with the underlying daily_summary.csv and zones.json for per-direction
reach counts), labels the round, and produces:

  reports/OKX_V2_FULLDAY_12_DATE_REPLAY_SUMMARY.md   (v2-only section + per-date table)
  reports/OKX_V2_FULLDAY_12_DATE_REPLAY_SUMMARY.json (v2 + 24-date aggregated rows)
  reports/OKX_V2_FULLDAY_12_DATE_REPLAY_SUMMARY.csv  (flat 24-row table)

NO strategy/threshold/score change. NO zone filtering. NO use of v1.
NO winrate claim. Unique moves are the headline metric.
"""
from __future__ import annotations
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
OKX_ROOT = ROOT / "data" / "okx-historical" / "BTC-USDT-SWAP"

CALIB = [
    "2024-01-01", "2025-10-01", "2025-12-01",
    "2024-10-01", "2024-07-01", "2026-04-01",
]
OOS_V1 = [
    "2025-04-01", "2025-05-01", "2024-05-01",
    "2024-09-01", "2024-06-01", "2025-11-01",
]


def load_v2_dates() -> list[str]:
    p = REPORTS / "OKX_SCORE_V2_CANDIDATE_DATES.json"
    if not p.exists():
        return []
    return [c["date"] for c in json.loads(p.read_text(encoding="utf-8"))["chosen"]]


def round_for(date: str, v2_dates: list[str]) -> str:
    if date in CALIB:
        return "calibration"
    if date in OOS_V1:
        return "oos_v1"
    if date in v2_dates:
        return "v2"
    return "unknown"


def fullday_json_for(date: str, round_label: str) -> Path:
    if round_label == "calibration":
        return REPORTS / f"OKX_TECHNICAL_REPLAY_{date}_fullday.json"
    if round_label == "oos_v1":
        return REPORTS / f"OKX_OOS_TECHNICAL_REPLAY_{date}_fullday.json"
    if round_label == "v2":
        return REPORTS / f"OKX_V2_TECHNICAL_REPLAY_{date}_fullday.json"
    return REPORTS / f"OKX_TECHNICAL_REPLAY_{date}_fullday.json"


def fullday_zones_csv_for(date: str, round_label: str) -> Path:
    if round_label == "calibration":
        return REPORTS / f"OKX_TECHNICAL_REPLAY_{date}_fullday_ZONES.csv"
    if round_label == "oos_v1":
        return REPORTS / f"OKX_OOS_TECHNICAL_REPLAY_{date}_fullday_ZONES.csv"
    if round_label == "v2":
        return REPORTS / f"OKX_V2_TECHNICAL_REPLAY_{date}_fullday_ZONES.csv"
    return REPORTS / f"OKX_TECHNICAL_REPLAY_{date}_fullday_ZONES.csv"


def parse_pct(s: str) -> float | None:
    try:
        return float(s)
    except Exception:
        return None


def load_regime_row(date: str) -> dict:
    p = REPORTS / "OKX_REGIME_TABLE.json"
    if not p.exists():
        return {}
    rt = json.loads(p.read_text(encoding="utf-8"))
    for r in rt.get("dates", []):
        if r.get("date") == date:
            return r
    return {}


def metrics_for(date: str, round_label: str) -> dict[str, Any]:
    """Extract headline metrics for a single date from its full-day output."""
    out: dict[str, Any] = {
        "date": date,
        "round": round_label,
        "json_present": False,
        "underlying_dir_present": False,
    }
    j_path = fullday_json_for(date, round_label)
    if not j_path.exists():
        return out
    out["json_present"] = True
    outer = json.loads(j_path.read_text(encoding="utf-8"))
    inner = outer.get("underlying_backtest_summary") or {}
    ds = inner.get("daily_summary") or {}
    zones = inner.get("zones") or []
    out["fullday_runtime_seconds"] = round((outer.get("underlying_backtest_duration_ms") or 0) / 1000.0, 1)
    out["zones_total"] = int(ds.get("zones_total", len(zones)))
    out["zones_triggered"] = int(ds.get("zones_triggered", 0))
    out["zones_reached_raw"] = int(ds.get("zones_reached", 0))
    out["unique_reached_moves"] = int(ds.get("unique_reached_moves", 0))
    out["duplicate_move_credits"] = int(ds.get("duplicate_move_credits", 0))
    out["raw_triggered_hit_rate"] = ds.get("raw_triggered_hit_rate", 0.0)
    out["unique_move_adjusted_hit_rate"] = ds.get("unique_move_adjusted_hit_rate", 0.0)
    out["direction_LONG"] = int(ds.get("direction_LONG", 0))
    out["direction_SHORT"] = int(ds.get("direction_SHORT", 0))
    out["duplicate_suppression_count"] = int(ds.get("duplicate_suppression_count", 0))
    out["status_RESOLVED_REACHED"] = int(ds.get("status_RESOLVED_REACHED", 0))
    out["status_RESOLVED_FAILED"] = int(ds.get("status_RESOLVED_FAILED", 0))
    out["status_INVALIDATED"] = int(ds.get("status_INVALIDATED", 0))
    out["status_NO_TRIGGER"] = int(ds.get("status_NO_TRIGGER", 0))
    out["status_EXPIRED"] = int(ds.get("status_EXPIRED", 0))

    # LONG/SHORT reached split from zone list
    long_reached = sum(
        1 for z in zones
        if (z.get("status") or "").upper() == "RESOLVED_REACHED" and (z.get("direction") or "").upper() == "LONG"
    )
    short_reached = sum(
        1 for z in zones
        if (z.get("status") or "").upper() == "RESOLVED_REACHED" and (z.get("direction") or "").upper() == "SHORT"
    )
    out["long_reached"] = long_reached
    out["short_reached"] = short_reached

    # Quality flags summary
    qf_summary: dict[str, int] = {}
    for z in zones:
        for f in z.get("qualityFlags") or []:
            qf_summary[f] = qf_summary.get(f, 0) + 1
    out["quality_flags_summary"] = qf_summary

    # L2 row count + trades row count (lightweight: pull from
    # OKX_FIRST_DAY_REGIME_AND_REPLAY_SUMMARY.json if it covers this date, or
    # leave as None; the chain log has wall clock).
    out["l2_rows"] = None
    out["trades_rows"] = None

    # Regime context
    rg = load_regime_row(date)
    out["regime"] = rg.get("regime")
    out["day_return_pct"] = rg.get("day_return_pct")
    out["range_pct"] = rg.get("range_pct")
    out["feasibility_2pct"] = (rg.get("feasibility") or {}).get("2.0pct")
    out["feasibility_1pct"] = (rg.get("feasibility") or {}).get("1.0pct")
    out["trades_n_regime"] = rg.get("trades_n")
    return out


def aggregate(rows: list[dict]) -> dict[str, Any]:
    return {
        "n_dates": len(rows),
        "zones_total": sum(r.get("zones_total", 0) for r in rows),
        "zones_triggered": sum(r.get("zones_triggered", 0) for r in rows),
        "zones_reached_raw": sum(r.get("zones_reached_raw", 0) for r in rows),
        "unique_reached_moves": sum(r.get("unique_reached_moves", 0) for r in rows),
        "duplicate_move_credits": sum(r.get("duplicate_move_credits", 0) for r in rows),
        "long_reached": sum(r.get("long_reached", 0) for r in rows),
        "short_reached": sum(r.get("short_reached", 0) for r in rows),
        "duplicate_suppression_count": sum(r.get("duplicate_suppression_count", 0) for r in rows),
        "status_RESOLVED_FAILED": sum(r.get("status_RESOLVED_FAILED", 0) for r in rows),
        "status_INVALIDATED": sum(r.get("status_INVALIDATED", 0) for r in rows),
        "status_NO_TRIGGER": sum(r.get("status_NO_TRIGGER", 0) for r in rows),
        "status_EXPIRED": sum(r.get("status_EXPIRED", 0) for r in rows),
        "wall_clock_seconds": sum(r.get("fullday_runtime_seconds") or 0.0 for r in rows),
    }


def main() -> int:
    v2_dates = load_v2_dates()
    all_dates = CALIB + OOS_V1 + v2_dates
    rows = [metrics_for(d, round_for(d, v2_dates)) for d in all_dates]

    by_round: dict[str, list[dict]] = {"calibration": [], "oos_v1": [], "v2": []}
    for r in rows:
        if r["round"] in by_round and r["json_present"]:
            by_round[r["round"]].append(r)
    aggregates = {
        "calibration": aggregate(by_round["calibration"]),
        "oos_v1": aggregate(by_round["oos_v1"]),
        "v2": aggregate(by_round["v2"]),
        "all_24": aggregate(by_round["calibration"] + by_round["oos_v1"] + by_round["v2"]),
    }

    # ---- v2 dates: missing chain entries flagged ----
    v2_completed = sum(1 for r in rows if r["round"] == "v2" and r["json_present"])
    v2_missing = [r["date"] for r in rows if r["round"] == "v2" and not r["json_present"]]

    out_json = {
        "venue": "OKX (okex-swap)",
        "symbol": "BTC-USDT-SWAP",
        "purpose": "Combined 24-date OKX full-day summary (6 calibration + 6 OOS_v1 + 12 v2)",
        "build_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "v2_dates_completed": v2_completed,
        "v2_dates_missing": v2_missing,
        "rounds": {
            "calibration": [r["date"] for r in rows if r["round"] == "calibration"],
            "oos_v1": [r["date"] for r in rows if r["round"] == "oos_v1"],
            "v2": [r["date"] for r in rows if r["round"] == "v2"],
        },
        "per_date": rows,
        "aggregates_per_round": aggregates,
        "honest_headline_metric": "unique_reached_moves",
        "strategy_thresholds_unchanged": True,
        "zone_score_v1_archived": True,
        "zone_score_v2_not_built": True,
    }
    (REPORTS / "OKX_V2_FULLDAY_12_DATE_REPLAY_SUMMARY.json").write_text(
        json.dumps(out_json, indent=2, default=str), encoding="utf-8"
    )

    # ---- CSV (flat per-date) ----
    csv_cols = [
        "date", "round", "regime", "day_return_pct", "range_pct",
        "feasibility_2pct", "feasibility_1pct",
        "fullday_runtime_seconds",
        "zones_total", "zones_triggered", "zones_reached_raw",
        "unique_reached_moves", "duplicate_move_credits",
        "raw_triggered_hit_rate", "unique_move_adjusted_hit_rate",
        "direction_LONG", "direction_SHORT",
        "long_reached", "short_reached",
        "duplicate_suppression_count",
        "status_RESOLVED_REACHED", "status_RESOLVED_FAILED",
        "status_INVALIDATED", "status_NO_TRIGGER", "status_EXPIRED",
    ]
    with (REPORTS / "OKX_V2_FULLDAY_12_DATE_REPLAY_SUMMARY.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(csv_cols)
        for r in rows:
            w.writerow([r.get(c, "") for c in csv_cols])

    # ---- Markdown ----
    def fnum(v, w=7, p=2):
        if v is None: return "-".rjust(w)
        return f"{v:>{w}.{p}f}"

    md: list[str] = [
        "# OKX full-day 24-date combined summary (calibration + OOS_v1 + v2)",
        "",
        f"**Build time:** {out_json['build_time_utc']}",
        "**Venue:** OKX `okex-swap` BTC-USDT-SWAP",
        f"**v2 dates completed:** {v2_completed} / {len(v2_dates)}",
        f"**v2 dates missing:** {', '.join(v2_missing) if v2_missing else '(none)'}",
        "",
        "## HARD DISCLAIMER",
        "",
        "  • Strategy thresholds: Binance USDS-M Futures defaults — UNCHANGED.",
        "  • `zone_score_v1` is ARCHIVED as a failed OOS hypothesis (see `ZONE_SCORE_V1_FINAL_VERDICT.md`). Not used here.",
        "  • `zone_score_v2` is NOT built. This round is data-collection / labelling only.",
        "  • Headline metric: **`unique_reached_moves`**, NOT raw reached zones.",
        "  • No winrate / profitability claim is made.",
        "  • OKX is NOT Binance.",
        "",
        "## A. Aggregates per round",
        "",
        "| round | n dates | zones | triggered | reached_raw | **unique moves** | LONG reached | SHORT reached | dup credits | dedup suppr. | wall-clock (h) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ("calibration", "oos_v1", "v2", "all_24"):
        a = aggregates[label]
        if a["n_dates"] == 0:
            md.append(f"| {label} | 0 | — | — | — | — | — | — | — | — | — |")
            continue
        md.append(
            f"| {label} | {a['n_dates']} | {a['zones_total']} | {a['zones_triggered']} | "
            f"{a['zones_reached_raw']} | **{a['unique_reached_moves']}** | {a['long_reached']} | "
            f"{a['short_reached']} | {a['duplicate_move_credits']} | {a['duplicate_suppression_count']} | "
            f"{a['wall_clock_seconds']/3600:.2f} |"
        )

    md.extend([
        "",
        "## B. Per-date table",
        "",
        "| date | round | regime | day Δ % | 2%-feas | zones | triggered | reached_raw | unique | LONG/SHORT | LONG reached / SHORT reached | raw hit | uniq-move hit | runtime (min) |",
        "|------|-------|--------|--------:|:-------:|------:|----------:|------------:|-------:|------------|-----------------------------:|--------:|--------------:|--------------:|",
    ])
    for r in rows:
        if not r["json_present"]:
            md.append(f"| {r['date']} | {r['round']} | — | — | — | — | — | — | — | — | — | — | — | (missing) |")
            continue
        feas = "yes" if r.get("feasibility_2pct") else "no"
        rt_min = (r.get("fullday_runtime_seconds") or 0) / 60.0
        raw_hit = f"{r.get('raw_triggered_hit_rate', 0)*100:.2f}%"
        uniq_hit = f"{r.get('unique_move_adjusted_hit_rate', 0)*100:.2f}%"
        md.append(
            f"| {r['date']} | {r['round']} | {r.get('regime','—'):<7s} | {fnum(r.get('day_return_pct'), 6, 2)} | "
            f"  {feas:^3s}  | {r['zones_total']:>5d} | {r['zones_triggered']:>9d} | "
            f"{r['zones_reached_raw']:>11d} | **{r['unique_reached_moves']}** | "
            f"{r['direction_LONG']:>3d}/{r['direction_SHORT']:<3d}  | "
            f"{r['long_reached']:>20d} / {r['short_reached']:<3d}      | "
            f"{raw_hit:>7s} | {uniq_hit:>13s} | {rt_min:>13.1f} |"
        )

    md.extend([
        "",
        "## C. Unique-move yield, per round",
        "",
        "Why this matters: `unique_reached_moves` is the *positive class* a future v2 calibration will fit on. n=positives is the binding constraint for any held-out validation. Below is what we have accumulated so far.",
        "",
        "| round | n dates | unique moves | unique-moves / date |",
        "|---|---:|---:|---:|",
    ])
    for label in ("calibration", "oos_v1", "v2", "all_24"):
        a = aggregates[label]
        ratio = a["unique_reached_moves"] / a["n_dates"] if a["n_dates"] else 0
        md.append(f"| {label} | {a['n_dates']} | {a['unique_reached_moves']} | {ratio:.2f} |")

    md.extend([
        "",
        "## D. What this round does NOT do",
        "",
        "- Does NOT build zone_score_v2 (model fitting is a separate task).",
        "- Does NOT filter zones (no score is consulted at entry time).",
        "- Does NOT change strategy thresholds or move weights.",
        "- Does NOT use zone_score_v1 (archived).",
        "- Does NOT claim profitability.",
        "",
        "## E. Files",
        "",
        "- `reports/OKX_V2_TECHNICAL_REPLAY_<date>_fullday.{md,json,_ZONES.csv}` — 12 per-date triplets.",
        "- `reports/OKX_V2_FULLDAY_CHAIN_RESULTS.json` — chain manifest with per-date exit codes + runtimes.",
        "- `reports/OKX_V2_FULLDAY_12_DATE_REPLAY_SUMMARY.{md,json,csv}` — this combined summary.",
        "- `reports/BTC-USDT-SWAP_<date>/` — per-date underlying backtest output (zones.json, daily_summary.csv, etc.).",
        "",
    ])

    (REPORTS / "OKX_V2_FULLDAY_12_DATE_REPLAY_SUMMARY.md").write_text("\n".join(md), encoding="utf-8")

    print(f"wrote OKX_V2_FULLDAY_12_DATE_REPLAY_SUMMARY.md / .json / .csv")
    print()
    for label in ("calibration", "oos_v1", "v2", "all_24"):
        a = aggregates[label]
        print(f"  {label:<14s}  n_dates={a['n_dates']:>3d}  zones={a['zones_total']:>5d}  triggered={a['zones_triggered']:>4d}  reached_raw={a['zones_reached_raw']:>4d}  unique_moves={a['unique_reached_moves']:>3d}  wall-clock={a['wall_clock_seconds']/3600:.2f}h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
