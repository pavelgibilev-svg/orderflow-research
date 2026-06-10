"""Interim sanity check on 2026-03-16 and 2026-03-18 only.

READ-ONLY over the 2 completed OKX direct backtest outputs:
  reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_2026-03-{16,18}.json
  reports/BTC-USDT-SWAP_2026-03-{16,18}/zones.json
  data/okx-historical/BTC-USDT-SWAP/2026-03-{16,18}/trades.csv.gz

Does NOT touch the running chain; does NOT re-run any backtest; does NOT touch
03-02..03-15 or the in-progress 03-19 onwards.

Applies the canonical ledger module (single source of truth) for both variants:
  A) trigger_entry__stop_1pct
  B) delay_15m__stop_1.5pct

Output:
  reports/strategy-calibration/OKX_MARCH_SECOND_HALF_INTERIM_0316_0318_CHECK.{md,json}
"""
from __future__ import annotations
import csv
import datetime as dt
import gzip
import json
import statistics as stats
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

# Make canonical_ledger importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import (
    Signal, Bucket, ExecutionConfig,
    build_buckets_from_trades_csv, canonical_ledger_walk, aggregate, aggregate_after_cost,
)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
REP_OKX = REPORTS / "okx-direct"
REP_OUT = REPORTS / "strategy-calibration"
REP_OUT.mkdir(parents=True, exist_ok=True)
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"

DATES = ["2026-03-16", "2026-03-18"]
WINDOW_MIN = 60
PRICE_BAND_PCT = 1.0
FAST_X_MIN_BASE = 60
FEE_ROUNDTRIP_PCT = 0.08
SLIPPAGE_MID_PCT = 0.06
BASIC_COST_PCT = FEE_ROUNDTRIP_PCT + SLIPPAGE_MID_PCT   # 0.14 %


# ---------- helpers ----------

def mid_price(z: dict) -> float | None:
    lo, hi = z.get("zoneLow"), z.get("zoneHigh")
    if lo is None or hi is None: return None
    return (lo + hi) / 2.0


def is_triggered(z: dict) -> bool:
    return z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED")


def confirm_to_trigger_min(z: dict) -> float | None:
    c, t = z.get("confirmedTs"), z.get("triggerTs")
    if c is None or t is None: return None
    return (t - c) / 60000.0


def class_label(z: dict) -> str:
    s = z.get("status")
    if s == "RESOLVED_REACHED":
        return "primary_unique_reached_move" if z.get("isPrimaryMoveZone") else "duplicate_reached_move"
    if s == "RESOLVED_FAILED":
        return "failed_triggered"
    if s == "NO_TRIGGER":
        return "no_trigger"
    if s in ("INVALIDATED", "EXPIRED"):
        return "invalidated_or_expired"
    return "unknown"


def load_zones_for_dates(dates: list[str]) -> list[dict]:
    out: list[dict] = []
    for d in dates:
        # Prefer full per-zone dump
        p_full = REPORTS / f"BTC-USDT-SWAP_{d}" / "zones.json"
        p_wrap = REP_OKX / f"OKX_DIRECT_TECHNICAL_REPLAY_{d}.json"
        zones = []
        if p_full.exists():
            obj = json.loads(p_full.read_text(encoding="utf-8"))
            zones = obj if isinstance(obj, list) else obj.get("zones", [])
        elif p_wrap.exists():
            w = json.loads(p_wrap.read_text(encoding="utf-8"))
            zones = (w.get("underlying_backtest_summary") or {}).get("zones") or []
        for z in zones:
            z["_date"] = d
            z["_class"] = class_label(z)
        out.extend(zones)
    return out


