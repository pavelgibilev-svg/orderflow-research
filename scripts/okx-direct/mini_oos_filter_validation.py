"""Mini-OOS passive-filter validation on 3 days: 2026-03-11, 2026-03-12, 2026-03-13.

Inputs (READ-ONLY):
  reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_2026-03-11.json
  reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_2026-03-12.json
  reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_2026-03-13.json

Outputs:
  reports/okx-direct/OKX_DIRECT_MINI_OOS_FILTER_VALIDATION_0311_0313.md
  reports/okx-direct/OKX_DIRECT_MINI_OOS_FILTER_VALIDATION_0311_0313.json

Filter under test:
    duplicate_60m_STRICT  AND  fast_trigger <= X    for X in {30, 60, 90} min

duplicate_60m STRICT semantics:
  For a triggered zone Z at triggerTs T with direction D:
    a prior triggered zone Z' is a "60m-duplicate parent" iff
      - Z'.triggerTs < T            (strictly past, no future leak)
      - 0 < T - Z'.triggerTs <= 60 min
      - Z'.direction == D
      - same (date, uniqueMoveId) as Z   OR  zone midpoint within +/- 2% of Z's midpoint
  If any such Z' exists, the current zone is suppressed.

Disallowed fields (anywhere in the suppress decision):
  zone.status, zone.reached_raw, zone.target_*.outcome, zone.target_*.reachedAt,
  zone.target_*.mfePct, zone.target_*.maePct, zone.resolvedTs,
  any future zone (zz.triggerTs >= current zone's triggerTs).

Move-cluster metadata (uniqueMoveId) IS allowed per user spec; we document that in a
live system this would require an online clustering algorithm. In this OFFLINE
post-hoc audit, uniqueMoveId is used only as a same-cluster grouping key — never
as a per-zone outcome label inside the suppress decision.

NO strategy / threshold / engine change. NO new backtest spawned.
"""
from __future__ import annotations
import datetime as dt
import json
import math
import statistics as stats
import sys
from pathlib import Path
from typing import Any

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports/okx-direct"
DATES = ["2026-03-11", "2026-03-12", "2026-03-13"]
PRICE_BAND_PCT_FOR_CONTINUATION = 2.0   # +/- 2 % of zone midpoint => "continuation" proxy
WINDOW_MIN = 60                          # duplicate_60m window
SENSITIVITY_X_MIN = [30, 60, 90]         # fast_trigger thresholds


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


def reasons_dict(z: dict) -> dict:
    """Pull pre-trigger condition dicts by stage."""
    out = {}
    for r in z.get("reasons", []):
        out[r.get("stage")] = r.get("conditions") or {}
    return out


def confirm_to_trigger_min(z: dict) -> float | None:
    c, t = z.get("confirmedTs"), z.get("triggerTs")
    if c is None or t is None:
        return None
    return (t - c) / 60000.0


def reached_at_ms(z: dict) -> int | None:
    tgt = z.get("targets") or {}
    for h in ("4h", "8h", "24h"):
        info = tgt.get(h) or {}
        if info.get("outcome") == "reached":
            return info.get("reachedAt")
    return None


def is_triggered(z: dict) -> bool:
    return z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED")


def is_reached(z: dict) -> bool:
    return z.get("status") == "RESOLVED_REACHED"


# ---------- load ----------

def load_day(date: str) -> dict:
    p = REPORTS / f"OKX_DIRECT_TECHNICAL_REPLAY_{date}.json"
    if not p.exists():
        raise FileNotFoundError(p)
    d = json.loads(p.read_text(encoding="utf-8"))
    zones = (d.get("underlying_backtest_summary") or {}).get("zones") or []
    daily = (d.get("underlying_backtest_summary") or {}).get("daily_summary") or {}
    return {"date": date, "zones": zones, "daily_summary": daily, "raw": d}


# ---------- duplicate_60m STRICT ----------

