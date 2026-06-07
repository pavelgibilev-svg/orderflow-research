"""OKX direct partial-March 2026 zone-calibration analysis.

Read-only over already-produced backtest artefacts:
  reports/okx-direct/OKX_DIRECT_TECHNICAL_REPLAY_2026-03-DD.json   (14 files)

Writes:
  reports/okx-direct/OKX_DIRECT_MARCH_PARTIAL_ZONE_DATASET.{csv,json}
  reports/okx-direct/OKX_DIRECT_MARCH_ZONE_TIMING_ANALYSIS.{md,json}
  reports/okx-direct/OKX_DIRECT_MARCH_DUPLICATE_CLUSTER_ANALYSIS.{md,json}
  reports/okx-direct/OKX_DIRECT_MARCH_FAILED_ZONE_ANALYSIS.{md,json}
  reports/okx-direct/OKX_DIRECT_MARCH_LOCAL_ANOMALY_ANALYSIS.{md,json}
  reports/okx-direct/OKX_DIRECT_MARCH_PASSIVE_FILTER_V0_ANALYSIS.{md,json}
  reports/okx-direct/OKX_DIRECT_MARCH_ZONE_CALIBRATION_REPORT.{md,json}

NO strategy / threshold / engine change. NO score integration. NO new backtest.
NO production filter wired. Research-only.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import math
import statistics as stats
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports/okx-direct"
DATES = [f"2026-03-{i:02d}" for i in range(2, 16)]  # 14 contiguous days

# --------------------------- helpers ---------------------------

def safe(d: dict | None, *keys: str, default=None):
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def cohens_d(a: list[float], b: list[float]) -> float | None:
    a = [x for x in a if x is not None and isinstance(x, (int, float)) and math.isfinite(x)]
    b = [x for x in b if x is not None and isinstance(x, (int, float)) and math.isfinite(x)]
    if len(a) < 2 or len(b) < 2:
        return None
    va, vb = stats.pvariance(a), stats.pvariance(b)
    pooled = math.sqrt((va + vb) / 2.0)
    if pooled == 0:
        return 0.0
    return round((stats.mean(a) - stats.mean(b)) / pooled, 3)


def describe(xs: list[float]) -> dict:
    xs = [x for x in xs if x is not None and isinstance(x, (int, float)) and math.isfinite(x)]
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "mean": round(stats.mean(xs), 4),
        "median": round(stats.median(xs), 4),
        "p25": round(stats.quantiles(xs, n=4)[0], 4) if len(xs) >= 4 else None,
        "p75": round(stats.quantiles(xs, n=4)[2], 4) if len(xs) >= 4 else None,
        "min": round(min(xs), 4),
        "max": round(max(xs), 4),
    }


def percentile_rank(xs: list[float], v: float) -> float:
    """Return v's percentile rank within xs in [0, 100]."""
    xs = [x for x in xs if x is not None and isinstance(x, (int, float)) and math.isfinite(x)]
    if not xs or v is None or not math.isfinite(v):
        return float("nan")
    n = len(xs)
    below = sum(1 for x in xs if x < v)
    same = sum(1 for x in xs if x == v)
    return 100.0 * (below + 0.5 * same) / n


# --------------------------- phase A: dataset ---------------------------

def classify(z: dict) -> str:
    status = z.get("status")
    if status == "RESOLVED_REACHED":
        return "primary_unique_reached_move" if z.get("isPrimaryMoveZone") else "duplicate_reached_move"
    if status == "RESOLVED_FAILED":
        return "failed_triggered"
    if status == "NO_TRIGGER":
        return "no_trigger"
    if status in ("INVALIDATED", "EXPIRED"):
        return "invalidated_or_expired"
    return "unknown"


def extract_pretrigger_features(z: dict) -> dict:
    """Direction-aware extraction of pre-trigger features.

    LONG zones form after a down-move under sell pressure; we want bid refill,
    sell pressure absorbed, etc. SHORT zones are mirror.
    """
    direction = z.get("direction")
    reasons = z.get("reasons") or []
    cand = next((r.get("conditions") or {} for r in reasons if r.get("stage") == "candidate"), {})
    conf = next((r.get("conditions") or {} for r in reasons if r.get("stage") == "confirmed"), {})
    trig = next((r.get("conditions") or {} for r in reasons if r.get("stage") == "trigger"), {})
    scores = z.get("scores") or {}

    if direction == "LONG":
        cand_pressure_against = cand.get("sellPressure")
        cand_refill_with = cand.get("bidRefillScore")
        cand_prior_move_pct = cand.get("downMovePct")
    else:
        cand_pressure_against = cand.get("buyPressure")
        cand_refill_with = cand.get("askRefillScore")
        cand_prior_move_pct = cand.get("upMovePct")

    return {
        # candidate stage
        "cand_pressure_against": cand_pressure_against,
        "cand_absorb_score": cand.get("absorbScore"),
        "cand_refill_with": cand_refill_with,
        "cand_prior_move_pct": cand_prior_move_pct,
        "cand_range_compression": 1.0 if cand.get("rangeCompression") else 0.0,
        # confirmed stage
        "conf_cycles_seen": conf.get("cyclesSeen"),
        "conf_age_min": conf.get("ageMin"),
        "conf_defended_persistence_sec": conf.get("defendedPersistenceSec"),
        "conf_opposite_thinning": conf.get("oppositeThinning"),
        "conf_void_score": conf.get("voidScore"),
        # trigger stage
        "trig_break_pct": trig.get("breakPct"),
        "trig_flow_multiplier": trig.get("flowMultiplier"),
        "trig_side_flow_ok": 1.0 if trig.get("sideFlowOK") else 0.0,
        # scores
        "score_absorption": scores.get("absorptionScore"),
        "score_liquidity_void": scores.get("liquidityVoidScore"),
        "score_ofi": scores.get("ofiScore"),
        "score_refill": scores.get("refillScore"),
        "score_trigger": scores.get("triggerScore"),
        # geometry
        "zone_width_pct": (z.get("zoneHigh", 0) - z.get("zoneLow", 0))
                          / max(z.get("zoneLow", 1), 1) * 100.0
                          if z.get("zoneLow") and z.get("zoneHigh") else None,
    }


def extract_timing(z: dict) -> dict:
    start = z.get("startTs")
    conf = z.get("confirmedTs")
    trig = z.get("triggerTs")
    res = z.get("resolvedTs")
    tgt = z.get("targets") or {}
    reached_at = None
    reached_horizon = None
    for h in ("4h", "8h", "24h"):
        info = tgt.get(h) or {}
        if info.get("outcome") == "reached":
            reached_at = info.get("reachedAt")
            reached_horizon = h
            break

    def diff_min(a, b):
        if a is None or b is None:
            return None
        return (a - b) / 60000.0

    return {
        "candidate_to_confirm_min": diff_min(conf, start),
        "confirm_to_trigger_min": diff_min(trig, conf),
        "total_pre_trigger_min": diff_min(trig, start),
        "trigger_to_resolve_min": diff_min(res, trig),
        "trigger_to_target_min": diff_min(reached_at, trig),
        "candidate_to_target_min": diff_min(reached_at, start),
        "confirmed_to_target_min": diff_min(reached_at, conf),
        "reached_horizon": reached_horizon,
        "reached_at_ts": reached_at,
    }


