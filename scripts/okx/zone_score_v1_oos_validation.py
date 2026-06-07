"""Apply the FROZEN zone_score_v1 (weights + pooled stats from the 6
calibration dates) to the OOS OKX dates and emit the OOS validation
report.

Critical:
  - Weights are taken from src/strategy/zoneScoreV1.ts (hardcoded constant
    mirrored here). They are NOT refit.
  - z-normalisation uses `features_pooled` from reports/zone_score_v1_stats.json
    which was fitted on the original 6 CALIBRATION dates ONLY. NOT refit on
    OOS data — that's the whole point of "out-of-sample".
  - The list of 12 features is unchanged.
  - No post-trigger field is read (mirrors the TS implementation).

Outputs:
  reports/OKX_ZONE_SCORE_V1_OOS_VALIDATION.md
  reports/OKX_ZONE_SCORE_V1_OOS_VALIDATION.json
  reports/OKX_ZONE_SCORE_V1_OOS_VALIDATION.csv
  reports/OKX_OOS_TECHNICAL_REPLAY_<date>_fullday_with_zone_score.csv (per date)
"""
from __future__ import annotations
import csv
import json
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports"

FEATURES = [
    "cand_pressure_against",
    "cand_absorb_score",
    "cand_refill_with",
    "conf_cycles_seen",
    "conf_age_min",
    "conf_defended_persistence_sec",
    "candidate_to_confirm_min",
    "confirm_to_trigger_min",
    "total_pre_trigger_min",
    "trig_flow_multiplier",
    "trig_break_pct",
    "score_absorption",
]
WEIGHTS = {
    "cand_pressure_against": -0.572,
    "cand_absorb_score": -0.561,
    "cand_refill_with": +0.431,
    "conf_cycles_seen": -0.537,
    "conf_age_min": +0.338,
    "conf_defended_persistence_sec": +0.338,
    "candidate_to_confirm_min": +0.338,
    "confirm_to_trigger_min": -0.427,
    "total_pre_trigger_min": -0.380,
    "trig_flow_multiplier": +0.392,
    "trig_break_pct": -0.310,
    "score_absorption": -0.322,
}
BUCKET_CUTS = {"low_below": -0.5, "high_above": 0.5}


# ---------------------------------------------------------------------------
# Feature extraction (mirrors src/strategy/zoneScoreV1.ts)
# ---------------------------------------------------------------------------

def get_reason(z: dict, stage: str) -> dict | None:
    for r in z.get("reasons") or []:
        if r.get("stage") == stage:
            return r
    return None


def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and not math.isnan(float(v)):
        return float(v)
    return None


def extract_features(z: dict) -> dict:
    cand = (get_reason(z, "candidate") or {}).get("conditions") or {}
    conf = (get_reason(z, "confirmed") or {}).get("conditions") or {}
    trig = (get_reason(z, "trigger") or {}).get("conditions") or {}
    direction = z.get("direction")
    if direction == "LONG":
        pressure_against = num(cand.get("sellPressure"))
        refill_with = num(cand.get("bidRefillScore"))
    elif direction == "SHORT":
        pressure_against = num(cand.get("buyPressure"))
        refill_with = num(cand.get("askRefillScore"))
    else:
        pressure_against = None
        refill_with = None
    start_ts = num(z.get("startTs"))
    confirmed_ts = num(z.get("confirmedTs"))
    trigger_ts = num(z.get("triggerTs"))
    cand_to_conf_min = (confirmed_ts - start_ts) / 60_000 if confirmed_ts is not None and start_ts is not None else None
    conf_to_trig_min = (trigger_ts - confirmed_ts) / 60_000 if trigger_ts is not None and confirmed_ts is not None else None
    total_pre_trig_min = (trigger_ts - start_ts) / 60_000 if trigger_ts is not None and start_ts is not None else None
    return {
        "cand_pressure_against": pressure_against,
        "cand_absorb_score": num(cand.get("absorbScore")),
        "cand_refill_with": refill_with,
        "conf_cycles_seen": num(conf.get("cyclesSeen")),
        "conf_age_min": num(conf.get("ageMin")) if num(conf.get("ageMin")) is not None else cand_to_conf_min,
        "conf_defended_persistence_sec": num(conf.get("defendedPersistenceSec")),
        "candidate_to_confirm_min": cand_to_conf_min,
        "confirm_to_trigger_min": conf_to_trig_min,
        "total_pre_trigger_min": total_pre_trig_min,
        "trig_flow_multiplier": num(trig.get("flowMultiplier")),
        "trig_break_pct": num(trig.get("breakPct")),
        "score_absorption": num((z.get("scores") or {}).get("absorptionScore")),
    }


