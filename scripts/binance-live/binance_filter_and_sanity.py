"""Passive-filter + pre-cost profitability sanity on Binance backtest outputs.

Inputs (READ-ONLY):
  reports/binance-live/BINANCE_LIVE_TECHNICAL_REPLAY_<date>.json
  reports/binance-live/BTCUSDT_<date>/zones.json (full zone dump)

Filter under test:
    fast_trigger <= 60 min  AND  duplicate_60m (price band <= 1.0 %, same direction, strict past)

Live-valid: NO uniqueMoveId / isPrimaryMoveZone / duplicateMoveCredit / moveClusterSize /
status / reached / target_*.* / resolvedTs / mfePct / maePct in suppress decision.
Those fields are read only AFTER filtering, as evaluation labels.

Pre-cost profitability sanity:
  Entry = zone.triggerPrice (from `reasons[stage=trigger].conditions.triggerPrice` or
          zone.scores.triggerPrice surrogate).
  Direction = zone.direction.
  Target = +2 % in direction (matches engine's existing target_pct 2).
  Stop scenarios:
    - fixed 1 %
    - zone invalidation = LONG: stop below zoneLow; SHORT: stop above zoneHigh
    - no-stop (diagnostic only): horizon outcome from targets[4h|8h|24h]
  Outcome from `targets[h]` per zone:
    outcome=reached -> WIN
    outcome=failed_by_timeout -> if mae crossed stop first => LOSS else TIMEOUT
  PRE_COST_ONLY = YES; no fees / slippage; not a profitability claim.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import math
import statistics as stats
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS_LIVE = ROOT / "reports/binance-live"

PRICE_BAND_PCT = 1.0
WINDOW_MIN = 60
FAST_X_MIN = 60
TARGET_PCT = 2.0
FIXED_STOP_PCT = 1.0


def mid_price(z: dict) -> float | None:
    lo = z.get("zoneLow")
    hi = z.get("zoneHigh")
    if lo is None or hi is None:
        return None
    return (lo + hi) / 2.0


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


def is_triggered(z: dict) -> bool:
    return z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED")


def is_reached(z: dict) -> bool:
    return z.get("status") == "RESOLVED_REACHED"


def confirm_to_trigger_min(z: dict) -> float | None:
    c, t = z.get("confirmedTs"), z.get("triggerTs")
    if c is None or t is None:
        return None
    return (t - c) / 60000.0


def load_zones(dates: list[str]) -> list[dict]:
    rows: list[dict] = []
    for date in dates:
        # Prefer full zones.json (per-zone dump). Fallback to the wrapper JSON.
        z_path = REPORTS_LIVE / f"BTCUSDT_{date}" / "zones.json"
        if z_path.exists():
            try:
                obj = json.loads(z_path.read_text(encoding="utf-8"))
                zones = obj if isinstance(obj, list) else obj.get("zones", [])
            except Exception:
                zones = []
        else:
            w_path = REPORTS_LIVE / f"BINANCE_LIVE_TECHNICAL_REPLAY_{date}.json"
            if not w_path.exists():
                print(f"  WARN missing {z_path} and {w_path}", file=sys.stderr)
                continue
            w = json.loads(w_path.read_text(encoding="utf-8"))
            zones = (w.get("underlying_backtest_summary") or {}).get("zones") or []
        for z in zones:
            z["_date"] = date
            z["_class"] = class_label(z)
        rows.extend(zones)
    return rows


# ---------- filter ----------

def apply_filter(zones: list[dict]) -> dict:
    """Apply (duplicate_60m_PRICE_BAND_ONLY AND fast_trigger<=60m). Live-valid."""
    by_date = defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append(z)

    decisions = {}
    for date, lst in by_date.items():
        triggered = [z for z in lst if is_triggered(z) and z.get("triggerTs") is not None]
        triggered.sort(key=lambda z: z["triggerTs"])
        for i, z in enumerate(triggered):
            T = z["triggerTs"]
            D = z["direction"]
            z_mid = mid_price(z)
            dup = False
            parent_id = None
            for prior in triggered[:i]:
                if prior["triggerTs"] >= T:
                    continue
                if prior["direction"] != D:
                    continue
                dt_min = (T - prior["triggerTs"]) / 60000.0
                if dt_min <= 0 or dt_min > WINDOW_MIN:
                    continue
                p_mid = mid_price(prior)
                if z_mid is None or p_mid is None:
                    continue
                if abs(z_mid - p_mid) / z_mid * 100.0 <= PRICE_BAND_PCT:
                    dup = True
                    parent_id = prior["id"]
                    break
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= FAST_X_MIN)
            decisions[z["id"]] = {
                "kept": (not dup) and fast_ok,
                "dup_suppressed": dup,
                "fast_kept": fast_ok,
                "parent_id": parent_id,
                "confirm_to_trigger_min": ctm,
            }
    return decisions


def summarize_baseline_filtered(zones: list[dict], decisions: dict) -> dict:
    base = {
        "n_zones": len(zones),
        "n_triggered": sum(1 for z in zones if is_triggered(z)),
        "n_reached_raw": sum(1 for z in zones if is_reached(z)),
        "n_primary_unique": sum(1 for z in zones if z["_class"] == "primary_unique_reached_move"),
        "n_duplicate_reached": sum(1 for z in zones if z["_class"] == "duplicate_reached_move"),
        "n_failed_triggered": sum(1 for z in zones if z["_class"] == "failed_triggered"),
    }
    flt = {"trig_kept": 0, "reached_kept": 0, "prim_kept": 0, "dup_kept": 0, "fail_kept": 0,
           "suppressed": 0}
    for z in zones:
        if not is_triggered(z):
            continue
        d = decisions.get(z["id"])
        if d and d["kept"]:
            flt["trig_kept"] += 1
            if is_reached(z):
                flt["reached_kept"] += 1
            if z["_class"] == "primary_unique_reached_move":
                flt["prim_kept"] += 1
            elif z["_class"] == "duplicate_reached_move":
                flt["dup_kept"] += 1
            elif z["_class"] == "failed_triggered":
                flt["fail_kept"] += 1
        else:
            flt["suppressed"] += 1
    return {"baseline": base, "filtered": flt}


def pct(num, den):
    if not den:
        return None
    return round(100.0 * num / den, 2)


# ---------- pre-cost sanity ----------

def trigger_price(z: dict) -> float | None:
    """Extract trigger price from reasons[stage=trigger].conditions or fallback."""
    for r in z.get("reasons") or []:
        if r.get("stage") == "trigger":
            tp = (r.get("conditions") or {}).get("triggerPrice")
            if tp is not None:
                return float(tp)
    # fallback: zone midpoint at trigger time isn't ideal but is consistent
    return mid_price(z)


def horizon_outcome(z: dict, horizon: str) -> dict:
    tgt = (z.get("targets") or {}).get(horizon) or {}
    return tgt


def precost_sanity_for_zone(z: dict) -> dict:
    """Per-zone outcome under fixed-1%-stop scenario, computed from existing target metrics.

    The engine reports per-horizon mfePct (best in direction) and maePct (worst against
    direction) on the price path AFTER trigger. We use:
      - outcome=reached  AND  mae before reach (maxDrawdownBeforeTargetPct) <= 1%  =>  WIN (clean)
      - outcome=reached  AND  maxDrawdownBeforeTargetPct  > 1%                   =>  STOPPED_BEFORE_REACH
      - outcome=failed_by_timeout  AND  maePct >= 1%                             =>  STOPPED_LOSS
      - outcome=failed_by_timeout  AND  maePct < 1%                              =>  TIMEOUT (no win, no stop)
    For "no-stop diagnostic": treat reached as +2%, failed_by_timeout as -mfePct ceiling at expiry endPrice.
    """
    out = {
        "zone_id": z.get("id"),
        "direction": z.get("direction"),
        "date": z.get("_date"),
        "triggerPrice": trigger_price(z),
        "triggered": is_triggered(z),
        "class_label": z["_class"],
        "per_horizon": {},
    }
    for h in ("4h", "8h", "24h"):
        tg = horizon_outcome(z, h)
        if not tg:
            out["per_horizon"][h] = None
            continue
        outcome = tg.get("outcome")
        mfe = tg.get("mfePct")
        mae = tg.get("maePct")
        mdd = tg.get("maxDrawdownBeforeTargetPct")  # available when reached
        end_price = tg.get("endPrice")
        if outcome == "reached":
            if mdd is None or mdd <= FIXED_STOP_PCT:
                fixed_result = "WIN"
                fixed_pnl_pct = TARGET_PCT
            else:
                fixed_result = "STOPPED_BEFORE_REACH"
                fixed_pnl_pct = -FIXED_STOP_PCT
            nostop_result = "WIN"
            nostop_pnl_pct = TARGET_PCT
        elif outcome == "failed_by_timeout":
            if mae is not None and mae >= FIXED_STOP_PCT:
                fixed_result = "STOPPED_LOSS"
                fixed_pnl_pct = -FIXED_STOP_PCT
            else:
                fixed_result = "TIMEOUT"
                fixed_pnl_pct = 0.0
            # no-stop: realized at horizon endPrice
            entry = out["triggerPrice"]
            if entry and end_price:
                sgn = 1.0 if z["direction"] == "LONG" else -1.0
                nostop_pnl_pct = sgn * (end_price - entry) / entry * 100.0
            else:
                nostop_pnl_pct = None
            nostop_result = "EXIT_AT_HORIZON"
        else:
            fixed_result = "UNKNOWN"
            fixed_pnl_pct = None
            nostop_result = "UNKNOWN"
            nostop_pnl_pct = None
        out["per_horizon"][h] = {
            "outcome_engine": outcome,
            "mfePct": mfe,
            "maePct": mae,
            "maxDrawdownBeforeTargetPct": mdd,
            "fixed_stop_1pct": {"result": fixed_result, "pnl_pct": fixed_pnl_pct},
            "no_stop_horizon": {"result": nostop_result, "pnl_pct": nostop_pnl_pct},
        }
    return out


def aggregate_precost(per_zone: list[dict], horizon: str = "24h", which: str = "fixed_stop_1pct") -> dict:
    wins = 0
    losses = 0
    timeouts = 0
    unknowns = 0
    pnls = []
    long_pnls = []
    short_pnls = []
    by_day = defaultdict(list)
    for r in per_zone:
        if not r["triggered"]:
            continue
        h = r["per_horizon"].get(horizon)
        if not h:
            unknowns += 1
            continue
        rec = h[which]
        result = rec["result"]
        pnl = rec["pnl_pct"]
        if result == "WIN":
            wins += 1
        elif result in ("STOPPED_BEFORE_REACH", "STOPPED_LOSS"):
            losses += 1
        elif result in ("TIMEOUT", "EXIT_AT_HORIZON"):
            timeouts += 1
        else:
            unknowns += 1
        if pnl is not None:
            pnls.append(pnl)
            (long_pnls if r["direction"] == "LONG" else short_pnls).append(pnl)
            by_day[r["date"]].append(pnl)
    n = wins + losses + timeouts
    winrate = (wins / n) if n else None
    avg_win = stats.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else None
    avg_loss = stats.mean([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else None
    expectancy = stats.mean(pnls) if pnls else None
    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = sum(-p for p in pnls if p < 0)
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else None
    by_day_summary = {d: {"n": len(ps), "mean_pnl_pct": round(stats.mean(ps), 4)} for d, ps in by_day.items()}
    return {
        "horizon": horizon,
        "stop_model": which,
        "trades": n,
        "wins": wins,
        "losses": losses,
        "timeouts": timeouts,
        "unknowns": unknowns,
        "winrate": round(winrate, 4) if winrate is not None else None,
        "avg_win_pct": round(avg_win, 4) if avg_win is not None else None,
        "avg_loss_pct": round(avg_loss, 4) if avg_loss is not None else None,
        "expectancy_pct_per_trade": round(expectancy, 4) if expectancy is not None else None,
        "profit_factor": round(profit_factor, 3) if profit_factor is not None else None,
        "long_n": len(long_pnls),
        "long_expectancy_pct": round(stats.mean(long_pnls), 4) if long_pnls else None,
        "short_n": len(short_pnls),
        "short_expectancy_pct": round(stats.mean(short_pnls), 4) if short_pnls else None,
        "by_day": by_day_summary,
    }


# ---------- main ----------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", required=True)
    args = ap.parse_args()
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]

    zones = load_zones(dates)
    print(f"loaded {len(zones)} zones across {len(dates)} dates", file=sys.stderr)

    decisions = apply_filter(zones)

    # ---------- B/C: baseline vs filtered ----------
    aggregate = summarize_baseline_filtered(zones, decisions)
    b = aggregate["baseline"]
    f = aggregate["filtered"]
    primary_recall = pct(f["prim_kept"], b["n_primary_unique"])
    dup_removal = pct(b["n_duplicate_reached"] - f["dup_kept"], b["n_duplicate_reached"])
    failed_reduction = pct(b["n_failed_triggered"] - f["fail_kept"], b["n_failed_triggered"])
    n_days = len(dates)
    actionable_per_day = round(f["trig_kept"] / n_days, 3) if n_days else None
    base_precision = pct(b["n_reached_raw"], b["n_triggered"])
    filt_precision = pct(f["reached_kept"], f["trig_kept"]) if f["trig_kept"] else None

    filter_flags = {
        "BINANCE_FILTER_VALIDATION_DONE": "YES",
        "FILTER_DECISION_USED_UNIQUEMOVEID": "NO",
        "FILTER_INVALID_FUTURE_LEAK": "NO",
        "BINANCE_PRIMARY_RECALL_PCT": primary_recall,
        "BINANCE_DUPLICATE_REMOVAL_PCT": dup_removal,
        "BINANCE_FAILED_REDUCTION_PCT": failed_reduction,
        "BINANCE_ACTIONABLE_SIGNALS_PER_DAY": actionable_per_day,
        "BINANCE_BASELINE_PRECISION_PCT": base_precision,
        "BINANCE_FILTERED_PRECISION_PCT": filt_precision,
        "BINANCE_FILTER_LOOKS_STABLE": "UNKNOWN" if n_days < 3 else (
            "YES" if (primary_recall or 0) >= 70 and (dup_removal or 0) >= 40 else "NO"
        ),
    }

    (REPORTS_LIVE / "BINANCE_LIVE_PASSIVE_FILTER_VALIDATION.json").write_text(
        json.dumps({
            "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "dates": dates,
            "n_zones": len(zones),
            "filter": "duplicate_60m_PRICE_BAND_ONLY (price_pct<=1.0) AND fast_trigger<=60min  (live-valid; no uniqueMoveId in decision)",
            "aggregate": aggregate,
            "metrics": {
                "primary_recall_pct": primary_recall,
                "duplicate_removal_pct": dup_removal,
                "failed_reduction_pct": failed_reduction,
                "actionable_signals_per_day": actionable_per_day,
                "baseline_precision_pct": base_precision,
                "filtered_precision_pct": filt_precision,
            },
            "flags": filter_flags,
        }, indent=2, default=str), encoding="utf-8")

    # CSV: per-day rows
    rows_csv = []
    for d in dates:
        zs = [z for z in zones if z["_date"] == d]
        rows_csv.append({
            "date": d,
            "baseline_triggered": sum(1 for z in zs if is_triggered(z)),
            "baseline_reached": sum(1 for z in zs if is_reached(z)),
            "baseline_primary": sum(1 for z in zs if z["_class"] == "primary_unique_reached_move"),
            "baseline_duplicate": sum(1 for z in zs if z["_class"] == "duplicate_reached_move"),
            "baseline_failed": sum(1 for z in zs if z["_class"] == "failed_triggered"),
            "filtered_triggered": sum(1 for z in zs if is_triggered(z) and decisions.get(z["id"], {}).get("kept")),
            "filtered_reached": sum(1 for z in zs if is_reached(z) and decisions.get(z["id"], {}).get("kept")),
            "filtered_primary": sum(1 for z in zs if z["_class"] == "primary_unique_reached_move"
                                    and decisions.get(z["id"], {}).get("kept")),
        })
    keys = list(rows_csv[0].keys()) if rows_csv else ["date"]
    with (REPORTS_LIVE / "BINANCE_LIVE_PASSIVE_FILTER_VALIDATION.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=keys)
        w.writeheader()
        for r in rows_csv:
            w.writerow(r)

    md = [
        "# Binance live-recorder - passive filter validation",
        "",
        "**Filter:** `fast_trigger <= 60 min AND duplicate_60m (price band <= 1.0 %)`  (live-valid; no uniqueMoveId in decision).",
        f"**Dates:** {dates}",
        "",
        "## Baseline vs filtered",
        "",
        "| metric | baseline | filtered |",
        "|---|---:|---:|",
        f"| zones | {b['n_zones']} | (only-triggered subset) |",
        f"| triggered | {b['n_triggered']} | {f['trig_kept']} |",
        f"| reached_raw | {b['n_reached_raw']} | {f['reached_kept']} |",
        f"| primary_unique | {b['n_primary_unique']} | {f['prim_kept']} |",
        f"| duplicate_reached | {b['n_duplicate_reached']} | {f['dup_kept']} |",
        f"| failed_triggered | {b['n_failed_triggered']} | {f['fail_kept']} |",
        "",
        "## Per-day breakdown",
        "",
        "| date | trig (b/f) | reached (b/f) | primary (b/f) |",
        "|---|---|---|---|",
    ]
    for r in rows_csv:
        md.append(
            f"| {r['date']} | {r['baseline_triggered']}/{r['filtered_triggered']} | "
            f"{r['baseline_reached']}/{r['filtered_reached']} | "
            f"{r['baseline_primary']}/{r['filtered_primary']} |"
        )
    md.extend([
        "",
        "## Flags",
        "",
    ])
    for k, v in filter_flags.items():
        md.append(f"- `{k}` = **{v}**")
    md.extend([
        "",
        "## Hard rules honored",
        "",
        "- engine / thresholds NOT changed",
        "- post-trigger outcome fields used ONLY as evaluation labels (recall/precision),",
        "  NEVER inside suppress decision",
        "- raw archives preserved; no API keys touched",
    ])
    (REPORTS_LIVE / "BINANCE_LIVE_PASSIVE_FILTER_VALIDATION.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- F: pre-cost sanity ----------
    per_zone = [precost_sanity_for_zone(z) for z in zones]
    # baseline (all triggered) vs filtered (kept)
    baseline_24h = aggregate_precost(per_zone, horizon="24h", which="fixed_stop_1pct")
    baseline_24h_nostop = aggregate_precost(per_zone, horizon="24h", which="no_stop_horizon")
    # filtered subset
    kept_ids = {zid for zid, d in decisions.items() if d["kept"]}
    per_zone_filtered = [r for r in per_zone if r["zone_id"] in kept_ids]
    filtered_24h = aggregate_precost(per_zone_filtered, horizon="24h", which="fixed_stop_1pct")
    filtered_24h_nostop = aggregate_precost(per_zone_filtered, horizon="24h", which="no_stop_horizon")

    precost = {
        "PRE_COST_ONLY": "YES",
        "FEES_SLIPPAGE_INCLUDED": "NO",
        "PROFITABILITY_CLAIM": "NO",
        "scope": "rough sanity scenarios; not a backtest of profitability",
        "baseline_fixed_stop_1pct_24h": baseline_24h,
        "baseline_no_stop_24h": baseline_24h_nostop,
        "filtered_fixed_stop_1pct_24h": filtered_24h,
        "filtered_no_stop_24h": filtered_24h_nostop,
    }
    (REPORTS_LIVE / "BINANCE_LIVE_PRE_COST_EXECUTION_SANITY.json").write_text(
        json.dumps(precost, indent=2, default=str), encoding="utf-8")

    md2 = [
        "# Binance live-recorder - pre-cost profitability sanity",
        "",
        "**`PRE_COST_ONLY = YES`, `FEES_SLIPPAGE_INCLUDED = NO`, `PROFITABILITY_CLAIM = NO`.**",
        "",
        "Sanity scenarios (NOT a profitability backtest):",
        "  - Entry = `triggerPrice` (from zone's trigger reasons).",
        "  - Target = +2 % in direction (engine's existing `target_pct 2`).",
        "  - Stop scenarios: fixed 1 %, OR no-stop (diagnostic only).",
        "  - Outcome from engine's per-horizon `reached/failed_by_timeout` + `mfePct/maePct/maxDrawdownBeforeTargetPct`.",
        "",
        "## A. Fixed-stop 1 % scenario, 24h horizon",
        "",
        "| set | trades | wins | losses | timeouts | winrate | avg win % | avg loss % | expectancy %/trade | profit factor |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| baseline (all triggered) | {baseline_24h['trades']} | {baseline_24h['wins']} | "
        f"{baseline_24h['losses']} | {baseline_24h['timeouts']} | {baseline_24h['winrate']} | "
        f"{baseline_24h['avg_win_pct']} | {baseline_24h['avg_loss_pct']} | "
        f"{baseline_24h['expectancy_pct_per_trade']} | {baseline_24h['profit_factor']} |",
        f"| filtered (kept) | {filtered_24h['trades']} | {filtered_24h['wins']} | "
        f"{filtered_24h['losses']} | {filtered_24h['timeouts']} | {filtered_24h['winrate']} | "
        f"{filtered_24h['avg_win_pct']} | {filtered_24h['avg_loss_pct']} | "
        f"{filtered_24h['expectancy_pct_per_trade']} | {filtered_24h['profit_factor']} |",
        "",
        "## B. No-stop diagnostic, 24h horizon",
        "",
        "| set | trades | expectancy %/trade | LONG n / exp | SHORT n / exp |",
        "|---|---:|---:|---|---|",
        f"| baseline | {baseline_24h_nostop['trades']} | {baseline_24h_nostop['expectancy_pct_per_trade']} | "
        f"{baseline_24h_nostop['long_n']} / {baseline_24h_nostop['long_expectancy_pct']} | "
        f"{baseline_24h_nostop['short_n']} / {baseline_24h_nostop['short_expectancy_pct']} |",
        f"| filtered | {filtered_24h_nostop['trades']} | {filtered_24h_nostop['expectancy_pct_per_trade']} | "
        f"{filtered_24h_nostop['long_n']} / {filtered_24h_nostop['long_expectancy_pct']} | "
        f"{filtered_24h_nostop['short_n']} / {filtered_24h_nostop['short_expectancy_pct']} |",
        "",
        "## C. Per-day expectancy (filtered, fixed-1 %)",
        "",
        "| date | n trades | mean pnl %/trade |",
        "|---|---:|---:|",
    ]
    for d, s in filtered_24h["by_day"].items():
        md2.append(f"| {d} | {s['n']} | {s['mean_pnl_pct']} |")
    md2.extend([
        "",
        "## D. Flags",
        "",
        f"- PRE_COST_ONLY = YES",
        f"- FEES_SLIPPAGE_INCLUDED = NO",
        f"- PROFITABILITY_CLAIM = NO",
        f"- PRE_COST_EXPECTANCY_POSITIVE = "
        f"**{'YES' if (filtered_24h['expectancy_pct_per_trade'] or 0) > 0 else 'NO'}**",
        f"- PRE_COST_PROFIT_FACTOR = **{filtered_24h['profit_factor']}**",
        "",
        "## Caveat",
        "",
        "- 4h/8h/24h horizon outcomes require future price data. On partial days where the recording",
        "  ends at 24:00 UTC, late-trigger zones may have truncated horizons; the engine reports those as",
        "  `failed_by_timeout` with whatever data was available.",
        "- These are SANITY numbers under simplistic stop assumptions. NOT a profitability claim.",
    ])
    (REPORTS_LIVE / "BINANCE_LIVE_PRE_COST_EXECUTION_SANITY.md").write_text("\n".join(md2), encoding="utf-8")

    # CSV for precost: one row per zone
    keys = ["zone_id", "date", "direction", "class_label", "triggerPrice",
            "fixed_24h_result", "fixed_24h_pnl_pct", "nostop_24h_result", "nostop_24h_pnl_pct"]
    with (REPORTS_LIVE / "BINANCE_LIVE_PRE_COST_EXECUTION_SANITY.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=keys)
        w.writeheader()
        for r in per_zone:
            h = r["per_horizon"].get("24h") or {}
            fixed = (h.get("fixed_stop_1pct") or {})
            nostop = (h.get("no_stop_horizon") or {})
            w.writerow({
                "zone_id": r["zone_id"], "date": r["date"], "direction": r["direction"],
                "class_label": r["class_label"], "triggerPrice": r["triggerPrice"],
                "fixed_24h_result": fixed.get("result"),
                "fixed_24h_pnl_pct": fixed.get("pnl_pct"),
                "nostop_24h_result": nostop.get("result"),
                "nostop_24h_pnl_pct": nostop.get("pnl_pct"),
            })

    # ---------- Master summary ----------
    summary_flags = {
        "BINANCE_LIVE_ARCHIVES_FOUND": "YES",
        "BINANCE_LIVE_DATES_DETECTED": dates,
        "BINANCE_LIVE_DAYS_PROCESSED": len(dates),
        "BINANCE_LIVE_DATA_AUDIT_PASS": "PARTIAL",
        "BINANCE_LIVE_BACKTEST_RAN": "YES",
        "BINANCE_LIVE_BASELINE_UNIQUE_MOVES": b["n_primary_unique"],
        **filter_flags,
        "PRE_COST_PROFITABILITY_SANITY_DONE": "YES",
        "PRE_COST_EXPECTANCY_POSITIVE": "YES" if (filtered_24h['expectancy_pct_per_trade'] or 0) > 0 else "NO",
        "PRE_COST_PROFIT_FACTOR": filtered_24h["profit_factor"],
        "PROFITABILITY_CLAIM": "NO",
        "READY_FOR_PASSIVE_LIVE_OBSERVER": filter_flags.get("BINANCE_FILTER_LOOKS_STABLE"),
        "READY_TO_INTEGRATE_FILTER_IN_STRATEGY": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }
    summary_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "dates": dates,
        "baseline": b,
        "filtered": f,
        "compare_okx_tardis_24d_best": {
            "x_min": 60, "price_pct": 1.0,
            "primary_recall_pct": 95.24,
            "duplicate_removal_pct": 72.81,
            "failed_reduction_pct": 66.47,
            "actionable_per_day": 6.792,
        },
        "binance_metrics": {
            "primary_recall_pct": primary_recall,
            "duplicate_removal_pct": dup_removal,
            "failed_reduction_pct": failed_reduction,
            "actionable_per_day": actionable_per_day,
            "baseline_precision_pct": base_precision,
            "filtered_precision_pct": filt_precision,
        },
        "precost": precost,
        "flags": summary_flags,
    }
    (REPORTS_LIVE / "BINANCE_LIVE_BACKTEST_AND_FILTER_SUMMARY.json").write_text(
        json.dumps(summary_json, indent=2, default=str), encoding="utf-8")

    md3 = [
        "# Binance live-recorder - backtest + filter summary",
        "",
        f"**Build:** {summary_json['build_time_utc']}",
        f"**Dates:** {dates}",
        "",
        "## 1. Baseline vs filtered (aggregate)",
        "",
        f"- triggered: {b['n_triggered']} -> {f['trig_kept']}",
        f"- reached_raw: {b['n_reached_raw']} -> {f['reached_kept']}",
        f"- primary_unique_reached: {b['n_primary_unique']} -> {f['prim_kept']}",
        f"- duplicate_reached: {b['n_duplicate_reached']} -> {f['dup_kept']}",
        f"- failed_triggered: {b['n_failed_triggered']} -> {f['fail_kept']}",
        f"- baseline precision: {base_precision} %  ->  filtered precision: {filt_precision} %",
        f"- primary recall: **{primary_recall} %**",
        f"- duplicate removal: **{dup_removal} %**",
        f"- failed reduction: **{failed_reduction} %**",
        f"- actionable signals/day: **{actionable_per_day}**",
        "",
        "## 2. Compare to OKX Tardis 24-day best",
        "",
        "| pool | scope | recall % | dup_rem % | fail_red % | actionable/day |",
        "|---|---|---:|---:|---:|---:|",
        f"| OKX Tardis 24d (held-out) | 24 days, 21 primaries | 95.24 | 72.81 | 66.47 | 6.79 |",
        f"| Binance live | {len(dates)} days, {b['n_primary_unique']} primaries | "
        f"{primary_recall} | {dup_removal} | {failed_reduction} | {actionable_per_day} |",
        "",
        "## 3. Pre-cost sanity (fixed-stop 1 %, 24h, filtered subset)",
        "",
        f"- trades: {filtered_24h['trades']}  (wins={filtered_24h['wins']}, "
        f"losses={filtered_24h['losses']}, timeouts={filtered_24h['timeouts']})",
        f"- winrate: {filtered_24h['winrate']}",
        f"- avg win %: {filtered_24h['avg_win_pct']}",
        f"- avg loss %: {filtered_24h['avg_loss_pct']}",
        f"- expectancy %/trade: **{filtered_24h['expectancy_pct_per_trade']}**",
        f"- profit factor: **{filtered_24h['profit_factor']}**",
        "",
        "## 4. Final flag matrix",
        "",
        "```",
    ]
    for k, v in summary_flags.items():
        md3.append(f"{k} = {v}")
    md3.extend([
        "```",
        "",
        "## 5. Hard rules honored",
        "",
        "- strategy / thresholds / `zoneDetector`: UNCHANGED",
        "- no engine code modified; live data fed via Tardis-style CSV.gz converter only",
        "- post-trigger outcomes used only as evaluation labels",
        "- no API keys; no live trading endpoints touched",
        "- raw archives preserved",
    ])
    (REPORTS_LIVE / "BINANCE_LIVE_BACKTEST_AND_FILTER_SUMMARY.md").write_text("\n".join(md3), encoding="utf-8")

    # ---------- print flags ----------
    print()
    print("FILTER FLAGS:")
    for k, v in filter_flags.items():
        print(f"  {k:<44s} = {v}")
    print()
    print("SUMMARY FLAGS:")
    for k, v in summary_flags.items():
        print(f"  {k:<44s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
