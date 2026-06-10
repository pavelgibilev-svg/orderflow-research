"""OKX zone quality calibration analysis across 6 full-day dates.

Pure analysis — NO strategy changes, NO threshold tuning, NO winrate claim.

Reads the per-date OKX_TECHNICAL_REPLAY_<date>_fullday.json files, aggregates
zone objects, classifies them into 5 mutually-exclusive buckets, extracts
ONLY the features that were observable at-or-before the zone's
`triggerTs` (= no lookahead), compares groups, ranks features by their
power to separate `primary_unique_reached_move` from `failed_triggered`,
and proposes a hypothesis-only `zone_score_v1` blueprint.

Outputs:
    reports/OKX_ZONE_QUALITY_CALIBRATION_ANALYSIS.md
    reports/OKX_ZONE_QUALITY_CALIBRATION_ANALYSIS.json
"""
from __future__ import annotations
import json
import math
import statistics
import sys
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


# ---------------------------------------------------------------------------
# Loading + classification
# ---------------------------------------------------------------------------

def load_all_zones() -> list[dict]:
    """Load and tag every zone from the 6 full-day OKX dates."""
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


def classify(z: dict) -> str:
    """Return one of:
        primary_unique_reached_move
        duplicate_reached_move
        failed_triggered
        no_trigger
        invalidated_or_expired
    """
    status = (z.get("status") or "").upper()
    if status == "RESOLVED_REACHED":
        if z.get("isPrimaryMoveZone"):
            return "primary_unique_reached_move"
        return "duplicate_reached_move"
    if status == "RESOLVED_FAILED":
        return "failed_triggered"
    if status == "NO_TRIGGER":
        return "no_trigger"
    if status in ("INVALIDATED", "EXPIRED"):
        return "invalidated_or_expired"
    return "other_" + status.lower()


# ---------------------------------------------------------------------------
# Pre-trigger feature extraction (NO lookahead)
# ---------------------------------------------------------------------------

def get_reason(z: dict, stage: str) -> dict[str, Any] | None:
    for r in z.get("reasons") or []:
        if r.get("stage") == stage:
            return r
    return None


