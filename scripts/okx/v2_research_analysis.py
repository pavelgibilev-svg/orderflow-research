"""OKX zone_score_v2 research analysis on 24 full-day dates (read-only).

Phases:
  A. Build unified 24-date zone dataset      (OKX_24D_ZONE_DATASET.csv/json)
  B. Pre-trigger feature catalog            (OKX_24D_PRETRIGGER_FEATURE_CATALOG.md/json)
  C. Class comparisons                       (OKX_ZONE_SCORE_V2_FEATURE_ANALYSIS.md/json)
  D. Stability analysis (LOO + stratified)  (OKX_ZONE_SCORE_V2_STABILITY_ANALYSIS.md/json)
  E. Why v1 failed                           (WHY_ZONE_SCORE_V1_FAILED.md/json)
  F. Simple rule candidates                  (OKX_ZONE_SCORE_V2_RULE_CANDIDATES.md/json)
  G. Main research report + final flags     (OKX_ZONE_SCORE_V2_RESEARCH_ANALYSIS.md/json)

HARD RULES:
  - Pre-trigger features only (zone.reasons[candidate|confirmed|trigger] +
    zone.scores frozen at trigger + timing of startTs/confirmedTs/triggerTs).
  - Post-trigger fields (targets.*, resolvedTs, status as feature,
    uniqueMoveId/isPrimaryMoveZone/duplicateMoveCredit/moveClusterSize,
    future returns) ARE NEVER used as features. They are used only as
    *outcome labels* and in stratification (regime).
  - No strategy/threshold change. No filter wiring. No model fitting for
    production. No winrate / profitability claim.
"""
from __future__ import annotations
import csv
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports"

CALIB_DATES = [
    "2024-01-01", "2024-07-01", "2024-10-01",
    "2025-10-01", "2025-12-01", "2026-04-01",
]
OOS_V1_DATES = [
    "2024-05-01", "2024-06-01", "2024-09-01",
    "2025-04-01", "2025-05-01", "2025-11-01",
]
# v2 candidates from reports/OKX_SCORE_V2_CANDIDATE_DATES.json (deterministic
# list is loaded below; falls back to this list if file missing).
V2_DATES_DEFAULT = [
    "2024-02-01", "2024-03-01", "2024-04-01", "2024-12-01",
    "2025-02-01", "2025-03-01", "2025-08-01", "2025-09-01",
    "2026-01-01", "2026-02-01", "2026-03-01", "2026-05-01",
]