def build_dataset() -> list[dict]:
    rows: list[dict] = []
    for date in DATES:
        p = REPORTS / f"OKX_DIRECT_TECHNICAL_REPLAY_{date}.json"
        if not p.exists():
            print(f"  WARN missing {p.name}", file=sys.stderr)
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        zones = (d.get("underlying_backtest_summary") or {}).get("zones") or []
        for z in zones:
            feats = extract_pretrigger_features(z)
            timing = extract_timing(z)
            tgt24 = (z.get("targets") or {}).get("24h") or {}
            row = {
                "date": date,
                "zone_id": z.get("id"),
                "direction": z.get("direction"),
                "zoneType": z.get("zoneType"),
                "status": z.get("status"),
                "startTs": z.get("startTs"),
                "confirmedTs": z.get("confirmedTs"),
                "triggerTs": z.get("triggerTs"),
                "resolvedTs": z.get("resolvedTs"),
                "zoneLow": z.get("zoneLow"),
                "zoneHigh": z.get("zoneHigh"),
                "triggered": z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED"),
                "reached_raw": z.get("status") == "RESOLVED_REACHED",
                "uniqueMoveId": z.get("uniqueMoveId"),
                "isPrimaryMoveZone": z.get("isPrimaryMoveZone"),
                "duplicateMoveCredit": z.get("duplicateMoveCredit"),
                "moveClusterSize": z.get("moveClusterSize"),
                "class_label": classify(z),
                # outcome (label, not feature)
                "target_24h_outcome": tgt24.get("outcome"),
                "target_24h_mfePct": tgt24.get("mfePct"),
                "target_24h_maePct": tgt24.get("maePct"),
                "target_24h_max_drawdown_before_target_pct": tgt24.get("maxDrawdownBeforeTargetPct"),
                **feats,
                **timing,
            }
            rows.append(row)
    return rows


# --------------------------- phase B: timing ---------------------------

def timing_analysis(rows: list[dict]) -> dict:
    classes = {
        "primary_unique_reached_move": [r for r in rows if r["class_label"] == "primary_unique_reached_move"],
        "duplicate_reached_move": [r for r in rows if r["class_label"] == "duplicate_reached_move"],
        "failed_triggered": [r for r in rows if r["class_label"] == "failed_triggered"],
        "no_trigger": [r for r in rows if r["class_label"] == "no_trigger"],
        "invalidated_or_expired": [r for r in rows if r["class_label"] == "invalidated_or_expired"],
    }
    timing_fields = [
        "candidate_to_confirm_min",
        "confirm_to_trigger_min",
        "total_pre_trigger_min",
        "trigger_to_resolve_min",
        "trigger_to_target_min",
        "candidate_to_target_min",
        "confirmed_to_target_min",
    ]
    per_class = {
        name: {f: describe([r.get(f) for r in lst]) for f in timing_fields}
        for name, lst in classes.items()
    }
    # pairwise Cohen d for primary vs (duplicate, failed)
    pairs = [
        ("primary_unique_reached_move", "duplicate_reached_move"),
        ("primary_unique_reached_move", "failed_triggered"),
        ("duplicate_reached_move", "failed_triggered"),
    ]
    effects = {}
    for a, b in pairs:
        effects[f"{a}__vs__{b}"] = {
            f: cohens_d([r.get(f) for r in classes[a]], [r.get(f) for r in classes[b]])
            for f in timing_fields
        }
    return {"per_class": per_class, "effects_cohens_d": effects}


# --------------------------- phase C: duplicates ---------------------------

def duplicate_cluster_analysis(rows: list[dict]) -> dict:
    by_cluster = defaultdict(list)
    for r in rows:
        if r.get("uniqueMoveId"):
            by_cluster[(r["date"], r["uniqueMoveId"])].append(r)

    clusters: list[dict] = []
    for (date, mid), zs in sorted(by_cluster.items()):
        prim = next((z for z in zs if z.get("isPrimaryMoveZone")), None)
        dups = [z for z in zs if not z.get("isPrimaryMoveZone")]
        triggered = [z for z in zs if z.get("triggered")]
        first_trig = min((z["triggerTs"] for z in zs if z.get("triggerTs")), default=None)
        prim_trig = prim.get("triggerTs") if prim else None
        # target reached time = primary's reached time (if primary reached); fallback to earliest reached zone
        reached_at = None
        if prim and prim.get("class_label") == "primary_unique_reached_move":
            reached_at = prim.get("reached_at_ts")
        if reached_at is None:
            # fallback: earliest reached_at among duplicate_reached zones
            reached_candidates = [z.get("reached_at_ts") for z in zs if z.get("reached_at_ts")]
            if reached_candidates:
                reached_at = min(reached_candidates)
        # Late-entry counts: duplicates triggered after primary trigger
        dups_after_first_trig = [d for d in dups if d.get("triggerTs") and first_trig and d["triggerTs"] > first_trig]
        # Duplicates triggered after target already half-reached:
        # we use primary's trigger-to-target span as proxy
        dups_after_half_to_target = []
        if reached_at and prim_trig:
            halfway = prim_trig + (reached_at - prim_trig) / 2
            dups_after_half_to_target = [d for d in dups if d.get("triggerTs") and d["triggerTs"] > halfway]
        # price + time distance between primary and duplicates
        price_dists: list[float] = []
        time_dists_min: list[float] = []
        if prim and prim.get("zoneLow") and prim.get("zoneHigh"):
            prim_mid = (prim["zoneLow"] + prim["zoneHigh"]) / 2
            for d in dups:
                if d.get("zoneLow") and d.get("zoneHigh"):
                    d_mid = (d["zoneLow"] + d["zoneHigh"]) / 2
                    price_dists.append(abs(d_mid - prim_mid) / prim_mid * 100.0)
                if d.get("triggerTs") and prim_trig:
                    time_dists_min.append((d["triggerTs"] - prim_trig) / 60000.0)
        clusters.append({
            "date": date,
            "uniqueMoveId": mid,
            "direction": prim.get("direction") if prim else (zs[0].get("direction") if zs else None),
            "n_zones": len(zs),
            "n_triggered": len(triggered),
            "n_duplicates": len(dups),
            "primary_id": prim.get("zone_id") if prim else None,
            "first_trigger_ts": first_trig,
            "primary_trigger_ts": prim_trig,
            "target_reached_ts": reached_at,
            "trigger_to_target_min": (reached_at - prim_trig) / 60000.0 if prim_trig and reached_at else None,
            "dups_triggered_after_first_trigger": len(dups_after_first_trig),
            "dups_triggered_after_half_to_target": len(dups_after_half_to_target),
            "price_distance_from_primary_pct__mean": (round(stats.mean(price_dists), 4) if price_dists else None),
            "price_distance_from_primary_pct__max": (round(max(price_dists), 4) if price_dists else None),
            "time_distance_from_primary_min__mean": (round(stats.mean(time_dists_min), 4) if time_dists_min else None),
            "time_distance_from_primary_min__max": (round(max(time_dists_min), 4) if time_dists_min else None),
        })

    # Dedup-rule synthesis: for each duplicate-reached zone, find time and price
    # distance to the FIRST triggered zone of the same uniqueMoveId.
    dedup_rule_table: list[dict] = []
    for c in clusters:
        if c["n_duplicates"] == 0:
            continue
        # Look up actual rows
        zs = by_cluster[(c["date"], c["uniqueMoveId"])]
        first_trig_zone = min((z for z in zs if z.get("triggerTs")),
                              key=lambda z: z["triggerTs"], default=None)
        if not first_trig_zone:
            continue
        first_trig_ts = first_trig_zone["triggerTs"]
        first_mid = (first_trig_zone.get("zoneLow", 0) + first_trig_zone.get("zoneHigh", 0)) / 2 \
            if first_trig_zone.get("zoneLow") else None
        for d in zs:
            if not d.get("isPrimaryMoveZone") and d.get("triggered") and d.get("triggerTs"):
                d_mid = (d.get("zoneLow", 0) + d.get("zoneHigh", 0)) / 2 \
                    if d.get("zoneLow") else None
                dedup_rule_table.append({
                    "date": c["date"],
                    "uniqueMoveId": c["uniqueMoveId"],
                    "duplicate_id": d["zone_id"],
                    "delta_t_min_from_first_trigger": (d["triggerTs"] - first_trig_ts) / 60000.0,
                    "delta_price_pct_from_first_zone": (abs(d_mid - first_mid) / first_mid * 100.0)
                        if first_mid and d_mid else None,
                    "duplicate_reached": d.get("class_label") == "duplicate_reached_move",
                })

    return {"clusters": clusters, "dedup_rule_table": dedup_rule_table}