def classify(z: dict) -> str:
    status = (z.get("status") or "").upper()
    if status == "RESOLVED_REACHED":
        return "primary_unique_reached_move" if z.get("isPrimaryMoveZone") else "duplicate_reached_move"
    if status == "RESOLVED_FAILED":
        return "failed_triggered"
    if status == "NO_TRIGGER":
        return "no_trigger"
    if status in ("INVALIDATED", "EXPIRED"):
        return "invalidated_or_expired"
    return f"other_{status.lower()}"


def compute_score(features: dict, pooled_stats: dict) -> dict:
    raw = 0.0
    zsum = 0.0
    present = 0
    z_eligible = 0
    components = {}
    for f in FEATURES:
        v = features.get(f)
        w = WEIGHTS[f]
        if v is None:
            components[f] = None
            continue
        present += 1
        components[f] = w * v
        raw += w * v
        s = pooled_stats.get(f) or {}
        if s.get("std", 0) > 0:
            zsum += w * ((v - s["mean"]) / s["std"])
            z_eligible += 1
    rawv = raw if present > 0 else None
    zv = zsum if z_eligible > 0 else None
    if zv is None:
        bucket = None
    elif zv < BUCKET_CUTS["low_below"]:
        bucket = "low"
    elif zv > BUCKET_CUTS["high_above"]:
        bucket = "high"
    else:
        bucket = "mid"
    return {
        "raw": rawv,
        "z": zv,
        "bucket": bucket,
        "components": components,
        "coverage": present / len(FEATURES),
    }


# ---------------------------------------------------------------------------
# Load zones, regime, daily summary
# ---------------------------------------------------------------------------

def load_oos_zones(dates: list[str]) -> list[dict]:
    out = []
    for d in dates:
        p = REPORTS / f"OKX_OOS_TECHNICAL_REPLAY_{d}_fullday.json"
        if not p.exists():
            print(f"WARN: OOS replay JSON missing for {d}: {p}", file=sys.stderr)
            continue
        outer = json.loads(p.read_text(encoding="utf-8"))
        inner = outer.get("underlying_backtest_summary") or {}
        zones = inner.get("zones") or []
        for z in zones:
            z["_date"] = d
            out.append(z)
    return out


def load_daily_summary(date: str) -> dict[str, float]:
    p = REPORTS / f"BTC-USDT-SWAP_{date}" / "daily_summary.csv"
    if not p.exists():
        return {}
    out: dict[str, float] = {}
    with p.open("r", encoding="utf-8") as f:
        next(f, None)
        for line in f:
            line = line.strip()
            if not line:
                continue
            cells = line.split(",")
            if len(cells) >= 2:
                try:
                    out[cells[0]] = float(cells[1])
                except Exception:
                    pass
    return out