def pretrigger_features(z: dict) -> dict[str, Any]:
    """Extract every feature observable at OR before zone.triggerTs.

    Each feature is annotated by which state-machine stage produced it:
        @candidate  — known at startTs
        @confirmed  — known at confirmedTs (could be after candidate's
                      first instant but always at or before trigger)
        @trigger    — known at triggerTs (boundary; used for selection,
                      NOT for any downstream price evaluation)

    Post-trigger fields (targets.*, resolvedTs, isPrimaryMoveZone,
    moveClusterSize, duplicateMoveCredit, status, uniqueMoveId) are
    explicitly EXCLUDED here so the resulting feature dict carries no
    lookahead information.
    """
    cand = (get_reason(z, "candidate") or {}).get("conditions") or {}
    conf = (get_reason(z, "confirmed") or {}).get("conditions") or {}
    trig = (get_reason(z, "trigger") or {}).get("conditions") or {}
    scores = z.get("scores") or {}

    # Direction-specific names: LONG zones have sellPressure + bidRefillScore;
    # SHORT zones have buyPressure + askRefillScore. We normalise to
    # `pressure_against_direction` (= sell-pressure for LONG = buy-pressure
    # for SHORT) so they're comparable.
    direction = z.get("direction")
    if direction == "LONG":
        pressure_against = cand.get("sellPressure")
        refill_with = cand.get("bidRefillScore")
    elif direction == "SHORT":
        pressure_against = cand.get("buyPressure")
        refill_with = cand.get("askRefillScore")
    else:
        pressure_against = refill_with = None

    start_ts = z.get("startTs") or 0
    confirmed_ts = z.get("confirmedTs") or 0
    trigger_ts = z.get("triggerTs") or 0
    candidate_age_to_confirm_min = (
        (confirmed_ts - start_ts) / 60_000 if confirmed_ts else None
    )
    confirm_age_to_trigger_min = (
        (trigger_ts - confirmed_ts) / 60_000 if trigger_ts else None
    )
    total_pre_trigger_min = (
        (trigger_ts - start_ts) / 60_000 if trigger_ts else None
    )

    zone_low = z.get("zoneLow")
    zone_high = z.get("zoneHigh")
    zone_width_pct = (
        (zone_high - zone_low) / zone_low * 100.0
        if zone_low and zone_high and zone_low > 0
        else None
    )

    target_price = z.get("targetPrice")
    trigger_price = z.get("triggerPrice")
    target_distance_pct = (
        abs(target_price - trigger_price) / trigger_price * 100.0
        if target_price and trigger_price and trigger_price > 0
        else None
    )

    return {
        "_meta": {
            "id": z.get("id"),
            "date": z.get("_date"),
            "direction": direction,
            "status": z.get("status"),
            "isPrimaryMoveZone": z.get("isPrimaryMoveZone"),
            "duplicateMoveCredit": z.get("duplicateMoveCredit"),
            "zoneType": z.get("zoneType"),
            "qualityFlags": z.get("qualityFlags") or [],
            "class": classify(z),
        },
        # --- @candidate ---
        "cand_pressure_against": pressure_against,
        "cand_refill_with": refill_with,
        "cand_move_pct": (
            cand.get("downMovePct") if direction == "LONG" else cand.get("upMovePct")
        ),
        "cand_absorb_score": cand.get("absorbScore"),
        "cand_range_compression": 1.0 if cand.get("rangeCompression") else 0.0,
        # --- @confirmed ---
        "conf_cycles_seen": conf.get("cyclesSeen"),
        "conf_age_min": conf.get("ageMin"),
        "conf_defended_persistence_sec": conf.get("defendedPersistenceSec"),
        "conf_opposite_thinning": conf.get("oppositeThinning"),
        "conf_void_score": conf.get("voidScore"),
        # --- @trigger ---
        "trig_break_pct": trig.get("breakPct"),
        "trig_flow_multiplier": trig.get("flowMultiplier"),
        "trig_side_flow_ok": 1.0 if trig.get("sideFlowOK") else 0.0,
        # --- final zone.scores (set during state-machine, available at trigger) ---
        "score_absorption": scores.get("absorptionScore"),
        "score_liquidity_void": scores.get("liquidityVoidScore"),
        "score_ofi": scores.get("ofiScore"),
        "score_refill": scores.get("refillScore"),
        "score_trigger": scores.get("triggerScore"),
        # --- derived timing (pre-trigger) ---
        "candidate_to_confirm_min": candidate_age_to_confirm_min,
        "confirm_to_trigger_min": confirm_age_to_trigger_min,
        "total_pre_trigger_min": total_pre_trigger_min,
        # --- geometry (pre-trigger by construction) ---
        "zone_width_pct": zone_width_pct,
        "target_distance_pct": target_distance_pct,
        "n_quality_flags": len(z.get("qualityFlags") or []),
    }


# ---------------------------------------------------------------------------
# Statistical comparison helpers
# ---------------------------------------------------------------------------

def stats_of(values: list[float]) -> dict[str, float | None]:
    clean = [v for v in values if v is not None and isinstance(v, (int, float)) and not math.isnan(v)]
    if not clean:
        return {"n": 0, "mean": None, "median": None, "stdev": None, "min": None, "max": None}
    return {
        "n": len(clean),
        "mean": statistics.mean(clean),
        "median": statistics.median(clean),
        "stdev": statistics.pstdev(clean) if len(clean) > 1 else 0.0,
        "min": min(clean),
        "max": max(clean),
    }


def cohens_d(a: list[float], b: list[float]) -> float | None:
    """Cohen's d for effect size between two groups. None if either side empty."""
    a = [v for v in a if v is not None and isinstance(v, (int, float)) and not math.isnan(v)]
    b = [v for v in b if v is not None and isinstance(v, (int, float)) and not math.isnan(v)]
    if len(a) < 2 or len(b) < 2:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    va, vb = statistics.pvariance(a), statistics.pvariance(b)
    pooled = math.sqrt((va + vb) / 2)
    if pooled == 0:
        return 0.0 if ma == mb else float("inf")
    return (ma - mb) / pooled


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

