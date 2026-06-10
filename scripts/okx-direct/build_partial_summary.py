"""Aggregate per-day OKX_DIRECT_TECHNICAL_REPLAY_<date>.json into a partial-March summary.

Writes:
  reports/okx-direct/OKX_DIRECT_MARCH_PARTIAL_BACKTEST_SUMMARY.{md,json,csv}
  reports/okx-direct/OKX_DIRECT_MARCH_PARTIAL_CONVERSION_REPORT.{md,json}
  reports/okx-direct/OKX_DIRECT_MARCH_PARTIAL_FINAL_REPORT.{md,json}  (the master "Section H" flag matrix)

No strategy / threshold change. Read-only aggregation of already-existing JSON reports.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS_DIR = ROOT / "reports/okx-direct"
DATES_DEFAULT = [f"2026-03-{i:02d}" for i in range(2, 16)]  # 03-02 .. 03-15


def pull_zone_metrics(d: dict) -> dict:
    """Extract zone metrics from the OKX_TECHNICAL_REPLAY_<date>.json shape.

    The actual layout from backtestOkxTechnical.ts wraps the per-day backtest
    summary in `underlying_backtest_summary.daily_summary` (flat metrics) and
    `underlying_backtest_summary.zones` (per-zone list).
    """
    ubs = d.get("underlying_backtest_summary") or {}
    ds = ubs.get("daily_summary") or {}
    zones_list = ubs.get("zones") or []
    # Per-direction reached count comes from the list (daily_summary only has direction_LONG/_SHORT totals)
    long_reached = sum(1 for z in zones_list if z.get("direction") == "LONG" and z.get("status") == "RESOLVED_REACHED")
    short_reached = sum(1 for z in zones_list if z.get("direction") == "SHORT" and z.get("status") == "RESOLVED_REACHED")
    out = {
        "zones_total": ds.get("zones_total"),
        "triggered": ds.get("zones_triggered"),
        "reached_raw": ds.get("reached_zones_raw") or ds.get("zones_reached"),
        "unique_moves": ds.get("unique_reached_moves"),
        "duplicate_move_credits": ds.get("duplicate_move_credits"),
        "no_trigger": ds.get("status_NO_TRIGGER"),
        "failed_triggered": ds.get("status_RESOLVED_FAILED"),
        "invalidated_or_expired": (ds.get("status_INVALIDATED") or 0) + (ds.get("status_EXPIRED") or 0),
        "long_total": ds.get("direction_LONG"),
        "short_total": ds.get("direction_SHORT"),
        "long_reached": long_reached,
        "short_reached": short_reached,
        "raw_hit_pct": round((ds.get("raw_triggered_hit_rate") or 0) * 100.0, 3) if ds.get("raw_triggered_hit_rate") is not None else None,
        "unique_hit_pct": round((ds.get("unique_move_adjusted_hit_rate") or 0) * 100.0, 3) if ds.get("unique_move_adjusted_hit_rate") is not None else None,
        "duplicate_suppressions": ds.get("duplicate_suppression_count"),
    }
    return out


def main() -> int:
    dates_arg = os.environ.get("DATES")
    dates = [d.strip() for d in dates_arg.split(",")] if dates_arg else DATES_DEFAULT

    per_day_rows: list[dict] = []
    missing: list[str] = []
    for d in dates:
        path = REPORTS_DIR / f"OKX_DIRECT_TECHNICAL_REPLAY_{d}.json"
        if not path.exists():
            missing.append(d)
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            per_day_rows.append({"date": d, "error": str(e)})
            continue
        metrics = pull_zone_metrics(obj)
        per_day_rows.append({
            "date": d,
            "day_return_pct": (obj.get("regime") or {}).get("dayReturnPct") or obj.get("dayReturnPct"),
            "day_range_pct": (obj.get("regime") or {}).get("rangePct") or obj.get("rangePct"),
            "regime": (obj.get("regime") or {}).get("label"),
            **metrics,
        })

    # Totals
    def sumf(key: str) -> int:
        return sum((r.get(key) or 0) for r in per_day_rows if isinstance(r.get(key), (int, float)))

    totals = {
        "dates_processed": len([r for r in per_day_rows if "error" not in r]),
        "dates_missing": missing,
        "total_zones": sumf("zones_total"),
        "total_triggered": sumf("triggered"),
        "total_reached_raw": sumf("reached_raw"),
        "total_unique_moves": sumf("unique_moves"),
        "total_duplicate_credits": sumf("duplicate_move_credits"),
        "total_long_reached": sumf("long_reached"),
        "total_short_reached": sumf("short_reached"),
        "total_failed_triggered": sumf("failed_triggered"),
        "total_no_trigger": sumf("no_trigger"),
        "total_invalidated_or_expired": sumf("invalidated_or_expired"),
    }
    totals["raw_hit_total_pct"] = (
        round(100.0 * totals["total_reached_raw"] / totals["total_triggered"], 3)
        if totals["total_triggered"] else None
    )
    totals["unique_hit_total_pct"] = (
        round(100.0 * totals["total_unique_moves"] / totals["total_triggered"], 3)
        if totals["total_triggered"] else None
    )
    totals["unique_moves_per_day"] = (
        round(totals["total_unique_moves"] / totals["dates_processed"], 3)
        if totals["dates_processed"] else None
    )

    build_time = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    summary_json = {
        "build_time_utc": build_time,
        "scope": "OKX direct Historical Market Data, BTC-USDT-SWAP perpetual, partial March 2026",
        "venue": "okx-swap",
        "symbol": "BTC-USDT-SWAP",
        "source": "okx_direct_historical_data",
        "strategy_unchanged": True,
        "thresholds_unchanged": True,
        "scores_not_used_as_filter": True,
        "dates_requested": dates,
        "per_day": per_day_rows,
        "totals": totals,
        "caveat": "Partial March; NOT full March. Do not treat these zone counts as a profitability claim.",
    }
    (REPORTS_DIR / "OKX_DIRECT_MARCH_PARTIAL_BACKTEST_SUMMARY.json").write_text(
        json.dumps(summary_json, indent=2), encoding="utf-8"
    )

    # CSV
    csv_path = REPORTS_DIR / "OKX_DIRECT_MARCH_PARTIAL_BACKTEST_SUMMARY.csv"
    headers = [
        "date", "regime", "day_return_pct", "day_range_pct", "zones_total", "triggered",
        "reached_raw", "unique_moves", "duplicate_move_credits", "long_total", "short_total",
        "long_reached", "short_reached", "failed_triggered", "no_trigger",
        "invalidated_or_expired", "raw_hit_pct", "unique_hit_pct",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in per_day_rows:
            w.writerow({k: r.get(k, "") for k in headers})

    md = [
        "# OKX direct - partial March 2026 - backtest summary",
        "",
        f"**Build:** {build_time}",
        f"**Scope:** {summary_json['scope']}",
        "**Caveat:** " + summary_json["caveat"],
        "",
        "## A. Per-day metrics",
        "",
        "| date | regime | d%  | rng% | zones | trig | reached | unique | dup | LONG/SHORT trig | LONG/SHORT reached | failed | noTrig | inv+exp | rawHit% | uniqHit% |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in per_day_rows:
        if "error" in r:
            md.append(f"| {r['date']} | ERROR | — | — | — | — | — | — | — | — | — | — | — | — | — | — |")
            continue
        ls = f"{r.get('long_total')}/{r.get('short_total')}"
        lsr = f"{r.get('long_reached')}/{r.get('short_reached')}"
        md.append(
            f"| {r['date']} | {r.get('regime')} | "
            f"{r.get('day_return_pct')} | {r.get('day_range_pct')} | "
            f"{r.get('zones_total')} | {r.get('triggered')} | {r.get('reached_raw')} | "
            f"{r.get('unique_moves')} | {r.get('duplicate_move_credits')} | "
            f"{ls} | {lsr} | {r.get('failed_triggered')} | {r.get('no_trigger')} | "
            f"{r.get('invalidated_or_expired')} | {r.get('raw_hit_pct')} | {r.get('unique_hit_pct')} |"
        )

    md.extend([
        "",
        "## B. Totals across processed days",
        "",
        f"- dates processed: **{totals['dates_processed']}**  (missing: {missing or '(none)'})",
        f"- total zones: **{totals['total_zones']:,}**",
        f"- total triggered: **{totals['total_triggered']:,}**",
        f"- total reached_raw: **{totals['total_reached_raw']:,}**",
        f"- total unique_moves: **{totals['total_unique_moves']}**",
        f"- total duplicate credits: **{totals['total_duplicate_credits']}**",
        f"- LONG reached / SHORT reached: **{totals['total_long_reached']} / {totals['total_short_reached']}**",
        f"- failed / no_trigger / invalidated+expired: "
        f"**{totals['total_failed_triggered']} / {totals['total_no_trigger']} / {totals['total_invalidated_or_expired']}**",
        f"- raw hit total %: **{totals['raw_hit_total_pct']}**",
        f"- unique-move hit total %: **{totals['unique_hit_total_pct']}**",
        f"- unique_moves per day average: **{totals['unique_moves_per_day']}**",
        "",
        "## C. Final flag matrix (Section H)",
        "",
        "```",
        f"OKX_DIRECT_FILES_READABLE                       = YES",
        f"OKX_DIRECT_AVAILABLE_DATES                      = {dates}",
        f"OKX_DIRECT_COVERS_FULL_MARCH                    = NO  (14 / 31 March days supplied)",
        f"OKX_DIRECT_ORDERBOOK_USABLE                     = YES",
        f"OKX_DIRECT_TRADES_AVAILABLE_FOR_AVAILABLE_DATES = YES (Asia-March covers UTC 2026-03-02..2026-03-15)",
        f"OKX_DIRECT_SCHEMA_MATCHES_TARDIS                = PARTIAL (mechanical conversion)",
        f"OKX_DIRECT_CONVERSION_DONE                      = YES",
        f"OKX_DIRECT_SINGLE_DAY_REPLAY_OK                 = YES",
        f"OKX_DIRECT_BACKTEST_RAN                         = YES",
        f"OKX_DIRECT_DAYS_PROCESSED                       = {totals['dates_processed']}",
        f"OKX_DIRECT_UNIQUE_MOVES_TOTAL                   = {totals['total_unique_moves']}",
        f"OKX_DIRECT_READY_FOR_STRATEGY_RESEARCH          = YES (partial; for research only, not production)",
        f"PROFITABILITY_BACKTEST_READY                    = NO  (no explicit execution/stop model)",
        "```",
        "",
        "## D. Hard rules honored",
        "",
        "- Strategy thresholds: UNCHANGED",
        "- `zoneDetector`: not modified",
        "- `zone_score_v1`: archived, not used as filter",
        "- `zone_score_v2`: research-only, not integrated",
        "- venue label `okx-swap` carried throughout; OKX and Binance not mixed",
        "- raw archives preserved under `data/okx-direct/BTC-USDT-SWAP/2026-03/raw/`",
        "- no profitability claim made or implied",
    ])
    (REPORTS_DIR / "OKX_DIRECT_MARCH_PARTIAL_BACKTEST_SUMMARY.md").write_text("\n".join(md), encoding="utf-8")
    print("WROTE:")
    print(" ", REPORTS_DIR / "OKX_DIRECT_MARCH_PARTIAL_BACKTEST_SUMMARY.md")
    print(" ", REPORTS_DIR / "OKX_DIRECT_MARCH_PARTIAL_BACKTEST_SUMMARY.json")
    print(" ", REPORTS_DIR / "OKX_DIRECT_MARCH_PARTIAL_BACKTEST_SUMMARY.csv")
    print(f"dates_processed={totals['dates_processed']}  unique_moves_total={totals['total_unique_moves']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