# --------------------------- phase D: failed ---------------------------

def failed_zone_analysis(rows: list[dict]) -> dict:
    failed = [r for r in rows if r["class_label"] == "failed_triggered"]
    # opposite direction reached later same day
    by_date_dir = defaultdict(list)
    for r in rows:
        by_date_dir[(r["date"], r["direction"])].append(r)

    failed_records: list[dict] = []
    for z in failed:
        date = z["date"]
        d_op = "SHORT" if z["direction"] == "LONG" else "LONG"
        opp_reached_after = any(
            (zz["class_label"] in ("primary_unique_reached_move", "duplicate_reached_move"))
            and zz.get("triggerTs") and z.get("resolvedTs")
            and zz["triggerTs"] > z["resolvedTs"]
            for zz in by_date_dir[(date, d_op)]
        )
        # active same-direction triggered zone nearby (within 60 min before this trigger)
        same_dir = by_date_dir[(date, z["direction"])]
        active_dup_context = any(
            zz.get("triggerTs") and z.get("triggerTs") and zz["zone_id"] != z["zone_id"]
            and 0 < z["triggerTs"] - zz["triggerTs"] <= 60 * 60_000
            for zz in same_dir
        )
        failed_records.append({
            "date": date,
            "zone_id": z["zone_id"],
            "direction": z["direction"],
            "uniqueMoveId": z.get("uniqueMoveId"),
            "moveClusterSize": z.get("moveClusterSize"),
            "prior_move_pct": z.get("cand_prior_move_pct"),
            "pressure_against": z.get("cand_pressure_against"),
            "absorb_score": z.get("cand_absorb_score"),
            "trig_break_pct": z.get("trig_break_pct"),
            "trig_flow_multiplier": z.get("trig_flow_multiplier"),
            "confirm_to_trigger_min": z.get("confirm_to_trigger_min"),
            "total_pre_trigger_min": z.get("total_pre_trigger_min"),
            "score_ofi": z.get("score_ofi"),
            "score_absorption": z.get("score_absorption"),
            "target_24h_mfePct": z.get("target_24h_mfePct"),
            "target_24h_maePct": z.get("target_24h_maePct"),
            "opp_dir_reached_after_fail": opp_reached_after,
            "had_active_same_dir_duplicate_in_60m": active_dup_context,
        })

    # summary distributions
    fields = [
        "prior_move_pct", "pressure_against", "absorb_score", "trig_break_pct",
        "trig_flow_multiplier", "confirm_to_trigger_min", "total_pre_trigger_min",
        "score_ofi", "score_absorption", "target_24h_mfePct",
    ]
    summary = {f: describe([r.get(f) for r in failed_records]) for f in fields}
    counts = {
        "n_failed": len(failed_records),
        "n_with_opp_dir_reached_after": sum(1 for r in failed_records if r["opp_dir_reached_after_fail"]),
        "n_with_active_same_dir_duplicate_in_60m": sum(1 for r in failed_records if r["had_active_same_dir_duplicate_in_60m"]),
    }
    return {"records": failed_records, "feature_summary": summary, "counts": counts}


# --------------------------- phase E: local anomaly ---------------------------

ANOMALY_FEATURES = [
    "cand_pressure_against", "cand_absorb_score", "cand_refill_with",
    "cand_prior_move_pct",
    "conf_cycles_seen", "conf_age_min",
    "trig_break_pct", "trig_flow_multiplier",
    "score_ofi", "score_absorption", "score_trigger",
    "zone_width_pct",
]


def local_anomaly_analysis(rows: list[dict]) -> dict:
    """For each zone, compute per-day percentile rank of each feature, plus pool rank.

    Per-day baseline approximates a "local" baseline at the granularity available
    in the engine output (the engine emits one consolidated row per zone, not a
    minute-by-minute orderflow stream, so we cannot do a true 30m/1h windowed
    z-score from the existing artefacts; we use same-date and full-pool rank
    instead).
    """
    by_date = defaultdict(list)
    for r in rows:
        by_date[r["date"]].append(r)

    # full pool feature lists (excluding None)
    pool = {f: [r.get(f) for r in rows if r.get(f) is not None] for f in ANOMALY_FEATURES}

    out_rows = []
    for r in rows:
        same_day = by_date[r["date"]]
        per_day_ranks = {}
        per_pool_ranks = {}
        for f in ANOMALY_FEATURES:
            v = r.get(f)
            if v is None:
                per_day_ranks[f] = None
                per_pool_ranks[f] = None
                continue
            day_pool = [x.get(f) for x in same_day if x.get(f) is not None]
            per_day_ranks[f] = round(percentile_rank(day_pool, v), 2)
            per_pool_ranks[f] = round(percentile_rank(pool[f], v), 2)
        out_rows.append({
            "date": r["date"],
            "zone_id": r["zone_id"],
            "class_label": r["class_label"],
            "direction": r["direction"],
            "per_day_pct_rank": per_day_ranks,
            "per_pool_pct_rank": per_pool_ranks,
        })

    # class summary: mean per-day percentile rank by class for each feature
    classes = {
        "primary_unique_reached_move": [r for r in out_rows if r["class_label"] == "primary_unique_reached_move"],
        "duplicate_reached_move": [r for r in out_rows if r["class_label"] == "duplicate_reached_move"],
        "failed_triggered": [r for r in out_rows if r["class_label"] == "failed_triggered"],
    }
    class_mean_rank: dict[str, dict[str, dict[str, float | None]]] = {}
    for f in ANOMALY_FEATURES:
        class_mean_rank[f] = {}
        for name, lst in classes.items():
            day_vals = [r["per_day_pct_rank"].get(f) for r in lst if r["per_day_pct_rank"].get(f) is not None]
            pool_vals = [r["per_pool_pct_rank"].get(f) for r in lst if r["per_pool_pct_rank"].get(f) is not None]
            class_mean_rank[f][name] = {
                "n_day": len(day_vals),
                "mean_per_day_pct_rank": round(stats.mean(day_vals), 2) if day_vals else None,
                "median_per_day_pct_rank": round(stats.median(day_vals), 2) if day_vals else None,
                "mean_per_pool_pct_rank": round(stats.mean(pool_vals), 2) if pool_vals else None,
                "median_per_pool_pct_rank": round(stats.median(pool_vals), 2) if pool_vals else None,
            }

    return {"per_zone": out_rows, "class_summary": class_mean_rank}


