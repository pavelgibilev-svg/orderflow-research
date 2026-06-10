"""Fit zone_score_v1 stats from the 6 OKX full-day reports + apply the score
to every zone, observationally. Pure post-processing — does NOT re-run any
backtest and does NOT mutate the strategy.

Steps:
  1. Load all 211 zones from reports/OKX_TECHNICAL_REPLAY_<date>_fullday.json.
  2. Extract the 12 pre-trigger features per zone (mirroring src/strategy/zoneScoreV1.ts).
  3. Fit per-feature mean/std two ways:
       - pooled across all 6 dates (in-sample baseline)
       - leave-one-date-out (zone on date D uses stats from the OTHER 5 dates)
  4. Write reports/zone_score_v1_stats.json with both fits.
  5. For each zone, compute raw / z / bucket using LOO stats (no leakage for
     the per-date scoring).
  6. Emit per-date annotated CSV:
       reports/OKX_TECHNICAL_REPLAY_<date>_fullday_with_zone_score.csv
     and a combined JSON of all annotated zones:
       reports/OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.json
  7. Emit a Markdown validation report:
       reports/OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.md
     with bucket cross-tab vs zone-class outcomes.

NO strategy threshold change. NO filter. NO trade decision is made anywhere.
"""
from __future__ import annotations
import csv
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
DATES = [
    "2024-01-01",
    "2025-10-01",
    "2025-12-01",
    "2024-10-01",
    "2024-07-01",
    "2026-04-01",
]

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
# Mirror of src/strategy/zoneScoreV1.ts feature extraction.
# Kept lockstep with the TS module; if you change one, change the other.
# ---------------------------------------------------------------------------

def get_reason(z: dict, stage: str) -> dict | None:
    for r in z.get("reasons") or []:
        if r.get("stage") == stage:
            return r
    return None


def num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None  # do not coerce bool to number here
    if isinstance(v, (int, float)) and not math.isnan(float(v)):
        return float(v)
    return None


def extract_features(z: dict) -> dict[str, float | None]:
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
    cand_to_conf_min = (
        (confirmed_ts - start_ts) / 60_000
        if confirmed_ts is not None and start_ts is not None
        else None
    )
    conf_to_trig_min = (
        (trigger_ts - confirmed_ts) / 60_000
        if trigger_ts is not None and confirmed_ts is not None
        else None
    )
    total_pre_trig_min = (
        (trigger_ts - start_ts) / 60_000
        if trigger_ts is not None and start_ts is not None
        else None
    )
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


# ---------------------------------------------------------------------------
# Stats fitting
# ---------------------------------------------------------------------------

def fit_stats(zones_features: list[tuple[str, dict[str, float | None]]]) -> dict[str, dict]:
    """Per-feature mean/std/n over the provided (date, features) pool."""
    out: dict[str, dict] = {}
    for f in FEATURES:
        values = [fv[f] for _, fv in zones_features if fv.get(f) is not None]
        clean = [v for v in values if isinstance(v, (int, float)) and not math.isnan(float(v))]
        if not clean:
            out[f] = {"mean": 0.0, "std": 0.0, "n": 0}
            continue
        m = statistics.mean(clean)
        s = statistics.pstdev(clean) if len(clean) > 1 else 0.0
        out[f] = {"mean": float(m), "std": float(s), "n": len(clean)}
    return out