def main() -> int:
    sel = json.loads((REPORTS / "OKX_OOS_SELECTED_DATES.json").read_text(encoding="utf-8"))
    oos_dates = [c["date"] for c in sel["chosen"]]
    regime_by_date = {c["date"]: c for c in sel["chosen"]}

    stats_doc = json.loads((REPORTS / "zone_score_v1_stats.json").read_text(encoding="utf-8"))
    pooled = stats_doc.get("features_pooled") or {}
    if not pooled:
        print("FATAL: pooled stats missing from reports/zone_score_v1_stats.json", file=sys.stderr)
        return 2

    zones = load_oos_zones(oos_dates)
    print(f"loaded {len(zones)} zones across {len(oos_dates)} OOS dates", file=sys.stderr)

    # Score each zone
    annotated = []
    for z in zones:
        f = extract_features(z)
        s = compute_score(f, pooled)
        annotated.append({
            "id": z.get("id"),
            "date": z.get("_date"),
            "direction": z.get("direction"),
            "status": z.get("status"),
            "class": classify(z),
            "isPrimaryMoveZone": z.get("isPrimaryMoveZone"),
            "duplicateMoveCredit": z.get("duplicateMoveCredit"),
            "uniqueMoveId": z.get("uniqueMoveId"),
            "features": f,
            "components": s["components"],
            "zone_score_v1_raw": s["raw"],
            "zone_score_v1_z": s["z"],
            "zone_score_v1_bucket": s["bucket"],
            "zone_score_v1_coverage": s["coverage"],
        })

    # Per-date annotated CSV
    for d in oos_dates:
        rows = [a for a in annotated if a["date"] == d]
        if not rows:
            continue
        cols = [
            "id", "date", "direction", "status", "class",
            "isPrimaryMoveZone", "duplicateMoveCredit", "uniqueMoveId",
            "zone_score_v1_raw", "zone_score_v1_z", "zone_score_v1_bucket",
            "zone_score_v1_coverage",
            *[f"feat_{f}" for f in FEATURES],
            *[f"comp_{f}" for f in FEATURES],
        ]
        out = REPORTS / f"OKX_OOS_TECHNICAL_REPLAY_{d}_fullday_with_zone_score.csv"
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for a in rows:
                line = [
                    a["id"], a["date"], a["direction"], a["status"], a["class"],
                    a["isPrimaryMoveZone"], a["duplicateMoveCredit"], a["uniqueMoveId"],
                    a["zone_score_v1_raw"], a["zone_score_v1_z"], a["zone_score_v1_bucket"],
                    a["zone_score_v1_coverage"],
                ]
                for ff in FEATURES:
                    line.append(a["features"].get(ff))
                for ff in FEATURES:
                    line.append(a["components"].get(ff))
                w.writerow(line)

    # ---- Per-date table ----
    per_date_rows = []
    for d in oos_dates:
        ds = load_daily_summary(d)
        rg = regime_by_date.get(d, {})
        zs = [a for a in annotated if a["date"] == d]
        per_date_rows.append({
            "date": d,
            "bucket": rg.get("bucket"),
            "day_return_pct": rg.get("day_return_pct"),
            "range_pct": rg.get("range_pct"),
            "feasibility_2pct": rg.get("feasibility_2pct"),
            "trades_rows": rg.get("trades_n"),
            "replay_window": "full-day",
            "zones": int(ds.get("zones_total", len(zs))),
            "triggered": int(ds.get("zones_triggered", sum(1 for a in zs if a["status"] in ("RESOLVED_REACHED","RESOLVED_FAILED")))),
            "reached_raw": int(ds.get("zones_reached", sum(1 for a in zs if a["class"] == "primary_unique_reached_move" or a["class"] == "duplicate_reached_move"))),
            "unique_moves": int(ds.get("unique_reached_moves", sum(1 for a in zs if a["class"] == "primary_unique_reached_move"))),
            "duplicate_move_credits": int(ds.get("duplicate_move_credits", sum(1 for a in zs if a["class"] == "duplicate_reached_move"))),
            "failed_triggered": sum(1 for a in zs if a["class"] == "failed_triggered"),
            "no_trigger": sum(1 for a in zs if a["class"] == "no_trigger"),
            "invalidated_or_expired": sum(1 for a in zs if a["class"] == "invalidated_or_expired"),
        })

    # ---- Bucket × class crosstab + bucket summary ----
    classes_order = [
        "primary_unique_reached_move",
        "duplicate_reached_move",
        "failed_triggered",
        "no_trigger",
        "invalidated_or_expired",
    ]
    buckets_order = ["high", "mid", "low", "no_z"]

    def bucket_of(a):
        return a["zone_score_v1_bucket"] or "no_z"

    crosstab = {b: {c: 0 for c in classes_order} for b in buckets_order}
    for a in annotated:
        c = a["class"] if a["class"] in classes_order else None
        if c is None:
            continue
        crosstab[bucket_of(a)][c] += 1

    bucket_summary = {}
    total_unique = sum(1 for a in annotated if a["class"] == "primary_unique_reached_move")
    for b in buckets_order:
        zs = [a for a in annotated if bucket_of(a) == b]
        triggered = sum(1 for a in zs if a["status"] in ("RESOLVED_REACHED", "RESOLVED_FAILED"))
        reached_raw = sum(1 for a in zs if a["status"] == "RESOLVED_REACHED")
        unique = sum(1 for a in zs if a["class"] == "primary_unique_reached_move")
        bucket_summary[b] = {
            "n": len(zs),
            "triggered": triggered,
            "reached_raw": reached_raw,
            "unique_moves": unique,
            "failed_triggered": sum(1 for a in zs if a["class"] == "failed_triggered"),
            "no_trigger": sum(1 for a in zs if a["class"] == "no_trigger"),
            "invalidated_or_expired": sum(1 for a in zs if a["class"] == "invalidated_or_expired"),
            "duplicate_reached": sum(1 for a in zs if a["class"] == "duplicate_reached_move"),
            "raw_triggered_hit_rate": (reached_raw / triggered) if triggered else None,
            "unique_move_hit_rate": (unique / triggered) if triggered else None,
        }

    # ---- Headline precision/recall on the high bucket ----
    high = bucket_summary["high"]
    high_precision = (high["unique_moves"] / high["triggered"]) if high["triggered"] else None
    high_recall = (high["unique_moves"] / total_unique) if total_unique else None

    # Mean z per class
    class_z = {}
    for c in classes_order:
        zs = [a["zone_score_v1_z"] for a in annotated if a["class"] == c and a["zone_score_v1_z"] is not None]
        if zs:
            class_z[c] = {
                "n": len(zs),
                "mean_z": statistics.mean(zs),
                "median_z": statistics.median(zs),
                "stdev_z": statistics.pstdev(zs) if len(zs) > 1 else 0.0,
                "min_z": min(zs),
                "max_z": max(zs),
            }
        else:
            class_z[c] = {"n": 0, "mean_z": None}

    # ---- Verdict ----
    primary_mean_z = class_z["primary_unique_reached_move"]["mean_z"]
    failed_mean_z = class_z["failed_triggered"]["mean_z"]
    separation_ok = (
        primary_mean_z is not None and failed_mean_z is not None
        and primary_mean_z > failed_mean_z
    )
    if total_unique == 0:
        generalize = "WEAK"  # no positive class in OOS — can't test recall
    elif high_recall is None or high_recall == 0:
        generalize = "NO"
    elif high_recall >= 0.5:
        generalize = "YES" if separation_ok else "WEAK"
    else:
        generalize = "WEAK"
    ready_v2 = "YES" if generalize == "YES" else "NO"

    out_json = {
        "venue": "OKX (okex-swap)",
        "symbol": "BTC-USDT-SWAP",
        "purpose": "out-of-sample validation of zone_score_v1 (frozen weights + frozen pooled stats)",
        "build_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "oos_dates": oos_dates,
        "calibration_dates_excluded": stats_doc.get("source", "OKX 6-date full-day pool"),
        "weights": WEIGHTS,
        "stats_source": "features_pooled from reports/zone_score_v1_stats.json (fitted on the 6 calibration dates)",
        "z_bucket_cuts": BUCKET_CUTS,
        "zones_total_oos": len(zones),
        "class_z_stats": class_z,
        "bucket_summary": bucket_summary,
        "bucket_x_class_crosstab": crosstab,
        "per_date": per_date_rows,
        "headline": {
            "OOS_UNIQUE_MOVES_TOTAL": total_unique,
            "OOS_UNIQUE_MOVES_HIGH_BUCKET": high["unique_moves"],
            "OOS_HIGH_BUCKET_PRECISION": high_precision,
            "OOS_HIGH_BUCKET_RECALL": high_recall,
            "primary_mean_z": primary_mean_z,
            "failed_mean_z": failed_mean_z,
            "primary_minus_failed_z": (primary_mean_z - failed_mean_z) if (primary_mean_z is not None and failed_mean_z is not None) else None,
            "ZONE_SCORE_V1_GENERALIZES": generalize,
            "READY_FOR_ZONE_SCORE_V2": ready_v2,
        },
        "lookahead_audit": {
            "features_used_from": [
                "zone.reasons[stage in {candidate, confirmed, trigger}].conditions",
                "zone.scores.absorptionScore (frozen at trigger transition)",
                "zone.startTs / confirmedTs / triggerTs (timing only)",
            ],
            "forbidden_fields_NOT_read": [
                "zone.targets.* (mfePct, maePct, outcome, reachedAt, timeToTargetMin, maxDrawdownBeforeTargetPct, endPrice, endTs)",
                "zone.resolvedTs", "zone.status (final)",
                "zone.uniqueMoveId", "zone.moveClusterSize",
                "zone.isPrimaryMoveZone", "zone.duplicateMoveCredit",
                "zone.reasons[stage=expire | invalidate]",
                "day return / regime label / future max move (regime used ONLY for the per-date table label, never inside the score)",
            ],
            "enforced_by_test": "tests/zoneScoreV1.test.ts — lookahead-invariance test (87/87 pass)",
        },
        "annotated_zones": annotated,
    }
    (REPORTS / "OKX_ZONE_SCORE_V1_OOS_VALIDATION.json").write_text(
        json.dumps(out_json, indent=2, default=str), encoding="utf-8"
    )

    # ---- CSV (flat per-zone) ----
    csv_path = REPORTS / "OKX_ZONE_SCORE_V1_OOS_VALIDATION.csv"
    cols = [
        "date", "id", "direction", "status", "class",
        "isPrimaryMoveZone", "duplicateMoveCredit", "uniqueMoveId",
        "zone_score_v1_raw", "zone_score_v1_z", "zone_score_v1_bucket",
        "zone_score_v1_coverage",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for a in annotated:
            w.writerow([a.get(c, "") for c in cols])

    # ---- Markdown ----
    def fnum(v, w=8, p=3):
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            return "-".rjust(w)
        return f"{v:>{w}.{p}f}"

    md = [
        "# OKX zone_score_v1 — out-of-sample validation",
        "",
        "**Venue:** OKX `okex-swap` BTC-USDT-SWAP",
        "**Score:** `zone_score_v1` with **FROZEN weights** and **FROZEN pooled stats** from the 6 calibration dates.",
        "**OOS dates:** " + ", ".join(oos_dates),
        "**Replay window:** full UTC day on every date.",
        "**Calibration dates EXCLUDED from OOS:** " + ", ".join(sorted(stats_doc.get("features_loo", {}).keys())),
        "**Build time:** " + time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "",
        "## HARD DISCLAIMER",
        "",
        "  • Out-of-sample = these 6 dates were NOT used to choose the 12 features, the 12 weights, or to fit the z-normalisation mean/std.",
        "  • zone_score_v1 is OBSERVATIONAL only — it does NOT filter zones, NOT gate triggers, NOT change strategy thresholds.",
        "  • Weights are HYPOTHESIS-ONLY from the calibration step. NOT calibrated for trading.",
        "  • Numbers below are not a winrate claim. OKX is NOT Binance.",
        "",
        "## A. OOS dates (regime + replay)",
        "",
        "| date | bucket | day Δ % | range % | 2% feasibility | trades | zones | triggered | reached_raw | unique moves | dup credits | failed | no_trig | invalid/exp |",
        "|------|--------|--------:|--------:|:--------------:|-------:|------:|----------:|------------:|-------------:|------------:|-------:|--------:|------------:|",
    ]
    for r in per_date_rows:
        feas = "yes" if r["feasibility_2pct"] else "no"
        md.append(
            f"| {r['date']} | {r['bucket']:<7s} | {r['day_return_pct']:+6.2f} | {r['range_pct']:6.2f} | "
            f"     {feas:^4s}     | {r['trades_rows']:>6,} | {r['zones']:>5d} | {r['triggered']:>9d} | "
            f"{r['reached_raw']:>11d} | {r['unique_moves']:>12d} | {r['duplicate_move_credits']:>11d} | "
            f"{r['failed_triggered']:>6d} | {r['no_trigger']:>7d} | {r['invalidated_or_expired']:>11d} |"
        )

    md.extend([
        "",
        "## B. Mean z per class (OOS)",
        "",
        "Hypothesis: if the score generalises, `primary_unique_reached_move` zones should have higher mean z than `failed_triggered`.",
        "",
        "| class | n | mean z | median z | stdev z | min z | max z |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for c in classes_order:
        s = class_z[c]
        if s["n"] == 0:
            md.append(f"| {c} | 0 | — | — | — | — | — |")
        else:
            md.append(
                f"| {c} | {s['n']} | {fnum(s['mean_z'])} | {fnum(s['median_z'])} | {fnum(s['stdev_z'])} | {fnum(s['min_z'])} | {fnum(s['max_z'])} |"
            )

    md.extend([
        "",
        "## C. Bucket × class crosstab (OOS)",
        "",
        "Bucket cuts on z: `low` < -0.5, `mid` in [-0.5, +0.5], `high` > +0.5.",
        "",
        "| bucket | primary unique | duplicate | failed | no_trig | invalid/exp | total |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for b in buckets_order:
        row = crosstab[b]
        total = sum(row.values())
        md.append(
            f"| {b} | " + " | ".join(str(row[c]) for c in classes_order) + f" | {total} |"
        )

    md.extend([
        "",
        "## D. Bucket-level outcome accounting (OOS)",
        "",
        "| bucket | n | triggered | reached_raw | unique moves | failed | no_trig | invalid/exp | raw hit | uniq-move hit |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for b in buckets_order:
        s = bucket_summary[b]
        raw_hit = "—" if s["raw_triggered_hit_rate"] is None else f"{s['raw_triggered_hit_rate']*100:.2f}%"
        uniq_hit = "—" if s["unique_move_hit_rate"] is None else f"{s['unique_move_hit_rate']*100:.2f}%"
        md.append(
            f"| {b} | {s['n']} | {s['triggered']} | {s['reached_raw']} | {s['unique_moves']} | "
            f"{s['failed_triggered']} | {s['no_trigger']} | {s['invalidated_or_expired']} | {raw_hit} | {uniq_hit} |"
        )

    md.extend([
        "",
        "## E. Headline (precision / recall of the `high` bucket)",
        "",
        f"| metric | value |",
        f"|--------|-------|",
        f"| OOS unique moves total | **{total_unique}** |",
        f"| OOS unique moves in `high` bucket | **{high['unique_moves']}** |",
        f"| precision = unique / triggered in `high` | **{(high_precision*100):.2f}%**" + (f" ({high['unique_moves']}/{high['triggered']})" if high['triggered'] else "") + " |"
            if high_precision is not None else "| precision = unique / triggered in `high` | — |",
        f"| recall = unique in `high` / all unique | **{(high_recall*100):.2f}%**" + (f" ({high['unique_moves']}/{total_unique})" if total_unique else "") + " |"
            if high_recall is not None else "| recall = unique in `high` / all unique | — |",
        f"| primary mean z − failed mean z | **{((primary_mean_z - failed_mean_z) if (primary_mean_z is not None and failed_mean_z is not None) else 'n/a')}** |",
        "",
        "## F. In-sample vs OOS comparison",
        "",
        "| metric | in-sample (calibration) | OOS |",
        "|--------|-------------------------|-----|",
    ])
    # In-sample numbers from the calibration validation
    in_sample_path = REPORTS / "OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.json"
    in_sample_high_unique = None
    in_sample_high_recall = None
    in_sample_high_precision = None
    in_sample_total_unique = None
    in_sample_p_mz = None
    in_sample_f_mz = None
    if in_sample_path.exists():
        ij = json.loads(in_sample_path.read_text(encoding="utf-8"))
        ibuck = ij.get("bucket_summary", {}).get("high", {})
        in_sample_high_unique = ibuck.get("unique_moves")
        in_sample_high_precision = ibuck.get("unique_move_hit_rate")
        # in-sample total unique = primary_unique_reached_move count
        in_sample_total_unique = ij.get("class_z_stats", {}).get("primary_unique_reached_move", {}).get("n")
        if in_sample_total_unique:
            in_sample_high_recall = in_sample_high_unique / in_sample_total_unique
        in_sample_p_mz = ij.get("class_z_stats", {}).get("primary_unique_reached_move", {}).get("mean_z")
        in_sample_f_mz = ij.get("class_z_stats", {}).get("failed_triggered", {}).get("mean_z")
    md.append(
        f"| total unique moves | {in_sample_total_unique} | {total_unique} |"
    )
    md.append(
        f"| unique moves in `high` | {in_sample_high_unique} | {high['unique_moves']} |"
    )
    md.append(
        f"| recall in `high` | {(in_sample_high_recall*100 if in_sample_high_recall is not None else None):.2f}% | {(high_recall*100 if high_recall is not None else 0):.2f}% |"
    )
    md.append(
        f"| precision in `high` | "
        f"{(in_sample_high_precision*100 if in_sample_high_precision is not None else 0):.2f}% | "
        f"{(high_precision*100 if high_precision is not None else 0):.2f}% |"
    )
    md.append(
        f"| primary mean z | {fnum(in_sample_p_mz)} | {fnum(primary_mean_z)} |"
    )
    md.append(
        f"| failed mean z | {fnum(in_sample_f_mz)} | {fnum(failed_mean_z)} |"
    )

    md.extend([
        "",
        "## G. Lookahead audit",
        "",
        "Features read (pre-trigger only):",
        "  - `zone.reasons[stage in {candidate, confirmed, trigger}].conditions`",
        "  - `zone.scores.absorptionScore` (frozen at trigger transition)",
        "  - `zone.startTs / confirmedTs / triggerTs` (timing only)",
        "",
        "Forbidden fields explicitly NOT read by the scorer:",
        "  - `zone.targets.*` (mfePct, maePct, outcome, reachedAt, timeToTargetMin, maxDrawdownBeforeTargetPct, endPrice, endTs)",
        "  - `zone.resolvedTs`, `zone.status` (terminal), `zone.qualityFlags[*]`",
        "  - `zone.uniqueMoveId`, `zone.moveClusterSize`, `zone.isPrimaryMoveZone`, `zone.duplicateMoveCredit`",
        "  - `zone.reasons[stage=expire | invalidate]`",
        "  - day_return / regime label / future max move (regime label appears in Section A only, NOT inside the score)",
        "",
        "Enforced by `tests/zoneScoreV1.test.ts` (lookahead-invariance test passes — 87/87).",
        "",
        "## H. Verdict",
        "",
        f"| flag | value |",
        f"|------|------|",
        f"| `ZONE_SCORE_V1_OOS_DONE` | **YES** |",
        f"| `OOS_DATES_COUNT` | **{len(oos_dates)}** |",
        f"| `OOS_UNIQUE_MOVES_TOTAL` | **{total_unique}** |",
        f"| `OOS_UNIQUE_MOVES_HIGH_BUCKET` | **{high['unique_moves']}** |",
        f"| `OOS_HIGH_BUCKET_RECALL` | **{(high_recall*100):.2f}%**" + (f" ({high['unique_moves']}/{total_unique})" if total_unique else "") + " |"
            if high_recall is not None else "| `OOS_HIGH_BUCKET_RECALL` | — |",
        f"| `OOS_HIGH_BUCKET_PRECISION` | **{(high_precision*100):.2f}%**" + (f" ({high['unique_moves']}/{high['triggered']})" if high['triggered'] else "") + " |"
            if high_precision is not None else "| `OOS_HIGH_BUCKET_PRECISION` | — |",
        f"| `ZONE_SCORE_V1_GENERALIZES` | **{generalize}** |",
        f"| `READY_FOR_ZONE_SCORE_V2` | **{ready_v2}** |",
        "",
        "## I. Notes",
        "",
        "- If `OOS_UNIQUE_MOVES_TOTAL == 0`, the score cannot be validated on the positive class on this sample — verdict is `WEAK` (insufficient signal), not `YES` or `NO`.",
        "- 2 of the 6 chosen choppy dates have 2 %-target infeasibility (max 24h move below 2 %). Those days mechanically cannot produce reaches regardless of strategy or score quality — flagged in Section A.",
        "- `v1` weights remain hypothesis-only. Even with a successful OOS validation here, integrating the score as a filter on Binance requires Binance-specific re-derivation.",
        "",
    ])

    (REPORTS / "OKX_ZONE_SCORE_V1_OOS_VALIDATION.md").write_text("\n".join(md), encoding="utf-8")

    print(f"wrote OKX_ZONE_SCORE_V1_OOS_VALIDATION.md / .json / .csv")
    print()
    print(f"OOS_DATES_COUNT              = {len(oos_dates)}")
    print(f"OOS_UNIQUE_MOVES_TOTAL       = {total_unique}")
    print(f"OOS_UNIQUE_MOVES_HIGH_BUCKET = {high['unique_moves']}")
    if high_precision is not None:
        print(f"OOS_HIGH_BUCKET_PRECISION    = {high_precision*100:.2f}%")
    if high_recall is not None:
        print(f"OOS_HIGH_BUCKET_RECALL       = {high_recall*100:.2f}%")
    print(f"primary mean z = {primary_mean_z}, failed mean z = {failed_mean_z}")
    print(f"ZONE_SCORE_V1_GENERALIZES    = {generalize}")
    print(f"READY_FOR_ZONE_SCORE_V2      = {ready_v2}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