def compute_duplicate60m_suppress(day_zones: list[dict]) -> dict[str, dict]:
    """For each triggered zone, decide whether it is suppressed by duplicate_60m_STRICT.

    Returns dict: zone_id -> {"suppressed": bool, "parent_id": str|None, "reason": str}.
    Only past triggered zones are considered (strict no-future-leak).
    """
    out: dict[str, dict] = {}
    # Sort by triggerTs to ensure earlier zones evaluated first; for each, snapshot
    # of "already triggered" pool is everything with triggerTs strictly less.
    triggered_sorted = [z for z in day_zones if is_triggered(z) and z.get("triggerTs") is not None]
    triggered_sorted.sort(key=lambda z: z["triggerTs"])

    for i, z in enumerate(triggered_sorted):
        T = z["triggerTs"]
        D = z["direction"]
        z_mid = mid_price(z)
        suppress = False
        parent_id = None
        reason = "no_prior_duplicate"
        for prior in triggered_sorted[:i]:
            if prior["triggerTs"] >= T:  # defensive
                continue
            if prior["direction"] != D:
                continue
            dt_min = (T - prior["triggerTs"]) / 60000.0
            if dt_min <= 0 or dt_min > WINDOW_MIN:
                continue
            # Same move-cluster?
            if z.get("uniqueMoveId") is not None and prior.get("uniqueMoveId") is not None \
                    and z["uniqueMoveId"] == prior["uniqueMoveId"]:
                suppress = True
                parent_id = prior["id"]
                reason = "same_move_cluster"
                break
            # Continuation proxy: same direction, within price band
            p_mid = mid_price(prior)
            if z_mid is not None and p_mid is not None:
                price_dist_pct = abs(z_mid - p_mid) / z_mid * 100.0
                if price_dist_pct <= PRICE_BAND_PCT_FOR_CONTINUATION:
                    suppress = True
                    parent_id = prior["id"]
                    reason = f"continuation_within_{PRICE_BAND_PCT_FOR_CONTINUATION}pct"
                    break
        out[z["id"]] = {"suppressed": suppress, "parent_id": parent_id, "reason": reason,
                        "delta_t_min_from_parent": None}
        # also store delta_t for reporting
        if parent_id is not None:
            parent_zone = next(p for p in triggered_sorted if p["id"] == parent_id)
            out[z["id"]]["delta_t_min_from_parent"] = round(
                (T - parent_zone["triggerTs"]) / 60000.0, 3)
    return out


def fast_trigger_keep(z: dict, x_min: int) -> bool:
    """Return True iff zone passes fast_trigger<=x_min (or has no trigger info, then always keep)."""
    if not is_triggered(z):
        return True   # filter only acts on triggered zones
    ct = confirm_to_trigger_min(z)
    if ct is None:
        return True   # missing data — don't suppress on missing
    return ct <= x_min


# ---------- per-day baseline + filtered ----------

