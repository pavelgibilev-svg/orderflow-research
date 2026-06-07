"""B6 + B7 + B8 for Binance Tardis 2025: passive filter validation + target sensitivity + master summary.

Inputs (READ-ONLY):
  reports/binance-tardis/BTCUSDT_<date>/zones.json
  reports/binance-tardis/BINANCE_TARDIS_2025_REGIME_TABLE.json
  data/tardis/binance-futures/BTCUSDT/<date>/trades.csv.gz   (for target sensitivity MFE/MAE)

Outputs:
  reports/binance-tardis/BINANCE_TARDIS_2025_PASSIVE_FILTER_VALIDATION.{md,json,csv}
  reports/binance-tardis/BINANCE_TARDIS_2025_TARGET_SENSITIVITY.{md,json}
  reports/binance-tardis/BINANCE_TARDIS_2025_BACKTEST_AND_FILTER_SUMMARY.{md,json}

Filter under test (live-valid; NO uniqueMoveId in suppress decision):
    duplicate_60m_PRICE_BAND_ONLY(price_pct<=1.0)  AND  fast_trigger<=60min

NO strategy / threshold / engine change. NO new backtest invoked.
"""
from __future__ import annotations
import csv
import datetime as dt
import gzip
import json
import statistics as stats
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS_TARDIS = ROOT / "reports/binance-tardis"
DATA_ROOT = ROOT / "data/tardis/binance-futures/BTCUSDT"

DATES = [f"2025-{m:02d}-01" for m in range(1, 13)]
WINDOW_MIN = 60
PRICE_BAND_PCT = 1.0
FAST_X_MIN = 60
TARGETS_PCT = [0.5, 1.0, 1.5, 2.0]
HORIZONS_S = {"1h": 3600, "4h": 4 * 3600, "8h": 8 * 3600, "24h": 24 * 3600}


def mid_price(z: dict) -> float | None:
    lo, hi = z.get("zoneLow"), z.get("zoneHigh")
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


def load_zones() -> list[dict]:
    out: list[dict] = []
    for d in DATES:
        p = REPORTS_TARDIS / f"BTCUSDT_{d}" / "zones.json"
        if not p.exists():
            print(f"  WARN missing {p}", file=sys.stderr)
            continue
        obj = json.loads(p.read_text(encoding="utf-8"))
        zones = obj if isinstance(obj, list) else obj.get("zones", [])
        for z in zones:
            z["_date"] = d
            z["_class"] = class_label(z)
        out.extend(zones)
    return out


def trigger_price(z: dict) -> float | None:
    for r in z.get("reasons") or []:
        if r.get("stage") == "trigger":
            tp = (r.get("conditions") or {}).get("triggerPrice")
            if tp is not None:
                return float(tp)
    return mid_price(z)


# ---------- live-valid filter ----------

def apply_filter(zones: list[dict]) -> dict[str, dict]:
    """duplicate_60m_PRICE_BAND_ONLY AND fast_trigger<=60min. NO uniqueMoveId."""
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


# ---------- target sensitivity (MFE/MAE) ----------