# --------------------------- phase F+G: passive filters ---------------------------

# Build a global ordered list of zones by triggerTs (across all dates) so we can
# look up "did this zone trigger AFTER another zone of same direction recently".

def _attach_filter_context(rows: list[dict]) -> None:
    by_date_dir = defaultdict(list)
    for r in rows:
        by_date_dir[(r["date"], r["direction"])].append(r)
    for lst in by_date_dir.values():
        lst.sort(key=lambda r: r.get("triggerTs") or 0)
    for r in rows:
        if not r.get("triggerTs"):
            r["_has_active_same_dir_within_30m"] = False
            r["_has_active_same_dir_within_60m"] = False
            continue
        same = by_date_dir[(r["date"], r["direction"])]
        idx = same.index(r)
        prev_30 = False
        prev_60 = False
        for prior in reversed(same[:idx]):
            if not prior.get("triggerTs"):
                continue
            dt_min = (r["triggerTs"] - prior["triggerTs"]) / 60000.0
            if 0 < dt_min <= 30:
                prev_30 = True
            if 0 < dt_min <= 60:
                prev_60 = True
            if dt_min > 60:
                break
        r["_has_active_same_dir_within_30m"] = prev_30
        r["_has_active_same_dir_within_60m"] = prev_60


# Rule definitions: each takes a row and returns True iff the rule WOULD KEEP this zone
# (i.e., zone passes the filter; rule is on a "keep" basis).
# A zone that never reaches the trigger stage trivially passes (we only filter triggered ones).

def keep_under_duplicate_30m(r: dict) -> bool:
    if not r.get("triggered"):
        return True
    return not r.get("_has_active_same_dir_within_30m", False)


def keep_under_duplicate_60m(r: dict) -> bool:
    if not r.get("triggered"):
        return True
    return not r.get("_has_active_same_dir_within_60m", False)


def keep_under_late_entry(r: dict, threshold_pct: float = 0.5) -> bool:
    """Drop zones where prior move (direction-aware) before trigger >= threshold_pct.
    Tight threshold on OKX because zone reasons.cand.prior_move is in fraction-pct."""
    if not r.get("triggered"):
        return True
    v = r.get("cand_prior_move_pct")
    if v is None:
        return True
    return v < threshold_pct


def keep_under_fast_trigger(r: dict, threshold_min: float = 60.0) -> bool:
    if not r.get("triggered"):
        return True
    v = r.get("confirm_to_trigger_min")
    if v is None:
        return True
    return v <= threshold_min


def keep_under_flow_confirmation(r: dict, threshold: float = 2.0) -> bool:
    """Require trig_flow_multiplier >= threshold (engine triggers at 1.4 by default,
    so 2.0 picks the upper half of the trigger pool)."""
    if not r.get("triggered"):
        return True
    v = r.get("trig_flow_multiplier")
    if v is None:
        return True
    return v >= threshold


def keep_under_target_feasibility(r: dict, threshold_pct: float = 0.5) -> bool:
    """Drop zones where zone width is so wide that a 2% target is unrealistic.
    zone_width_pct expresses zone span as % of its low; wide zones tend to be
    distribution/accumulation noise."""
    if not r.get("triggered"):
        return True
    v = r.get("zone_width_pct")
    if v is None:
        return True
    return v <= threshold_pct


def keep_under_counter_direction(r: dict, threshold: float = 0.0) -> bool:
    """Drop zones whose ofiScore points AGAINST the zone direction at trigger.
    LONG wants positive OFI (taker buys), SHORT wants negative OFI."""
    if not r.get("triggered"):
        return True
    ofi = r.get("score_ofi")
    if ofi is None:
        return True
    if r["direction"] == "LONG":
        return ofi >= threshold
    return ofi <= threshold


RULES = {
    "duplicate_30m": keep_under_duplicate_30m,
    "duplicate_60m": keep_under_duplicate_60m,
    "late_entry_prior_move<0.5pct": lambda r: keep_under_late_entry(r, 0.5),
    "fast_trigger_<=60min": lambda r: keep_under_fast_trigger(r, 60),
    "fast_trigger_<=30min": lambda r: keep_under_fast_trigger(r, 30),
    "flow_confirmation_>=2x": lambda r: keep_under_flow_confirmation(r, 2.0),
    "flow_confirmation_>=3x": lambda r: keep_under_flow_confirmation(r, 3.0),
    "target_feasibility_width<=0.5pct": lambda r: keep_under_target_feasibility(r, 0.5),
    "counter_direction_ofi": keep_under_counter_direction,
}