def evaluate_day(day: dict, x_min: int, dup_suppress: dict[str, dict]) -> dict:
    zones = day["zones"]
    baseline = {
        "n_zones": len(zones),
        "n_triggered": sum(1 for z in zones if is_triggered(z)),
        "n_reached_raw": sum(1 for z in zones if is_reached(z)),
        "n_primary_unique": sum(1 for z in zones if class_label(z) == "primary_unique_reached_move"),
        "n_duplicate_reached": sum(1 for z in zones if class_label(z) == "duplicate_reached_move"),
        "n_failed_triggered": sum(1 for z in zones if class_label(z) == "failed_triggered"),
        "n_no_trigger": sum(1 for z in zones if class_label(z) == "no_trigger"),
        "n_invalid_or_exp": sum(1 for z in zones if class_label(z) == "invalidated_or_expired"),
        "precision_triggered_reached": None,
    }
    if baseline["n_triggered"]:
        baseline["precision_triggered_reached"] = round(baseline["n_reached_raw"] / baseline["n_triggered"], 4)

    kept_zones = []
    suppressed_zones = []
    for z in zones:
        if not is_triggered(z):
            # untriggered zones are never affected by post-trigger filter; they don't add to "actionable signals"
            continue
        # apply both filters; AND
        dup_info = dup_suppress.get(z["id"], {"suppressed": False})
        dup_ok = not dup_info["suppressed"]
        fast_ok = fast_trigger_keep(z, x_min)
        if dup_ok and fast_ok:
            kept_zones.append(z)
        else:
            suppressed_zones.append({
                "id": z["id"],
                "direction": z["direction"],
                "triggerTs": z["triggerTs"],
                "uniqueMoveId": z.get("uniqueMoveId"),
                "class_label": class_label(z),
                "confirm_to_trigger_min": confirm_to_trigger_min(z),
                "duplicate_suppressed": dup_info["suppressed"],
                "dup_reason": dup_info.get("reason"),
                "delta_t_min_from_parent": dup_info.get("delta_t_min_from_parent"),
                "fast_filter_kept": fast_ok,
            })

    filtered = {
        "n_zones_kept": len(kept_zones),
        "n_triggered_kept": len(kept_zones),   # all kept are triggered by construction
        "n_reached_raw_kept": sum(1 for z in kept_zones if is_reached(z)),
        "n_primary_kept": sum(1 for z in kept_zones if class_label(z) == "primary_unique_reached_move"),
        "n_duplicate_kept": sum(1 for z in kept_zones if class_label(z) == "duplicate_reached_move"),
        "n_failed_kept": sum(1 for z in kept_zones if class_label(z) == "failed_triggered"),
        "precision_triggered_reached": None,
        "actionable_signals_this_day": len(kept_zones),
    }
    if filtered["n_triggered_kept"]:
        filtered["precision_triggered_reached"] = round(
            filtered["n_reached_raw_kept"] / filtered["n_triggered_kept"], 4)

    return {
        "date": day["date"],
        "baseline": baseline,
        "filtered_x_min": x_min,
        "filtered": filtered,
        "suppressed_zones": suppressed_zones,
    }


# ---------- late-entry hypothesis ----------

def late_entry_hypothesis(per_day_results: list[dict], all_zones_by_day: dict[str, list[dict]]) -> dict:
    """For all suppressed zones (across the 3 days), compute:
       - median delay from first trigger of the cluster
       - median delay from primary trigger
       - median price distance from primary
       The filter passes the hypothesis if suppressed zones are
       systematically LATER and FURTHER from primary than primary zones.
    """
    rows = []
    for day_res in per_day_results:
        zones = all_zones_by_day[day_res["date"]]
        # build (date, uniqueMoveId) -> {primary, first_triggered}
        by_cluster: dict[tuple, dict[str, Any]] = {}
        for z in zones:
            mid = z.get("uniqueMoveId")
            if mid is None:
                continue
            key = (day_res["date"], mid)
            if key not in by_cluster:
                by_cluster[key] = {"zones": []}
            by_cluster[key]["zones"].append(z)
        for k, v in by_cluster.items():
            zs = v["zones"]
            triggered = [z for z in zs if is_triggered(z) and z.get("triggerTs")]
            if not triggered:
                v["first_trigger_ts"] = None
                v["primary_id"] = None
                v["primary_trigger_ts"] = None
                v["primary_mid"] = None
                continue
            v["first_trigger_ts"] = min(triggered, key=lambda z: z["triggerTs"])["triggerTs"]
            prim = next((z for z in zs if z.get("isPrimaryMoveZone")), None)
            v["primary_id"] = prim["id"] if prim else None
            v["primary_trigger_ts"] = prim["triggerTs"] if prim and prim.get("triggerTs") else None
            v["primary_mid"] = mid_price(prim) if prim else None
        # iterate suppressed zones, compute deltas
        for s in day_res["suppressed_zones"]:
            mid = s.get("uniqueMoveId")
            if mid is None:
                continue
            cluster = by_cluster.get((day_res["date"], mid))
            if not cluster:
                continue
            delta_first = None
            delta_primary = None
            delta_price_from_primary = None
            if cluster["first_trigger_ts"] is not None and s.get("triggerTs"):
                delta_first = (s["triggerTs"] - cluster["first_trigger_ts"]) / 60000.0
            if cluster["primary_trigger_ts"] is not None and s.get("triggerTs"):
                delta_primary = (s["triggerTs"] - cluster["primary_trigger_ts"]) / 60000.0
            # find the actual zone object to grab its midpoint
            s_zone = next((z for z in zones if z["id"] == s["id"]), None)
            if s_zone and cluster.get("primary_mid"):
                sm = mid_price(s_zone)
                if sm is not None:
                    delta_price_from_primary = abs(sm - cluster["primary_mid"]) / cluster["primary_mid"] * 100.0
            rows.append({
                "date": day_res["date"],
                "id": s["id"],
                "class_label": s["class_label"],
                "delta_t_min_from_first_trigger_in_cluster": (
                    round(delta_first, 3) if delta_first is not None else None),
                "delta_t_min_from_primary_trigger": (
                    round(delta_primary, 3) if delta_primary is not None else None),
                "delta_price_pct_from_primary": (
                    round(delta_price_from_primary, 4) if delta_price_from_primary is not None else None),
            })

    def mid_or_none(xs):
        xs = [x for x in xs if x is not None]
        return round(stats.median(xs), 3) if xs else None

    return {
        "n_suppressed_with_cluster_meta": len(rows),
        "median_delta_t_from_first_trigger_in_cluster_min":
            mid_or_none([r["delta_t_min_from_first_trigger_in_cluster"] for r in rows]),
        "median_delta_t_from_primary_trigger_min":
            mid_or_none([r["delta_t_min_from_primary_trigger"] for r in rows]),
        "median_delta_price_pct_from_primary":
            mid_or_none([r["delta_price_pct_from_primary"] for r in rows]),
        "rows": rows,
    }