def apply_passive_filter(zones: list[dict]) -> dict[str, dict]:
    by_date = defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append(z)
    decisions = {}
    for date, lst in by_date.items():
        triggered = [z for z in lst if is_triggered(z) and z.get("triggerTs") is not None]
        triggered.sort(key=lambda z: z["triggerTs"])
        for i, z in enumerate(triggered):
            T = z["triggerTs"]; D = z["direction"]; zm = mid_price(z)
            dup = False
            for prior in triggered[:i]:
                if prior["triggerTs"] >= T or prior["direction"] != D: continue
                dt_min = (T - prior["triggerTs"]) / 60000.0
                if dt_min <= 0 or dt_min > WINDOW_MIN: continue
                pm = mid_price(prior)
                if zm is None or pm is None: continue
                if abs(zm - pm) / zm * 100.0 <= PRICE_BAND_PCT:
                    dup = True; break
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= FAST_X_MIN_BASE)
            decisions[z["id"]] = {"kept": (not dup) and fast_ok}
    return decisions


def per_day_metrics(zones: list[dict]) -> dict[str, dict]:
    """Engine-level per-day numbers (zones / triggered / reached / primaries / dedup)."""
    by_date = defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append(z)
    out = {}
    for d in DATES:
        lst = by_date.get(d, [])
        wrap_path = REP_OKX / f"OKX_DIRECT_TECHNICAL_REPLAY_{d}.json"
        runtime_s = None
        ds_extras = {}
        if wrap_path.exists():
            w = json.loads(wrap_path.read_text(encoding="utf-8"))
            runtime_s = w.get("underlying_backtest_duration_ms")
            if runtime_s is not None:
                runtime_s = round(runtime_s / 1000.0, 1)
            ds = (w.get("underlying_backtest_summary") or {}).get("daily_summary") or {}
            ds_extras = ds
        out[d] = {
            "zones": len(lst),
            "triggered": sum(1 for z in lst if is_triggered(z)),
            "reached_raw": sum(1 for z in lst if z.get("status") == "RESOLVED_REACHED"),
            "primary_unique_reached": sum(1 for z in lst if z["_class"] == "primary_unique_reached_move"),
            "duplicate_reached": sum(1 for z in lst if z["_class"] == "duplicate_reached_move"),
            "failed_triggered": sum(1 for z in lst if z["_class"] == "failed_triggered"),
            "no_trigger": sum(1 for z in lst if z["_class"] == "no_trigger"),
            "invalidated_or_expired": sum(1 for z in lst if z["_class"] == "invalidated_or_expired"),
            "long": sum(1 for z in lst if z.get("direction") == "LONG"),
            "short": sum(1 for z in lst if z.get("direction") == "SHORT"),
            "raw_triggered_hit_rate_pct":
                round(100.0 * ds_extras.get("raw_triggered_hit_rate", 0), 2)
                if ds_extras.get("raw_triggered_hit_rate") is not None else None,
            "unique_move_adjusted_hit_rate_pct":
                round(100.0 * ds_extras.get("unique_move_adjusted_hit_rate", 0), 2)
                if ds_extras.get("unique_move_adjusted_hit_rate") is not None else None,
            "duplicate_suppression_count": ds_extras.get("duplicate_suppression_count"),
            "runtime_s": runtime_s,
        }
    return out


def to_signal(z: dict) -> Signal:
    return Signal(id=z["id"], date=z["_date"], trigger_ts_ms=z["triggerTs"],
                  direction=z["direction"], zone_low=z.get("zoneLow"), zone_high=z.get("zoneHigh"))


def per_day_pnl_breakdown(trades: list, dates: list[str]) -> dict:
    out = {}
    for d in dates:
        day_trades = [t for t in trades if t.date == d]
        pnls = [t.pnl_pct for t in day_trades]
        out[d] = {
            "n_trades": len(day_trades),
            "wins": sum(1 for t in day_trades if t.exit_reason == "target_2pct"),
            "losses": sum(1 for t in day_trades if t.exit_reason == "stop"),
            "timeouts": sum(1 for t in day_trades if t.exit_reason == "timeout"),
            "total_pnl_pct_pre_cost": round(sum(pnls), 4) if pnls else 0.0,
            "total_pnl_pct_after_cost": round(sum(pnls) - BASIC_COST_PCT * len(pnls), 4) if pnls else 0.0,
            "expectancy_pct_per_trade_pre_cost": round(stats.mean(pnls), 4) if pnls else None,
        }
    return out