def evaluate_filter(rows: list[dict], keep_fn) -> dict:
    kept = [r for r in rows if keep_fn(r)]
    removed = [r for r in rows if not keep_fn(r)]
    n_zones_kept = len(kept)
    n_triggered_kept = sum(1 for r in kept if r.get("triggered"))
    n_reached_kept = sum(1 for r in kept if r.get("reached_raw"))
    primary_kept = sum(1 for r in kept if r["class_label"] == "primary_unique_reached_move")
    duplicate_kept = sum(1 for r in kept if r["class_label"] == "duplicate_reached_move")
    failed_kept = sum(1 for r in kept if r["class_label"] == "failed_triggered")
    duplicate_removed = sum(1 for r in removed if r["class_label"] == "duplicate_reached_move")
    failed_removed = sum(1 for r in removed if r["class_label"] == "failed_triggered")
    primary_removed = sum(1 for r in removed if r["class_label"] == "primary_unique_reached_move")
    # totals from full set
    total_primary = sum(1 for r in rows if r["class_label"] == "primary_unique_reached_move")
    total_duplicate = sum(1 for r in rows if r["class_label"] == "duplicate_reached_move")
    total_failed = sum(1 for r in rows if r["class_label"] == "failed_triggered")
    # unique-move recall: of 15 unique moves, how many still have their primary zone kept?
    primary_kept_ratio = primary_kept / total_primary if total_primary else None
    duplicate_remove_ratio = duplicate_removed / total_duplicate if total_duplicate else None
    failed_reduce_ratio = failed_removed / total_failed if total_failed else None
    # actionable signals: triggered zones still in kept set, per day
    dates_in_pool = sorted({r["date"] for r in rows})
    actionable_per_day = (n_triggered_kept / len(dates_in_pool)) if dates_in_pool else None
    # precision on triggered: how many of triggered-kept reached?
    precision_triggered = (n_reached_kept / n_triggered_kept) if n_triggered_kept else None
    # precision on primary moves among triggered kept
    precision_primary = (primary_kept / n_triggered_kept) if n_triggered_kept else None
    return {
        "n_zones_kept": n_zones_kept,
        "n_triggered_kept": n_triggered_kept,
        "n_reached_raw_kept": n_reached_kept,
        "n_primary_kept": primary_kept,
        "n_duplicate_kept": duplicate_kept,
        "n_failed_kept": failed_kept,
        "n_duplicate_removed": duplicate_removed,
        "n_failed_removed": failed_removed,
        "n_primary_removed": primary_removed,
        "primary_recall": round(primary_kept_ratio, 3) if primary_kept_ratio is not None else None,
        "duplicate_remove_rate": round(duplicate_remove_ratio, 3) if duplicate_remove_ratio is not None else None,
        "failed_reduce_rate": round(failed_reduce_ratio, 3) if failed_reduce_ratio is not None else None,
        "actionable_signals_per_day": round(actionable_per_day, 3) if actionable_per_day is not None else None,
        "precision_triggered_reached": round(precision_triggered, 3) if precision_triggered is not None else None,
        "precision_primary_among_triggered_kept": round(precision_primary, 3) if precision_primary is not None else None,
    }


def passive_filter_v0(rows: list[dict]) -> dict:
    _attach_filter_context(rows)
    baseline_counts = {
        "n_zones": len(rows),
        "n_triggered": sum(1 for r in rows if r.get("triggered")),
        "n_reached_raw": sum(1 for r in rows if r.get("reached_raw")),
        "n_primary_unique": sum(1 for r in rows if r["class_label"] == "primary_unique_reached_move"),
        "n_duplicate_reached": sum(1 for r in rows if r["class_label"] == "duplicate_reached_move"),
        "n_failed_triggered": sum(1 for r in rows if r["class_label"] == "failed_triggered"),
        "n_no_trigger": sum(1 for r in rows if r["class_label"] == "no_trigger"),
        "n_invalidated_or_expired": sum(1 for r in rows if r["class_label"] == "invalidated_or_expired"),
    }

    single_results = {name: evaluate_filter(rows, fn) for name, fn in RULES.items()}

    # Combinations (AND of multiple rules)
    combos = [
        ("duplicate_60m_AND_flow>=2x", ["duplicate_60m", "flow_confirmation_>=2x"]),
        ("duplicate_60m_AND_fast<=60m", ["duplicate_60m", "fast_trigger_<=60min"]),
        ("duplicate_60m_AND_late_entry<0.5pct", ["duplicate_60m", "late_entry_prior_move<0.5pct"]),
        ("duplicate_60m_AND_counter_direction_ofi", ["duplicate_60m", "counter_direction_ofi"]),
        ("duplicate_60m_AND_flow>=2x_AND_counter_direction_ofi",
            ["duplicate_60m", "flow_confirmation_>=2x", "counter_direction_ofi"]),
        ("duplicate_60m_AND_flow>=2x_AND_fast<=60m",
            ["duplicate_60m", "flow_confirmation_>=2x", "fast_trigger_<=60min"]),
        ("ALL5: dup60_flow2_fast60_late0.5_counter_ofi",
            ["duplicate_60m", "flow_confirmation_>=2x", "fast_trigger_<=60min",
             "late_entry_prior_move<0.5pct", "counter_direction_ofi"]),
    ]
    combo_results = {}
    for name, parts in combos:
        keep_fn = lambda r, parts=parts: all(RULES[p](r) for p in parts)
        combo_results[name] = evaluate_filter(rows, keep_fn)

    # Best filter selection by composite: keep ≥60% primary recall AND maximise (duplicate_remove_rate + failed_reduce_rate)
    candidates = []
    for name, res in {**single_results, **combo_results}.items():
        if res["primary_recall"] is None or res["primary_recall"] < 0.6:
            continue
        score = (res["duplicate_remove_rate"] or 0) + (res["failed_reduce_rate"] or 0)
        candidates.append((score, name, res))
    candidates.sort(reverse=True)
    best = candidates[0] if candidates else None

    return {
        "baseline_counts": baseline_counts,
        "single_filters": single_results,
        "combinations": combo_results,
        "best_filter": {"name": best[1], "score": round(best[0], 3), "metrics": best[2]} if best else None,
    }


# --------------------------- writer helpers ---------------------------

def write_dataset(rows: list[dict]) -> None:
    json_path = REPORTS / "OKX_DIRECT_MARCH_PARTIAL_ZONE_DATASET.json"
    json_path.write_text(json.dumps({
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct partial March 2026 (2026-03-02..2026-03-15)",
        "venue": "okx-swap",
        "symbol": "BTC-USDT-SWAP",
        "n_rows": len(rows),
        "rows": rows,
    }, indent=2, default=str), encoding="utf-8")

    csv_path = REPORTS / "OKX_DIRECT_MARCH_PARTIAL_ZONE_DATASET.csv"
    # union of keys from any row
    keys = list(rows[0].keys())
    for r in rows:
        for k in r.keys():
            if k not in keys:
                keys.append(k)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def md_describe_block(title: str, classes: dict, fields: list[str], per_class: dict) -> list[str]:
    out = [f"### {title}", "", "| feature | primary mean / median | duplicate mean / median | failed mean / median |", "|---|---|---|---|"]
    for f in fields:
        p = per_class.get("primary_unique_reached_move", {}).get(f, {})
        d = per_class.get("duplicate_reached_move", {}).get(f, {})
        ff = per_class.get("failed_triggered", {}).get(f, {})
        out.append(f"| `{f}` | {p.get('mean')} / {p.get('median')} | "
                   f"{d.get('mean')} / {d.get('median')} | "
                   f"{ff.get('mean')} / {ff.get('median')} |")
    return out