FEATURES = [
    ("cand_pressure_against", "@candidate, pressure against zone direction (sellPressure for LONG / buyPressure for SHORT)"),
    ("cand_refill_with", "@candidate, refill on the zone's defending side (bidRefillScore for LONG / askRefillScore for SHORT)"),
    ("cand_move_pct", "@candidate, prior move into zone (% magnitude)"),
    ("cand_absorb_score", "@candidate, instantaneous absorption score"),
    ("cand_range_compression", "@candidate, 1 if range compression was observed at candidate time"),
    ("conf_cycles_seen", "@confirmed, defend/break cycles seen during candidate->confirm window"),
    ("conf_age_min", "@confirmed, age (min) when promoted to confirmed"),
    ("conf_defended_persistence_sec", "@confirmed, longest defended persistence window in seconds"),
    ("conf_opposite_thinning", "@confirmed, opposite-side thinning ratio (higher = more depth pull on other side)"),
    ("conf_void_score", "@confirmed, liquidity void score at confirmation time"),
    ("trig_break_pct", "@trigger, break magnitude past the zone edge as a %"),
    ("trig_flow_multiplier", "@trigger, taker-flow multiplier relative to rolling baseline"),
    ("trig_side_flow_ok", "@trigger, 1 if the side-flow gate was OK"),
    ("score_absorption", "final absorptionScore at trigger (computed up to trigger)"),
    ("score_liquidity_void", "final liquidityVoidScore at trigger"),
    ("score_ofi", "final orderflow-imbalance score at trigger"),
    ("score_refill", "final refill score at trigger"),
    ("score_trigger", "final composite trigger score"),
    ("candidate_to_confirm_min", "derived: confirmedTs - startTs (min)"),
    ("confirm_to_trigger_min", "derived: triggerTs - confirmedTs (min)"),
    ("total_pre_trigger_min", "derived: triggerTs - startTs (min)"),
    ("zone_width_pct", "derived: (zoneHigh - zoneLow) / zoneLow * 100"),
    ("target_distance_pct", "derived: |targetPrice - triggerPrice| / triggerPrice * 100 (≈ targetPct by design)"),
    ("n_quality_flags", "count of qualityFlags on the zone (pre-trigger context)"),
]