def main() -> int:
    # ---------- 1. Verify outputs ----------
    file_status = {}
    for d in DATES:
        wrap = REP_OKX / f"OKX_DIRECT_TECHNICAL_REPLAY_{d}.json"
        zones = REPORTS / f"BTC-USDT-SWAP_{d}" / "zones.json"
        trades = DATA_ROOT / d / "trades.csv.gz"
        file_status[d] = {
            "wrapper_report_exists": wrap.exists(),
            "full_zones_exists": zones.exists(),
            "trades_csv_gz_exists": trades.exists(),
        }
    all_present = all(
        s["wrapper_report_exists"] and s["full_zones_exists"] and s["trades_csv_gz_exists"]
        for s in file_status.values()
    )

    # ---------- 2. Engine-level per-day ----------
    zones_all = load_zones_for_dates(DATES)
    decisions = apply_passive_filter(zones_all)
    daily = per_day_metrics(zones_all)

    # ---------- 3. Canonical ledger on filtered triggered ----------
    filtered = [z for z in zones_all if is_triggered(z) and decisions.get(z["id"], {}).get("kept")]
    signals = [to_signal(z) for z in filtered]
    print(f"  loaded {len(zones_all)} zones / {len(filtered)} filtered triggered", file=sys.stderr)

    print("  building 1s buckets ...", file=sys.stderr)
    buckets_by_date: dict[str, list[Bucket]] = {}
    for d in DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        if not p.exists():
            buckets_by_date[d] = []
            continue
        buckets_by_date[d] = build_buckets_from_trades_csv(p)
        print(f"    {d}: {len(buckets_by_date[d]):,} buckets", file=sys.stderr)

    cfg_a = ExecutionConfig(entry_strategy="trigger", stop_pct=1.0, target_pct=2.0, timeout_hours=24)
    cfg_b = ExecutionConfig(entry_strategy="delay_15m", stop_pct=1.5, target_pct=2.0, timeout_hours=24)

    print("  variant A: trigger_entry + stop_1pct ...", file=sys.stderr)
    res_a = canonical_ledger_walk(signals, buckets_by_date, cfg_a)
    agg_a = aggregate(res_a.trades)
    agg_a_after = aggregate_after_cost(res_a.trades, BASIC_COST_PCT)
    perday_a = per_day_pnl_breakdown(res_a.trades, DATES)

    print("  variant B: delay_15m + stop_1.5pct ...", file=sys.stderr)
    res_b = canonical_ledger_walk(signals, buckets_by_date, cfg_b)
    agg_b = aggregate(res_b.trades)
    agg_b_after = aggregate_after_cost(res_b.trades, BASIC_COST_PCT)
    perday_b = per_day_pnl_breakdown(res_b.trades, DATES)

    # ---------- 4. Sanity flags ----------
    sanity_issues = []
    for d in DATES:
        if daily[d]["triggered"] > 0:
            # No corresponding ledger trades is suspicious (unless all skipped)
            if perday_a[d]["n_trades"] == 0:
                sanity_issues.append(f"{d}: variant A 0 trades despite {daily[d]['triggered']} triggered")
            if perday_b[d]["n_trades"] == 0:
                sanity_issues.append(f"{d}: variant B 0 trades despite {daily[d]['triggered']} triggered")
    if agg_a["n_trades"] > 0 and agg_a["wins"] == 0 and agg_a["losses"] == agg_a["n_trades"]:
        sanity_issues.append("variant A: ALL trades are losses (suspicious all-stop)")
    if agg_b["n_trades"] > 0 and agg_b["wins"] == 0 and agg_b["losses"] == agg_b["n_trades"]:
        sanity_issues.append("variant B: ALL trades are losses (suspicious all-stop)")
    skipped_share_a = (res_a.skipped_due_to_position / len(signals)) if signals else 0
    if skipped_share_a > 0.85:
        sanity_issues.append(f"variant A: too many skipped due to open position ({res_a.skipped_due_to_position}/{len(signals)} = {skipped_share_a:.1%})")
    canonical_ok = (
        len(sanity_issues) == 0
        and all(b for b in buckets_by_date.values())
        and any(t.entry_price > 0 for t in res_a.trades)
        and any(t.entry_price > 0 for t in res_b.trades)
    )

    # Best/worst trade
    def best_worst(trades):
        if not trades: return (None, None)
        best = max(trades, key=lambda t: t.pnl_pct)
        worst = min(trades, key=lambda t: t.pnl_pct)
        return (best, worst)
    bw_a = best_worst(res_a.trades)
    bw_b = best_worst(res_b.trades)

    # ---------- 5. Chain status ----------
    chain_log = ROOT / "data/okx-historical/_okx_direct_partial_chain.log"
    chain_current_day = "UNKNOWN"
    main_chain_running = False
    if chain_log.exists():
        lines = chain_log.read_text(encoding="utf-8").splitlines()
        # Find the latest "--- N/15: YYYY-MM-DD" entry not followed by chain DONE for this run
        last_run_idx = None
        for i, line in enumerate(lines):
            if "chain dates (15):" in line and "2026-03-16" in line:
                last_run_idx = i
        if last_run_idx is not None:
            after = lines[last_run_idx:]
            done_lines = [l for l in after if "chain DONE" in l]
            main_chain_running = len(done_lines) == 0
            for l in reversed(after):
                if l.startswith("[") and "--- " in l and "/15:" in l:
                    chain_current_day = l.split(": ")[-1].strip()
                    break

    # ---------- 6. Compose output ----------
    out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Interim sanity check on 2026-03-16 + 2026-03-18 only (chain still running for the other 13 days)",
        "file_status": file_status,
        "engine_per_day_metrics": daily,
        "filtered_triggered_count": len(filtered),
        "variant_A_trigger_entry_stop_1pct": {
            "aggregate_pre_cost": agg_a,
            "aggregate_after_basic_cost": agg_a_after,
            "n_skipped_due_to_position": res_a.skipped_due_to_position,
            "n_skipped_no_data": res_a.skipped_no_data,
            "per_day": perday_a,
            "best_trade": asdict(bw_a[0]) if bw_a[0] else None,
            "worst_trade": asdict(bw_a[1]) if bw_a[1] else None,
        },
        "variant_B_delay15m_stop_1.5pct": {
            "aggregate_pre_cost": agg_b,
            "aggregate_after_basic_cost": agg_b_after,
            "n_skipped_due_to_position": res_b.skipped_due_to_position,
            "n_skipped_no_data": res_b.skipped_no_data,
            "per_day": perday_b,
            "best_trade": asdict(bw_b[0]) if bw_b[0] else None,
            "worst_trade": asdict(bw_b[1]) if bw_b[1] else None,
        },
        "cost_assumption_pct_roundtrip": BASIC_COST_PCT,
        "sanity_issues_found": sanity_issues,
        "chain_status": {
            "main_chain_still_running": main_chain_running,
            "main_chain_current_day": chain_current_day,
        },
    }

    flags = {
        "INTERIM_CHECK_DONE": "YES",
        "INTERIM_DAYS_CHECKED": DATES,
        "INTERIM_BACKTEST_OUTPUTS_PRESENT": "YES" if all_present else "NO",
        "INTERIM_CANONICAL_LEDGER_OK": "YES" if canonical_ok else "NO",
        "INTERIM_TRIGGER_ENTRY_STOP1_TRADES": agg_a["n_trades"],
        "INTERIM_TRIGGER_ENTRY_STOP1_EXPECTANCY": agg_a["expectancy_pct_per_trade"],
        "INTERIM_TRIGGER_ENTRY_STOP1_PF": agg_a["profit_factor"],
        "INTERIM_TRIGGER_ENTRY_STOP1_TOTAL_RETURN_PRE_COST": agg_a["total_return_pct_1unit"],
        "INTERIM_TRIGGER_ENTRY_STOP1_TOTAL_RETURN_AFTER_COST": agg_a_after["total_return_pct_1unit"],
        "INTERIM_DELAY15_STOP15_TRADES": agg_b["n_trades"],
        "INTERIM_DELAY15_STOP15_EXPECTANCY": agg_b["expectancy_pct_per_trade"],
        "INTERIM_DELAY15_STOP15_PF": agg_b["profit_factor"],
        "INTERIM_DELAY15_STOP15_TOTAL_RETURN_PRE_COST": agg_b["total_return_pct_1unit"],
        "INTERIM_DELAY15_STOP15_TOTAL_RETURN_AFTER_COST": agg_b_after["total_return_pct_1unit"],
        "INTERIM_DELAY15_STOP15_EXPECTANCY_AFTER_COST": agg_b_after["expectancy_pct_per_trade"],
        "INTERIM_DELAY15_STOP15_PROFITABLE_ON_2DAYS": (
            "YES" if (agg_b_after["expectancy_pct_per_trade"] or 0) > 0
            else ("NO" if agg_b_after["expectancy_pct_per_trade"] is not None else "UNKNOWN")
        ),
        "INTERIM_RESULT_LOOKS_NORMAL": "YES" if canonical_ok else "NO",
        "MAIN_CHAIN_STILL_RUNNING": "YES" if main_chain_running else "NO",
        "MAIN_CHAIN_CURRENT_DAY": chain_current_day,
        "INTERIM_PROFITABILITY_SAMPLE_TOO_SMALL": "YES",   # only 2 days
    }
    out["flags"] = flags

    (REP_OUT / "OKX_MARCH_SECOND_HALF_INTERIM_0316_0318_CHECK.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")

    md = [
        "# OKX direct March - INTERIM sanity check on 2026-03-16 + 2026-03-18",
        "",
        f"**Build:** {out['build_time_utc']}",
        "**Scope:** ONLY 2 already-completed days; main chain still running for the other 13.",
        "**Canonical model:** `scripts/strategy-calibration/canonical_ledger.py` (= `src/research/canonicalLedger.ts`).",
        "**Target STRICT 2 %. Stop variants: 1.0 % (A) and 1.5 % (B). Timeout 24h.**",
        "",
        "## 1. File presence",
        "",
        "| date | wrapper report | full zones.json | trades.csv.gz |",
        "|---|:---:|:---:|:---:|",
    ]
    for d in DATES:
        s = file_status[d]
        md.append(f"| {d} | {'YES' if s['wrapper_report_exists'] else 'NO'} | "
                  f"{'YES' if s['full_zones_exists'] else 'NO'} | "
                  f"{'YES' if s['trades_csv_gz_exists'] else 'NO'} |")

    md.extend([
        "",
        "## 2. Engine-level per-day metrics (already-produced backtest reports)",
        "",
        "| date | zones | trig | reached | prim | dup | fail | no_trig | inval | LONG | SHORT | raw_hit % | unique_hit % | dedup_supp | runtime s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for d in DATES:
        x = daily[d]
        md.append(
            f"| {d} | {x['zones']} | {x['triggered']} | {x['reached_raw']} | "
            f"{x['primary_unique_reached']} | {x['duplicate_reached']} | {x['failed_triggered']} | "
            f"{x['no_trigger']} | {x['invalidated_or_expired']} | {x['long']} | {x['short']} | "
            f"{x['raw_triggered_hit_rate_pct']} | {x['unique_move_adjusted_hit_rate_pct']} | "
            f"{x['duplicate_suppression_count']} | {x['runtime_s']} |"
        )

    def render_variant(name: str, agg, agg_after, perday, skip_pos, skip_nd, best, worst):
        out_lines = [
            "",
            f"## {name}",
            "",
            "| metric | value |",
            "|---|---:|",
            f"| n_trades | **{agg['n_trades']}** |",
            f"| W / L / T | **{agg['wins']} / {agg['losses']} / {agg['timeouts']}** |",
            f"| winrate % | {agg['winrate_pct']} |",
            f"| avg win % | {agg['avg_win_pct']} |",
            f"| avg loss % | {agg['avg_loss_pct']} |",
            f"| **expectancy %/trade pre-cost** | **{agg['expectancy_pct_per_trade']}** |",
            f"| expectancy %/trade after basic cost (0.14 %) | {agg_after['expectancy_pct_per_trade']} |",
            f"| profit factor pre-cost | **{agg['profit_factor']}** |",
            f"| profit factor after cost | {agg_after['profit_factor']} |",
            f"| total return % (1 unit/trade) pre-cost | {agg['total_return_pct_1unit']} |",
            f"| total return % after basic cost | {agg_after['total_return_pct_1unit']} |",
            f"| max consecutive losses | {agg['max_consecutive_losses']} |",
            f"| LONG n / exp % | {agg['long_n']} / {agg['long_expectancy_pct']} |",
            f"| SHORT n / exp % | {agg['short_n']} / {agg['short_expectancy_pct']} |",
            f"| skipped due to open position | {skip_pos} |",
            f"| skipped no data | {skip_nd} |",
            "",
            "### per-day result",
            "",
            "| date | n trades | W/L/T | total pnl % (pre) | total pnl % (after cost) | expectancy %/trade |",
            "|---|---:|---|---:|---:|---:|",
        ]
        for d in DATES:
            p = perday[d]
            out_lines.append(
                f"| {d} | {p['n_trades']} | {p['wins']}/{p['losses']}/{p['timeouts']} | "
                f"{p['total_pnl_pct_pre_cost']} | {p['total_pnl_pct_after_cost']} | "
                f"{p['expectancy_pct_per_trade_pre_cost']} |"
            )
        if best and worst:
            out_lines.extend([
                "",
                "### best / worst trade",
                "",
                f"- best trade: `{best.zone_id}` on **{best.date}** ({best.direction}) — pnl **{best.pnl_pct} %**, exit `{best.exit_reason}`",
                f"- worst trade: `{worst.zone_id}` on **{worst.date}** ({worst.direction}) — pnl **{worst.pnl_pct} %**, exit `{worst.exit_reason}`",
            ])
        return out_lines

    md.extend(render_variant(
        "3. Variant A - trigger_entry + stop 1.0 % (canonical baseline)",
        agg_a, agg_a_after, perday_a, res_a.skipped_due_to_position, res_a.skipped_no_data, bw_a[0], bw_a[1],
    ))
    md.extend(render_variant(
        "4. Variant B - delay 15 min entry + stop 1.5 % (diagnostic)",
        agg_b, agg_b_after, perday_b, res_b.skipped_due_to_position, res_b.skipped_no_data, bw_b[0], bw_b[1],
    ))

    md.extend([
        "",
        "## 5. Sanity check verdict",
        "",
    ])
    if sanity_issues:
        for s in sanity_issues:
            md.append(f"- ⚠️ {s}")
    else:
        md.append("- No sanity issues detected. Canonical ledger appears applied correctly on both days.")

    md.extend([
        "",
        "## 6. Main chain status",
        "",
        f"- main chain still running: **{flags['MAIN_CHAIN_STILL_RUNNING']}**",
        f"- main chain current day: **{flags['MAIN_CHAIN_CURRENT_DAY']}**",
        "",
        "## 7. Interim flag matrix",
        "",
        "```",
    ])
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.append("```")
    md.extend([
        "",
        "## 8. Caveats",
        "",
        "- This is only 2 days of OOS data. **`INTERIM_PROFITABILITY_SAMPLE_TOO_SMALL = YES`**.",
        "- Final verdict requires all 15 days completed and a separate retest report.",
        "- No engine / threshold change; no production integration.",
    ])
    (REP_OUT / "OKX_MARCH_SECOND_HALF_INTERIM_0316_0318_CHECK.md").write_text("\n".join(md), encoding="utf-8")

    print()
    print("INTERIM FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<60s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