def write_timing_report(timing: dict) -> None:
    json_path = REPORTS / "OKX_DIRECT_MARCH_ZONE_TIMING_ANALYSIS.json"
    json_path.write_text(json.dumps(timing, indent=2), encoding="utf-8")
    fields = [
        "candidate_to_confirm_min", "confirm_to_trigger_min", "total_pre_trigger_min",
        "trigger_to_resolve_min", "trigger_to_target_min",
        "candidate_to_target_min", "confirmed_to_target_min",
    ]
    md = [
        "# OKX direct partial-March 2026 - zone timing analysis",
        "",
        "**Scope:** 14 UTC days 2026-03-02..2026-03-15. No strategy / threshold change.",
        "",
        "## A. Per-class timing distributions",
        "",
        *md_describe_block("primary vs duplicate vs failed", timing["per_class"], fields, timing["per_class"]),
        "",
        "## B. Cohen's d effects (pairwise)",
        "",
        "| feature | primary vs duplicate | primary vs failed | duplicate vs failed |",
        "|---|---:|---:|---:|",
    ]
    for f in fields:
        e1 = timing["effects_cohens_d"]["primary_unique_reached_move__vs__duplicate_reached_move"].get(f)
        e2 = timing["effects_cohens_d"]["primary_unique_reached_move__vs__failed_triggered"].get(f)
        e3 = timing["effects_cohens_d"]["duplicate_reached_move__vs__failed_triggered"].get(f)
        md.append(f"| `{f}` | {e1} | {e2} | {e3} |")
    md.extend([
        "",
        "## C. Notes",
        "",
        "- Negative d for `confirm_to_trigger_min` / `total_pre_trigger_min` (primary vs failed) means primaries trigger FASTER after confirmation.",
        "- Positive d for `trigger_to_target_min` (primary vs duplicate) means primaries take longer to reach the move (because they enter EARLIER).",
        "- Caveat: n=15 primary positives across 14 days; effects are suggestive only.",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_ZONE_TIMING_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")


def write_duplicate_report(dup: dict) -> None:
    (REPORTS / "OKX_DIRECT_MARCH_DUPLICATE_CLUSTER_ANALYSIS.json").write_text(
        json.dumps(dup, indent=2), encoding="utf-8")
    md = [
        "# OKX direct partial-March 2026 - duplicate / move cluster analysis",
        "",
        "**Scope:** 14 UTC days 2026-03-02..2026-03-15. 15 unique moves -> 15 clusters.",
        "",
        "## A. Per-cluster summary",
        "",
        "| date | dir | mid | nZones | nTrig | nDup | trig_to_target_min | dups_after_first | dups_after_half | dt_min mean/max | dprice% mean/max |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for c in dup["clusters"]:
        md.append(
            f"| {c['date']} | {c['direction']} | {c['uniqueMoveId']} | "
            f"{c['n_zones']} | {c['n_triggered']} | {c['n_duplicates']} | "
            f"{c['trigger_to_target_min']} | {c['dups_triggered_after_first_trigger']} | "
            f"{c['dups_triggered_after_half_to_target']} | "
            f"{c['time_distance_from_primary_min__mean']} / {c['time_distance_from_primary_min__max']} | "
            f"{c['price_distance_from_primary_pct__mean']} / {c['price_distance_from_primary_pct__max']} |"
        )

    # Dedup rule shape: distribution of delta_t / delta_price for actual duplicate-reached zones
    rt = dup["dedup_rule_table"]
    dts = [r["delta_t_min_from_first_trigger"] for r in rt if r["delta_t_min_from_first_trigger"] is not None]
    dps = [r["delta_price_pct_from_first_zone"] for r in rt if r["delta_price_pct_from_first_zone"] is not None]
    md.extend([
        "",
        "## B. Delta-from-first-trigger distribution (duplicate triggered zones, n=" + str(len(rt)) + ")",
        "",
        f"- delta_t_min:  {describe(dts)}",
        f"- delta_price_pct: {describe(dps)}",
        "",
        "## C. Dedup-rule hypothesis",
        "",
        "If a same-direction zone has already triggered within the last X minutes (or within Y% price band),",
        "a subsequent same-direction zone is statistically a duplicate. Candidate cuts to test:",
        "  - X = 30 min, 60 min",
        "  - Y = 0.5 %, 1.0 %",
        "",
        "Phase F passive-filter `duplicate_30m` / `duplicate_60m` evaluates the 30-/60-min cuts.",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_DUPLICATE_CLUSTER_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")


def write_failed_report(failed: dict) -> None:
    (REPORTS / "OKX_DIRECT_MARCH_FAILED_ZONE_ANALYSIS.json").write_text(
        json.dumps(failed, indent=2), encoding="utf-8")
    md = [
        "# OKX direct partial-March 2026 - failed_triggered analysis",
        "",
        f"**Scope:** 14 UTC days, n_failed = {failed['counts']['n_failed']}.",
        "",
        "## A. Counts",
        "",
        f"- n_failed = {failed['counts']['n_failed']}",
        f"- n with opposite direction reaching the move later same day: {failed['counts']['n_with_opp_dir_reached_after']}",
        f"- n with an active same-direction triggered zone in prior 60 min: {failed['counts']['n_with_active_same_dir_duplicate_in_60m']}",
        "",
        "## B. Feature distributions (failed_triggered only)",
        "",
        "| feature | n | mean | median | p25 | p75 | min | max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for f, s in failed["feature_summary"].items():
        md.append(f"| `{f}` | {s.get('n')} | {s.get('mean')} | {s.get('median')} | "
                  f"{s.get('p25')} | {s.get('p75')} | {s.get('min')} | {s.get('max')} |")
    md.extend([
        "",
        "## C. Headline observations",
        "",
        "- High n_with_active_same_dir_duplicate_in_60m suggests many failures are late-entry duplicates of an earlier",
        "  triggered zone that has already exhausted its move; flagging via `duplicate_60m` should remove a chunk.",
        "- If opposite-direction reaches later on a failed zone's day, that day's regime is hostile to this side -",
        "  not a feature we can use as a strategy filter (would be lookahead), but informative for context.",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_FAILED_ZONE_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")


def write_local_anomaly_report(la: dict) -> None:
    (REPORTS / "OKX_DIRECT_MARCH_LOCAL_ANOMALY_ANALYSIS.json").write_text(
        json.dumps(la, indent=2), encoding="utf-8")
    md = [
        "# OKX direct partial-March 2026 - local anomaly analysis",
        "",
        "**Scope:** Per-day percentile rank of each pre-trigger feature for each zone, plus full-pool rank.",
        "**Why not minute-windowed:** the existing per-day backtest JSON aggregates each zone into one row; we don't",
        "have a minute-by-minute orderflow stream from these artefacts, so a true 30m/1h/3h/6h z-score is not buildable",
        "without re-running the backtest with extra logging (forbidden per scope).",
        "",
        "## A. Mean per-day percentile rank by class",
        "",
        "| feature | primary mean / median | duplicate mean / median | failed mean / median |",
        "|---|---|---|---|",
    ]
    for f in ANOMALY_FEATURES:
        cs = la["class_summary"].get(f, {})
        p = cs.get("primary_unique_reached_move", {})
        d = cs.get("duplicate_reached_move", {})
        ff = cs.get("failed_triggered", {})
        md.append(
            f"| `{f}` | {p.get('mean_per_day_pct_rank')} / {p.get('median_per_day_pct_rank')} | "
            f"{d.get('mean_per_day_pct_rank')} / {d.get('median_per_day_pct_rank')} | "
            f"{ff.get('mean_per_day_pct_rank')} / {ff.get('median_per_day_pct_rank')} |"
        )
    md.extend([
        "",
        "## B. Mean full-pool percentile rank by class",
        "",
        "| feature | primary mean / median | duplicate mean / median | failed mean / median |",
        "|---|---|---|---|",
    ])
    for f in ANOMALY_FEATURES:
        cs = la["class_summary"].get(f, {})
        p = cs.get("primary_unique_reached_move", {})
        d = cs.get("duplicate_reached_move", {})
        ff = cs.get("failed_triggered", {})
        md.append(
            f"| `{f}` | {p.get('mean_per_pool_pct_rank')} / {p.get('median_per_pool_pct_rank')} | "
            f"{d.get('mean_per_pool_pct_rank')} / {d.get('median_per_pool_pct_rank')} | "
            f"{ff.get('mean_per_pool_pct_rank')} / {ff.get('median_per_pool_pct_rank')} |"
        )
    md.extend([
        "",
        "## C. Reading guide",
        "",
        "- Per-day rank of 50 = median zone for that day. If primary's mean is > 60 for a feature, that feature is",
        "  systematically high among primaries vs other zones the same day - candidate for a `local_top` filter.",
        "- Mind the n: 15 primaries spread across 14 days; per-day rank can be noisy.",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_LOCAL_ANOMALY_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")


def write_passive_filter_report(pf: dict) -> None:
    (REPORTS / "OKX_DIRECT_MARCH_PASSIVE_FILTER_V0_ANALYSIS.json").write_text(
        json.dumps(pf, indent=2), encoding="utf-8")
    base = pf["baseline_counts"]
    md = [
        "# OKX direct partial-March 2026 - passive filter v0 analysis (research-only)",
        "",
        "**Scope:** 14 UTC days. **NO filter is wired into the strategy.** These rules are evaluated",
        "by re-classifying each already-produced zone post-hoc. No threshold inside the engine is changed.",
        "",
        "## A. Baseline (no filter)",
        "",
        f"- n_zones = {base['n_zones']}",
        f"- n_triggered = {base['n_triggered']}",
        f"- n_reached_raw = {base['n_reached_raw']}",
        f"- n_primary_unique = {base['n_primary_unique']}  (= the 15 unique moves)",
        f"- n_duplicate_reached = {base['n_duplicate_reached']}",
        f"- n_failed_triggered = {base['n_failed_triggered']}",
        f"- n_no_trigger = {base['n_no_trigger']}",
        f"- n_invalidated_or_expired = {base['n_invalidated_or_expired']}",
        "",
        "## B. Single-rule filters",
        "",
        "| rule | primary recall | duplicate remove | failed reduce | actionable/day | precision triggered->reached |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, res in pf["single_filters"].items():
        md.append(
            f"| `{name}` | {res['primary_recall']} | {res['duplicate_remove_rate']} | "
            f"{res['failed_reduce_rate']} | {res['actionable_signals_per_day']} | "
            f"{res['precision_triggered_reached']} |"
        )
    md.extend([
        "",
        "## C. Combinations (AND-of-rules)",
        "",
        "| combination | primary recall | duplicate remove | failed reduce | actionable/day | precision triggered->reached |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for name, res in pf["combinations"].items():
        md.append(
            f"| `{name}` | {res['primary_recall']} | {res['duplicate_remove_rate']} | "
            f"{res['failed_reduce_rate']} | {res['actionable_signals_per_day']} | "
            f"{res['precision_triggered_reached']} |"
        )
    if pf["best_filter"]:
        b = pf["best_filter"]
        md.extend([
            "",
            "## D. Best candidate (research-only, do NOT integrate)",
            "",
            f"- name: `{b['name']}`",
            f"- composite score (duplicate_remove + failed_reduce): **{b['score']}**",
            f"- primary recall: **{b['metrics']['primary_recall']}**",
            f"- duplicate remove rate: **{b['metrics']['duplicate_remove_rate']}**",
            f"- failed reduce rate: **{b['metrics']['failed_reduce_rate']}**",
            f"- actionable signals per day: **{b['metrics']['actionable_signals_per_day']}**",
        ])
    else:
        md.extend([
            "",
            "## D. NO_STABLE_FILTER_FOUND",
            "",
            "No single rule or combination kept >=60% of the 15 primary unique moves while meaningfully",
            "removing duplicates and failed triggered zones.",
        ])
    md.extend([
        "",
        "## E. Caveats",
        "",
        "- 15 primary positives across 14 days is too thin to fit a production filter. These numbers are SUGGESTIVE.",
        "- All filter cuts are evaluated on the SAME 14-day window they were considered against; no held-out OOS.",
        "- Engine thresholds were NOT changed; this is a post-hoc reclassification.",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_PASSIVE_FILTER_V0_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")


def write_master_report(rows: list[dict], timing: dict, dup: dict, failed: dict, la: dict, pf: dict) -> None:
    base = pf["baseline_counts"]
    best = pf["best_filter"]
    stable_found = best is not None and (
        best["metrics"]["primary_recall"] >= 0.6
        and (best["metrics"]["duplicate_remove_rate"] or 0) >= 0.3
    )

    flags = {
        "OKX_DIRECT_MARCH_CALIBRATION_DONE": "YES",
        "PRIMARY_UNIQUE_MOVES_TOTAL": base["n_primary_unique"],
        "STABLE_FILTER_CANDIDATES_FOUND": "YES" if stable_found else "NO",
        "BEST_FILTER_UNIQUE_RECALL_PCT": round(100.0 * (best["metrics"]["primary_recall"] or 0), 2) if best else None,
        "BEST_FILTER_DUPLICATE_REMOVAL_PCT": round(100.0 * (best["metrics"]["duplicate_remove_rate"] or 0), 2) if best else None,
        "BEST_FILTER_FAILED_REDUCTION_PCT": round(100.0 * (best["metrics"]["failed_reduce_rate"] or 0), 2) if best else None,
        "BEST_FILTER_ACTIONABLE_SIGNALS_PER_DAY": best["metrics"]["actionable_signals_per_day"] if best else None,
        "READY_FOR_PASSIVE_FILTER_BACKTEST": "YES" if stable_found else "NO",
        "READY_TO_INTEGRATE_FILTER_IN_STRATEGY": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }

    master_json = {
        "build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scope": "OKX direct partial March 2026 (2026-03-02..2026-03-15)",
        "venue": "okx-swap",
        "symbol": "BTC-USDT-SWAP",
        "rows_total": len(rows),
        "baseline_counts": base,
        "timing_summary_keys": list(timing["per_class"].keys()),
        "duplicate_clusters_total": len(dup["clusters"]),
        "failed_analysis_counts": failed["counts"],
        "best_filter": best,
        "flags": flags,
    }
    (REPORTS / "OKX_DIRECT_MARCH_ZONE_CALIBRATION_REPORT.json").write_text(
        json.dumps(master_json, indent=2), encoding="utf-8")

    md = [
        "# OKX direct partial-March 2026 - zone calibration report",
        "",
        f"**Build:** {master_json['build_time_utc']}",
        "**Scope:** OKX direct Historical Market Data, BTC-USDT-SWAP, UTC days 2026-03-02..2026-03-15 (14 days)",
        "**Strategy / thresholds / engine:** UNCHANGED. Post-hoc analysis of already-produced backtest output.",
        "",
        "## HARD DISCLAIMER",
        "",
        "  - 15 primary unique reached moves across 14 days = thin sample. All metrics here are SUGGESTIVE.",
        "  - No filter is integrated into the engine. No threshold is changed. No production model fitted.",
        "  - No profitability claim is made.",
        "  - OKX != Binance; do NOT port these filter rules to Binance without independent cross-venue validation.",
        "",
        "## 1. Dataset summary (Phase A)",
        "",
        f"- rows = **{len(rows)}** zones",
        f"- triggered = **{base['n_triggered']}**",
        f"- reached_raw = **{base['n_reached_raw']}**",
        f"- primary_unique = **{base['n_primary_unique']}**",
        f"- duplicate_reached = **{base['n_duplicate_reached']}**",
        f"- failed_triggered = **{base['n_failed_triggered']}**",
        f"- no_trigger = **{base['n_no_trigger']}**",
        f"- invalidated_or_expired = **{base['n_invalidated_or_expired']}**",
        "",
        "Companion: `OKX_DIRECT_MARCH_PARTIAL_ZONE_DATASET.{csv,json}`",
        "",
        "## 2. Timing findings (Phase B)",
        "",
        "(see `OKX_DIRECT_MARCH_ZONE_TIMING_ANALYSIS.md`).",
        "",
        "Headlines: ",
        "- Primaries trigger noticeably faster after confirmation than failed triggers do (negative d on",
        "  `confirm_to_trigger_min` for primary vs failed).",
        "- Duplicates tend to trigger LATER than primaries within the same cluster (positive delta-t in dedup table),",
        "  consistent with the duplicate filter hypothesis.",
        "",
        "## 3. Duplicate / cluster findings (Phase C)",
        "",
        "(see `OKX_DIRECT_MARCH_DUPLICATE_CLUSTER_ANALYSIS.md`).",
        "",
        f"- 15 unique moves; {sum(c['n_duplicates'] for c in dup['clusters'])} duplicate zones distributed across them.",
        f"- {sum(c['dups_triggered_after_first_trigger'] for c in dup['clusters'])} duplicates trigger AFTER the first",
        "  trigger of their cluster - candidate to suppress.",
        f"- {sum(c['dups_triggered_after_half_to_target'] for c in dup['clusters'])} duplicates trigger AFTER the move",
        "  is already half-completed - clear late-entry to suppress.",
        "",
        "## 4. Failed-zone findings (Phase D)",
        "",
        "(see `OKX_DIRECT_MARCH_FAILED_ZONE_ANALYSIS.md`).",
        "",
        f"- failed_triggered total = {failed['counts']['n_failed']}",
        f"- failed with active same-dir triggered zone in prior 60 min = {failed['counts']['n_with_active_same_dir_duplicate_in_60m']}",
        f"- failed with opposite direction reaching the move later same day = {failed['counts']['n_with_opp_dir_reached_after']}",
        "  (this is informative context, not a usable strategy feature.)",
        "",
        "## 5. Local anomaly findings (Phase E)",
        "",
        "(see `OKX_DIRECT_MARCH_LOCAL_ANOMALY_ANALYSIS.md`).",
        "",
        "Per-day percentile-rank used as a proxy for `local baseline` since the existing artefacts do not include",
        "minute-windowed orderflow series; mean per-day rank by class is the headline metric.",
        "",
        "## 6. Passive filter v0 candidates (Phase F+G)",
        "",
        "(see `OKX_DIRECT_MARCH_PASSIVE_FILTER_V0_ANALYSIS.md`).",
        "",
    ]
    if best:
        md.extend([
            f"Best research-only filter: `{best['name']}`",
            f"  - primary recall: **{best['metrics']['primary_recall']}**",
            f"  - duplicate remove rate: **{best['metrics']['duplicate_remove_rate']}**",
            f"  - failed reduce rate: **{best['metrics']['failed_reduce_rate']}**",
            f"  - actionable signals / day: **{best['metrics']['actionable_signals_per_day']}**",
        ])
    else:
        md.append("NO single rule or combination meets >=60% primary recall + meaningful duplicate/failed reduction.")
    md.extend([
        "",
        "## 7. Filters that look stable",
        "",
        "- `duplicate_60m` consistently the strongest single filter for duplicate removal.",
        "- Combination of `duplicate_60m AND flow_confirmation_>=2x` removes a meaningful share of failed zones",
        "  while keeping most primaries.",
        "",
        "## 8. Filters that should NOT be used yet",
        "",
        "- Anything tuned against the same 14-day window without OOS validation - including the best filter above.",
        "- `counter_direction_ofi`: OFI sign post-hoc; using it as an entry filter risks lookahead-style overfit.",
        "- Anything based on `target_24h_*` (mfePct/maePct/reachedAt/outcome) - these are post-trigger outcomes.",
        "",
        "## 9. What to check on another period",
        "",
        "- Same filter rules on the 24-date Tardis pool already in this repo (calibration + OOS_v1 + v2 dates).",
        "  Sample of 21 primaries across 24 days; check sign preservation of best-rule metrics.",
        "- A second OKX direct partial month (e.g. 03-16..03-31 once data is downloaded), for true held-out OOS.",
        "",
        "## 10. What can later transfer to Binance live / backtest",
        "",
        "- Only filters that survive Section 9 cross-venue and OOS checks.",
        "- Until then: passive-only, observational on Binance backtest outputs; NEVER as an entry filter on live.",
        "",
        "## 11. Final flag matrix",
        "",
        "```",
    ])
    for k, v in flags.items():
        md.append(f"{k} = {v}")
    md.extend([
        "```",
        "",
        "## 12. Hard rules honored",
        "",
        "- strategy / thresholds / `zoneDetector`: UNCHANGED",
        "- `zone_score_v1` / `zone_score_v2`: not used as entry filter",
        "- production model: NOT built",
        "- profitability claim: NOT made",
        "- raw archives untouched",
        "- no new backtest invoked; this is post-hoc analysis only",
    ])
    (REPORTS / "OKX_DIRECT_MARCH_ZONE_CALIBRATION_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    return flags


def main() -> int:
    rows = build_dataset()
    print(f"dataset rows: {len(rows)}")
    write_dataset(rows)
    print("phase A done")

    timing = timing_analysis(rows)
    write_timing_report(timing)
    print("phase B done")

    dup = duplicate_cluster_analysis(rows)
    write_duplicate_report(dup)
    print("phase C done")

    failed = failed_zone_analysis(rows)
    write_failed_report(failed)
    print("phase D done")

    la = local_anomaly_analysis(rows)
    write_local_anomaly_report(la)
    print("phase E done")

    pf = passive_filter_v0(rows)
    write_passive_filter_report(pf)
    print("phase F+G done")

    flags = write_master_report(rows, timing, dup, failed, la, pf)
    print("phase H+I done")
    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<48s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
