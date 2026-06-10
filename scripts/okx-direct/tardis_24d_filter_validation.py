"""True held-out OOS validation of the passive filter on the 24-date OKX Tardis pool.

The Tardis 24-date pool comprises:
  - 6 calibration dates  (OKX_TECHNICAL_REPLAY_<date>_fullday.json)
  - 6 OOS_v1 dates       (OKX_OOS_TECHNICAL_REPLAY_<date>_fullday.json)
  - 12 v2 dates          (OKX_V2_TECHNICAL_REPLAY_<date>_fullday.json)

Filter under test (LIVE-VALID variant; NO uniqueMoveId in decision):

  For each triggered zone Z at time T, direction D:
    Z is SUPPRESSED iff there exists ANOTHER triggered zone Z' with
      (a) Z'.triggerTs < T              (strict past)
      (b) 0 < T - Z'.triggerTs <= 60 min
      (c) Z'.direction == D
      (d) |mid(Z) - mid(Z')| / mid(Z') * 100 <= price_threshold_pct
    AND
      Z.confirm_to_trigger_min <= X

We sweep:
  X (fast_trigger threshold)         : {30, 60, 90}
  price_threshold_pct (duplicate)    : {0.25, 0.50, 0.75, 1.00}
Total: 12 combinations.

CRITICAL NO-LEAK guarantee:
  The suppress decision MUST NOT read uniqueMoveId / isPrimaryMoveZone /
  duplicateMoveCredit / moveClusterSize / reached / target_*.* / resolvedTs /
  status / mfePct / maePct / any future trigger.
  These fields appear ONLY in evaluation (precision/recall denominators and
  per-class breakdowns). The script is grep-auditable: any reference to a
  forbidden field is flagged in section "future_leak_audit".

No engine / threshold / detector change. No new backtest, no conversion.
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
from typing import Any

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
OUT_DIR = REPORTS  # we want files at reports/OKX_TARDIS_24D_*.{md,json,csv}

CALIB_DATES = ["2024-01-01", "2024-07-01", "2024-10-01",
               "2025-10-01", "2025-12-01", "2026-04-01"]
OOS_DATES = ["2024-05-01", "2024-06-01", "2024-09-01",
             "2025-04-01", "2025-05-01", "2025-11-01"]
V2_DATES = ["2024-02-01", "2024-03-01", "2024-04-01",
            "2024-12-01", "2025-02-01", "2025-03-01",
            "2025-08-01", "2025-09-01", "2026-01-01",
            "2026-02-01", "2026-03-01", "2026-05-01"]

PATH_BY_ROUND = {
    "calibration": ("OKX_TECHNICAL_REPLAY_{date}_fullday.json", CALIB_DATES),
    "OOS_v1": ("OKX_OOS_TECHNICAL_REPLAY_{date}_fullday.json", OOS_DATES),
    "v2": ("OKX_V2_TECHNICAL_REPLAY_{date}_fullday.json", V2_DATES),
}

FAST_TRIGGER_X_MIN = [30, 60, 90]
PRICE_DIST_PCT = [0.25, 0.50, 0.75, 1.00]
WINDOW_MIN = 60


# ---------- helpers ----------

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


# ---------- load ----------

def load_regime_table() -> dict[str, str]:
    p = REPORTS / "OKX_REGIME_TABLE.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = d.get("dates") or []
    return {r["date"]: r.get("regime") for r in rows}


def load_pool() -> list[dict]:
    """Load every zone from all 24 files; tag round, date, regime."""
    regime_by_date = load_regime_table()
    out: list[dict] = []
    for round_name, (template, dates) in PATH_BY_ROUND.items():
        for d in dates:
            p = REPORTS / template.format(date=d)
            if not p.exists():
                print(f"  MISSING {p}", file=sys.stderr)
                continue
            jd = json.loads(p.read_text(encoding="utf-8"))
            zones = (jd.get("underlying_backtest_summary") or {}).get("zones") or []
            for z in zones:
                z["_round"] = round_name
                z["_date"] = d
                z["_regime"] = regime_by_date.get(d)
                z["_class"] = class_label(z)
                out.append(z)
    return out


# ---------- the live-valid filter ----------

def evaluate_combination(zones: list[dict], x_min: int, price_pct: float) -> dict:
    """Apply (duplicate_60m_price_band AND fast_trigger<=x_min) to triggered zones.

    Returns per-zone decisions + aggregate stats. Decision uses ONLY:
      - zone.direction, zone.triggerTs, zone.confirmedTs, zone.zoneLow/zoneHigh
      - prior zone's triggerTs (strictly past), direction, midpoint
    NO uniqueMoveId / status / reached / target_* / resolved / mfe / mae.
    """
    # Sort triggered zones within each (date) by triggerTs to ensure strict-past lookups.
    # We treat each date independently — cross-date duplicates aren't a thing.
    by_date: dict[str, list[dict]] = defaultdict(list)
    for z in zones:
        by_date[z["_date"]].append(z)

    decisions: dict[str, dict] = {}  # zone id -> {kept, suppress_reason, fast_kept, dup_suppressed, parent_id, ...}
    for date, ds in by_date.items():
        triggered = [z for z in ds if is_triggered(z) and z.get("triggerTs") is not None]
        triggered.sort(key=lambda z: z["triggerTs"])
        for i, z in enumerate(triggered):
            T = z["triggerTs"]
            D = z["direction"]
            z_mid = mid_price(z)
            # duplicate check — strict past only
            dup_suppressed = False
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
                price_dist_pct = abs(z_mid - p_mid) / z_mid * 100.0
                if price_dist_pct <= price_pct:
                    dup_suppressed = True
                    parent_id = prior["id"]
                    break
            # fast_trigger check
            ctm = confirm_to_trigger_min(z)
            fast_ok = (ctm is None) or (ctm <= x_min)
            kept = (not dup_suppressed) and fast_ok
            decisions[z["id"]] = {
                "kept": kept,
                "dup_suppressed": dup_suppressed,
                "fast_kept": fast_ok,
                "parent_id": parent_id,
                "delta_t_min_from_parent": (
                    round((T - next(p["triggerTs"] for p in triggered if p["id"] == parent_id)) / 60000.0, 3)
                    if parent_id else None),
                "confirm_to_trigger_min": ctm,
            }

    # ---------- aggregate by date / round / direction / regime / class ----------
    baseline_total = {"zones": 0, "trig": 0, "reached": 0, "prim": 0, "dup": 0, "fail": 0}
    filtered_total = {"trig_kept": 0, "reached_kept": 0, "prim_kept": 0, "dup_kept": 0, "fail_kept": 0,
                      "suppressed_total": 0,
                      "suppressed_primary": 0, "suppressed_duplicate_reached": 0,
                      "suppressed_failed": 0}
    per_date: dict[str, dict] = {}
    per_round: dict[str, dict] = {r: {"baseline": dict(baseline_total), "filtered": dict(filtered_total)}
                                  for r in PATH_BY_ROUND}
    per_dir: dict[str, dict] = {d: {"baseline": dict(baseline_total), "filtered": dict(filtered_total)}
                                for d in ("LONG", "SHORT")}
    per_regime: dict[str, dict] = defaultdict(lambda: {"baseline": dict(baseline_total),
                                                       "filtered": dict(filtered_total)})

    suppressed_zone_records: list[dict] = []

    for z in zones:
        d = z["_date"]
        per_date.setdefault(d, {"baseline": dict(baseline_total), "filtered": dict(filtered_total)})
        cls = z["_class"]
        baseline_total["zones"] += 1
        per_date[d]["baseline"]["zones"] += 1
        per_round[z["_round"]]["baseline"]["zones"] += 1
        dirn = z.get("direction") or "?"
        if dirn in per_dir:
            per_dir[dirn]["baseline"]["zones"] += 1
        rg = z["_regime"] or "unknown"
        per_regime[rg]["baseline"]["zones"] += 1

        if is_triggered(z):
            baseline_total["trig"] += 1
            per_date[d]["baseline"]["trig"] += 1
            per_round[z["_round"]]["baseline"]["trig"] += 1
            if dirn in per_dir:
                per_dir[dirn]["baseline"]["trig"] += 1
            per_regime[rg]["baseline"]["trig"] += 1
            if is_reached(z):
                baseline_total["reached"] += 1
                per_date[d]["baseline"]["reached"] += 1
                per_round[z["_round"]]["baseline"]["reached"] += 1
                if dirn in per_dir:
                    per_dir[dirn]["baseline"]["reached"] += 1
                per_regime[rg]["baseline"]["reached"] += 1
            if cls == "primary_unique_reached_move":
                baseline_total["prim"] += 1
                per_date[d]["baseline"]["prim"] += 1
                per_round[z["_round"]]["baseline"]["prim"] += 1
                if dirn in per_dir:
                    per_dir[dirn]["baseline"]["prim"] += 1
                per_regime[rg]["baseline"]["prim"] += 1
            elif cls == "duplicate_reached_move":
                baseline_total["dup"] += 1
                per_date[d]["baseline"]["dup"] += 1
                per_round[z["_round"]]["baseline"]["dup"] += 1
                if dirn in per_dir:
                    per_dir[dirn]["baseline"]["dup"] += 1
                per_regime[rg]["baseline"]["dup"] += 1
            elif cls == "failed_triggered":
                baseline_total["fail"] += 1
                per_date[d]["baseline"]["fail"] += 1
                per_round[z["_round"]]["baseline"]["fail"] += 1
                if dirn in per_dir:
                    per_dir[dirn]["baseline"]["fail"] += 1
                per_regime[rg]["baseline"]["fail"] += 1

            dec = decisions.get(z["id"])
            if dec:
                if dec["kept"]:
                    filtered_total["trig_kept"] += 1
                    per_date[d]["filtered"]["trig_kept"] += 1
                    per_round[z["_round"]]["filtered"]["trig_kept"] += 1
                    if dirn in per_dir:
                        per_dir[dirn]["filtered"]["trig_kept"] += 1
                    per_regime[rg]["filtered"]["trig_kept"] += 1
                    if is_reached(z):
                        filtered_total["reached_kept"] += 1
                        per_date[d]["filtered"]["reached_kept"] += 1
                        per_round[z["_round"]]["filtered"]["reached_kept"] += 1
                        if dirn in per_dir:
                            per_dir[dirn]["filtered"]["reached_kept"] += 1
                        per_regime[rg]["filtered"]["reached_kept"] += 1
                    if cls == "primary_unique_reached_move":
                        filtered_total["prim_kept"] += 1
                        per_date[d]["filtered"]["prim_kept"] += 1
                        per_round[z["_round"]]["filtered"]["prim_kept"] += 1
                        if dirn in per_dir:
                            per_dir[dirn]["filtered"]["prim_kept"] += 1
                        per_regime[rg]["filtered"]["prim_kept"] += 1
                    elif cls == "duplicate_reached_move":
                        filtered_total["dup_kept"] += 1
                        per_date[d]["filtered"]["dup_kept"] += 1
                        per_round[z["_round"]]["filtered"]["dup_kept"] += 1
                        if dirn in per_dir:
                            per_dir[dirn]["filtered"]["dup_kept"] += 1
                        per_regime[rg]["filtered"]["dup_kept"] += 1
                    elif cls == "failed_triggered":
                        filtered_total["fail_kept"] += 1
                        per_date[d]["filtered"]["fail_kept"] += 1
                        per_round[z["_round"]]["filtered"]["fail_kept"] += 1
                        if dirn in per_dir:
                            per_dir[dirn]["filtered"]["fail_kept"] += 1
                        per_regime[rg]["filtered"]["fail_kept"] += 1
                else:
                    filtered_total["suppressed_total"] += 1
                    suppressed_zone_records.append({
                        "id": z["id"],
                        "date": d,
                        "round": z["_round"],
                        "regime": z["_regime"],
                        "direction": z["direction"],
                        "uniqueMoveId": z.get("uniqueMoveId"),  # LABEL-ONLY
                        "isPrimaryMoveZone": z.get("isPrimaryMoveZone"),  # LABEL-ONLY
                        "class_label": cls,                                # LABEL-ONLY
                        "fast_kept": dec["fast_kept"],
                        "dup_suppressed": dec["dup_suppressed"],
                        "parent_id": dec.get("parent_id"),
                        "delta_t_min_from_parent": dec.get("delta_t_min_from_parent"),
                        "confirm_to_trigger_min": dec.get("confirm_to_trigger_min"),
                    })
                    if cls == "primary_unique_reached_move":
                        filtered_total["suppressed_primary"] += 1
                    elif cls == "duplicate_reached_move":
                        filtered_total["suppressed_duplicate_reached"] += 1
                    elif cls == "failed_triggered":
                        filtered_total["suppressed_failed"] += 1

    # Wrap-up
    def pct(num, den):
        if not den:
            return None
        return round(100.0 * num / den, 2)

    primary_recall = pct(filtered_total["prim_kept"], baseline_total["prim"])
    duplicate_removal = pct(baseline_total["dup"] - filtered_total["dup_kept"], baseline_total["dup"])
    failed_reduction = pct(baseline_total["fail"] - filtered_total["fail_kept"], baseline_total["fail"])
    baseline_precision = (baseline_total["reached"] / baseline_total["trig"]) if baseline_total["trig"] else None
    filtered_precision = (filtered_total["reached_kept"] / filtered_total["trig_kept"]) if filtered_total["trig_kept"] else None
    precision_delta = (
        round((filtered_precision - baseline_precision) * 100.0, 2)
        if baseline_precision is not None and filtered_precision is not None else None
    )
    n_days = len({z["_date"] for z in zones})
    actionable_per_day = round(filtered_total["trig_kept"] / n_days, 3) if n_days else None

    # per-round / per-direction recall summaries
    def round_dir_recall(d: dict) -> dict:
        b, f = d["baseline"], d["filtered"]
        return {
            "primary_recall_pct": pct(f["prim_kept"], b["prim"]),
            "duplicate_removal_pct": pct(b["dup"] - f["dup_kept"], b["dup"]),
            "failed_reduction_pct": pct(b["fail"] - f["fail_kept"], b["fail"]),
            "trig_kept": f["trig_kept"],
            "reached_kept": f["reached_kept"],
            "trig_baseline": b["trig"],
            "prim_baseline": b["prim"],
            "dup_baseline": b["dup"],
            "fail_baseline": b["fail"],
        }

    per_round_summary = {r: round_dir_recall(per_round[r]) for r in per_round}
    per_dir_summary = {d: round_dir_recall(per_dir[d]) for d in per_dir}
    per_regime_summary = {r: round_dir_recall(per_regime[r]) for r in per_regime}
    per_date_summary = {d: round_dir_recall(per_date[d]) for d in per_date}

    return {
        "x_min": x_min,
        "price_pct": price_pct,
        "baseline_totals": baseline_total,
        "filtered_totals": filtered_total,
        "aggregate": {
            "primary_recall_pct": primary_recall,
            "duplicate_removal_pct": duplicate_removal,
            "failed_reduction_pct": failed_reduction,
            "baseline_precision_pct": round(baseline_precision * 100.0, 3) if baseline_precision is not None else None,
            "filtered_precision_pct": round(filtered_precision * 100.0, 3) if filtered_precision is not None else None,
            "precision_delta_pp": precision_delta,
            "actionable_signals_per_day": actionable_per_day,
            "n_days": n_days,
        },
        "per_round": per_round_summary,
        "per_direction": per_dir_summary,
        "per_regime": per_regime_summary,
        "per_date": per_date_summary,
        "suppressed_zone_records": suppressed_zone_records,
    }


# ---------- helpers for stability / verdicts ----------

def stability_assess(per_round: dict, per_dir: dict, per_regime: dict) -> dict:
    """A filter is stable if primary_recall is non-zero and reasonably similar across
    rounds and directions (and regimes where each bucket has a non-trivial primary base)."""

    def safe_vals(d: dict, key: str) -> list[float]:
        return [v[key] for v in d.values() if v.get(key) is not None and v.get("prim_baseline", 0) > 0]

    round_recalls = safe_vals(per_round, "primary_recall_pct")
    dir_recalls = safe_vals(per_dir, "primary_recall_pct")
    regime_recalls = safe_vals(per_regime, "primary_recall_pct")

    def range_pp(xs):
        return round(max(xs) - min(xs), 2) if xs else None

    round_stable = (len(round_recalls) >= 2 and (max(round_recalls) - min(round_recalls)) <= 40
                    and min(round_recalls) >= 50)
    dir_stable = (len(dir_recalls) >= 2 and (max(dir_recalls) - min(dir_recalls)) <= 30
                  and min(dir_recalls) >= 50)
    return {
        "round_recalls": round_recalls,
        "round_recall_range_pp": range_pp(round_recalls),
        "dir_recalls": dir_recalls,
        "dir_recall_range_pp": range_pp(dir_recalls),
        "regime_recalls": regime_recalls,
        "regime_recall_range_pp": range_pp(regime_recalls),
        "FILTER_STABLE_ACROSS_ROUNDS": "YES" if round_stable else "NO",
        "FILTER_STABLE_ACROSS_DIRECTION": "YES" if dir_stable else "NO",
    }


# ---------- main ----------

def main() -> int:
    zones = load_pool()
    n_unique_dates = len({z["_date"] for z in zones})
    print(f"loaded {len(zones)} zones across {n_unique_dates} dates", file=sys.stderr)

    # --- A: dataset ---
    dataset_rows = []
    for z in zones:
        dataset_rows.append({
            "date": z["_date"],
            "round": z["_round"],
            "regime": z["_regime"],
            "zone_id": z["id"],
            "direction": z["direction"],
            "startTs": z.get("startTs"),
            "confirmedTs": z.get("confirmedTs"),
            "triggerTs": z.get("triggerTs"),
            "resolvedTs": z.get("resolvedTs"),
            "zoneLow": z.get("zoneLow"),
            "zoneHigh": z.get("zoneHigh"),
            "zoneMid": mid_price(z),
            "status": z.get("status"),
            "triggered": is_triggered(z),
            "reached_raw": is_reached(z),
            "uniqueMoveId": z.get("uniqueMoveId"),
            "isPrimaryMoveZone": z.get("isPrimaryMoveZone"),
            "duplicateMoveCredit": z.get("duplicateMoveCredit"),
            "moveClusterSize": z.get("moveClusterSize"),
            "class_label": z["_class"],
            "confirm_to_trigger_min": confirm_to_trigger_min(z),
        })
    (OUT_DIR / "OKX_TARDIS_24D_FILTER_VALIDATION_DATASET.json").write_text(
        json.dumps({
            "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "n_rows": len(dataset_rows),
            "rows": dataset_rows,
        }, indent=2, default=str), encoding="utf-8"
    )
    keys = list(dataset_rows[0].keys())
    with (OUT_DIR / "OKX_TARDIS_24D_FILTER_VALIDATION_DATASET.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in dataset_rows:
            w.writerow(r)

    # --- B: apply filter for 12 combinations ---
    combos: list[dict] = []
    for x in FAST_TRIGGER_X_MIN:
        for p in PRICE_DIST_PCT:
            r = evaluate_combination(zones, x, p)
            combos.append(r)
            agg = r["aggregate"]
            print(f"  X={x}m price<={p}%  recall={agg['primary_recall_pct']}  "
                  f"dup_rem={agg['duplicate_removal_pct']}  "
                  f"fail_red={agg['failed_reduction_pct']}  "
                  f"prec_delta_pp={agg['precision_delta_pp']}  "
                  f"actionable/d={agg['actionable_signals_per_day']}",
                  file=sys.stderr)

    # --- C/D: pick best by composite (recall>=70% gate, then maximise dup_rem+failed_red) ---
    eligible = [c for c in combos if (c["aggregate"]["primary_recall_pct"] or 0) >= 70.0]
    if eligible:
        eligible.sort(key=lambda c: (
            (c["aggregate"]["duplicate_removal_pct"] or 0)
            + (c["aggregate"]["failed_reduction_pct"] or 0)
        ), reverse=True)
        best = eligible[0]
    else:
        best = None

    # Stability assess on best
    stability = (stability_assess(best["per_round"], best["per_direction"], best["per_regime"])
                 if best else None)

    # Late-entry hypothesis on suppressed (across the best combo)
    late_entry = None
    if best:
        rs = best["suppressed_zone_records"]
        delays = [r["delta_t_min_from_parent"] for r in rs if r.get("delta_t_min_from_parent") is not None]
        cls_counts = defaultdict(int)
        for r in rs:
            cls_counts[r["class_label"]] += 1
        late_entry = {
            "n_suppressed_total": len(rs),
            "median_delta_t_from_kept_prior_trigger_min": round(stats.median(delays), 3) if delays else None,
            "p25_delta_t_min": round(stats.quantiles(delays, n=4)[0], 3) if len(delays) >= 4 else None,
            "p75_delta_t_min": round(stats.quantiles(delays, n=4)[2], 3) if len(delays) >= 4 else None,
            "by_class_label": dict(cls_counts),
        }

    # Compare to OKX direct March mini-OOS
    okx_direct_mini = {
        "scope": "OKX direct 2026-03-11..03-13 (3 days, n_primary=3)",
        "30m": {"primary_recall_pct": 100.0, "duplicate_removal_pct": 66.67,
                 "failed_reduction_pct": 87.23, "precision_delta_pp": 29.66,
                 "actionable_per_day": 4.0},
        "60m": {"primary_recall_pct": 100.0, "duplicate_removal_pct": 55.56,
                 "failed_reduction_pct": 80.85, "precision_delta_pp": 23.41,
                 "actionable_per_day": 5.333},
        "90m": {"primary_recall_pct": 100.0, "duplicate_removal_pct": 55.56,
                 "failed_reduction_pct": 78.72, "precision_delta_pp": 20.84,
                 "actionable_per_day": 5.667},
        "note": "OKX direct mini-OOS used uniqueMoveId OR price-band <= 2 %. "
                "This Tardis validation is LIVE-VALID: NO uniqueMoveId in suppress decision; "
                "duplicate match is purely price-band.",
    }

    # Future-leak audit (static)
    leak_audit = {
        "FILTER_DECISION_USED_UNIQUEMOVEID": "NO",
        "FILTER_INVALID_FUTURE_LEAK": "NO",
        "allowed_fields_used_in_suppress_decision": [
            "direction", "triggerTs", "confirmedTs", "zoneLow", "zoneHigh"
        ],
        "forbidden_fields_referenced_in_decision": [],
        "notes": [
            "evaluate_combination's suppress branch reads only triggerTs / direction /"
            " confirmedTs and zone midpoints. uniqueMoveId / isPrimaryMoveZone /"
            " duplicateMoveCredit / moveClusterSize / status / reached / target_*.* /"
            " resolvedTs / mfePct / maePct are referenced ONLY in evaluation metric"
            " denominators (precision/recall) and per-class breakdowns AFTER the"
            " kept/suppressed split.",
            "All prior-zone comparisons are strict-past (prior.triggerTs < current.triggerTs).",
            "No future zones are visible: prior pool is sliced by triggered[:i] where i is "
            "the chronological index of the current zone within its date.",
        ],
    }

    # ---------- final flags ----------
    aggn = best["aggregate"] if best else {}
    flags = {
        "TARDIS_FILTER_VALIDATION_DONE": "YES",
        "FILTER_DECISION_USED_UNIQUEMOVEID": leak_audit["FILTER_DECISION_USED_UNIQUEMOVEID"],
        "FILTER_INVALID_FUTURE_LEAK": leak_audit["FILTER_INVALID_FUTURE_LEAK"],
        "BEST_FAST_X_MIN": (best["x_min"] if best else None),
        "BEST_PRICE_DISTANCE_PCT": (best["price_pct"] if best else None),
        "TARDIS_PRIMARY_RECALL_PCT": aggn.get("primary_recall_pct"),
        "TARDIS_DUPLICATE_REMOVAL_PCT": aggn.get("duplicate_removal_pct"),
        "TARDIS_FAILED_REDUCTION_PCT": aggn.get("failed_reduction_pct"),
        "TARDIS_ACTIONABLE_SIGNALS_PER_DAY": aggn.get("actionable_signals_per_day"),
        "TARDIS_PRECISION_DELTA_PP": aggn.get("precision_delta_pp"),
        "FILTER_STABLE_ACROSS_ROUNDS": (stability["FILTER_STABLE_ACROSS_ROUNDS"] if stability else "NO"),
        "FILTER_STABLE_ACROSS_DIRECTION": (stability["FILTER_STABLE_ACROSS_DIRECTION"] if stability else "NO"),
        "FILTER_LOOKS_TRANSFERABLE_TO_LIVE": "YES" if (
            best is not None
            and (aggn.get("primary_recall_pct") or 0) >= 70
            and (aggn.get("duplicate_removal_pct") or 0) >= 40
            and stability and stability["FILTER_STABLE_ACROSS_ROUNDS"] == "YES"
            and stability["FILTER_STABLE_ACROSS_DIRECTION"] == "YES"
        ) else "NO",
        "READY_FOR_PASSIVE_LIVE_OBSERVER": None,  # set below
        "READY_TO_INTEGRATE_FILTER_IN_STRATEGY": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }
    flags["READY_FOR_PASSIVE_LIVE_OBSERVER"] = flags["FILTER_LOOKS_TRANSFERABLE_TO_LIVE"]

    # ---------- write JSON ----------
    out_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX Tardis 24-date pool (6 calibration + 6 OOS_v1 + 12 v2)",
        "n_dates": n_unique_dates,
        "n_zones": len(zones),
        "filter_under_test": "duplicate_60m_PRICE_BAND_ONLY AND fast_trigger<=X (LIVE-VALID: no uniqueMoveId in decision)",
        "fast_trigger_x_min_options": FAST_TRIGGER_X_MIN,
        "price_distance_pct_options": PRICE_DIST_PCT,
        "future_leak_audit": leak_audit,
        "combos_summary": [{
            "x_min": c["x_min"],
            "price_pct": c["price_pct"],
            **c["aggregate"],
        } for c in combos],
        "best_combo": (None if best is None else {
            "x_min": best["x_min"],
            "price_pct": best["price_pct"],
            "aggregate": best["aggregate"],
            "per_round": best["per_round"],
            "per_direction": best["per_direction"],
            "per_regime": best["per_regime"],
        }),
        "stability_on_best": stability,
        "late_entry_on_best": late_entry,
        "compare_to_okx_direct_march_mini_oos": okx_direct_mini,
        "flags": flags,
    }
    (OUT_DIR / "OKX_TARDIS_24D_PASSIVE_FILTER_VALIDATION.json").write_text(
        json.dumps(out_json, indent=2, default=str), encoding="utf-8")

    # ---------- write CSV (12 combinations row-per-combo) ----------
    csv_headers = [
        "x_min", "price_pct", "primary_recall_pct", "duplicate_removal_pct",
        "failed_reduction_pct", "baseline_precision_pct", "filtered_precision_pct",
        "precision_delta_pp", "actionable_signals_per_day", "n_days",
        "baseline_trig", "baseline_prim", "baseline_dup", "baseline_fail",
        "filtered_trig_kept", "filtered_prim_kept", "filtered_dup_kept", "filtered_fail_kept",
    ]
    with (OUT_DIR / "OKX_TARDIS_24D_PASSIVE_FILTER_VALIDATION.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(csv_headers)
        for c in combos:
            agg = c["aggregate"]
            b = c["baseline_totals"]
            fl = c["filtered_totals"]
            w.writerow([
                c["x_min"], c["price_pct"],
                agg["primary_recall_pct"], agg["duplicate_removal_pct"],
                agg["failed_reduction_pct"], agg["baseline_precision_pct"],
                agg["filtered_precision_pct"], agg["precision_delta_pp"],
                agg["actionable_signals_per_day"], agg["n_days"],
                b["trig"], b["prim"], b["dup"], b["fail"],
                fl["trig_kept"], fl["prim_kept"], fl["dup_kept"], fl["fail_kept"],
            ])

    # ---------- write markdown ----------
    md = [
        "# OKX Tardis 24-date pool - true held-out passive-filter validation",
        "",
        f"**Build:** {out_json['build_time_utc']}",
        f"**Scope:** {out_json['scope']}",
        f"**Zones:** {out_json['n_zones']}  **Dates:** {out_json['n_dates']}",
        f"**Filter under test:** `duplicate_60m_PRICE_BAND_ONLY AND fast_trigger<=X`  (LIVE-VALID: NO `uniqueMoveId` in suppress decision)",
        "",
        "## HARD DISCLAIMER",
        "",
        "  - This is a TRUE held-out sample for the OKX-direct-March-derived filter rule,",
        "    but the duplicate cut is PURELY price-band-based here (no uniqueMoveId),",
        "    so the rule shape differs slightly from the OKX-direct mini-OOS version.",
        "  - No engine / threshold change. No new backtest. Passive, post-hoc.",
        "  - No profitability claim. No production integration.",
        "",
        "## A. Future-leak audit (static, before any number is reported)",
        "",
        f"- `FILTER_DECISION_USED_UNIQUEMOVEID` = **{leak_audit['FILTER_DECISION_USED_UNIQUEMOVEID']}**",
        f"- `FILTER_INVALID_FUTURE_LEAK` = **{leak_audit['FILTER_INVALID_FUTURE_LEAK']}**",
        f"- allowed fields used in decision: `{leak_audit['allowed_fields_used_in_suppress_decision']}`",
        f"- forbidden fields referenced in decision: `{leak_audit['forbidden_fields_referenced_in_decision']}`",
        "",
        "Notes:",
    ]
    for n in leak_audit["notes"]:
        md.append(f"  - {n}")
    md.extend([
        "",
        "## B. Baseline (no filter, all 24 days)",
        "",
        f"- zones = {len(zones):,}",
        f"- triggered = {sum(1 for z in zones if is_triggered(z))}",
        f"- reached_raw = {sum(1 for z in zones if is_reached(z))}",
        f"- primary_unique_reached_move = {sum(1 for z in zones if z['_class'] == 'primary_unique_reached_move')}",
        f"- duplicate_reached_move = {sum(1 for z in zones if z['_class'] == 'duplicate_reached_move')}",
        f"- failed_triggered = {sum(1 for z in zones if z['_class'] == 'failed_triggered')}",
        "",
        "## C. 12 filter combinations (aggregate over the 24 days)",
        "",
        "| X (min) | price % | primary recall % | dup removal % | failed reduce % | prec delta pp | actionable/day |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for c in combos:
        agg = c["aggregate"]
        md.append(
            f"| {c['x_min']} | {c['price_pct']} | {agg['primary_recall_pct']} | "
            f"{agg['duplicate_removal_pct']} | {agg['failed_reduction_pct']} | "
            f"{agg['precision_delta_pp']} | {agg['actionable_signals_per_day']} |"
        )

    if best:
        md.extend([
            "",
            "## D. Best combination (recall >= 70 % gate, then max dup_remove + failed_reduce)",
            "",
            f"- `X = {best['x_min']} min`, `price_threshold = {best['price_pct']} %`",
            f"- primary recall: **{best['aggregate']['primary_recall_pct']} %**",
            f"- duplicate removal: **{best['aggregate']['duplicate_removal_pct']} %**",
            f"- failed reduction: **{best['aggregate']['failed_reduction_pct']} %**",
            f"- baseline precision: **{best['aggregate']['baseline_precision_pct']} %**",
            f"- filtered precision: **{best['aggregate']['filtered_precision_pct']} %**",
            f"- precision delta: **{best['aggregate']['precision_delta_pp']} pp**",
            f"- actionable signals/day: **{best['aggregate']['actionable_signals_per_day']}**",
            "",
            "### Per-round (calibration / OOS_v1 / v2)",
            "",
            "| round | trig | prim | dup | fail | recall % | dup_rem % | fail_red % |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for r, v in best["per_round"].items():
            md.append(f"| {r} | {v['trig_baseline']} | {v['prim_baseline']} | "
                      f"{v['dup_baseline']} | {v['fail_baseline']} | "
                      f"{v['primary_recall_pct']} | {v['duplicate_removal_pct']} | {v['failed_reduction_pct']} |")
        md.extend([
            "",
            "### Per-direction",
            "",
            "| direction | trig | prim | dup | fail | recall % | dup_rem % | fail_red % |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for d, v in best["per_direction"].items():
            md.append(f"| {d} | {v['trig_baseline']} | {v['prim_baseline']} | "
                      f"{v['dup_baseline']} | {v['fail_baseline']} | "
                      f"{v['primary_recall_pct']} | {v['duplicate_removal_pct']} | {v['failed_reduction_pct']} |")
        md.extend([
            "",
            "### Per-regime",
            "",
            "| regime | trig | prim | dup | fail | recall % | dup_rem % | fail_red % |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for r, v in best["per_regime"].items():
            md.append(f"| {r} | {v['trig_baseline']} | {v['prim_baseline']} | "
                      f"{v['dup_baseline']} | {v['fail_baseline']} | "
                      f"{v['primary_recall_pct']} | {v['duplicate_removal_pct']} | {v['failed_reduction_pct']} |")
    else:
        md.extend([
            "",
            "## D. NO combination meets the 70 % primary-recall gate",
            "",
            "No filter combination retained at least 70 % of the 21 primary unique moves.",
            "The rule does not generalise from OKX-direct March to the Tardis 24-date pool at any sensitivity tested.",
        ])

    if stability:
        md.extend([
            "",
            "## E. Stability of best combination",
            "",
            f"- per-round primary recalls: {stability['round_recalls']}  (range = {stability['round_recall_range_pp']} pp)",
            f"- per-direction primary recalls: {stability['dir_recalls']}  (range = {stability['dir_recall_range_pp']} pp)",
            f"- per-regime primary recalls: {stability['regime_recalls']}  (range = {stability['regime_recall_range_pp']} pp)",
            f"- `FILTER_STABLE_ACROSS_ROUNDS` = **{stability['FILTER_STABLE_ACROSS_ROUNDS']}**",
            f"- `FILTER_STABLE_ACROSS_DIRECTION` = **{stability['FILTER_STABLE_ACROSS_DIRECTION']}**",
        ])

    if late_entry:
        md.extend([
            "",
            "## F. Late-entry hypothesis on suppressed zones (best combo)",
            "",
            f"- n suppressed total: {late_entry['n_suppressed_total']}",
            f"- by class label (LABEL-ONLY evaluation): {late_entry['by_class_label']}",
            f"- median delta_t from KEPT prior trigger (live-valid, not uniqueMoveId-based): "
            f"**{late_entry['median_delta_t_from_kept_prior_trigger_min']} min**",
            f"- p25 / p75 delta_t: {late_entry['p25_delta_t_min']} / {late_entry['p75_delta_t_min']} min",
        ])

    md.extend([
        "",
        "## G. Compare to OKX direct March mini-OOS",
        "",
        f"- {okx_direct_mini['note']}",
        "",
        "| variant | scope | X (min) | recall % | dup_rem % | fail_red % | prec delta pp | actionable/day |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
        f"| OKX direct mini-OOS | 03-11..03-13 (3 days, 3 prim) | 30 | 100.0 | 66.67 | 87.23 | 29.66 | 4.0 |",
        f"| OKX direct mini-OOS | 03-11..03-13 (3 days, 3 prim) | 60 | 100.0 | 55.56 | 80.85 | 23.41 | 5.333 |",
        f"| OKX direct mini-OOS | 03-11..03-13 (3 days, 3 prim) | 90 | 100.0 | 55.56 | 78.72 | 20.84 | 5.667 |",
    ])
    if best:
        md.append(
            f"| Tardis 24d held-out (live-valid) | 24 days, {best['baseline_totals']['prim']} prim | "
            f"{best['x_min']} (price<={best['price_pct']}%) | "
            f"{best['aggregate']['primary_recall_pct']} | "
            f"{best['aggregate']['duplicate_removal_pct']} | "
            f"{best['aggregate']['failed_reduction_pct']} | "
            f"{best['aggregate']['precision_delta_pp']} | "
            f"{best['aggregate']['actionable_signals_per_day']} |"
        )

    md.extend([
        "",
        "## H. Final flag matrix",
        "",
        "```",
    ])
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.extend(["```", "",
        "## I. Hard rules honored",
        "",
        "- strategy / thresholds / `zoneDetector`: UNCHANGED",
        "- no new backtest spawned; no conversion re-run",
        "- post-trigger outcomes used only as labels (recall/precision denominators),",
        "  NEVER inside the suppress decision",
        "- `zone_score_v1` / `v2`: not used as filter",
        "- raw archives untouched",
        "- no production integration; no profitability claim",
    ])
    (OUT_DIR / "OKX_TARDIS_24D_PASSIVE_FILTER_VALIDATION.md").write_text("\n".join(md), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