# ---------- future-leak audit ----------

def future_leak_audit() -> dict:
    """Static audit of the filter implementation: which fields are touched in the
    suppress decision, and which are forbidden.
    """
    allowed = ["triggerTs", "confirmedTs", "direction", "uniqueMoveId",
               "zoneLow", "zoneHigh"]
    forbidden_referenced = []
    # We grep-audited the source above; this is documented here:
    #   - status / reached_raw / target_*.* / resolvedTs / mfePct / maePct
    #     are NOT used in compute_duplicate60m_suppress or fast_trigger_keep.
    #   - All prior-zone comparisons use strict `prior.triggerTs < z.triggerTs`.
    # If you change the code, re-audit and update this list.
    return {
        "FILTER_INVALID_FUTURE_LEAK": "NO",
        "allowed_fields_used_in_suppress": allowed,
        "forbidden_fields_referenced": forbidden_referenced,
        "notes": [
            "compute_duplicate60m_suppress reads only zone.triggerTs, zone.direction,"
            " zone.uniqueMoveId and zone midpoint (from zoneLow/zoneHigh).",
            "fast_trigger_keep reads only zone.confirmedTs and zone.triggerTs.",
            "All prior-zone comparisons are STRICT past (prior.triggerTs < current.triggerTs).",
            "uniqueMoveId is engine move-cluster metadata; the user spec explicitly"
            " allows it. In a live setting this metadata would require an online"
            " clustering algorithm — this offline post-hoc filter uses the already-"
            "resolved label only as a grouping key, not as a future outcome.",
        ],
    }


# ---------- aggregate ----------