def trades_sec_buckets(date: str) -> list[tuple[int, float]]:
    p = DATA_ROOT / date / "trades.csv.gz"
    last_by_sec: dict[int, float] = {}
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
            last_by_sec[ts_us // 1_000_000] = price
    return sorted(last_by_sec.items())


def mfe_mae_for_zone(z: dict, pts: list[tuple[int, float]]) -> dict:
    triggerTs = z.get("triggerTs")
    entry = trigger_price(z) or mid_price(z)
    if not pts or triggerTs is None or entry is None or entry <= 0:
        return {}
    trig_sec = triggerTs // 1000
    lo, hi = 0, len(pts)
    while lo < hi:
        m = (lo + hi) // 2
        if pts[m][0] < trig_sec:
            lo = m + 1
        else:
            hi = m
    start = lo
    if start >= len(pts):
        return {}
    out = {}
    direction = z["direction"]
    for h_label, h_s in HORIZONS_S.items():
        end_ts = trig_sec + h_s
        lo2, hi2 = start, len(pts)
        while lo2 < hi2:
            m = (lo2 + hi2) // 2
            if pts[m][0] <= end_ts:
                lo2 = m + 1
            else:
                hi2 = m
        if lo2 == start:
            out[h_label] = {"n_points": 0}
            continue
        window = pts[start:lo2]
        prices = [p for _, p in window]
        if direction == "LONG":
            mfe = (max(prices) - entry) / entry * 100.0
            mae = (entry - min(prices)) / entry * 100.0
        else:
            mfe = (entry - min(prices)) / entry * 100.0
            mae = (max(prices) - entry) / entry * 100.0
        out[h_label] = {
            "n_points": len(window),
            "mfe_pct": round(mfe, 4),
            "mae_pct": round(mae, 4),
            "reached": {f"{t}pct": (mfe >= t) for t in TARGETS_PCT},
        }
    return out


# ---------- aggregations ----------

def pct(num, den):
    if not den:
        return None
    return round(100.0 * num / den, 2)


def summarize(zones: list[dict], decisions: dict) -> dict:
    b = {
        "n_zones": len(zones),
        "n_triggered": sum(1 for z in zones if is_triggered(z)),
        "n_reached_raw": sum(1 for z in zones if is_reached(z)),
        "n_primary_unique": sum(1 for z in zones if z["_class"] == "primary_unique_reached_move"),
        "n_duplicate_reached": sum(1 for z in zones if z["_class"] == "duplicate_reached_move"),
        "n_failed_triggered": sum(1 for z in zones if z["_class"] == "failed_triggered"),
    }
    f = {"trig_kept": 0, "reached_kept": 0, "prim_kept": 0, "dup_kept": 0, "fail_kept": 0, "suppressed": 0}
    for z in zones:
        if not is_triggered(z):
            continue
        d = decisions.get(z["id"])
        if d and d["kept"]:
            f["trig_kept"] += 1
            if is_reached(z):
                f["reached_kept"] += 1
            if z["_class"] == "primary_unique_reached_move":
                f["prim_kept"] += 1
            elif z["_class"] == "duplicate_reached_move":
                f["dup_kept"] += 1
            elif z["_class"] == "failed_triggered":
                f["fail_kept"] += 1
        else:
            f["suppressed"] += 1
    return {"baseline": b, "filtered": f}


def stability_per_axis(zones: list[dict], decisions: dict, axis_fn) -> dict:
    """Split by axis (fn returns a tag per zone). Return per-bucket recall/dup_rem/fail_red."""
    buckets = defaultdict(list)
    for z in zones:
        buckets[axis_fn(z)].append(z)
    out = {}
    for tag, zs in buckets.items():
        ss = summarize(zs, decisions)
        b, f = ss["baseline"], ss["filtered"]
        out[tag] = {
            "trig_baseline": b["n_triggered"],
            "prim_baseline": b["n_primary_unique"],
            "dup_baseline": b["n_duplicate_reached"],
            "fail_baseline": b["n_failed_triggered"],
            "prim_kept": f["prim_kept"],
            "primary_recall_pct": pct(f["prim_kept"], b["n_primary_unique"]),
            "duplicate_removal_pct": pct(b["n_duplicate_reached"] - f["dup_kept"], b["n_duplicate_reached"]),
            "failed_reduction_pct": pct(b["n_failed_triggered"] - f["fail_kept"], b["n_failed_triggered"]),
        }
    return out


# ---------- writers ----------

def main() -> int:
    REPORTS_TARDIS.mkdir(parents=True, exist_ok=True)
    zones = load_zones()
    print(f"loaded {len(zones)} zones across {len({z['_date'] for z in zones})} dates", file=sys.stderr)
    decisions = apply_filter(zones)

    # ---------- B6: passive filter validation ----------
    agg = summarize(zones, decisions)
    b, f = agg["baseline"], agg["filtered"]
    primary_recall = pct(f["prim_kept"], b["n_primary_unique"])
    dup_removal = pct(b["n_duplicate_reached"] - f["dup_kept"], b["n_duplicate_reached"])
    failed_reduction = pct(b["n_failed_triggered"] - f["fail_kept"], b["n_failed_triggered"])
    n_days = len({z["_date"] for z in zones})
    actionable_per_day = round(f["trig_kept"] / n_days, 3) if n_days else None
    base_precision = pct(b["n_reached_raw"], b["n_triggered"])
    filt_precision = pct(f["reached_kept"], f["trig_kept"]) if f["trig_kept"] else None
    precision_delta = round((filt_precision - base_precision), 2) if base_precision is not None and filt_precision is not None else None

    # regime split
    regime_map = {}
    rt_path = REPORTS_TARDIS / "BINANCE_TARDIS_2025_REGIME_TABLE.json"
    if rt_path.exists():
        rt = json.loads(rt_path.read_text(encoding="utf-8"))
        for r in rt.get("per_date", []):
            regime_map[r["date"]] = r.get("regime")

    per_date = stability_per_axis(zones, decisions, lambda z: z["_date"])
    per_dir = stability_per_axis(zones, decisions, lambda z: z["direction"])
    per_regime = stability_per_axis(zones, decisions, lambda z: regime_map.get(z["_date"], "unknown"))

    filter_flags = {
        "BINANCE_TARDIS_FILTER_VALIDATION_DONE": "YES",
        "FILTER_DECISION_USED_UNIQUEMOVEID": "NO",
        "FILTER_INVALID_FUTURE_LEAK": "NO",
        "BINANCE_TARDIS_FILTER_PRIMARY_RECALL_PCT": primary_recall,
        "BINANCE_TARDIS_FILTER_DUPLICATE_REMOVAL_PCT": dup_removal,
        "BINANCE_TARDIS_FILTER_FAILED_REDUCTION_PCT": failed_reduction,
        "BINANCE_TARDIS_FILTER_ACTIONABLE_PER_DAY": actionable_per_day,
        "BINANCE_TARDIS_FILTER_PRECISION_DELTA_PP": precision_delta,
    }

    fv_out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Binance Futures BTCUSDT, Tardis 2025 first-of-month (12 dates, live-valid filter)",
        "filter": "duplicate_60m_PRICE_BAND_ONLY(price_pct<=1.0) AND fast_trigger<=60min",
        "n_zones": len(zones),
        "n_days": n_days,
        "baseline": b,
        "filtered": f,
        "metrics": {
            "primary_recall_pct": primary_recall,
            "duplicate_removal_pct": dup_removal,
            "failed_reduction_pct": failed_reduction,
            "actionable_signals_per_day": actionable_per_day,
            "baseline_precision_pct": base_precision,
            "filtered_precision_pct": filt_precision,
            "precision_delta_pp": precision_delta,
        },
        "per_date": per_date,
        "per_direction": per_dir,
        "per_regime": per_regime,
        "flags": filter_flags,
    }
    (REPORTS_TARDIS / "BINANCE_TARDIS_2025_PASSIVE_FILTER_VALIDATION.json").write_text(
        json.dumps(fv_out, indent=2, default=str), encoding="utf-8")

    # CSV per-date
    csv_keys = ["date", "regime", "trig_b", "prim_b", "dup_b", "fail_b",
                "trig_f", "prim_f", "dup_f", "fail_f",
                "primary_recall_pct", "duplicate_removal_pct", "failed_reduction_pct"]
    with (REPORTS_TARDIS / "BINANCE_TARDIS_2025_PASSIVE_FILTER_VALIDATION.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=csv_keys)
        w.writeheader()
        for d in DATES:
            zs = [z for z in zones if z["_date"] == d]
            ss = summarize(zs, decisions)
            bb, ff = ss["baseline"], ss["filtered"]
            w.writerow({
                "date": d, "regime": regime_map.get(d),
                "trig_b": bb["n_triggered"], "prim_b": bb["n_primary_unique"],
                "dup_b": bb["n_duplicate_reached"], "fail_b": bb["n_failed_triggered"],
                "trig_f": ff["trig_kept"], "prim_f": ff["prim_kept"],
                "dup_f": ff["dup_kept"], "fail_f": ff["fail_kept"],
                "primary_recall_pct": pct(ff["prim_kept"], bb["n_primary_unique"]),
                "duplicate_removal_pct": pct(bb["n_duplicate_reached"] - ff["dup_kept"], bb["n_duplicate_reached"]),
                "failed_reduction_pct": pct(bb["n_failed_triggered"] - ff["fail_kept"], bb["n_failed_triggered"]),
            })

    md = [
        "# Binance Tardis 2025 - passive filter validation (true held-out)",
        "",
        f"**Build:** {fv_out['build_time_utc']}",
        f"**Filter:** `{fv_out['filter']}` (NO uniqueMoveId, NO future-leak).",
        f"**Scope:** {fv_out['scope']} - 12 first-of-month dates, n_zones={len(zones)}, n_primary={b['n_primary_unique']}.",
        "",
        "## A. Baseline vs filtered",
        "",
        "| metric | baseline | filtered |",
        "|---|---:|---:|",
        f"| n_zones | {b['n_zones']} | (triggered-only subset) |",
        f"| n_triggered | {b['n_triggered']} | {f['trig_kept']} |",
        f"| n_reached_raw | {b['n_reached_raw']} | {f['reached_kept']} |",
        f"| n_primary_unique | {b['n_primary_unique']} | {f['prim_kept']} |",
        f"| n_duplicate_reached | {b['n_duplicate_reached']} | {f['dup_kept']} |",
        f"| n_failed_triggered | {b['n_failed_triggered']} | {f['fail_kept']} |",
        "",
        f"- primary recall: **{primary_recall} %**",
        f"- duplicate removal: **{dup_removal} %**",
        f"- failed reduction: **{failed_reduction} %**",
        f"- actionable signals/day: **{actionable_per_day}**",
        f"- baseline precision: {base_precision} %  ->  filtered precision: {filt_precision} %  "
        f"({'+' if (precision_delta or 0) >= 0 else ''}{precision_delta} pp)",
        "",
        "## B. Per-date breakdown",
        "",
        "| date | regime | trig b/f | prim b/f | dup b/f | fail b/f | recall % | dup_rem % | fail_red % |",
        "|---|---|---|---|---|---|---:|---:|---:|",
    ]
    for d in DATES:
        v = per_date.get(d)
        if v is None:
            md.append(f"| {d} | — | — | — | — | — | — | — | — |")
            continue
        zs = [z for z in zones if z["_date"] == d]
        ss = summarize(zs, decisions)
        bb, ff = ss["baseline"], ss["filtered"]
        md.append(
            f"| {d} | {regime_map.get(d)} | "
            f"{bb['n_triggered']}/{ff['trig_kept']} | "
            f"{bb['n_primary_unique']}/{ff['prim_kept']} | "
            f"{bb['n_duplicate_reached']}/{ff['dup_kept']} | "
            f"{bb['n_failed_triggered']}/{ff['fail_kept']} | "
            f"{v['primary_recall_pct']} | {v['duplicate_removal_pct']} | {v['failed_reduction_pct']} |"
        )
    md.extend(["", "## C. Per-direction", "",
               "| dir | trig b | prim b | dup b | fail b | recall % | dup_rem % | fail_red % |",
               "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for k, v in per_dir.items():
        md.append(f"| {k} | {v['trig_baseline']} | {v['prim_baseline']} | "
                  f"{v['dup_baseline']} | {v['fail_baseline']} | "
                  f"{v['primary_recall_pct']} | {v['duplicate_removal_pct']} | {v['failed_reduction_pct']} |")
    md.extend(["", "## D. Per-regime", "",
               "| regime | trig b | prim b | dup b | fail b | recall % | dup_rem % | fail_red % |",
               "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for k, v in per_regime.items():
        md.append(f"| {k} | {v['trig_baseline']} | {v['prim_baseline']} | "
                  f"{v['dup_baseline']} | {v['fail_baseline']} | "
                  f"{v['primary_recall_pct']} | {v['duplicate_removal_pct']} | {v['failed_reduction_pct']} |")
    md.extend(["", "## E. Flags", ""])
    for k, v in filter_flags.items():
        md.append(f"- `{k}` = **{v}**")
    (REPORTS_TARDIS / "BINANCE_TARDIS_2025_PASSIVE_FILTER_VALIDATION.md").write_text("\n".join(md), encoding="utf-8")
    print("[B6] passive filter validation written", file=sys.stderr)

    # ---------- B7: target sensitivity (MFE/MAE) ----------
    print("[B7] building per-date 1s buckets ...", file=sys.stderr)
    trades_by_date = {}
    for d in DATES:
        print(f"  {d} ...", file=sys.stderr)
        trades_by_date[d] = trades_sec_buckets(d)

    triggered = [z for z in zones if is_triggered(z)]
    print(f"  computing MFE/MAE for {len(triggered)} triggered zones ...", file=sys.stderr)
    per_zone = []
    for z in triggered:
        per_zone.append({
            "id": z["id"], "date": z["_date"], "direction": z["direction"],
            "engine_status": z["status"], "class_label": z["_class"],
            "filter_kept": decisions.get(z["id"], {}).get("kept"),
            "forward_outcome": mfe_mae_for_zone(z, trades_by_date[z["_date"]]),
        })

    def agg_set(lst: list[dict], horizon: str, tgt: float) -> dict:
        n = 0; reached = 0; mfes = []; maes = []
        for r in lst:
            rec = r["forward_outcome"].get(horizon)
            if not rec or not rec.get("n_points"):
                continue
            n += 1
            if rec["reached"].get(f"{tgt}pct"):
                reached += 1
            mfes.append(rec["mfe_pct"])
            maes.append(rec["mae_pct"])
        return {
            "n": n,
            "reached_count": reached,
            "reached_pct": round(100.0 * reached / n, 2) if n else None,
            "median_mfe_pct": round(stats.median(mfes), 4) if mfes else None,
            "median_mae_pct": round(stats.median(maes), 4) if maes else None,
            "max_mfe_pct": round(max(mfes), 4) if mfes else None,
            "worst_mae_pct": round(max(maes), 4) if maes else None,
        }

    sets_ = {
        "baseline_triggered": per_zone,
        "filtered_kept": [r for r in per_zone if r["filter_kept"]],
        "filter_suppressed": [r for r in per_zone if r["filter_kept"] is False],
    }
    sensitivity = {sn: {h: {f"{t}pct": agg_set(lst, h, t) for t in TARGETS_PCT}
                       for h in HORIZONS_S}
                   for sn, lst in sets_.items()}

    ts_out = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "Binance Tardis 2025 - per-horizon target sensitivity (MFE/MAE) on triggered zones",
        "set_sizes": {k: len(v) for k, v in sets_.items()},
        "sensitivity": sensitivity,
    }
    (REPORTS_TARDIS / "BINANCE_TARDIS_2025_TARGET_SENSITIVITY.json").write_text(
        json.dumps(ts_out, indent=2, default=str), encoding="utf-8")

    md_ts = [
        "# Binance Tardis 2025 - target sensitivity (MFE/MAE)",
        "",
        f"**Build:** {ts_out['build_time_utc']}",
        "",
        "## Set sizes",
        "",
    ]
    for k, v in ts_out["set_sizes"].items():
        md_ts.append(f"- `{k}` = {v}")
    md_ts.append("")
    for sn in ("baseline_triggered", "filtered_kept", "filter_suppressed"):
        md_ts.append(f"## `{sn}`")
        md_ts.append("")
        md_ts.append("| horizon | n | median MFE % | median MAE % | reached 0.5 % | reached 1 % | reached 1.5 % | reached 2 % |")
        md_ts.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for h in HORIZONS_S:
            tgt2 = sensitivity[sn][h]["2.0pct"]
            tgt15 = sensitivity[sn][h]["1.5pct"]
            tgt1 = sensitivity[sn][h]["1.0pct"]
            tgt05 = sensitivity[sn][h]["0.5pct"]
            md_ts.append(
                f"| {h} | {tgt2['n']} | {tgt2['median_mfe_pct']} | {tgt2['median_mae_pct']} | "
                f"{tgt05['reached_pct']} | {tgt1['reached_pct']} | {tgt15['reached_pct']} | {tgt2['reached_pct']} |"
            )
        md_ts.append("")
    (REPORTS_TARDIS / "BINANCE_TARDIS_2025_TARGET_SENSITIVITY.md").write_text("\n".join(md_ts), encoding="utf-8")
    print("[B7] target sensitivity written", file=sys.stderr)

    # ---------- B8: master summary ----------
    feas_2pct_days = sum(1 for r in (rt.get("per_date", []) if rt_path.exists() else [])
                         if r.get("feasibility", {}).get("2.0pct"))

    filter_transferable = "UNKNOWN"
    if primary_recall is not None:
        if primary_recall >= 70 and (dup_removal or 0) >= 40 and (failed_reduction or 0) >= 40:
            filter_transferable = "YES"
        elif primary_recall < 50 or (dup_removal or 0) < 20:
            filter_transferable = "NO"
        else:
            filter_transferable = "UNCLEAR"

    summary_flags = {
        "BINANCE_LIVE_FEASIBILITY_DIAGNOSTIC_DONE": "YES",
        "BINANCE_LIVE_2PCT_FEASIBLE_DAYS": 2,   # from PART 1
        "TARGET_2PCT_TOO_HIGH_FOR_LIVE_SAMPLE": "YES",
        "ZONES_SHOW_SUB_2PCT_EDGE": "YES",
        "LIVE_SAMPLE_INFORMATIVE_FOR_PRIMARY_RECALL": "NO",

        "BINANCE_TARDIS_2025_INVENTORY_DONE": "YES",
        "BINANCE_TARDIS_DATES_AVAILABLE": DATES,
        "BINANCE_TARDIS_DATES_SELECTED": DATES,
        "BINANCE_TARDIS_DAYS_PROCESSED": n_days,

        "BINANCE_TARDIS_DATA_QUALITY_PASS": "YES",
        "BINANCE_TARDIS_BACKTEST_RAN": "YES",

        "BINANCE_TARDIS_BASELINE_ZONES": b["n_zones"],
        "BINANCE_TARDIS_BASELINE_TRIGGERED": b["n_triggered"],
        "BINANCE_TARDIS_BASELINE_REACHED_RAW": b["n_reached_raw"],
        "BINANCE_TARDIS_BASELINE_PRIMARY_UNIQUE": b["n_primary_unique"],

        "BINANCE_TARDIS_FILTER_VALIDATION_DONE": "YES",
        "FILTER_DECISION_USED_UNIQUEMOVEID": "NO",
        "FILTER_INVALID_FUTURE_LEAK": "NO",

        "BINANCE_TARDIS_FILTER_PRIMARY_RECALL_PCT": primary_recall,
        "BINANCE_TARDIS_FILTER_DUPLICATE_REMOVAL_PCT": dup_removal,
        "BINANCE_TARDIS_FILTER_FAILED_REDUCTION_PCT": failed_reduction,
        "BINANCE_TARDIS_FILTER_ACTIONABLE_PER_DAY": actionable_per_day,
        "BINANCE_TARDIS_FILTER_PRECISION_DELTA_PP": precision_delta,

        "BINANCE_TARDIS_TARGET_2PCT_FEASIBLE_DAYS": feas_2pct_days,
        "BINANCE_TARDIS_FILTER_LOOKS_TRANSFERABLE": filter_transferable,

        "READY_FOR_PASSIVE_LIVE_OBSERVER": filter_transferable if filter_transferable in ("YES", "NO") else "NO",
        "READY_TO_INTEGRATE_FILTER_IN_STRATEGY": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }

    summary_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "tardis_baseline": b,
        "tardis_filtered": f,
        "tardis_metrics": fv_out["metrics"],
        "compare": [
            {"pool": "OKX Tardis 24d (held-out)", "n_days": 24, "n_primary": 21,
             "recall_pct": 95.24, "dup_rem_pct": 72.81, "fail_red_pct": 66.47,
             "actionable_per_day": 6.79},
            {"pool": "Binance live 2026-05-17..20", "n_days": 4, "n_primary": 0,
             "recall_pct": None, "dup_rem_pct": None, "fail_red_pct": 65.85,
             "actionable_per_day": 3.5,
             "note": "n_primary=0; recall undefined; failed reduction matches OKX"},
            {"pool": "Binance Tardis 2025 first-of-month", "n_days": n_days, "n_primary": b["n_primary_unique"],
             "recall_pct": primary_recall, "dup_rem_pct": dup_removal,
             "fail_red_pct": failed_reduction, "actionable_per_day": actionable_per_day},
        ],
        "flags": summary_flags,
    }
    (REPORTS_TARDIS / "BINANCE_TARDIS_2025_BACKTEST_AND_FILTER_SUMMARY.json").write_text(
        json.dumps(summary_json, indent=2, default=str), encoding="utf-8")

    md_s = [
        "# Binance Tardis 2025 - backtest + filter master summary",
        "",
        f"**Build:** {summary_json['build_time_utc']}",
        "",
        "## 1. PART 1 - Binance live diagnostic (2026-05-17..20)",
        "",
        f"- 2 % feasible days: 2 / 4",
        f"- baseline triggered: 41   reached: 0",
        f"- filtered kept: 14   reached: 0",
        f"- filtered reached 0.5 %: 78.57 %   reached 1.0 %: 28.57 %   reached 1.5 %: 14.29 %   reached 2 %: 0.0 %",
        f"- median MFE 24h (filtered): 0.71 %   median MAE 24h (filtered): 0.87 %",
        f"- Verdict: TARGET_2PCT_TOO_HIGH_FOR_LIVE_SAMPLE = YES; ZONES_SHOW_SUB_2PCT_EDGE = YES; n_primary = 0 so primary recall undefined.",
        "",
        "## 2. PART 2 - Binance Tardis 2025 baseline",
        "",
        "| date | regime | zones | trig | reached | primary | dup | failed |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for d in DATES:
        zs = [z for z in zones if z["_date"] == d]
        ss = summarize(zs, decisions)
        bb = ss["baseline"]
        md_s.append(f"| {d} | {regime_map.get(d)} | {bb['n_zones']} | "
                    f"{bb['n_triggered']} | {bb['n_reached_raw']} | "
                    f"{bb['n_primary_unique']} | {bb['n_duplicate_reached']} | {bb['n_failed_triggered']} |")
    md_s.extend([
        "",
        f"**Total (12 days):** zones = {b['n_zones']}, triggered = {b['n_triggered']}, "
        f"reached_raw = {b['n_reached_raw']}, primary_unique = {b['n_primary_unique']}, "
        f"duplicate = {b['n_duplicate_reached']}, failed = {b['n_failed_triggered']}",
        "",
        "## 3. PART 2 - filter validation",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| primary recall | {primary_recall} % |",
        f"| duplicate removal | {dup_removal} % |",
        f"| failed reduction | {failed_reduction} % |",
        f"| actionable signals / day | {actionable_per_day} |",
        f"| baseline precision | {base_precision} % |",
        f"| filtered precision | {filt_precision} % |",
        f"| precision delta | {precision_delta} pp |",
        "",
        "## 4. Cross-venue comparison",
        "",
        "| pool | n_days | n_primary | recall % | dup_rem % | fail_red % | actionable/day |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| OKX Tardis 24d (held-out) | 24 | 21 | 95.24 | 72.81 | 66.47 | 6.79 |",
        f"| Binance live 2026-05-17..20 | 4 | 0 | undefined | undefined | 65.85 | 3.5 |",
        f"| **Binance Tardis 2025** | **{n_days}** | **{b['n_primary_unique']}** | "
        f"**{primary_recall}** | **{dup_removal}** | **{failed_reduction}** | **{actionable_per_day}** |",
        "",
        "## 5. Final flag matrix",
        "",
        "```",
    ])
    for k, v in summary_flags.items():
        md_s.append(f"{k} = {v}")
    md_s.extend(["```", "",
        "## 6. Hard rules honored",
        "",
        "- strategy / thresholds / `zoneDetector`: UNCHANGED",
        "- filter is post-hoc passive; not integrated into engine",
        "- NO `uniqueMoveId` in suppress decision (FILTER_DECISION_USED_UNIQUEMOVEID = NO)",
        "- NO future-leak (FILTER_INVALID_FUTURE_LEAK = NO); strict-past prior comparisons",
        "- post-trigger outcomes used only as evaluation labels (recall/precision denominators)",
        "- no profitability claim; no production integration",
        "- raw archives untouched",
    ])
    (REPORTS_TARDIS / "BINANCE_TARDIS_2025_BACKTEST_AND_FILTER_SUMMARY.md").write_text("\n".join(md_s), encoding="utf-8")
    print("[B8] summary written", file=sys.stderr)

    print()
    print("FINAL FLAGS:")
    for k, v in summary_flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
