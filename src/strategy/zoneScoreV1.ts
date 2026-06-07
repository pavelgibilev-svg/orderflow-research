// Passive zone_score_v1 — observational metric only.
//
// HARD RULES (enforced by code path + tests):
//   • Pure function: takes a Zone object, returns score components.
//   • Reads ONLY pre-trigger fields: zone.reasons[stage in {candidate, confirmed, trigger}]
//     conditions, and zone.scores (frozen at trigger transition).
//   • Reads NOTHING from zone.targets, zone.resolvedTs, zone.status (terminal),
//     zone.uniqueMoveId, zone.isPrimaryMoveZone, zone.moveClusterSize,
//     zone.duplicateMoveCredit.
//   • Does NOT mutate the zone.
//   • Does NOT filter zones, gate triggers, or change strategy behaviour.
//   • Weights are HYPOTHESIS-ONLY, derived from
//     reports/OKX_ZONE_QUALITY_CALIBRATION_ANALYSIS.json
//     on a 6-day OKX sample. NOT cross-validated. NOT calibrated for trading.
//
// Output shape:
//   {
//     features:    { ...12 named pre-trigger numbers, undefined if missing },
//     weights:     { ...same 12 keys, the hypothesis weights },
//     raw:         Σ w_i * feature_i  (no normalisation; dominated by big-scale features)
//     z:           Σ w_i * z_i        (where z_i = (feature_i - mean_i)/std_i; needs stats)
//     bucket:      "low" | "mid" | "high"  (by quantile thresholds on `z`)
//   }
//
// Stats config: see reports/zone_score_v1_stats.json (per-feature mean/std).

import type { Zone, ZoneReason } from "./types.js";

// ---------------------------------------------------------------------------
// Feature definitions
// ---------------------------------------------------------------------------

/** 12 pre-trigger features used by zone_score_v1.
 *  Order matters: it is the canonical iteration order for reports.
 */
export const ZONE_SCORE_V1_FEATURES = [
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
] as const;

export type ZoneScoreV1FeatureKey = (typeof ZONE_SCORE_V1_FEATURES)[number];

/** Hypothesis weights from OKX_ZONE_QUALITY_CALIBRATION_ANALYSIS (6 OKX dates).
 *  Sign = direction of separation between primary-unique-reached and
 *  failed-triggered. Magnitude = |Cohen's d| / 1.5, clamped to [-1, +1].
 *  These are SHAPE only — not calibrated, not cross-validated. */
export const ZONE_SCORE_V1_WEIGHTS: Readonly<Record<ZoneScoreV1FeatureKey, number>> = Object.freeze({
  cand_pressure_against: -0.572,
  cand_absorb_score: -0.561,
  cand_refill_with: +0.431,
  conf_cycles_seen: -0.537,
  conf_age_min: +0.338,
  conf_defended_persistence_sec: +0.338,
  candidate_to_confirm_min: +0.338,
  confirm_to_trigger_min: -0.427,
  total_pre_trigger_min: -0.380,
  trig_flow_multiplier: +0.392,
  trig_break_pct: -0.310,
  score_absorption: -0.322,
});

/** Per-feature mean/std for z-score normalisation.
 *  Loaded from reports/zone_score_v1_stats.json at run time.
 *  When absent or std==0, that feature contributes 0 to `z`. */
export interface ZoneScoreV1Stats {
  fitted_at_iso: string;
  source: string;
  features: {
    [K in ZoneScoreV1FeatureKey]: { mean: number; std: number; n: number };
  };
  /** Optional quantile cuts for the `bucket` label. If absent, fall back
   *  to fixed cuts at z < -0.5 / -0.5..+0.5 / > +0.5. */
  z_bucket_cuts?: { low_below: number; high_above: number };
}

// ---------------------------------------------------------------------------
// Pre-trigger feature extraction (NO lookahead, NO mutation)
// ---------------------------------------------------------------------------

function getReason(reasons: ReadonlyArray<ZoneReason>, stage: ZoneReason["stage"]): ZoneReason | undefined {
  for (const r of reasons) {
    if (r.stage === stage) return r;
  }
  return undefined;
}