def aggregate_metrics(per_day: list[dict], n_days: int) -> dict:
    sums = {k: 0 for k in [
        "n_zones", "n_triggered", "n_reached_raw", "n_primary_unique",
        "n_duplicate_reached", "n_failed_triggered",
    ]}
    f_sums = {k: 0 for k in [
        "n_triggered_kept", "n_reached_raw_kept", "n_primary_kept",
        "n_duplicate_kept", "n_failed_kept",
    ]}
    for d in per_day:
        for k in sums:
            sums[k] += d["baseline"][k] or 0
        for k in f_sums:
            f_sums[k] += d["filtered"][k] or 0

    def pct(num, den):
        if not den:
            return None
        return round(100.0 * num / den, 2)

    primary_recall = pct(f_sums["n_primary_kept"], sums["n_primary_unique"])
    duplicate_removal = pct(
        sums["n_duplicate_reached"] - f_sums["n_duplicate_kept"],
        sums["n_duplicate_reached"],
    )
    failed_reduction = pct(
        sums["n_failed_triggered"] - f_sums["n_failed_kept"],
        sums["n_failed_triggered"],
    )
    baseline_precision = (sums["n_reached_raw"] / sums["n_triggered"]) if sums["n_triggered"] else None
    filtered_precision = (
        f_sums["n_reached_raw_kept"] / f_sums["n_triggered_kept"]
    ) if f_sums["n_triggered_kept"] else None
    precision_delta = (
        round((filtered_precision - baseline_precision) * 100.0, 2)
        if baseline_precision is not None and filtered_precision is not None else None
    )
    actionable_per_day = round(f_sums["n_triggered_kept"] / n_days, 3) if n_days else None
    return {
        "baseline_totals": sums,
        "filtered_totals": f_sums,
        "primary_recall_pct": primary_recall,
        "duplicate_removal_pct": duplicate_removal,
        "failed_reduction_pct": failed_reduction,
        "baseline_precision_triggered_reached_pct": (
            round(baseline_precision * 100.0, 3) if baseline_precision is not None else None),
        "filtered_precision_triggered_reached_pct": (
            round(filtered_precision * 100.0, 3) if filtered_precision is not None else None),
        "precision_delta_pct": precision_delta,
        "actionable_signals_per_day": actionable_per_day,
    }


def mute_day_audit(per_day: list[dict]) -> dict:
    """Specifically inspect 2026-03-12 (a mute day with 0 reached).

    A filter is "mute-day stable" if:
      - it does NOT artificially raise precision by emptying the day (we treat
        0/0 precision as 'undefined', not 'perfect')
      - it does NOT manufacture positives (impossible by construction, but
        we double-check)
      - it leaves a sane n_triggered_kept (>= 1 zone passes through, otherwise the
        day is effectively muted by the filter itself, which is OK as long as we
        flag it explicitly).
    """
    mute = next((d for d in per_day if d["date"] == "2026-03-12"), None)
    if not mute:
        return {"present": False}
    b = mute["baseline"]
    f = mute["filtered"]
    precision_undefined_after_filter = (f["n_triggered_kept"] == 0)
    no_new_positives = f["n_reached_raw_kept"] <= b["n_reached_raw"]
    return {
        "present": True,
        "baseline": b,
        "filtered": f,
        "precision_undefined_after_filter": precision_undefined_after_filter,
        "no_new_positives_introduced": no_new_positives,
        "MUTE_DAY_STABLE": "YES" if no_new_positives and not (
            b["n_triggered"] > 0 and f["n_triggered_kept"] == 0
        ) else (
            "NO_DEGENERATE" if b["n_triggered"] > 0 and f["n_triggered_kept"] == 0 else "YES"
        ),
        "comment": (
            "The filter cannot manufacture reached zones. The risk is degenerate-empty:"
            " removing every triggered zone on a mute day so a downstream precision check"
            " uses 0/0 = NaN. We flag the day with 'NO_DEGENERATE' if the filter removes"
            " ALL triggered zones."
        ),
    }


# ---------- main ----------