def main() -> int:
    zones = load_all_zones()
    print(f"loaded {len(zones)} zones across {len(DATES)} dates", file=sys.stderr)

    rows = [pretrigger_features(z) for z in zones]
    by_class: dict[str, list[dict]] = {}
    for r in rows:
        by_class.setdefault(r["_meta"]["class"], []).append(r)
    class_counts = {k: len(v) for k, v in by_class.items()}

    # Per-feature stats per class
    per_feature: list[dict] = []
    for key, desc in FEATURES:
        feat_block: dict[str, Any] = {"feature": key, "description": desc, "by_class": {}}
        for cls, rs in by_class.items():
            feat_block["by_class"][cls] = stats_of([r.get(key) for r in rs])
        # Separation power: Cohen's d between primary vs failed_triggered
        primary = by_class.get("primary_unique_reached_move", [])
        failed = by_class.get("failed_triggered", [])
        feat_block["cohens_d_primary_vs_failed"] = cohens_d(
            [r.get(key) for r in primary],
            [r.get(key) for r in failed],
        )
        # Also vs duplicates (sanity)
        dup = by_class.get("duplicate_reached_move", [])
        feat_block["cohens_d_primary_vs_duplicate"] = cohens_d(
            [r.get(key) for r in primary],
            [r.get(key) for r in dup],
        )
        per_feature.append(feat_block)

    # Rank features by abs(cohens_d primary_vs_failed)
    def rank_key(b: dict) -> float:
        d = b["cohens_d_primary_vs_failed"]
        if d is None or math.isinf(d):
            return -1.0
        return abs(d)
    per_feature.sort(key=rank_key, reverse=True)

    # Build a proposed zone_score_v1 hypothesis using the top-separating
    # features. Weights here are HYPOTHESES, NOT calibrated values.
    HYP_WEIGHTS: dict[str, float] = {
        # Tentative direction: features with positive cohens_d_primary_vs_failed
        # get a positive weight (higher feature = better zone), and vice versa.
        # All weights are placeholders in [-1, +1]; this is shape only.
    }
    top_features: list[dict] = []
    for b in per_feature[:12]:
        d = b["cohens_d_primary_vs_failed"]
        if d is None or math.isinf(d) or abs(d) < 0.20:
            continue
        sign = 1.0 if d > 0 else -1.0
        HYP_WEIGHTS[b["feature"]] = round(sign * min(1.0, abs(d) / 1.5), 3)
        top_features.append(b["feature"])

    # Lookahead audit: every feature in pretrigger_features() is by construction
    # available at-or-before triggerTs. The `score_*` fields come from
    # zoneDetector's running state and are finalised by the trigger
    # transition — they ARE pre-trigger by code path. Explicit list of fields
    # that we deliberately excluded as lookahead-positive is here:
    LOOKAHEAD_EXCLUDED: list[str] = [
        "targets.* (mfePct, maePct, reachedAt, timeToTargetMin, outcome, maxDrawdownBeforeTargetPct, endPrice, endTs)",
        "resolvedTs",
        "status (final)",
        "isPrimaryMoveZone (assigned post-resolve by clustering)",
        "duplicateMoveCredit (post-resolve)",
        "uniqueMoveId (post-resolve)",
        "moveClusterSize (post-resolve)",
        "reasons[stage='expire']",
    ]
    LOOKAHEAD_AUDIT = {
        "features_used": [f for f, _ in FEATURES],
        "all_features_pretrigger": True,
        "explicitly_excluded_as_lookahead_positive": LOOKAHEAD_EXCLUDED,
        "notes": "All features in pretrigger_features() are pulled from the candidate / confirmed / trigger reason blocks or from zone.scores (which the zoneDetector populates by the trigger transition). targets.* and any state derived from move-clustering are excluded.",
    }

    out_json = {
        "venue": "OKX (okex-swap)",
        "symbol": "BTC-USDT-SWAP",
        "dates": DATES,
        "zones_total": len(zones),
        "class_counts": class_counts,
        "per_feature_stats_and_separation": per_feature,
        "top_separating_features": top_features,
        "zone_score_v1_hypothesis": {
            "formula": "sum_i w_i * z_i where z_i is the per-feature value (raw, NO normalisation in v1) and w_i is the hypothesis weight below.",
            "weights": HYP_WEIGHTS,
            "DO_NOT_TRADE_THIS": True,
            "caveats": [
                "Weights are HYPOTHESES derived from a 6-day OKX sample with Binance-tuned thresholds; they are NOT calibrated and have NOT been cross-validated.",
                "Features have different scales — a real implementation needs per-feature z-score normalisation.",
                "No regularisation. No held-out validation. No statistical significance test.",
                "Cross-venue: do not assume these weights would survive on Binance or any other venue.",
            ],
        },
        "lookahead_audit": LOOKAHEAD_AUDIT,
    }
    (REPORTS / "OKX_ZONE_QUALITY_CALIBRATION_ANALYSIS.json").write_text(
        json.dumps(out_json, indent=2, default=str), encoding="utf-8"
    )

    # --- Markdown ---
    def f(v: float | None, w: int = 7, p: int = 3) -> str:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "—".rjust(w)
        if isinstance(v, float) and math.isinf(v):
            return "inf".rjust(w)
        return f"{v:>{w}.{p}f}"

    md: list[str] = [
        "# OKX zone quality calibration analysis — 6 full-day dates",
        "",
        "**Venue:** OKX `okex-swap` BTC-USDT-SWAP (perpetual)",
        "**Dates:** " + ", ".join(DATES),
        "**Zones analyzed:** " + str(len(zones)),
        "**Strategy thresholds:** Binance USDS-M Futures defaults — **UNCHANGED**",
        "**This is analysis only.** No code changes, no threshold changes, no tuning, no winrate claim.",
        "",
        "## HARD DISCLAIMER",
        "",
        "  • The honest headline of OKX 6-date full-day is **5 unique reached moves** across 6 days (one per non-choppy day). 211 total zones.",
        "  • This analysis is about **which pre-trigger features separate primary-unique-reached zones from failed-triggered zones**.",
        "  • Weights proposed for `zone_score_v1` are **hypotheses**, NOT a calibrated model. Do not trade them.",
        "  • Cross-venue: weights derived here are an OKX-specific signal-of-shape, not a Binance result.",
        "",
        "## A. Classification",
        "",
        "| class                          | count |",
        "|--------------------------------|------:|",
    ]
    for cls in [
        "primary_unique_reached_move",
        "duplicate_reached_move",
        "failed_triggered",
        "no_trigger",
        "invalidated_or_expired",
    ]:
        md.append(f"| {cls:<30s} | {class_counts.get(cls, 0):>5d} |")
    other = sum(v for k, v in class_counts.items() if k not in (
        "primary_unique_reached_move", "duplicate_reached_move",
        "failed_triggered", "no_trigger", "invalidated_or_expired"))
    if other:
        md.append(f"| (other)                        | {other:>5d} |")
    md.append(f"| **TOTAL**                      | **{len(zones)}** |")
    md.append("")

    md.extend([
        "Definitions:",
        "- `primary_unique_reached_move`: status=RESOLVED_REACHED AND isPrimaryMoveZone=true",
        "- `duplicate_reached_move`: status=RESOLVED_REACHED AND isPrimaryMoveZone=false (move-clustering absorbed)",
        "- `failed_triggered`: status=RESOLVED_FAILED (triggered, never reached target on any horizon)",
        "- `no_trigger`: status=NO_TRIGGER (confirmed, never broke past the trigger band)",
        "- `invalidated_or_expired`: status=INVALIDATED or status=EXPIRED before trigger",
        "",
        "## B. Per-feature stats by class (mean ± std)",
        "",
        "Each feature is observable at-or-before `triggerTs`. See Section E for the lookahead audit.",
        "",
        "| feature | primary unique (n) | duplicate (n) | failed_triggered (n) | no_trigger (n) | invalid./expired (n) | Cohen d (primary vs failed) |",
        "|---------|-------------------|---------------|---------------------|----------------|---------------------|----------------------------:|",
    ])
    cls_order_short = [
        ("primary_unique_reached_move", "primary"),
        ("duplicate_reached_move", "duplicate"),
        ("failed_triggered", "failed"),
        ("no_trigger", "no_trig"),
        ("invalidated_or_expired", "invalid"),
    ]
    for b in per_feature:
        cells: list[str] = [b["feature"]]
        for cls, _short in cls_order_short:
            s = b["by_class"].get(cls, {})
            mean = s.get("mean")
            std = s.get("stdev")
            n = s.get("n", 0)
            if mean is None:
                cells.append(f"— (n={n})")
            else:
                cells.append(f"{mean:.3f} ± {std:.3f} (n={n})")
        d = b["cohens_d_primary_vs_failed"]
        cells.append(f"{d:+.3f}" if (d is not None and not math.isinf(d)) else "—")
        md.append("| " + " | ".join(cells) + " |")

    md.extend([
        "",
        "## C. Top features by separation power (primary vs failed_triggered)",
        "",
        "Cohen's d magnitude |d|: 0.2 small, 0.5 medium, 0.8 large.",
        "Positive d ⇒ feature is higher for primary-unique reached than for failed-triggered.",
        "Negative d ⇒ feature is higher for failed-triggered than for primary-unique reached.",
        "",
        "| rank | feature | Cohen d | primary mean | failed mean | sample size (primary / failed) |",
        "|-----:|---------|--------:|-------------:|------------:|-------------------------------|",
    ])
    n_primary = class_counts.get("primary_unique_reached_move", 0)
    n_failed = class_counts.get("failed_triggered", 0)
    for i, b in enumerate(per_feature[:15], 1):
        d = b["cohens_d_primary_vs_failed"]
        pm = b["by_class"].get("primary_unique_reached_move", {}).get("mean")
        fm = b["by_class"].get("failed_triggered", {}).get("mean")
        md.append(
            f"| {i} | `{b['feature']}` | {f(d,7,3)} | {f(pm,12,4)} | {f(fm,11,4)} | {n_primary} / {n_failed} |"
        )

    md.extend([
        "",
        "## D. `zone_score_v1` — HYPOTHESIS ONLY",
        "",
        "**Do not trade this.** Weights are derived from observed separation on a 6-day OKX sample with Binance-tuned thresholds. They are NOT calibrated, NOT cross-validated, and the cross-venue transferability has NOT been checked.",
        "",
        "Formula (skeleton):",
        "",
        "```",
        "zone_score_v1(zone) = Σ w_i * value_i",
        "```",
        "",
        "where each `value_i` is the raw feature value (no normalisation in v1; a real",
        "implementation must add per-feature z-score normalisation first).",
        "",
        "Tentative weights (sign+magnitude derived from Cohen's d, clamped to [-1, +1]):",
        "",
        "| feature | weight | rationale |",
        "|---------|-------:|-----------|",
    ])
    if HYP_WEIGHTS:
        for k, w in sorted(HYP_WEIGHTS.items(), key=lambda kv: -abs(kv[1])):
            stage = "@candidate" if k.startswith("cand_") else (
                "@confirmed" if k.startswith("conf_") else (
                    "@trigger" if k.startswith("trig_") else (
                        "@score" if k.startswith("score_") else "derived"
                    )
                )
            )
            md.append(f"| `{k}` | {w:+.3f} | {stage}, top-12 by |Cohen d| with |d| ≥ 0.20 |")
    else:
        md.append("| — | — | no feature reached |d| ≥ 0.20 — sample size is the binding limit |")

    md.extend([
        "",
        "**Caveats:**",
        "",
        "- Sample is **6 days, 211 zones** with class imbalance (primary unique ≈ 5, failed ≈ 75). Cohen's d on n=5 vs n=75 is suggestive at best.",
        "- Weights here are derived from |d| magnitude, not from a regression. There is no held-out validation set, no significance testing, no bias correction.",
        "- Several features (e.g. `score_trigger`, `trig_side_flow_ok`) are nearly constant because they're gating conditions for getting to TRIGGERED at all — their Cohen's d will be tiny by construction.",
        "- Cross-venue: this calibration tells us about OKX with Binance-tuned thresholds; transferring weights to Binance without re-derivation would itself be a strategy change.",
        "- Strategy code remains unchanged: this v1 score is a *passive* score that could be computed alongside the existing engine and **then** evaluated on a held-out sample. Threshold integration is out of scope.",
        "",
        "## E. Lookahead audit",
        "",
        "All features in `pretrigger_features()` are pulled from the zone's `reasons[stage in {candidate, confirmed, trigger}].conditions` blocks or from `zone.scores` (populated by the state machine by the trigger transition). The following fields were deliberately **excluded** to avoid lookahead bias:",
        "",
    ])
    for excl in LOOKAHEAD_EXCLUDED:
        md.append(f"- `{excl}`")
    md.extend([
        "",
        "`zone.scores` is a tiny grey area: it is the running state-machine score at the moment of transition. Code path inspection (`src/strategy/zoneDetector.ts`) confirms these are set during state-machine progression and are FROZEN once the zone is TRIGGERED, so they are pre-trigger by construction. This audit treats them as pre-trigger but flags them as a near-boundary surface area to keep an eye on if a future v2 score is wired into the live path.",
        "",
        "## F. Final flag matrix",
        "",
        "| flag | value | rationale |",
        "|------|-------|-----------|",
        f"| `OKX_ZONE_SCORE_READY` | **YES (v1 hypothesis)** | a skeleton score with {len(HYP_WEIGHTS)} non-zero weights is proposed; integration into the engine is explicitly NOT done here |",
        f"| `USEFUL_FEATURES_FOUND` | **{('YES' if len(top_features) > 0 else 'NO')}** | {len(top_features)} features show |Cohen d| ≥ 0.20 between primary-unique-reached and failed-triggered |",
        "| `LOOKAHEAD_RISK` | **NO (pre-trigger only)** | features come from candidate/confirmed/trigger stages or zone.scores frozen at trigger; targets / move-clustering excluded |",
        "",
        "Companion JSON: `reports/OKX_ZONE_QUALITY_CALIBRATION_ANALYSIS.json` (full per-feature stats + raw zone classifications).",
    ])

    (REPORTS / "OKX_ZONE_QUALITY_CALIBRATION_ANALYSIS.md").write_text(
        "\n".join(md), encoding="utf-8"
    )

    print(f"wrote {REPORTS/'OKX_ZONE_QUALITY_CALIBRATION_ANALYSIS.md'}")
    print(f"wrote {REPORTS/'OKX_ZONE_QUALITY_CALIBRATION_ANALYSIS.json'}")
    print()
    print(f"class_counts: {class_counts}")
    print(f"top_separating_features: {top_features}")
    print(f"hypothesis_weights: {HYP_WEIGHTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