function num(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

function boolToNum(v: unknown): number | undefined {
  if (v === true) return 1;
  if (v === false) return 0;
  return undefined;
}

/** Extract the 12 pre-trigger features from a zone. Every field is
 *  observable at or before zone.triggerTs by construction.
 *
 *  Returns `undefined` for a feature if its source datum is missing.
 *  Caller decides how to treat undefined (we skip such features when
 *  computing raw/z and report it as a coverage stat).
 */
export function extractPreTriggerFeatures(zone: Zone): Record<ZoneScoreV1FeatureKey, number | undefined> {
  const cand = getReason(zone.reasons, "candidate")?.conditions ?? {};
  const conf = getReason(zone.reasons, "confirmed")?.conditions ?? {};
  const trig = getReason(zone.reasons, "trigger")?.conditions ?? {};

  const direction = zone.direction;
  // LONG defends from BID side: pressure-against is sellPressure, refill on
  // defending side is bidRefillScore. SHORT mirrors it.
  const pressureAgainst =
    direction === "LONG" ? num(cand["sellPressure"]) : num(cand["buyPressure"]);
  const refillWith =
    direction === "LONG" ? num(cand["bidRefillScore"]) : num(cand["askRefillScore"]);

  const startTs = num(zone.startTs);
  const confirmedTs = num(zone.confirmedTs);
  const triggerTs = num(zone.triggerTs);
  const candidateToConfirmMin =
    startTs !== undefined && confirmedTs !== undefined ? (confirmedTs - startTs) / 60_000 : undefined;
  const confirmToTriggerMin =
    confirmedTs !== undefined && triggerTs !== undefined ? (triggerTs - confirmedTs) / 60_000 : undefined;
  const totalPreTriggerMin =
    startTs !== undefined && triggerTs !== undefined ? (triggerTs - startTs) / 60_000 : undefined;

  // Note: conf_age_min and candidate_to_confirm_min are intentionally the
  // same quantity. The calibration analysis ranked both in the top-12
  // independently; carrying both with their separate weights preserves
  // the analysis as-is. Tests assert they are always equal.
  const confAgeMin = num(conf["ageMin"]) ?? candidateToConfirmMin;
  const confDefendedPersistenceSec = num(conf["defendedPersistenceSec"]);
  const confCyclesSeen = num(conf["cyclesSeen"]);

  const trigFlowMultiplier = num(trig["flowMultiplier"]);
  const trigBreakPct = num(trig["breakPct"]);

  const candAbsorbScore = num(cand["absorbScore"]);
  const scoreAbsorption = num(zone.scores?.absorptionScore);

  return {
    cand_pressure_against: pressureAgainst,
    cand_absorb_score: candAbsorbScore,
    cand_refill_with: refillWith,
    conf_cycles_seen: confCyclesSeen,
    conf_age_min: confAgeMin,
    conf_defended_persistence_sec: confDefendedPersistenceSec,
    candidate_to_confirm_min: candidateToConfirmMin,
    confirm_to_trigger_min: confirmToTriggerMin,
    total_pre_trigger_min: totalPreTriggerMin,
    trig_flow_multiplier: trigFlowMultiplier,
    trig_break_pct: trigBreakPct,
    score_absorption: scoreAbsorption,
  };
}

// ---------------------------------------------------------------------------
// Score computation
// ---------------------------------------------------------------------------

export interface ZoneScoreV1Result {
  features: Record<ZoneScoreV1FeatureKey, number | undefined>;
  raw: number | null;
  /** z-normalised score; null if stats missing or zero coverage. */
  z: number | null;
  bucket: "low" | "mid" | "high" | null;
  /** Per-feature contribution to `raw` (w_i * feature_i) for audit. */
  components: Record<ZoneScoreV1FeatureKey, number | undefined>;
  /** Coverage = fraction of the 12 features that had a non-undefined value. */
  coverage: number;
}

/** Compute zone_score_v1 for a single zone.
 *
 *  - `raw` is Σ w_i * feature_i over features that were present.
 *  - `z`   is Σ w_i * z_i where z_i = (feature_i - mean_i)/std_i; null if
 *          stats argument is undefined or std == 0 for every present feature.
 *  - `bucket` is derived from `z` (NOT `raw`, since `raw` is dominated by
 *    large-scale features like total_pre_trigger_min).
 */
export function computeZoneScoreV1(
  zone: Zone,
  stats?: ZoneScoreV1Stats,
): ZoneScoreV1Result {
  const features = extractPreTriggerFeatures(zone);
  const components: Record<ZoneScoreV1FeatureKey, number | undefined> = {} as Record<
    ZoneScoreV1FeatureKey,
    number | undefined
  >;
  let rawSum = 0;
  let zSum = 0;
  let presentFeatureCount = 0;
  let zEligibleCount = 0;

  for (const key of ZONE_SCORE_V1_FEATURES) {
    const v = features[key];
    const w = ZONE_SCORE_V1_WEIGHTS[key];
    if (v === undefined) {
      components[key] = undefined;
      continue;
    }
    presentFeatureCount += 1;
    components[key] = w * v;
    rawSum += w * v;
    if (stats) {
      const s = stats.features?.[key];
      if (s && typeof s.std === "number" && s.std > 0) {
        zSum += w * ((v - s.mean) / s.std);
        zEligibleCount += 1;
      }
    }
  }

  const coverage = presentFeatureCount / ZONE_SCORE_V1_FEATURES.length;
  const raw = presentFeatureCount > 0 ? rawSum : null;
  const z = stats && zEligibleCount > 0 ? zSum : null;

  const lowCut = stats?.z_bucket_cuts?.low_below ?? -0.5;
  const highCut = stats?.z_bucket_cuts?.high_above ?? +0.5;
  let bucket: "low" | "mid" | "high" | null;
  if (z === null) {
    bucket = null;
  } else if (z < lowCut) {
    bucket = "low";
  } else if (z > highCut) {
    bucket = "high";
  } else {
    bucket = "mid";
  }

  return { features, raw, z, bucket, components, coverage };
}

// ---------------------------------------------------------------------------
// Self-audit helpers (used by tests)
// ---------------------------------------------------------------------------

/** List of zone object keys that ZoneScoreV1 must NEVER read, by hard
 *  rule. Tests prove the implementation does not touch these fields. */
export const ZONE_SCORE_V1_FORBIDDEN_ZONE_KEYS: ReadonlyArray<keyof Zone> = [
  "targets",
  "resolvedTs",
  "status",
  "uniqueMoveId",
  "moveClusterSize",
  "isPrimaryMoveZone",
  "duplicateMoveCredit",
];