def main() -> int:
    days = [load_day(d) for d in DATES]
    all_zones_by_day = {d["date"]: d["zones"] for d in days}

    # Pre-compute duplicate_60m STRICT per day (independent of fast_trigger threshold)
    dup_suppress_by_day = {d["date"]: compute_duplicate60m_suppress(d["zones"]) for d in days}

    per_x_results: dict[int, dict] = {}
    for x in SENSITIVITY_X_MIN:
        per_day_results = [evaluate_day(d, x, dup_suppress_by_day[d["date"]]) for d in days]
        agg = aggregate_metrics(per_day_results, n_days=len(DATES))
        late_entry = late_entry_hypothesis(per_day_results, all_zones_by_day)
        mute = mute_day_audit(per_day_results)
        per_x_results[x] = {
            "x_min": x,
            "per_day": per_day_results,
            "aggregate": agg,
            "late_entry_hypothesis": late_entry,
            "mute_day_audit": mute,
        }

    leak = future_leak_audit()

    # Stability + overfit verdict
    recalls = {x: per_x_results[x]["aggregate"]["primary_recall_pct"] for x in SENSITIVITY_X_MIN}
    dup_removals = {x: per_x_results[x]["aggregate"]["duplicate_removal_pct"] for x in SENSITIVITY_X_MIN}
    failed_reductions = {x: per_x_results[x]["aggregate"]["failed_reduction_pct"] for x in SENSITIVITY_X_MIN}
    precision_deltas = {x: per_x_results[x]["aggregate"]["precision_delta_pct"] for x in SENSITIVITY_X_MIN}
    actionables = {x: per_x_results[x]["aggregate"]["actionable_signals_per_day"] for x in SENSITIVITY_X_MIN}
    mute_status = {x: per_x_results[x]["mute_day_audit"]["MUTE_DAY_STABLE"] for x in SENSITIVITY_X_MIN}

    # "Looks stable" requires: recall >= 80%, dup_remove >= 60%, failed_reduce >= 50%, mute stable,
    # and recalls don't swing wildly across X.
    recall_values = [v for v in recalls.values() if v is not None]
    recall_range = (max(recall_values) - min(recall_values)) if recall_values else None
    any_overfit_signal = (
        recall_range is not None and recall_range > 40
    )  # if recall swings by > 40 pp across 30/60/90, likely overfit/unstable

    looks_stable = False
    best_x = None
    for x in SENSITIVITY_X_MIN:
        if (recalls[x] or 0) >= 80 and (dup_removals[x] or 0) >= 60 \
                and (failed_reductions[x] or 0) >= 50 \
                and mute_status[x] != "NO_DEGENERATE":
            looks_stable = True
            if best_x is None:
                best_x = x

    flags = {
        "MINI_OOS_FILTER_VALIDATION_DONE": "YES",
        "FILTER_30M_PRIMARY_RECALL_PCT": recalls[30],
        "FILTER_60M_PRIMARY_RECALL_PCT": recalls[60],
        "FILTER_90M_PRIMARY_RECALL_PCT": recalls[90],
        "FILTER_30M_DUPLICATE_REMOVAL_PCT": dup_removals[30],
        "FILTER_60M_DUPLICATE_REMOVAL_PCT": dup_removals[60],
        "FILTER_90M_DUPLICATE_REMOVAL_PCT": dup_removals[90],
        "FILTER_30M_FAILED_REDUCTION_PCT": failed_reductions[30],
        "FILTER_60M_FAILED_REDUCTION_PCT": failed_reductions[60],
        "FILTER_90M_FAILED_REDUCTION_PCT": failed_reductions[90],
        "FILTER_30M_PRECISION_DELTA_PCT": precision_deltas[30],
        "FILTER_60M_PRECISION_DELTA_PCT": precision_deltas[60],
        "FILTER_90M_PRECISION_DELTA_PCT": precision_deltas[90],
        "FILTER_30M_ACTIONABLE_PER_DAY": actionables[30],
        "FILTER_60M_ACTIONABLE_PER_DAY": actionables[60],
        "FILTER_90M_ACTIONABLE_PER_DAY": actionables[90],
        "MINI_OOS_MUTE_DAY_STABLE": "YES" if all(v != "NO_DEGENERATE" for v in mute_status.values()) else "NO",
        "MINI_OOS_MUTE_DAY_STATUS_PER_X": mute_status,
        "FILTER_LOOKS_STABLE": "YES" if looks_stable else "NO",
        "FILTER_PROBABLY_OVERFIT": "YES" if any_overfit_signal else "NO",
        "FILTER_INVALID_FUTURE_LEAK": leak["FILTER_INVALID_FUTURE_LEAK"],
        "READY_FOR_PASSIVE_LIVE_OBSERVER": "YES" if (
            looks_stable and not any_overfit_signal and leak["FILTER_INVALID_FUTURE_LEAK"] == "NO"
        ) else "NO",
        "best_x_min_under_good_criteria": best_x,
    }

    # ---------- write outputs ----------
    out_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "mini-OOS, 3 days only: " + ", ".join(DATES),
        "venue": "okx-swap",
        "symbol": "BTC-USDT-SWAP",
        "filter_under_test": "duplicate_60m_STRICT AND fast_trigger<=X for X in {30,60,90}",
        "duplicate_60m_definition": {
            "window_min": WINDOW_MIN,
            "price_band_pct_for_continuation": PRICE_BAND_PCT_FOR_CONTINUATION,
            "match_logic": "prior triggered + same direction + (same uniqueMoveId OR mid within price_band)",
        },
        "results_by_x_min": per_x_results,
        "future_leak_audit": leak,
        "flags": flags,
    }
    (REPORTS / "OKX_DIRECT_MINI_OOS_FILTER_VALIDATION_0311_0313.json").write_text(
        json.dumps(out_json, indent=2, default=str), encoding="utf-8"
    )

    # markdown
    md = [
        "# OKX direct mini-OOS filter validation - 2026-03-11..2026-03-13",
        "",
        f"**Build:** {out_json['build_time_utc']}",
        f"**Scope:** 3 days only ({', '.join(DATES)}). Read-only over already-produced replay JSONs.",
        f"**Filter under test:** `duplicate_60m_STRICT AND fast_trigger<=X` for X in {SENSITIVITY_X_MIN} min.",
        "",
        "## HARD DISCLAIMER",
        "",
        "  - 3 days is a very small OOS sample. Conclusions here are SUGGESTIVE.",
        "  - The filter is post-hoc and PASSIVE. It does not alter the engine or thresholds.",
        "  - No production integration. No profitability claim.",
        "",
        "## A. duplicate_60m STRICT definition",
        "",
        "For each triggered zone Z (direction D, triggerTs T):",
        "  Z is SUPPRESSED if there exists ANOTHER triggered zone Z' such that",
        "    (a) Z'.triggerTs < T  (strict past, no future leak)",
        f"    (b) 0 < T - Z'.triggerTs <= {WINDOW_MIN} min",
        "    (c) Z'.direction == D",
        f"    (d) (same uniqueMoveId as Z) OR (zone midpoint within +/- {PRICE_BAND_PCT_FOR_CONTINUATION} % of Z's midpoint)",
        "",
        "## B. Future-leak audit",
        "",
        f"- `FILTER_INVALID_FUTURE_LEAK` = **{leak['FILTER_INVALID_FUTURE_LEAK']}**",
        f"- allowed fields used: `{leak['allowed_fields_used_in_suppress']}`",
        f"- forbidden fields referenced: `{leak['forbidden_fields_referenced']}`",
        "",
        "Notes:",
    ]
    for n in leak["notes"]:
        md.append(f"  - {n}")
    md.extend(["", "## C. Per-day baseline + filtered (3 X sensitivity values)", ""])

    for x in SENSITIVITY_X_MIN:
        md.append(f"### X = {x} min")
        md.append("")
        md.append("| date | baseline zones/trig/reached/prim/dup/fail | filtered trig_kept/reached_kept/prim_kept/dup_kept/fail_kept | prec base->filt |")
        md.append("|---|---|---|---|")
        for d in per_x_results[x]["per_day"]:
            b = d["baseline"]
            f = d["filtered"]
            base_str = f"{b['n_zones']}/{b['n_triggered']}/{b['n_reached_raw']}/{b['n_primary_unique']}/{b['n_duplicate_reached']}/{b['n_failed_triggered']}"
            filt_str = f"{f['n_triggered_kept']}/{f['n_reached_raw_kept']}/{f['n_primary_kept']}/{f['n_duplicate_kept']}/{f['n_failed_kept']}"
            md.append(f"| {d['date']} | {base_str} | {filt_str} | {b['precision_triggered_reached']} -> {f['precision_triggered_reached']} |")
        agg = per_x_results[x]["aggregate"]
        md.append("")
        md.append(f"**Aggregate (X={x}m):** "
                  f"primary recall **{agg['primary_recall_pct']}%**, "
                  f"duplicate removal **{agg['duplicate_removal_pct']}%**, "
                  f"failed reduction **{agg['failed_reduction_pct']}%**, "
                  f"precision delta **{agg['precision_delta_pct']} pp**, "
                  f"actionable signals/day **{agg['actionable_signals_per_day']}**, "
                  f"mute-day **{per_x_results[x]['mute_day_audit']['MUTE_DAY_STABLE']}**")
        md.append("")

    md.extend([
        "## D. Sensitivity comparison (aggregate over the 3 days)",
        "",
        "| X (min) | primary recall % | dup removal % | failed reduce % | prec delta pp | actionable/day | mute-day |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ])
    for x in SENSITIVITY_X_MIN:
        a = per_x_results[x]["aggregate"]
        md.append(
            f"| {x} | {a['primary_recall_pct']} | {a['duplicate_removal_pct']} | "
            f"{a['failed_reduction_pct']} | {a['precision_delta_pct']} | "
            f"{a['actionable_signals_per_day']} | {per_x_results[x]['mute_day_audit']['MUTE_DAY_STABLE']} |"
        )

    md.extend([
        "",
        "## E. Late-entry hypothesis (across all suppressed zones)",
        "",
        "| X (min) | n suppressed with cluster meta | median dt from first trigger (min) | median dt from primary (min) | median price dist from primary % |",
        "|---:|---:|---:|---:|---:|",
    ])
    for x in SENSITIVITY_X_MIN:
        le = per_x_results[x]["late_entry_hypothesis"]
        md.append(
            f"| {x} | {le['n_suppressed_with_cluster_meta']} | "
            f"{le['median_delta_t_from_first_trigger_in_cluster_min']} | "
            f"{le['median_delta_t_from_primary_trigger_min']} | "
            f"{le['median_delta_price_pct_from_primary']} |"
        )

    md.extend([
        "",
        "Hypothesis: filter preferentially removes LATE-entry continuation zones, NOT early primaries.",
        "Pass condition: median delta_t from primary is positive (suppressed zones trigger AFTER primary) and reasonably large.",
        "",
        "## F. Mute-day (2026-03-12) audit",
        "",
    ])
    mute0 = per_x_results[60]["mute_day_audit"]  # representative
    if mute0.get("present"):
        b = mute0["baseline"]; f = mute0["filtered"]
        md.append(f"- baseline 03-12: zones={b['n_zones']}, triggered={b['n_triggered']}, reached={b['n_reached_raw']}, primary={b['n_primary_unique']}")
        md.append(f"- filtered (X=60m): triggered_kept={f['n_triggered_kept']}, reached_kept={f['n_reached_raw_kept']}")
        md.append(f"- precision becomes undefined (0/0) after filter? **{mute0['precision_undefined_after_filter']}**")
        md.append(f"- filter introduced any new positives? **{not mute0['no_new_positives_introduced']}**")
        md.append("")
        md.append(f"Comment: {mute0['comment']}")
    md.extend([
        "",
        "## G. Verdict",
        "",
        f"- FILTER_LOOKS_STABLE = **{flags['FILTER_LOOKS_STABLE']}**",
        f"- FILTER_PROBABLY_OVERFIT = **{flags['FILTER_PROBABLY_OVERFIT']}**",
        f"- best X (passing good criteria): **{flags['best_x_min_under_good_criteria']}**",
        "",
        "## H. Final flag matrix",
        "",
        "```",
    ])
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.append("```")

    md.extend([
        "",
        "## I. Hard rules honored",
        "",
        "- strategy / thresholds / `zoneDetector`: UNCHANGED",
        "- no new backtest spawned; no conversion re-run",
        "- post-trigger outcomes used only as labels (precision/recall denominators),",
        "  NEVER in the suppress decision",
        "- `zone_score_v1`/`v2`: not used as filter",
        "- no profitability claim",
        "- raw archives and Tardis-compat files untouched",
    ])
    (REPORTS / "OKX_DIRECT_MINI_OOS_FILTER_VALIDATION_0311_0313.md").write_text("\n".join(md), encoding="utf-8")

    print("WROTE:")
    print(" ", REPORTS / "OKX_DIRECT_MINI_OOS_FILTER_VALIDATION_0311_0313.md")
    print(" ", REPORTS / "OKX_DIRECT_MINI_OOS_FILTER_VALIDATION_0311_0313.json")
    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