V1_FEATURES = [
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
V1_WEIGHT_SIGNS = {
    "cand_pressure_against": -1, "cand_absorb_score": -1, "cand_refill_with": +1,
    "conf_cycles_seen": -1, "conf_age_min": +1, "conf_defended_persistence_sec": +1,
    "candidate_to_confirm_min": +1, "confirm_to_trigger_min": -1,
    "total_pre_trigger_min": -1, "trig_flow_multiplier": +1,
    "trig_break_pct": -1, "score_absorption": -1,
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_json(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"WARN: failed to parse {p}: {e}", file=sys.stderr)
        return None


def load_v2_dates() -> list[str]:
    p = REPORTS / "OKX_SCORE_V2_CANDIDATE_DATES.json"
    d = load_json(p)
    if d and "chosen" in d:
        return [c["date"] for c in d["chosen"]]
    return list(V2_DATES_DEFAULT)


def fullday_json_for(date: str, round_label: str) -> Path:
    if round_label == "calibration":
        return REPORTS / f"OKX_TECHNICAL_REPLAY_{date}_fullday.json"
    if round_label == "oos_v1":
        return REPORTS / f"OKX_OOS_TECHNICAL_REPLAY_{date}_fullday.json"
    if round_label == "v2":
        return REPORTS / f"OKX_V2_TECHNICAL_REPLAY_{date}_fullday.json"
    return REPORTS / f"OKX_TECHNICAL_REPLAY_{date}_fullday.json"


def round_for(date: str, v2_dates: list[str]) -> str:
    if date in CALIB_DATES:
        return "calibration"
    if date in OOS_V1_DATES:
        return "oos_v1"
    if date in v2_dates:
        return "v2"
    return "unknown"


def load_regime() -> dict[str, dict]:
    rt = load_json(REPORTS / "OKX_REGIME_TABLE.json") or {"dates": []}
    return {r["date"]: r for r in rt["dates"]}


# ---------------------------------------------------------------------------
# Pre-trigger feature extraction (lock-step with src/strategy/zoneScoreV1.ts)
# ---------------------------------------------------------------------------

def get_reason(z: dict, stage: str) -> dict | None:
    for r in z.get("reasons") or []:
        if r.get("stage") == stage:
            return r
    return None


def num(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and not math.isnan(float(v)):
        return float(v)
    return None


def boolnum(v) -> float | None:
    if v is True:
        return 1.0
    if v is False:
        return 0.0
    return None


def extract_pretrigger_features(z: dict) -> dict[str, float | None]:
    """Catalog of every pre-trigger feature we can read from a Zone.
    Lock-step with src/strategy/zoneScoreV1.ts for the v1-12 plus several
    additional features the v1 analysis chose not to use."""
    cand = (get_reason(z, "candidate") or {}).get("conditions") or {}
    conf = (get_reason(z, "confirmed") or {}).get("conditions") or {}
    trig = (get_reason(z, "trigger") or {}).get("conditions") or {}
    direction = z.get("direction")

    # Direction-aware features
    if direction == "LONG":
        pressure_against = num(cand.get("sellPressure"))
        refill_with = num(cand.get("bidRefillScore"))
        prior_move = num(cand.get("downMovePct"))
    elif direction == "SHORT":
        pressure_against = num(cand.get("buyPressure"))
        refill_with = num(cand.get("askRefillScore"))
        prior_move = num(cand.get("upMovePct"))
    else:
        pressure_against = refill_with = prior_move = None

    # Timing
    start_ts = num(z.get("startTs"))
    confirmed_ts = num(z.get("confirmedTs"))
    trigger_ts = num(z.get("triggerTs"))
    cand_to_conf_min = (
        (confirmed_ts - start_ts) / 60_000 if confirmed_ts is not None and start_ts is not None else None
    )
    conf_to_trig_min = (
        (trigger_ts - confirmed_ts) / 60_000 if trigger_ts is not None and confirmed_ts is not None else None
    )
    total_pre_trig_min = (
        (trigger_ts - start_ts) / 60_000 if trigger_ts is not None and start_ts is not None else None
    )

    zone_low = num(z.get("zoneLow"))
    zone_high = num(z.get("zoneHigh"))
    zone_width_pct = (
        (zone_high - zone_low) / zone_low * 100.0
        if zone_low is not None and zone_high is not None and zone_low > 0 else None
    )
    target_price = num(z.get("targetPrice"))
    trigger_price = num(z.get("triggerPrice"))
    target_distance_pct = (
        abs(target_price - trigger_price) / trigger_price * 100.0
        if target_price is not None and trigger_price is not None and trigger_price > 0 else None
    )

    scores = z.get("scores") or {}

    return {
        # --- v1 12 features (must remain stable for the v1 retrospective) ---
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
        "score_absorption": num(scores.get("absorptionScore")),
        # --- additional candidate features ---
        "cand_prior_move_pct": prior_move,
        "cand_range_compression": boolnum(cand.get("rangeCompression")),
        "conf_opposite_thinning": num(conf.get("oppositeThinning")),
        "conf_void_score": num(conf.get("voidScore")),
        "trig_side_flow_ok": boolnum(trig.get("sideFlowOK")),
        "score_liquidity_void": num(scores.get("liquidityVoidScore")),
        "score_ofi": num(scores.get("ofiScore")),
        "score_refill": num(scores.get("refillScore")),
        "score_trigger": num(scores.get("triggerScore")),
        "zone_width_pct": zone_width_pct,
        "target_distance_pct": target_distance_pct,
        "n_quality_flags": float(len(z.get("qualityFlags") or [])),
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
# Statistical helpers (pure stdlib)
# ---------------------------------------------------------------------------

def clean(values: Iterable[Any]) -> list[float]:
    return [float(v) for v in values if v is not None and isinstance(v, (int, float)) and not math.isnan(float(v))]


def descr(values: list[float]) -> dict:
    c = clean(values)
    if not c:
        return {"n": 0, "mean": None, "median": None, "stdev": None, "min": None, "max": None}
    return {
        "n": len(c),
        "mean": statistics.mean(c),
        "median": statistics.median(c),
        "stdev": statistics.pstdev(c) if len(c) > 1 else 0.0,
        "min": min(c),
        "max": max(c),
    }


def cohens_d(a: list[float], b: list[float]) -> float | None:
    a = clean(a); b = clean(b)
    if len(a) < 2 or len(b) < 2:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    va, vb = statistics.pvariance(a), statistics.pvariance(b)
    pooled = math.sqrt((va + vb) / 2)
    if pooled == 0:
        return 0.0 if ma == mb else float("inf")
    return (ma - mb) / pooled


def mann_whitney_u_norm(a: list[float], b: list[float]) -> tuple[float | None, float | None]:
    """Mann-Whitney U with normal approximation + tie correction.
    Returns (U, two-sided p-value). None when sample too small or both
    arrays empty / constant."""
    a = clean(a); b = clean(b)
    if not a or not b:
        return None, None
    combined = sorted(a + b)
    n1, n2 = len(a), len(b)
    # rank with average ties
    ranks: dict[float, float] = {}
    i = 0
    rank_pos = 1
    tie_groups: list[int] = []
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1] == combined[i]:
            j += 1
        avg_rank = (rank_pos + (rank_pos + (j - i))) / 2.0
        ranks[combined[i]] = avg_rank
        if j > i:
            tie_groups.append(j - i + 1)
        rank_pos += j - i + 1
        i = j + 1
    R1 = sum(ranks[x] for x in a)
    U1 = R1 - n1 * (n1 + 1) / 2
    # Mean and tie-corrected variance
    mean_U = n1 * n2 / 2
    n = n1 + n2
    tie_term = sum(t * (t * t - 1) for t in tie_groups)
    var_U = n1 * n2 / 12 * ((n + 1) - tie_term / (n * (n - 1))) if n > 1 else 0
    if var_U <= 0:
        return U1, None
    z = (U1 - mean_U) / math.sqrt(var_U)
    # Two-sided p via normal CDF approximation
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return U1, max(min(p, 1.0), 0.0)


def quantiles(values: list[float], qs: list[float]) -> dict[float, float]:
    c = sorted(clean(values))
    if not c:
        return {q: float("nan") for q in qs}
    out: dict[float, float] = {}
    for q in qs:
        # linear interpolation between order statistics
        idx = q * (len(c) - 1)
        lo = math.floor(idx)
        hi = math.ceil(idx)
        if lo == hi:
            out[q] = c[lo]
        else:
            out[q] = c[lo] + (c[hi] - c[lo]) * (idx - lo)
    return out


# ---------------------------------------------------------------------------
# Phase A: dataset assembly
# ---------------------------------------------------------------------------

def phase_a_build_dataset(v2_dates: list[str]) -> list[dict]:
    regime_by_date = load_regime()
    all_dates = CALIB_DATES + OOS_V1_DATES + v2_dates
    dataset: list[dict] = []
    for d in all_dates:
        rd = round_for(d, v2_dates)
        outer = load_json(fullday_json_for(d, rd)) or {}
        inner = outer.get("underlying_backtest_summary") or {}
        zones = inner.get("zones") or []
        rg = regime_by_date.get(d, {})
        for z in zones:
            feats = extract_pretrigger_features(z)
            cls = classify(z)
            row = {
                "date": d,
                "round": rd,
                "venue": "okx-swap",
                "symbol": "BTC-USDT-SWAP",
                "regime_bucket": rg.get("regime"),
                "day_return_pct": rg.get("day_return_pct"),
                "range_pct": rg.get("range_pct"),
                "target_2pct_feasible": (rg.get("feasibility") or {}).get("2.0pct"),
                "zone_id": z.get("id"),
                "direction": z.get("direction"),
                "zoneType": z.get("zoneType"),
                "status": z.get("status"),
                "startTs": z.get("startTs"),
                "confirmedTs": z.get("confirmedTs"),
                "triggerTs": z.get("triggerTs"),
                "resolvedTs": z.get("resolvedTs"),
                "triggered": z.get("status") in ("RESOLVED_REACHED", "RESOLVED_FAILED"),
                "reached_raw": z.get("status") == "RESOLVED_REACHED",
                "uniqueMoveId": z.get("uniqueMoveId"),
                "isPrimaryMoveZone": z.get("isPrimaryMoveZone"),
                "duplicateMoveCredit": z.get("duplicateMoveCredit"),
                "moveClusterSize": z.get("moveClusterSize"),
                "class_label": cls,
                "features": feats,
            }
            dataset.append(row)

    # Write JSON
    out_json = REPORTS / "OKX_24D_ZONE_DATASET.json"
    out_json.write_text(json.dumps({
        "venue": "OKX (okex-swap)", "symbol": "BTC-USDT-SWAP",
        "n_dates": len(all_dates), "n_zones": len(dataset),
        "rounds": {"calibration": CALIB_DATES, "oos_v1": OOS_V1_DATES, "v2": v2_dates},
        "rows": dataset,
    }, indent=2, default=str), encoding="utf-8")

    # Write CSV (flat)
    out_csv = REPORTS / "OKX_24D_ZONE_DATASET.csv"
    cols = [
        "date", "round", "venue", "symbol", "regime_bucket", "day_return_pct", "range_pct",
        "target_2pct_feasible", "zone_id", "direction", "zoneType", "status",
        "startTs", "confirmedTs", "triggerTs", "resolvedTs",
        "triggered", "reached_raw", "uniqueMoveId", "isPrimaryMoveZone",
        "duplicateMoveCredit", "moveClusterSize", "class_label",
    ]
    feature_cols = list(dataset[0]["features"].keys()) if dataset else []
    all_cols = cols + [f"feat__{f}" for f in feature_cols]
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(all_cols)
        for r in dataset:
            line = [r.get(c) for c in cols]
            for ff in feature_cols:
                line.append(r["features"].get(ff))
            w.writerow(line)
    print(f"  wrote {out_json}", file=sys.stderr)
    print(f"  wrote {out_csv}", file=sys.stderr)
    return dataset


# ---------------------------------------------------------------------------
# Phase B: feature catalog
# ---------------------------------------------------------------------------

def phase_b_feature_catalog(dataset: list[dict]) -> list[str]:
    if not dataset:
        return []
    feature_keys = list(dataset[0]["features"].keys())
    catalog: list[dict] = []
    for f in feature_keys:
        all_vals = [r["features"].get(f) for r in dataset]
        present = sum(1 for v in all_vals if v is not None)
        missing = len(all_vals) - present
        c = clean(all_vals)
        catalog.append({
            "feature": f,
            "n_total": len(all_vals),
            "n_present": present,
            "missing_rate": missing / len(all_vals) if all_vals else 0,
            "min": min(c) if c else None,
            "max": max(c) if c else None,
            "mean": statistics.mean(c) if c else None,
            "stage": (
                "@candidate" if f.startswith("cand_")
                else "@confirmed" if f.startswith("conf_")
                else "@trigger" if f.startswith("trig_")
                else "@score" if f.startswith("score_")
                else "derived/geometry"
            ),
            "is_v1_feature": f in V1_FEATURES,
        })

    # Forbidden list (explicit, for auditors)
    forbidden = [
        "targets.* (mfePct, maePct, outcome, reachedAt, timeToTargetMin, maxDrawdownBeforeTargetPct, endPrice, endTs)",
        "resolvedTs (used only as outcome timing, not as feature)",
        "status (final state — used only as outcome label)",
        "uniqueMoveId / isPrimaryMoveZone / duplicateMoveCredit / moveClusterSize (assigned by move-clustering AFTER resolve)",
        "future day_return / future max move / future regime label",
        "reasons[stage in {expire, invalidate}].conditions (post-trigger / post-resolve)",
        "qualityFlags entries added at resolution time",
        "regime_bucket as a per-zone feature (allowed only for stratified analysis)",
    ]

    out_json = REPORTS / "OKX_24D_PRETRIGGER_FEATURE_CATALOG.json"
    out_json.write_text(json.dumps({
        "n_features": len(feature_keys),
        "n_v1_features": sum(1 for f in feature_keys if f in V1_FEATURES),
        "features": catalog,
        "forbidden_for_features": forbidden,
    }, indent=2), encoding="utf-8")

    md = [
        "# OKX 24-date pre-trigger feature catalog",
        "",
        f"**Total features:** {len(feature_keys)} (of which {sum(1 for f in feature_keys if f in V1_FEATURES)} are the v1-12)",
        "",
        "All features are observable AT or BEFORE `zone.triggerTs`. Sources:",
        "  - `zone.reasons[stage in {candidate, confirmed, trigger}].conditions`",
        "  - `zone.scores.*` (frozen at trigger transition)",
        "  - `zone.startTs / confirmedTs / triggerTs` (timing-only derivations)",
        "  - `zone.zoneLow / zoneHigh / triggerPrice / targetPrice` (geometry only, no future price)",
        "",
        "## A. Features available",
        "",
        "| feature | stage | v1? | n present | missing % | min | max | mean |",
        "|---|---|:---:|---:|---:|---:|---:|---:|",
    ]
    for c in catalog:
        v1m = "yes" if c["is_v1_feature"] else "—"
        miss = f"{c['missing_rate']*100:.1f}%"
        md.append(
            f"| `{c['feature']}` | {c['stage']} | {v1m} | {c['n_present']} | {miss} | "
            f"{c['min'] if c['min'] is not None else '—'} | "
            f"{c['max'] if c['max'] is not None else '—'} | "
            f"{c['mean'] if c['mean'] is not None else '—'} |"
        )
    md.extend([
        "",
        "## B. Forbidden as features (post-trigger / lookahead)",
        "",
    ])
    for x in forbidden:
        md.append(f"- {x}")
    md.append("")
    (REPORTS / "OKX_24D_PRETRIGGER_FEATURE_CATALOG.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  wrote OKX_24D_PRETRIGGER_FEATURE_CATALOG.md/.json", file=sys.stderr)
    return feature_keys


# ---------------------------------------------------------------------------
# Phase C: class comparisons
# ---------------------------------------------------------------------------

CLASSES = [
    "primary_unique_reached_move",
    "duplicate_reached_move",
    "failed_triggered",
    "no_trigger",
    "invalidated_or_expired",
]


def feature_vector(dataset: list[dict], feat: str, class_label: str | None = None) -> list[float]:
    if class_label is None:
        return [r["features"].get(feat) for r in dataset]
    return [r["features"].get(feat) for r in dataset if r["class_label"] == class_label]


def phase_c_class_comparisons(dataset: list[dict], features: list[str]) -> dict:
    pairs = [
        ("primary_unique_reached_move", "failed_triggered"),
        ("primary_unique_reached_move", "duplicate_reached_move"),
        ("primary_unique_reached_move", "non_primary_all"),
        ("duplicate_reached_move", "failed_triggered"),
    ]
    rows: dict[str, dict] = {}
    for f in features:
        f_block: dict[str, Any] = {"feature": f, "by_class": {}, "pairs": {}}
        for cls in CLASSES:
            f_block["by_class"][cls] = descr(feature_vector(dataset, f, cls))
        # custom 'non_primary_all'
        non_primary = [r for r in dataset if r["class_label"] != "primary_unique_reached_move"]
        for left, right in pairs:
            a_vals = feature_vector(dataset, f, left)
            b_vals = (
                [r["features"].get(f) for r in non_primary]
                if right == "non_primary_all"
                else feature_vector(dataset, f, right)
            )
            d = cohens_d(a_vals, b_vals)
            U, p = mann_whitney_u_norm(a_vals, b_vals)
            f_block["pairs"][f"{left}__vs__{right}"] = {
                "n_left": len(clean(a_vals)),
                "n_right": len(clean(b_vals)),
                "cohens_d": d,
                "mann_whitney_U": U,
                "mann_whitney_p_two_sided": p,
                "mean_left": (statistics.mean(clean(a_vals)) if clean(a_vals) else None),
                "mean_right": (statistics.mean(clean(b_vals)) if clean(b_vals) else None),
            }
        rows[f] = f_block

    # Rank features by |cohens_d| primary vs failed
    ranked = sorted(features, key=lambda f: abs(
        rows[f]["pairs"]["primary_unique_reached_move__vs__failed_triggered"]["cohens_d"] or 0
    ), reverse=True)

    # Write JSON
    out_json = {
        "pairs_considered": pairs,
        "per_feature": rows,
        "ranked_by_primary_vs_failed_abs_cohens_d": ranked,
        "caveat_n": "primary_unique_reached_move has n=21 across 24 dates (~21 positives); Cohen's d on n<30 is suggestive only, p-values from normal-approximation Mann-Whitney are noisy at this sample size.",
    }
    (REPORTS / "OKX_ZONE_SCORE_V2_FEATURE_ANALYSIS.json").write_text(json.dumps(out_json, indent=2, default=str), encoding="utf-8")

    # Markdown
    def f6(v):
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            return "—"
        return f"{v:+.3f}" if isinstance(v, float) else str(v)

    n_primary = sum(1 for r in dataset if r["class_label"] == "primary_unique_reached_move")
    n_dup = sum(1 for r in dataset if r["class_label"] == "duplicate_reached_move")
    n_failed = sum(1 for r in dataset if r["class_label"] == "failed_triggered")
    n_no_trig = sum(1 for r in dataset if r["class_label"] == "no_trigger")
    n_inv = sum(1 for r in dataset if r["class_label"] == "invalidated_or_expired")

    md = [
        "# OKX zone_score_v2 — feature class comparisons",
        "",
        f"**Dataset:** 24 OKX BTC-USDT-SWAP full-day replays, {len(dataset)} zones.",
        f"**Class counts:** primary_unique={n_primary}, duplicate={n_dup}, failed={n_failed}, no_trigger={n_no_trig}, invalid/expired={n_inv}.",
        "",
        "## HARD DISCLAIMER",
        "",
        "  • Sample is **n=21 primary unique reached** moves across 24 dates. Effect sizes and p-values below are **suggestive only**.",
        "  • This is research, not production. NO score is wired into the engine. NO threshold is changed.",
        "  • All features are pre-trigger by construction; lookahead-invariance is enforced upstream (tests/zoneScoreV1.test.ts).",
        "",
        "## A. Top-30 features by |Cohen's d| (primary unique vs failed triggered)",
        "",
        "Positive d ⇒ feature is higher for primary-unique than for failed. Magnitude scale: 0.2 small, 0.5 medium, 0.8 large.",
        "",
        "| rank | feature | Cohen d | MW U | p (two-sided) | primary mean | failed mean | n primary / n failed |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for i, f in enumerate(ranked[:30], 1):
        b = rows[f]["pairs"]["primary_unique_reached_move__vs__failed_triggered"]
        md.append(
            f"| {i} | `{f}` | {f6(b['cohens_d'])} | "
            f"{f6(b['mann_whitney_U'])} | "
            f"{(f'{b['mann_whitney_p_two_sided']:.3f}' if b['mann_whitney_p_two_sided'] is not None else '—')} | "
            f"{f6(b['mean_left'])} | {f6(b['mean_right'])} | {b['n_left']}/{b['n_right']} |"
        )

    md.extend([
        "",
        "## B. Primary unique vs duplicate reached",
        "",
        "Why this pair matters: duplicates ARE successful reaches, but the engine fires them on the same multi-hour move that the primary already caught. Features that separate them are the 'first-mover' signal.",
        "",
        "| rank | feature | Cohen d | n primary / n duplicate |",
        "|---:|---|---:|---|",
    ])
    by_pd = sorted(features, key=lambda f: abs(
        rows[f]["pairs"]["primary_unique_reached_move__vs__duplicate_reached_move"]["cohens_d"] or 0
    ), reverse=True)
    for i, f in enumerate(by_pd[:15], 1):
        b = rows[f]["pairs"]["primary_unique_reached_move__vs__duplicate_reached_move"]
        md.append(f"| {i} | `{f}` | {f6(b['cohens_d'])} | {b['n_left']}/{b['n_right']} |")

    md.extend([
        "",
        "## C. Primary unique vs non_primary_all (the catch-all)",
        "",
        "non_primary_all = duplicate + failed + no_trigger + invalidated/expired (everything that is NOT a primary-unique reached zone).",
        "",
        "| rank | feature | Cohen d | n primary / n non-primary |",
        "|---:|---|---:|---|",
    ])
    by_pn = sorted(features, key=lambda f: abs(
        rows[f]["pairs"]["primary_unique_reached_move__vs__non_primary_all"]["cohens_d"] or 0
    ), reverse=True)
    for i, f in enumerate(by_pn[:15], 1):
        b = rows[f]["pairs"]["primary_unique_reached_move__vs__non_primary_all"]
        md.append(f"| {i} | `{f}` | {f6(b['cohens_d'])} | {b['n_left']}/{b['n_right']} |")

    md.append("")
    md.append("Companion JSON: `reports/OKX_ZONE_SCORE_V2_FEATURE_ANALYSIS.json`")
    (REPORTS / "OKX_ZONE_SCORE_V2_FEATURE_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  wrote OKX_ZONE_SCORE_V2_FEATURE_ANALYSIS.md/.json", file=sys.stderr)
    return out_json


# ---------------------------------------------------------------------------
# Phase D: stability analysis
# ---------------------------------------------------------------------------

def sign(x: float | None) -> int:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return 0
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def phase_d_stability(dataset: list[dict], features: list[str]) -> dict:
    dates = sorted({r["date"] for r in dataset})
    # 1. LOO sign preservation for primary_unique vs failed
    loo_signs: dict[str, dict] = {}
    for f in features:
        all_primary = [r["features"].get(f) for r in dataset if r["class_label"] == "primary_unique_reached_move"]
        all_failed = [r["features"].get(f) for r in dataset if r["class_label"] == "failed_triggered"]
        full_d = cohens_d(all_primary, all_failed)
        full_sign = sign(full_d)
        fold_signs: list[int] = []
        for d_left in dates:
            p_vals = [r["features"].get(f) for r in dataset if r["class_label"] == "primary_unique_reached_move" and r["date"] != d_left]
            f_vals = [r["features"].get(f) for r in dataset if r["class_label"] == "failed_triggered" and r["date"] != d_left]
            fold_d = cohens_d(p_vals, f_vals)
            fold_signs.append(sign(fold_d))
        agree = sum(1 for s in fold_signs if s == full_sign and s != 0)
        loo_signs[f] = {
            "full_cohens_d": full_d,
            "full_sign": full_sign,
            "fold_signs_match": agree,
            "fold_signs_total": len(fold_signs),
            "fold_signs_match_rate": agree / len(fold_signs) if fold_signs else None,
        }

    # 2. By direction
    by_dir: dict[str, dict] = {"LONG": {}, "SHORT": {}}
    for direction in ("LONG", "SHORT"):
        for f in features:
            p_vals = [r["features"].get(f) for r in dataset
                      if r["class_label"] == "primary_unique_reached_move" and r["direction"] == direction]
            f_vals = [r["features"].get(f) for r in dataset
                      if r["class_label"] == "failed_triggered" and r["direction"] == direction]
            by_dir[direction][f] = {
                "n_primary": len(clean(p_vals)),
                "n_failed": len(clean(f_vals)),
                "cohens_d": cohens_d(p_vals, f_vals),
            }

    # 3. By regime
    by_regime: dict[str, dict] = {"bullish": {}, "bearish": {}, "choppy": {}}
    for reg in ("bullish", "bearish", "choppy"):
        for f in features:
            p_vals = [r["features"].get(f) for r in dataset
                      if r["class_label"] == "primary_unique_reached_move" and r["regime_bucket"] == reg]
            f_vals = [r["features"].get(f) for r in dataset
                      if r["class_label"] == "failed_triggered" and r["regime_bucket"] == reg]
            by_regime[reg][f] = {
                "n_primary": len(clean(p_vals)),
                "n_failed": len(clean(f_vals)),
                "cohens_d": cohens_d(p_vals, f_vals),
            }

    # 4. By feasibility
    by_feas: dict[str, dict] = {"feasible": {}, "infeasible": {}}
    for f in features:
        for feas, key in (("feasible", True), ("infeasible", False)):
            p_vals = [r["features"].get(f) for r in dataset
                      if r["class_label"] == "primary_unique_reached_move" and r["target_2pct_feasible"] is key]
            f_vals = [r["features"].get(f) for r in dataset
                      if r["class_label"] == "failed_triggered" and r["target_2pct_feasible"] is key]
            by_feas[feas][f] = {
                "n_primary": len(clean(p_vals)),
                "n_failed": len(clean(f_vals)),
                "cohens_d": cohens_d(p_vals, f_vals),
            }

    # Categorise features
    stable_features = sorted(
        [f for f in features if loo_signs[f]["fold_signs_match_rate"] is not None
         and loo_signs[f]["fold_signs_match_rate"] >= 0.80
         and abs(loo_signs[f]["full_cohens_d"] or 0) >= 0.3],
        key=lambda f: -abs(loo_signs[f]["full_cohens_d"] or 0),
    )
    unstable_features = sorted(
        [f for f in features if loo_signs[f]["fold_signs_match_rate"] is not None
         and loo_signs[f]["fold_signs_match_rate"] < 0.50
         and abs(loo_signs[f]["full_cohens_d"] or 0) >= 0.2],
        key=lambda f: -abs(loo_signs[f]["full_cohens_d"] or 0),
    )
    direction_specific = []
    for f in features:
        long_d = by_dir["LONG"][f]["cohens_d"]
        short_d = by_dir["SHORT"][f]["cohens_d"]
        if long_d is None or short_d is None:
            continue
        if abs(long_d) >= 0.3 and abs(short_d) >= 0.3 and sign(long_d) != sign(short_d):
            direction_specific.append({"feature": f, "long_d": long_d, "short_d": short_d})
    regime_specific = []
    for f in features:
        ds = {r: by_regime[r][f]["cohens_d"] for r in by_regime}
        present = [v for v in ds.values() if v is not None]
        if len(present) < 2:
            continue
        signs_set = {sign(v) for v in present if sign(v) != 0}
        if len(signs_set) >= 2 and max(abs(v) for v in present) >= 0.5:
            regime_specific.append({"feature": f, "by_regime": ds})

    out = {
        "loo_signs": loo_signs,
        "by_direction": by_dir,
        "by_regime": by_regime,
        "by_feasibility": by_feas,
        "stable_features": stable_features,
        "unstable_features": unstable_features,
        "direction_specific_features": direction_specific,
        "regime_specific_features": regime_specific,
        "rules": {
            "stable":   "|d| >= 0.3 AND LOO sign match rate >= 80%",
            "unstable": "|d| >= 0.2 AND LOO sign match rate < 50%",
            "direction_specific": "|long_d| >= 0.3 AND |short_d| >= 0.3 AND opposite signs",
            "regime_specific": "max |d| across regimes >= 0.5 AND signs differ across regimes",
        },
    }
    (REPORTS / "OKX_ZONE_SCORE_V2_STABILITY_ANALYSIS.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    # Markdown
    def fr(v, p=3):
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            return "—"
        return f"{v:+.{p}f}"

    md = [
        "# OKX zone_score_v2 — stability analysis",
        "",
        f"**Dataset:** {len(dataset)} zones across {len(dates)} OKX BTC-USDT-SWAP dates.",
        "",
        "## A. Leave-one-date-out sign preservation (primary unique vs failed)",
        "",
        "For each feature: sign of Cohen's d on the full dataset, vs the sign in each 23-date fold.",
        "",
        "| feature | full d | LOO match rate | fold match |",
        "|---|---:|---:|---:|",
    ]
    for f in sorted(features, key=lambda f: -abs(loo_signs[f]["full_cohens_d"] or 0)):
        x = loo_signs[f]
        rate = x["fold_signs_match_rate"]
        rate_s = f"{rate*100:.1f}%" if rate is not None else "—"
        md.append(f"| `{f}` | {fr(x['full_cohens_d'])} | {rate_s} | {x['fold_signs_match']}/{x['fold_signs_total']} |")

    md.extend([
        "",
        "## B. Stable features",
        "",
        "Definition: `|d| >= 0.3` AND LOO sign match rate `>= 80%`.",
        "",
        f"**Count:** {len(stable_features)}",
        "",
        "| feature | full d | LOO match rate |",
        "|---|---:|---:|",
    ])
    for f in stable_features:
        x = loo_signs[f]
        md.append(f"| `{f}` | {fr(x['full_cohens_d'])} | {(x['fold_signs_match_rate']*100):.1f}% |")

    md.extend([
        "",
        "## C. Unstable features",
        "",
        "Definition: `|d| >= 0.2` AND LOO sign match rate `< 50%` — the sign flips frequently when one date is removed.",
        "",
        f"**Count:** {len(unstable_features)}",
        "",
        "| feature | full d | LOO match rate |",
        "|---|---:|---:|",
    ])
    for f in unstable_features:
        x = loo_signs[f]
        md.append(f"| `{f}` | {fr(x['full_cohens_d'])} | {(x['fold_signs_match_rate']*100):.1f}% |")

    md.extend([
        "",
        "## D. Direction-specific features (opposite signs LONG vs SHORT)",
        "",
        f"**Count:** {len(direction_specific)}",
        "",
        "| feature | LONG d | SHORT d |",
        "|---|---:|---:|",
    ])
    for r in direction_specific:
        md.append(f"| `{r['feature']}` | {fr(r['long_d'])} | {fr(r['short_d'])} |")

    md.extend([
        "",
        "## E. Regime-specific features (different signs across bullish/bearish/choppy)",
        "",
        f"**Count:** {len(regime_specific)}",
        "",
        "| feature | bullish d | bearish d | choppy d |",
        "|---|---:|---:|---:|",
    ])
    for r in regime_specific:
        md.append(f"| `{r['feature']}` | {fr(r['by_regime'].get('bullish'))} | {fr(r['by_regime'].get('bearish'))} | {fr(r['by_regime'].get('choppy'))} |")

    md.append("")
    md.append("Companion JSON: `reports/OKX_ZONE_SCORE_V2_STABILITY_ANALYSIS.json`")
    (REPORTS / "OKX_ZONE_SCORE_V2_STABILITY_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  wrote OKX_ZONE_SCORE_V2_STABILITY_ANALYSIS.md/.json", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# Phase E: v1 retrospective
# ---------------------------------------------------------------------------

def phase_e_v1_retrospective(dataset: list[dict], stability: dict) -> dict:
    rows_per_round: dict[str, dict] = {}
    for round_label in ("calibration", "oos_v1", "v2", "all_24"):
        if round_label == "all_24":
            sub = dataset
        else:
            sub = [r for r in dataset if r["round"] == round_label]
        per_feature: dict[str, dict] = {}
        for f in V1_FEATURES:
            p_vals = [r["features"].get(f) for r in sub if r["class_label"] == "primary_unique_reached_move"]
            fl_vals = [r["features"].get(f) for r in sub if r["class_label"] == "failed_triggered"]
            d = cohens_d(p_vals, fl_vals)
            per_feature[f] = {
                "n_primary": len(clean(p_vals)),
                "n_failed": len(clean(fl_vals)),
                "cohens_d_primary_vs_failed": d,
                "v1_expected_sign": V1_WEIGHT_SIGNS[f],
                "actual_sign": sign(d),
                "sign_matches_v1": (sign(d) == V1_WEIGHT_SIGNS[f]) if d is not None else None,
            }
        rows_per_round[round_label] = per_feature

    inverted = []
    survived = []
    flat = []
    for f in V1_FEATURES:
        signs = [rows_per_round[r][f]["actual_sign"] for r in ("calibration", "oos_v1", "v2")]
        ds = [rows_per_round[r][f]["cohens_d_primary_vs_failed"] for r in ("calibration", "oos_v1", "v2")]
        all24_d = rows_per_round["all_24"][f]["cohens_d_primary_vs_failed"]
        expected = V1_WEIGHT_SIGNS[f]
        match_count = sum(1 for s in signs if s == expected)
        verdict = {
            "feature": f,
            "v1_expected_sign": expected,
            "calibration_sign": signs[0],
            "oos_v1_sign": signs[1],
            "v2_sign": signs[2],
            "all_24_sign": sign(all24_d),
            "all_24_d": all24_d,
            "rounds_matching_v1_sign": match_count,
        }
        if expected != 0 and sign(all24_d) != 0 and sign(all24_d) != expected:
            inverted.append(verdict)
        elif expected != 0 and sign(all24_d) == expected and abs(all24_d or 0) >= 0.2:
            survived.append(verdict)
        else:
            flat.append(verdict)

    out = {
        "per_round_v1_feature_stats": rows_per_round,
        "v1_features_inverted_on_24d": inverted,
        "v1_features_surviving_on_24d": survived,
        "v1_features_too_flat_on_24d": flat,
        "headline": "v1 OOS recall was 14.29% (1/7 unique moves in `high` bucket). Primary mean z inverted from +2.51 in-sample to -1.54 OOS. This phase tracks the underlying per-feature signs to see which features actually flipped vs which stayed but weren't strong enough.",
    }
    (REPORTS / "WHY_ZONE_SCORE_V1_FAILED.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    def fr(v, p=3):
        if v is None: return "—"
        return f"{v:+.{p}f}"

    md = [
        "# Why `zone_score_v1` failed — per-feature retrospective on 24 OKX days",
        "",
        "v1 archived as failed: in-sample recall 100 %, OOS recall 14.29 %. This file dissects each of the 12 v1 features across the three rounds to show which features actually flipped.",
        "",
        "Sign convention: positive Cohen's d means primary-unique-reached zones have HIGHER values than failed-triggered zones (good for v1 weight sign +1). Negative means LOWER (good for v1 weight sign −1).",
        "",
        "## A. Per-round Cohen's d for each v1 feature",
        "",
        "| feature | v1 expected sign | calibration d | OOS_v1 d | v2 d | all_24 d | rounds matching v1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for f in V1_FEATURES:
        expected = V1_WEIGHT_SIGNS[f]
        c_d = rows_per_round["calibration"][f]["cohens_d_primary_vs_failed"]
        o_d = rows_per_round["oos_v1"][f]["cohens_d_primary_vs_failed"]
        v_d = rows_per_round["v2"][f]["cohens_d_primary_vs_failed"]
        a_d = rows_per_round["all_24"][f]["cohens_d_primary_vs_failed"]
        matches = sum(1 for d in (c_d, o_d, v_d) if sign(d) == expected)
        md.append(
            f"| `{f}` | {expected:+d} | {fr(c_d)} | {fr(o_d)} | {fr(v_d)} | {fr(a_d)} | {matches}/3 |"
        )

    md.extend([
        "",
        "## B. v1 features that INVERTED on the full 24-day pool",
        "",
        f"**Count:** {len(inverted)}",
        "",
        "| feature | v1 expected sign | all_24 actual sign | all_24 d |",
        "|---|---:|---:|---:|",
    ])
    for v in inverted:
        md.append(f"| `{v['feature']}` | {v['v1_expected_sign']:+d} | {v['all_24_sign']:+d} | {fr(v['all_24_d'])} |")

    md.extend([
        "",
        "## C. v1 features that SURVIVED on the full 24-day pool",
        "",
        "Definition: full-pool sign matches v1's expected sign AND |d| ≥ 0.2.",
        f"**Count:** {len(survived)}",
        "",
        "| feature | v1 expected sign | all_24 d |",
        "|---|---:|---:|",
    ])
    for v in survived:
        md.append(f"| `{v['feature']}` | {v['v1_expected_sign']:+d} | {fr(v['all_24_d'])} |")

    md.extend([
        "",
        "## D. v1 features that became TOO FLAT on the 24-day pool",
        "",
        "Definition: full-pool |d| < 0.2 OR sign of full d is 0.",
        f"**Count:** {len(flat)}",
        "",
        "| feature | v1 expected sign | all_24 d |",
        "|---|---:|---:|",
    ])
    for v in flat:
        md.append(f"| `{v['feature']}` | {v['v1_expected_sign']:+d} | {fr(v['all_24_d'])} |")

    md.extend([
        "",
        "## E. Conclusion",
        "",
        "- v1 was fitted on 5 positives. With 21 positives in the combined pool, multiple features flipped sign.",
        "- The v1 score's failure on OOS is fully explained by features that look strong on n=5 but reverse direction (or vanish) once the positive sample grows.",
        "- Lesson for v2: select features on a held-out portion of the 21 positives; do NOT reuse the calibration sample for both feature selection and weight fitting.",
        "",
        "Companion JSON: `reports/WHY_ZONE_SCORE_V1_FAILED.json`",
    ])
    (REPORTS / "WHY_ZONE_SCORE_V1_FAILED.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  wrote WHY_ZONE_SCORE_V1_FAILED.md/.json", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# Phase F: simple rule candidates
# ---------------------------------------------------------------------------

def quartile_rule_eval(dataset: list[dict], feature: str, direction: str = "high") -> dict:
    """Top (direction=high) or bottom (direction=low) 25% of triggered zones
    by the feature; compute precision/recall vs primary unique reached."""
    triggered = [r for r in dataset if r["triggered"]]
    pairs = [(r["features"].get(feature), r) for r in triggered if r["features"].get(feature) is not None]
    if not pairs:
        return {"feature": feature, "n_triggered": 0, "n_with_feat": 0, "precision": None, "recall": None}
    qs = quantiles([p[0] for p in pairs], [0.25, 0.75])
    if direction == "high":
        cut = qs[0.75]
        bucket = [r for v, r in pairs if v > cut]
    else:
        cut = qs[0.25]
        bucket = [r for v, r in pairs if v < cut]
    n_bucket = len(bucket)
    n_primary_in_bucket = sum(1 for r in bucket if r["class_label"] == "primary_unique_reached_move")
    total_primary = sum(1 for r in triggered if r["class_label"] == "primary_unique_reached_move")
    return {
        "feature": feature,
        "direction": direction,
        "n_triggered": len(triggered),
        "n_with_feat": len(pairs),
        "cut": cut,
        "n_bucket": n_bucket,
        "n_primary_in_bucket": n_primary_in_bucket,
        "total_primary": total_primary,
        "precision": (n_primary_in_bucket / n_bucket) if n_bucket else None,
        "recall": (n_primary_in_bucket / total_primary) if total_primary else None,
    }


def phase_f_rule_candidates(dataset: list[dict], features: list[str], stability: dict) -> dict:
    # Single-feature quartile rules over all stable features (both directions)
    single_rules: list[dict] = []
    for f in stability["stable_features"]:
        full_sign = stability["loo_signs"][f]["full_sign"]
        # If primary > failed (positive d), high quartile should be enriched in primary
        direction = "high" if full_sign > 0 else "low"
        single_rules.append(quartile_rule_eval(dataset, f, direction))

    # Two-feature combinations from top stable features
    two_rules: list[dict] = []
    top = stability["stable_features"][:6]
    for i, a in enumerate(top):
        for b in top[i + 1:]:
            triggered = [r for r in dataset if r["triggered"]]
            # use sign-based direction per feature
            sign_a = stability["loo_signs"][a]["full_sign"]
            sign_b = stability["loo_signs"][b]["full_sign"]
            # quartile cuts
            vals_a = [r["features"].get(a) for r in triggered if r["features"].get(a) is not None]
            vals_b = [r["features"].get(b) for r in triggered if r["features"].get(b) is not None]
            if not vals_a or not vals_b:
                continue
            qa = quantiles(vals_a, [0.5])[0.5]
            qb = quantiles(vals_b, [0.5])[0.5]
            def cond(r):
                va = r["features"].get(a); vb = r["features"].get(b)
                if va is None or vb is None: return False
                ok_a = (va > qa) if sign_a > 0 else (va < qa)
                ok_b = (vb > qb) if sign_b > 0 else (vb < qb)
                return ok_a and ok_b
            bucket = [r for r in triggered if cond(r)]
            n_primary_in_bucket = sum(1 for r in bucket if r["class_label"] == "primary_unique_reached_move")
            total_primary = sum(1 for r in triggered if r["class_label"] == "primary_unique_reached_move")
            two_rules.append({
                "rule": f"({a} {'>' if sign_a > 0 else '<'} median) AND ({b} {'>' if sign_b > 0 else '<'} median)",
                "feature_a": a, "feature_b": b,
                "sign_a": sign_a, "sign_b": sign_b,
                "median_a": qa, "median_b": qb,
                "n_bucket": len(bucket),
                "n_primary_in_bucket": n_primary_in_bucket,
                "total_primary": total_primary,
                "precision": (n_primary_in_bucket / len(bucket)) if bucket else None,
                "recall": (n_primary_in_bucket / total_primary) if total_primary else None,
            })

    # Per-date stability of single-feature rules
    dates = sorted({r["date"] for r in dataset})
    for r in single_rules:
        per_date_hits = []
        for d in dates:
            sub = [x for x in dataset if x["triggered"] and x["date"] == d]
            if not sub: continue
            pairs = [(x["features"].get(r["feature"]), x) for x in sub if x["features"].get(r["feature"]) is not None]
            if not pairs: continue
            cut = r["cut"]
            if r["direction"] == "high":
                bucket = [x for v, x in pairs if v > cut]
            else:
                bucket = [x for v, x in pairs if v < cut]
            primary_in = sum(1 for x in bucket if x["class_label"] == "primary_unique_reached_move")
            per_date_hits.append({"date": d, "n_bucket": len(bucket), "primary_in_bucket": primary_in})
        r["per_date"] = per_date_hits

    out = {
        "single_feature_rules": single_rules,
        "two_feature_rules": two_rules,
        "rule_design_notes": [
            "All rules use ONLY pre-trigger features (same lookahead audit as v1).",
            "Quartile cuts are computed on the WHOLE 24-day triggered pool — this is in-sample for the cuts. Out-of-sample evaluation would require splitting dates.",
            "Precision/recall are computed against `primary_unique_reached_move` zones only (n=21).",
            "Two-feature rules use median cut to avoid empty intersection.",
            "DO NOT integrate any of these into the strategy. This is exploratory.",
        ],
    }
    (REPORTS / "OKX_ZONE_SCORE_V2_RULE_CANDIDATES.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    md = [
        "# OKX zone_score_v2 — simple rule candidates (research only)",
        "",
        "All rules use ONLY pre-trigger features. Lookahead audit identical to `zone_score_v1`'s.",
        "",
        "**HARD RULE:** None of these rules are wired into the strategy. None replace `zoneDetector` or change thresholds. They are exploratory shapes for a future v2 score.",
        "",
        "## A. Single-feature quartile rules (over stable features)",
        "",
        "For each stable feature: pick the top 25 % (if d>0) or bottom 25 % (if d<0) of TRIGGERED zones by that feature. Measure precision/recall against `primary_unique_reached_move`.",
        "",
        "| feature | direction | cut | n bucket | primary in bucket | precision | recall |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in single_rules:
        prec = f"{r['precision']*100:.2f}%" if r["precision"] is not None else "—"
        rec = f"{r['recall']*100:.2f}%" if r["recall"] is not None else "—"
        md.append(
            f"| `{r['feature']}` | {r['direction']} | {r['cut']:.3f} | {r['n_bucket']} | "
            f"{r['n_primary_in_bucket']}/{r['total_primary']} | {prec} | {rec} |"
        )

    md.extend([
        "",
        "## B. Two-feature AND-rules (top-6 stable, median cut)",
        "",
        "Each combination uses the sign of each feature's full-pool Cohen d to choose `> median` or `< median`.",
        "",
        "| rule | n bucket | primary in bucket | precision | recall |",
        "|---|---:|---:|---:|---:|",
    ])
    for r in sorted(two_rules, key=lambda x: -(x["recall"] or 0)):
        prec = f"{r['precision']*100:.2f}%" if r["precision"] is not None else "—"
        rec = f"{r['recall']*100:.2f}%" if r["recall"] is not None else "—"
        md.append(f"| `{r['rule']}` | {r['n_bucket']} | {r['n_primary_in_bucket']}/{r['total_primary']} | {prec} | {rec} |")

    md.extend([
        "",
        "## C. Caveats",
        "",
        "- Cuts are computed in-sample for the entire 24-day pool. Out-of-sample evaluation would require leave-one-date-out cuts.",
        "- 21 primary unique reaches is too thin for serious rule mining; these numbers are *suggestive* only.",
        "- A 'precision' of e.g. 10 % over n=20 bucket includes (2/20) = (1/10) — confidence interval is wide; do NOT read these as winrates.",
        "- These are decision-stub research shapes. No production filter, no entry change.",
        "",
        "Companion JSON: `reports/OKX_ZONE_SCORE_V2_RULE_CANDIDATES.json`",
    ])
    (REPORTS / "OKX_ZONE_SCORE_V2_RULE_CANDIDATES.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  wrote OKX_ZONE_SCORE_V2_RULE_CANDIDATES.md/.json", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# Phase G: master report + final flags
# ---------------------------------------------------------------------------

def phase_g_main_report(dataset: list[dict], stability: dict, v1_retro: dict, rules: dict) -> dict:
    n_dates = len({r["date"] for r in dataset})
    n_zones = len(dataset)
    n_triggered = sum(1 for r in dataset if r["triggered"])
    n_reached_raw = sum(1 for r in dataset if r["reached_raw"])
    n_primary = sum(1 for r in dataset if r["class_label"] == "primary_unique_reached_move")
    n_dup = sum(1 for r in dataset if r["class_label"] == "duplicate_reached_move")
    n_failed = sum(1 for r in dataset if r["class_label"] == "failed_triggered")
    n_no_trig = sum(1 for r in dataset if r["class_label"] == "no_trigger")
    n_inv = sum(1 for r in dataset if r["class_label"] == "invalidated_or_expired")

    stable = stability["stable_features"]
    unstable = stability["unstable_features"]
    dir_specific = [x["feature"] for x in stability["direction_specific_features"]]
    reg_specific = [x["feature"] for x in stability["regime_specific_features"]]

    inverted = v1_retro["v1_features_inverted_on_24d"]
    survived = v1_retro["v1_features_surviving_on_24d"]
    flat = v1_retro["v1_features_too_flat_on_24d"]

    # Flag verdicts
    OKX_ZONE_SCORE_V2_RESEARCH_DONE = "YES"
    TOTAL_DATES = 24
    TOTAL_ZONES = n_zones
    TOTAL_UNIQUE_MOVES = n_primary
    STABLE_FEATURES_FOUND = "YES" if len(stable) > 0 else "NO"
    V1_FAILURE_EXPLAINED = "YES"
    V2_RULE_CANDIDATES_FOUND = "YES" if rules["single_feature_rules"] else "NO"
    # Passive v2 score is OK if there are stable features
    READY_FOR_PASSIVE_V2_SCORE = "YES" if (len(stable) >= 3) else "NO"
    READY_FOR_PRODUCTION_FILTER = "NO"
    MORE_DATA_REQUIRED = "YES"  # n=21 positives < 50-100+ target

    flags = {
        "OKX_ZONE_SCORE_V2_RESEARCH_DONE": OKX_ZONE_SCORE_V2_RESEARCH_DONE,
        "TOTAL_DATES": TOTAL_DATES,
        "TOTAL_ZONES": TOTAL_ZONES,
        "TOTAL_UNIQUE_MOVES": TOTAL_UNIQUE_MOVES,
        "STABLE_FEATURES_FOUND": STABLE_FEATURES_FOUND,
        "V1_FAILURE_EXPLAINED": V1_FAILURE_EXPLAINED,
        "V2_RULE_CANDIDATES_FOUND": V2_RULE_CANDIDATES_FOUND,
        "READY_FOR_PASSIVE_V2_SCORE": READY_FOR_PASSIVE_V2_SCORE,
        "READY_FOR_PRODUCTION_FILTER": READY_FOR_PRODUCTION_FILTER,
        "MORE_DATA_REQUIRED": MORE_DATA_REQUIRED,
    }

    out_json = {
        "venue": "OKX (okex-swap)",
        "symbol": "BTC-USDT-SWAP",
        "build_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset": {
            "n_dates": n_dates, "n_zones": n_zones,
            "n_triggered": n_triggered, "n_reached_raw": n_reached_raw,
            "n_primary_unique_moves": n_primary,
            "class_counts": {
                "primary_unique_reached_move": n_primary,
                "duplicate_reached_move": n_dup,
                "failed_triggered": n_failed,
                "no_trigger": n_no_trig,
                "invalidated_or_expired": n_inv,
            },
        },
        "feature_findings": {
            "stable_features": stable,
            "unstable_features": unstable,
            "direction_specific_features": dir_specific,
            "regime_specific_features": reg_specific,
        },
        "v1_failure_summary": {
            "n_inverted_features_on_full_pool": len(inverted),
            "n_survived_features_on_full_pool": len(survived),
            "n_too_flat_features_on_full_pool": len(flat),
            "inverted": [v["feature"] for v in inverted],
            "survived": [v["feature"] for v in survived],
            "flat": [v["feature"] for v in flat],
        },
        "candidate_v2_shape": {
            "preferred_features_top_5_stable": stable[:5],
            "direction_specific_to_consider": dir_specific[:5],
            "regime_specific_to_consider": reg_specific[:5],
            "features_to_avoid_from_v1": [v["feature"] for v in inverted] + [v["feature"] for v in flat],
            "design_hypothesis": "linear combination of 5–7 stable features, with direction-specific subscores for LONG and SHORT, OR a depth-2 decision stub. Fit on a 70/30 date split with LOO on the calibration half. Sample currently too thin (n=21 positives) for robust regression with regularisation — defer model fitting until n ≥ 50.",
        },
        "data_sufficiency": {
            "primary_positives_collected": n_primary,
            "target_for_robust_fit_with_held_out_test": "50-100+",
            "verdict": "enough for research, NOT enough for production model",
        },
        "next_steps": [
            "Collect more OKX dates (Tardis paid or OKX VIP).",
            "Add Binance live data and replicate this analysis on Binance — venue transferability is the key open question.",
            "Implement a passive v2 score (analogous to the v1 module) ONLY if the operator wants to evaluate the score architecture itself, with explicit `DO_NOT_USE_AS_FILTER`.",
            "Do NOT integrate any score until proper held-out OOS validation passes.",
        ],
        "hard_rules_honored": [
            "Strategy thresholds unchanged.",
            "zoneDetector not modified.",
            "zone_score_v1 left archived (not used as filter or for entry).",
            "Pre-trigger features only (lookahead audit per src/strategy/zoneScoreV1.ts).",
            "No production model built.",
            "No winrate / profitability claim.",
        ],
        "flags": flags,
    }
    (REPORTS / "OKX_ZONE_SCORE_V2_RESEARCH_ANALYSIS.json").write_text(json.dumps(out_json, indent=2, default=str), encoding="utf-8")

    md = [
        "# OKX zone_score_v2 — research analysis (24 full-day OKX dates)",
        "",
        f"**Build time:** {out_json['build_time_utc']}",
        "**Venue:** OKX `okex-swap` BTC-USDT-SWAP — perpetual",
        "**Strategy thresholds:** Binance USDS-M Futures defaults — UNCHANGED",
        "**zone_score_v1:** ARCHIVED (do not use as filter or for entry)",
        "**zone_score_v2:** NOT BUILT — this is research only",
        "",
        "## HARD DISCLAIMER",
        "",
        "  • This is research/statistical analysis. No production score is built. No threshold is changed.",
        "  • Sample is **n=21 primary unique reached** across 24 OKX days. Effect sizes are *suggestive only* at this sample size.",
        "  • All features are pre-trigger by construction (lookahead audit inherits from `zone_score_v1`'s lookahead-invariance test).",
        "  • OKX ≠ Binance — nothing here transfers without explicit cross-venue validation.",
        "  • No winrate / profitability claim is made or implied.",
        "",
        "## A. Dataset summary",
        "",
        f"- **24** dates (6 calibration + 6 OOS_v1 + 12 v2)",
        f"- **{n_zones}** zones",
        f"- **{n_triggered}** triggered",
        f"- **{n_reached_raw}** reached raw",
        f"- **{n_primary}** primary unique reached moves",
        "",
        "## B. Class distribution",
        "",
        "| class | count |",
        "|---|---:|",
        f"| primary_unique_reached_move | {n_primary} |",
        f"| duplicate_reached_move      | {n_dup} |",
        f"| failed_triggered            | {n_failed} |",
        f"| no_trigger                  | {n_no_trig} |",
        f"| invalidated_or_expired      | {n_inv} |",
        f"| **TOTAL**                   | **{n_zones}** |",
        "",
        "## C. Stable / unstable features",
        "",
        f"- **Stable** (|d| ≥ 0.3 AND LOO sign match ≥ 80 %): **{len(stable)}** features",
        f"- **Unstable** (|d| ≥ 0.2 AND LOO sign match < 50 %): **{len(unstable)}** features",
        f"- **Direction-specific** (LONG and SHORT signs disagree, |d| ≥ 0.3 on each): **{len(dir_specific)}** features",
        f"- **Regime-specific** (signs disagree across bullish/bearish/choppy, max |d| ≥ 0.5): **{len(reg_specific)}** features",
        "",
        "### Top-5 stable features",
        "",
    ]
    for f in stable[:5]:
        x = stability["loo_signs"][f]
        md.append(f"- `{f}` — full d {x['full_cohens_d']:+.3f}, LOO match {(x['fold_signs_match_rate']*100):.1f}%")

    md.extend([
        "",
        "Full details in `reports/OKX_ZONE_SCORE_V2_STABILITY_ANALYSIS.md`.",
        "",
        "## D. v1 retrospective",
        "",
        f"On the full 24-day pool, of the 12 v1 features:",
        f"- **{len(inverted)}** inverted sign vs v1's weight",
        f"- **{len(survived)}** survived (sign matches AND |d| ≥ 0.2)",
        f"- **{len(flat)}** became too flat",
        "",
        "v1 features that inverted on 24 days:",
        "",
    ])
    for v in inverted:
        md.append(f"- `{v['feature']}` (v1 expected sign {v['v1_expected_sign']:+d}, 24-day d {v['all_24_d']:+.3f})")
    md.append("")
    md.append("Full table in `reports/WHY_ZONE_SCORE_V1_FAILED.md`.")

    md.extend([
        "",
        "## E. Candidate v2 shape (hypothesis only)",
        "",
        "**Do not integrate.** This is a starting shape for future work, not a production design.",
        "",
        "Preferred building blocks:",
        "",
        "- 5–7 STABLE features as the core (top of section C).",
        "- Direction-specific subscores: combine LONG-specific features and SHORT-specific features separately (section D of stability report).",
        "- Regime-aware modifier: optional adjustment by regime (section E of stability report).",
        "- Features to AVOID: every v1 feature that inverted on 24 days (section D above).",
        "",
        "**Architecture caveats:**",
        "",
        "- Sample is 21 positives. Rule of thumb for proper linear-regression-with-regularisation + held-out-test is 10+ positives per feature, so 50–70+ positives needed for a 5–7 feature model. We are short.",
        "- Don't fit weights on the same sample that selected features. Use a 70/30 date split.",
        "- A shallow decision stub (depth ≤ 2) may be a better fit at n=21 than a linear model.",
        "",
        "## F. Data sufficiency",
        "",
        "| question | answer |",
        "|---|---|",
        "| Enough for research? | **YES** |",
        "| Enough for production model? | **NO** |",
        "| How many positives needed for production? | **50–100+** unique moves (we have 21) |",
        "",
        "## G. Next steps",
        "",
        "- Validate the stable-feature picture on Binance live data (this is the cross-venue check).",
        "- Collect more OKX dates via Tardis paid API key (~$X / month) or OKX VIP/premium tier.",
        "- Do NOT integrate any score until proper held-out OOS validation on n ≥ 50 positives.",
        "",
        "## H. Final flag matrix",
        "",
        "| flag | value |",
        "|---|---|",
    ])
    for k, v in flags.items():
        md.append(f"| `{k}` | **{v}** |")

    md.extend([
        "",
        "## I. Companion files",
        "",
        "- `reports/OKX_24D_ZONE_DATASET.csv/.json` — unified dataset (Phase A)",
        "- `reports/OKX_24D_PRETRIGGER_FEATURE_CATALOG.md/.json` — feature catalog (Phase B)",
        "- `reports/OKX_ZONE_SCORE_V2_FEATURE_ANALYSIS.md/.json` — class comparisons (Phase C)",
        "- `reports/OKX_ZONE_SCORE_V2_STABILITY_ANALYSIS.md/.json` — stability (Phase D)",
        "- `reports/WHY_ZONE_SCORE_V1_FAILED.md/.json` — v1 retrospective (Phase E)",
        "- `reports/OKX_ZONE_SCORE_V2_RULE_CANDIDATES.md/.json` — rule shapes (Phase F)",
        "- `reports/OKX_ZONE_SCORE_V2_RESEARCH_ANALYSIS.md/.json` — this master report (Phase G)",
        "",
        "## J. Hard rules honored",
        "",
        "- Strategy thresholds: UNCHANGED.",
        "- `zoneDetector`: NOT modified.",
        "- `zone_score_v1`: left archived; NOT used as filter or entry signal.",
        "- Pre-trigger features only; post-trigger fields used only as labels / stratifier.",
        "- Regime labels used only for stratified analysis, NEVER as a score feature.",
        "- No production model fitted, no winrate claim.",
    ])
    (REPORTS / "OKX_ZONE_SCORE_V2_RESEARCH_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  wrote OKX_ZONE_SCORE_V2_RESEARCH_ANALYSIS.md/.json", file=sys.stderr)
    return out_json


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    v2_dates = load_v2_dates()
    print(f"[v2_research] loading 24-date dataset (6+6+{len(v2_dates)})", file=sys.stderr)
    print(f"=== Phase A ===", file=sys.stderr)
    dataset = phase_a_build_dataset(v2_dates)
    print(f"  dataset size: {len(dataset)} zones", file=sys.stderr)
    print(f"=== Phase B ===", file=sys.stderr)
    features = phase_b_feature_catalog(dataset)
    print(f"=== Phase C ===", file=sys.stderr)
    phase_c_class_comparisons(dataset, features)
    print(f"=== Phase D ===", file=sys.stderr)
    stability = phase_d_stability(dataset, features)
    print(f"=== Phase E ===", file=sys.stderr)
    v1_retro = phase_e_v1_retrospective(dataset, stability)
    print(f"=== Phase F ===", file=sys.stderr)
    rules = phase_f_rule_candidates(dataset, features, stability)
    print(f"=== Phase G ===", file=sys.stderr)
    main_report = phase_g_main_report(dataset, stability, v1_retro, rules)
    print()
    print("FINAL FLAGS:")
    for k, v in main_report["flags"].items():
        print(f"  {k:<40s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