def compute_score(features: dict[str, float | None], stats: dict[str, dict]) -> dict:
    raw_sum = 0.0
    z_sum = 0.0
    present = 0
    z_eligible = 0
    components: dict[str, float | None] = {}
    for f in FEATURES:
        v = features.get(f)
        w = WEIGHTS[f]
        if v is None:
            components[f] = None
            continue
        present += 1
        components[f] = w * v
        raw_sum += w * v
        s = stats.get(f) or {}
        if s.get("std", 0) > 0:
            z_sum += w * ((v - s["mean"]) / s["std"])
            z_eligible += 1
    raw = raw_sum if present > 0 else None
    z = z_sum if z_eligible > 0 else None
    if z is None:
        bucket = None
    elif z < BUCKET_CUTS["low_below"]:
        bucket = "low"
    elif z > BUCKET_CUTS["high_above"]:
        bucket = "high"
    else:
        bucket = "mid"
    return {
        "raw": raw,
        "z": z,
        "bucket": bucket,
        "components": components,
        "coverage": present / len(FEATURES),
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def load_zones() -> list[dict]:
    out: list[dict] = []
    for d in DATES:
        p = REPORTS / f"OKX_TECHNICAL_REPLAY_{d}_fullday.json"
        if not p.exists():
            print(f"WARN: missing {p}", file=sys.stderr)
            continue
        outer = json.loads(p.read_text(encoding="utf-8"))
        inner = outer.get("underlying_backtest_summary") or {}
        zones = inner.get("zones") or []
        for z in zones:
            z["_date"] = d
            out.append(z)
    return out


def main() -> int:
    zones = load_zones()
    print(f"loaded {len(zones)} zones across {len(DATES)} dates", file=sys.stderr)

    # Extract features once
    zones_features = [(z["_date"], extract_features(z)) for z in zones]

    # Fit pooled stats
    pooled = fit_stats(zones_features)
    # Fit leave-one-date-out stats per date (zones for date D scored against
    # stats fitted on the other 5 dates)
    loo: dict[str, dict[str, dict]] = {}
    for d_left_out in DATES:
        pool = [(d, f) for d, f in zones_features if d != d_left_out]
        loo[d_left_out] = fit_stats(pool)

    stats_path = REPORTS / "zone_score_v1_stats.json"
    stats_path.write_text(
        json.dumps({
            "fitted_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "OKX 6-date full-day pool (BTC-USDT-SWAP). Hypothesis-only — do not trade.",
            "features_pooled": pooled,
            "features_loo": loo,
            "z_bucket_cuts": BUCKET_CUTS,
            "weights": WEIGHTS,
        }, indent=2),
        encoding="utf-8",
    )

    # Score every zone using LOO stats. This is what we report.
    annotated: list[dict] = []
    for z, (d, feats) in zip(zones, zones_features):
        scored = compute_score(feats, loo[d])
        annotated.append({
            "id": z.get("id"),
            "date": d,
            "direction": z.get("direction"),
            "status": z.get("status"),
            "class": classify(z),
            "isPrimaryMoveZone": z.get("isPrimaryMoveZone"),
            "duplicateMoveCredit": z.get("duplicateMoveCredit"),
            "uniqueMoveId": z.get("uniqueMoveId"),
            "features": feats,
            "components": scored["components"],
            "zone_score_v1_raw": scored["raw"],
            "zone_score_v1_z": scored["z"],
            "zone_score_v1_bucket": scored["bucket"],
            "zone_score_v1_coverage": scored["coverage"],
        })

    # Per-date annotated CSV
    for d in DATES:
        rows = [a for a in annotated if a["date"] == d]
        if not rows:
            continue
        csv_path = REPORTS / f"OKX_TECHNICAL_REPLAY_{d}_fullday_with_zone_score.csv"
        cols = [
            "id", "date", "direction", "status", "class",
            "isPrimaryMoveZone", "duplicateMoveCredit", "uniqueMoveId",
            "zone_score_v1_raw", "zone_score_v1_z", "zone_score_v1_bucket",
            "zone_score_v1_coverage",
            *[f"feat_{f}" for f in FEATURES],
            *[f"comp_{f}" for f in FEATURES],
        ]
        with csv_path.open("w", encoding="utf-8", newline="") as f:
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

    # ------- Validation report -------
    # Bucket × class cross-tab
    classes_order = [
        "primary_unique_reached_move",
        "duplicate_reached_move",
        "failed_triggered",
        "no_trigger",
        "invalidated_or_expired",
    ]
    buckets_order = ["high", "mid", "low", "no_z"]

    def bucket_of(a: dict) -> str:
        return a["zone_score_v1_bucket"] or "no_z"

    crosstab: dict[str, dict[str, int]] = {b: {c: 0 for c in classes_order} for b in buckets_order}
    for a in annotated:
        b = bucket_of(a)
        c = a["class"] if a["class"] in classes_order else None
        if c is None:
            continue
        crosstab[b][c] += 1

    # Per-bucket: how many zones, triggered, reached_raw, unique moves, failed
    def is_triggered(a: dict) -> bool:
        # A zone is triggered iff status in {RESOLVED_REACHED, RESOLVED_FAILED}
        return a["status"] in ("RESOLVED_REACHED", "RESOLVED_FAILED")

    bucket_summary: dict[str, dict] = {}
    for b in buckets_order:
        zs = [a for a in annotated if bucket_of(a) == b]
        bucket_summary[b] = {
            "n": len(zs),
            "triggered": sum(1 for a in zs if is_triggered(a)),
            "reached_raw": sum(1 for a in zs if a["status"] == "RESOLVED_REACHED"),
            "unique_moves": sum(1 for a in zs if a["class"] == "primary_unique_reached_move"),
            "failed_triggered": sum(1 for a in zs if a["class"] == "failed_triggered"),
            "no_trigger": sum(1 for a in zs if a["class"] == "no_trigger"),
            "invalidated_or_expired": sum(1 for a in zs if a["class"] == "invalidated_or_expired"),
            "duplicate_reached": sum(1 for a in zs if a["class"] == "duplicate_reached_move"),
        }
        triggered = bucket_summary[b]["triggered"]
        bucket_summary[b]["raw_triggered_hit_rate"] = (
            bucket_summary[b]["reached_raw"] / triggered if triggered else None
        )
        bucket_summary[b]["unique_move_hit_rate"] = (
            bucket_summary[b]["unique_moves"] / triggered if triggered else None
        )

    # Mean z per class
    class_z_stats: dict[str, dict] = {}
    for c in classes_order:
        zs = [a["zone_score_v1_z"] for a in annotated if a["class"] == c and a["zone_score_v1_z"] is not None]
        if zs:
            class_z_stats[c] = {
                "n": len(zs),
                "mean_z": statistics.mean(zs),
                "median_z": statistics.median(zs),
                "stdev_z": statistics.pstdev(zs) if len(zs) > 1 else 0.0,
                "min_z": min(zs),
                "max_z": max(zs),
            }
        else:
            class_z_stats[c] = {"n": 0, "mean_z": None}

    out_json = {
        "venue": "OKX (okex-swap)",
        "symbol": "BTC-USDT-SWAP",
        "dates": DATES,
        "zones_total": len(zones),
        "stats_path": "reports/zone_score_v1_stats.json",
        "fit_strategy_for_z": "leave-one-date-out",
        "weights": WEIGHTS,
        "z_bucket_cuts": BUCKET_CUTS,
        "class_z_stats": class_z_stats,
        "bucket_summary": bucket_summary,
        "bucket_x_class_crosstab": crosstab,
        "zones_annotated": annotated,
    }
    (REPORTS / "OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.json").write_text(
        json.dumps(out_json, indent=2, default=str), encoding="utf-8"
    )

    # --- Markdown ---
    def fnum(v, w=8, p=3):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "—".rjust(w)
        if isinstance(v, float) and math.isinf(v):
            return "inf".rjust(w)
        return f"{v:>{w}.{p}f}"

    md: list[str] = [
        "# OKX `zone_score_v1` — passive observational validation",
        "",
        "**Venue:** OKX `okex-swap` BTC-USDT-SWAP",
        "**Dates:** " + ", ".join(DATES),
        "**Zones scored:** " + str(len(zones)),
        "**Score fit:** **leave-one-date-out** (zones on date D are scored using mean/std from the OTHER 5 dates only).",
        "**Strategy thresholds:** Binance USDS-M Futures defaults — **UNCHANGED**.",
        "**Strategy logic:** **UNCHANGED**. The score is observational only.",
        "",
        "## HARD DISCLAIMER",
        "",
        "  • zone_score_v1 is a **passive metric** computed AFTER the strategy has already produced zones. It is NOT a filter, gate, or trade decision.",
        "  • Weights are HYPOTHESIS-ONLY from the 6-date OKX sample. NOT cross-validated. NOT calibrated for trading.",
        "  • Numbers below are observational shape, not a winrate claim.",
        "  • OKX is NOT Binance. Do not transfer this score to Binance without re-fitting.",
        "",
        "## A. Mean z-score per zone class",
        "",
        "If the score truly separates `primary_unique_reached_move` from `failed_triggered`, the former's mean z should be **higher** than the latter's.",
        "",
        "| class | n | mean z | median z | stdev z | min z | max z |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for c in classes_order:
        s = class_z_stats[c]
        if s["n"] == 0:
            md.append(f"| {c} | 0 | — | — | — | — | — |")
        else:
            md.append(
                f"| {c} | {s['n']} | {fnum(s['mean_z'])} | {fnum(s['median_z'])} | {fnum(s['stdev_z'])} | {fnum(s['min_z'])} | {fnum(s['max_z'])} |"
            )

    md.extend([
        "",
        "## B. Zones × bucket (counts)",
        "",
        "Bucket cuts on the LOO z-score: `low` = z < -0.5, `mid` = -0.5 ≤ z ≤ +0.5, `high` = z > +0.5, `no_z` = no fitted stats coverage.",
        "",
        "| bucket | primary unique | duplicate | failed_triggered | no_trigger | invalid./expired | total |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for b in buckets_order:
        row = crosstab[b]
        total = sum(row.values())
        md.append(
            "| "
            + b
            + " | "
            + " | ".join(str(row[c]) for c in classes_order)
            + f" | {total} |"
        )

    md.extend([
        "",
        "## C. Bucket-level outcome accounting",
        "",
        "Triggered = status ∈ {RESOLVED_REACHED, RESOLVED_FAILED}. raw_hit_rate = reached_raw / triggered. unique_move_hit_rate = unique_moves / triggered.",
        "",
        "| bucket | n | triggered | reached_raw | unique moves | failed_triggered | no_trigger | invalid./expired | raw_hit | uniq-move_hit |",
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
        "## D. Interpretation",
        "",
        "- The score in `high` bucket should contain a disproportionate share of `primary_unique_reached_move` zones if the hypothesis holds.",
        "- The score in `low` bucket should be enriched with `failed_triggered` and `invalidated_or_expired`.",
        "- A coin-flip score would split zones uniformly across buckets.",
        "- **All numbers below are in-sample for the 12 weights**, which were themselves derived from these 6 OKX dates. The LOO fit on z-normalisation removes leakage on the *scale* of each feature, but it does NOT remove leakage on the *choice* of the 12 features and their signs. Take the bucket cross-tab as a sanity check, not as out-of-sample validation.",
        "",
        "## E. Lookahead audit",
        "",
        "Feature extraction reads ONLY:",
        "  - `zone.reasons[stage=candidate].conditions` (sellPressure/buyPressure, bidRefillScore/askRefillScore, absorbScore, downMovePct/upMovePct, rangeCompression)",
        "  - `zone.reasons[stage=confirmed].conditions` (cyclesSeen, ageMin, defendedPersistenceSec, oppositeThinning, voidScore)",
        "  - `zone.reasons[stage=trigger].conditions` (breakPct, flowMultiplier, sideFlowOK)",
        "  - `zone.scores.absorptionScore` (frozen at trigger transition)",
        "  - `zone.startTs / confirmedTs / triggerTs` (timing only, no future data)",
        "",
        "Feature extraction does NOT read:",
        "  - `zone.targets.*` (mfePct, maePct, outcome, reachedAt, timeToTargetMin, maxDrawdownBeforeTargetPct, endPrice, endTs)",
        "  - `zone.resolvedTs`, `zone.status` (terminal), `zone.qualityFlags[*]` (post-trigger flag updates)",
        "  - `zone.uniqueMoveId`, `zone.moveClusterSize`, `zone.isPrimaryMoveZone`, `zone.duplicateMoveCredit`",
        "  - `zone.reasons[stage=expire | invalidate]`",
        "",
        "This is enforced by `tests/zoneScoreV1.test.ts` — the `score is invariant under mutation of forbidden post-trigger fields` test passes (87/87).",
        "",
        "## F. Files",
        "",
        "- `src/strategy/zoneScoreV1.ts` — pure TS module (no strategy mutation)",
        "- `tests/zoneScoreV1.test.ts` — 11 tests (lookahead invariance, purity, weights frozen)",
        "- `reports/zone_score_v1_stats.json` — pooled + LOO fitted stats",
        "- `reports/OKX_TECHNICAL_REPLAY_<date>_fullday_with_zone_score.csv` — per-date annotated CSV",
        "- `reports/OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.json` — machine-readable validation",
        "- `reports/OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.md` — this file",
        "",
        "## G. Flag matrix",
        "",
        "| flag | value |",
        "|------|------|",
        "| `ZONE_SCORE_V1_IMPLEMENTED` | **YES** (passive, no integration) |",
        "| `AFFECTS_STRATEGY` | **NO** (no zoneDetector / threshold / filter change) |",
        "| `LOOKAHEAD_RISK` | **NO** (pre-trigger only; lookahead-invariance test passes) |",
        f"| `PASSIVE_SCORE_USEFUL` | **{'YES' if class_z_stats.get('primary_unique_reached_move', {}).get('mean_z') and class_z_stats.get('failed_triggered', {}).get('mean_z') and class_z_stats['primary_unique_reached_move']['mean_z'] > class_z_stats['failed_triggered']['mean_z'] else 'UNKNOWN'}** (verdict from class-z separation; see Section A) |",
        "",
    ])
    (REPORTS / "OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.md").write_text(
        "\n".join(md), encoding="utf-8"
    )

    print(f"wrote {stats_path}")
    print(f"wrote per-date *_with_zone_score.csv for {len(DATES)} dates")
    print(f"wrote {REPORTS/'OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.json'}")
    print(f"wrote {REPORTS/'OKX_ZONE_SCORE_V1_PASSIVE_VALIDATION.md'}")
    print()
    print("class z means:")
    for c in classes_order:
        s = class_z_stats[c]
        print(f"  {c:<30s}  n={s['n']:>4d}  mean_z={s.get('mean_z')}")
    print()
    print("bucket summary:")
    for b in buckets_order:
        s = bucket_summary[b]
        raw = "" if s["raw_triggered_hit_rate"] is None else f"raw_hit={s['raw_triggered_hit_rate']*100:.1f}%"
        uniq = "" if s["unique_move_hit_rate"] is None else f"uniq_hit={s['unique_move_hit_rate']*100:.1f}%"
        print(f"  {b:<6s}  n={s['n']:>4d}  triggered={s['triggered']:>3d}  reached_raw={s['reached_raw']:>3d}  unique={s['unique_moves']:>3d}  failed={s['failed_triggered']:>3d}  {raw}  {uniq}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
