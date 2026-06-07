// Tests for src/strategy/zoneScoreV1.ts — the passive observational metric.
//
// Hard guarantees this test file enforces:
//   1. The score is a pure function — no Zone mutation.
//   2. NO lookahead: forbidden post-trigger fields can be set to any value
//      and the score does not change.
//   3. Pre-trigger feature extraction matches what the calibration analyser
//      computes (see scripts/okx/zone_quality_analysis.py).
//   4. Direction-aware extraction works for both LONG and SHORT.
//   5. raw/z/bucket arithmetic is correct.

import { describe, expect, it } from "vitest";
import {
  ZONE_SCORE_V1_FEATURES,
  ZONE_SCORE_V1_WEIGHTS,
  ZONE_SCORE_V1_FORBIDDEN_ZONE_KEYS,
  computeZoneScoreV1,
  extractPreTriggerFeatures,
  type ZoneScoreV1Stats,
} from "../src/strategy/zoneScoreV1.js";
import type { Zone } from "../src/strategy/types.js";

// ---------------------------------------------------------------------------
// Fixture: a zone shaped like the OKX 2024-01-01 first reached zone.
// ---------------------------------------------------------------------------

function longFixture(): Zone {
  return {
    id: "BTC-USDT-SWAP-LONG-1704067235000-1",
    symbol: "BTC-USDT-SWAP",
    date: "2024-01-01",
    direction: "LONG",
    zoneType: "ACCUMULATION",
    status: "RESOLVED_REACHED",
    startTs: 1704067235000,
    confirmedTs: 1704067851000,
    triggerTs: 1704067897000,
    resolvedTs: 1704137370507,
    zoneLow: 42277.9,
    zoneHigh: 42447.95,
    triggerPrice: 42477.25,
    referencePrice: 42477.25,
    targetPrice: 43326.795,
    scores: {
      absorptionScore: 0.6016,
      liquidityVoidScore: 1.0,
      ofiScore: -0.077,
      triggerScore: 1.0,
      refillScore: 0.5002,
    },
    qualityFlags: [],
    targets: {
      "4h": { horizon: "4h", outcome: "failed_by_timeout", endPrice: 42350, endTs: 1704082297000, mfePct: 0.77, maePct: 0.6, maxDrawdownBeforeTargetPct: 0.6 },
      "8h": { horizon: "8h", outcome: "failed_by_timeout", endPrice: 42527.8, endTs: 1704096697000, mfePct: 0.77, maePct: 0.7, maxDrawdownBeforeTargetPct: 0.7 },
      "24h": { horizon: "24h", outcome: "reached", endPrice: 44220, endTs: 1704154297000, reachedAt: 1704137370507, timeToTargetMin: 1157.89, mfePct: 4.18, maePct: 0.7, maxDrawdownBeforeTargetPct: 0.7 },
    },
    reasons: [
      {
        stage: "candidate",
        ts: 1704067235000,
        conditions: {
          sellPressure: 0.5503,
          bidRefillScore: 0.5008,
          downMovePct: 0,
          absorbScore: 0.6054,
          rangeCompression: true,
        },
      },
      {
        stage: "confirmed",
        ts: 1704067851000,
        conditions: {
          cyclesSeen: 6,
          ageMin: 10.27,
          defendedPersistenceSec: 616,
          oppositeThinning: 0.4994,
          voidScore: 1,
        },
      },
      {
        stage: "trigger",
        ts: 1704067897000,
        conditions: {
          breakPct: 0.069,
          flowMultiplier: 9.17,
          sideFlowOK: true,
          triggerPrice: 42477.25,
          targetPrice: 43326.795,
        },
      },
      {
        stage: "expire",
        ts: 1704137370507,
        conditions: { earliestReachedHorizon: "24h", targetPrice: 43326.795 },
      },
    ],
    uniqueMoveId: 1,
    moveClusterSize: 13,
    isPrimaryMoveZone: true,
    duplicateMoveCredit: false,
  };
}

function shortFixture(): Zone {
  const z = longFixture();
  z.id = "BTC-USDT-SWAP-SHORT-test";
  z.direction = "SHORT";
  z.zoneType = "DISTRIBUTION";
  z.reasons[0].conditions = {
    buyPressure: 0.6,
    askRefillScore: 0.49,
    upMovePct: 0,
    absorbScore: 0.7,
    rangeCompression: true,
  };
  return z;
}

const FIXTURE_STATS: ZoneScoreV1Stats = {
  fitted_at_iso: "2026-05-17T00:00:00Z",
  source: "test-fixture",
  features: {
    cand_pressure_against: { mean: 0.595, std: 0.04, n: 211 },
    cand_absorb_score: { mean: 0.645, std: 0.04, n: 211 },
    cand_refill_with: { mean: 0.5003, std: 0.001, n: 211 },
    conf_cycles_seen: { mean: 60, std: 50, n: 211 },
    conf_age_min: { mean: 12, std: 12, n: 211 },
    conf_defended_persistence_sec: { mean: 700, std: 600, n: 211 },
    candidate_to_confirm_min: { mean: 12, std: 12, n: 211 },
    confirm_to_trigger_min: { mean: 60, std: 100, n: 117 },
    total_pre_trigger_min: { mean: 75, std: 110, n: 117 },
    trig_flow_multiplier: { mean: 2.1, std: 1.3, n: 117 },
    trig_break_pct: { mean: 0.21, std: 0.19, n: 117 },
    score_absorption: { mean: 0.645, std: 0.045, n: 211 },
  },
  z_bucket_cuts: { low_below: -0.5, high_above: 0.5 },
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("zoneScoreV1: pre-trigger feature extraction", () => {
  it("extracts 12 features for a LONG zone", () => {
    const z = longFixture();
    const f = extractPreTriggerFeatures(z);
    expect(Object.keys(f).sort()).toEqual([...ZONE_SCORE_V1_FEATURES].sort());
    expect(f.cand_pressure_against).toBeCloseTo(0.5503);
    expect(f.cand_refill_with).toBeCloseTo(0.5008);
    expect(f.cand_absorb_score).toBeCloseTo(0.6054);
    expect(f.conf_cycles_seen).toBe(6);
    expect(f.conf_age_min).toBeCloseTo(10.27);
    expect(f.conf_defended_persistence_sec).toBe(616);
    expect(f.candidate_to_confirm_min).toBeCloseTo((1704067851000 - 1704067235000) / 60_000);
    expect(f.confirm_to_trigger_min).toBeCloseTo((1704067897000 - 1704067851000) / 60_000);
    expect(f.total_pre_trigger_min).toBeCloseTo((1704067897000 - 1704067235000) / 60_000);
    expect(f.trig_flow_multiplier).toBeCloseTo(9.17);
    expect(f.trig_break_pct).toBeCloseTo(0.069);
    expect(f.score_absorption).toBeCloseTo(0.6016);
  });

  it("uses buyPressure / askRefillScore for SHORT direction", () => {
    const z = shortFixture();
    const f = extractPreTriggerFeatures(z);
    expect(f.cand_pressure_against).toBeCloseTo(0.6);
    expect(f.cand_refill_with).toBeCloseTo(0.49);
  });

  it("returns undefined for missing pre-trigger reasons", () => {
    const z = longFixture();
    z.reasons = z.reasons.filter((r) => r.stage !== "trigger");
    delete z.triggerTs;
    const f = extractPreTriggerFeatures(z);
    expect(f.trig_flow_multiplier).toBeUndefined();
    expect(f.trig_break_pct).toBeUndefined();
    expect(f.confirm_to_trigger_min).toBeUndefined();
    expect(f.total_pre_trigger_min).toBeUndefined();
    // But candidate/confirmed-stage features stay valid:
    expect(f.cand_pressure_against).toBeCloseTo(0.5503);
    expect(f.conf_cycles_seen).toBe(6);
  });
});

describe("zoneScoreV1: NO lookahead", () => {
  // The whole point of these tests: prove that mutating any post-trigger
  // field on the zone object does NOT change the score. If a future change
  // accidentally peeks at zone.targets / zone.status / etc., these tests
  // will fail.
  it("score is invariant under mutation of forbidden post-trigger fields", () => {
    const z = longFixture();
    const before = computeZoneScoreV1(z, FIXTURE_STATS);

    // Mutate every forbidden field to obviously different values
    const mutated = JSON.parse(JSON.stringify(z)) as Zone;
    mutated.targets = {
      "4h": { horizon: "4h", outcome: "reached", reachedAt: 999, timeToTargetMin: 1, mfePct: 99, maePct: 99, endPrice: 99, endTs: 99, maxDrawdownBeforeTargetPct: 99 },
      "8h": { horizon: "8h", outcome: "reached", mfePct: 99, maePct: 99 },
      "24h": { horizon: "24h", outcome: "reached", mfePct: 99, maePct: 99 },
    };
    mutated.resolvedTs = 999999999999;
    mutated.status = "RESOLVED_FAILED";
    mutated.uniqueMoveId = 42;
    mutated.moveClusterSize = 42;
    mutated.isPrimaryMoveZone = false;
    mutated.duplicateMoveCredit = true;
    // Also remove the "expire" reason — it's post-trigger by stage name and
    // must not influence the score.
    mutated.reasons = mutated.reasons.filter((r) => r.stage !== "expire");

    const after = computeZoneScoreV1(mutated, FIXTURE_STATS);
    expect(after.raw).toBe(before.raw);
    expect(after.z).toBe(before.z);
    expect(after.bucket).toBe(before.bucket);
    expect(after.coverage).toBe(before.coverage);
  });

  it("forbidden field list is non-empty and matches Zone keys", () => {
    expect(ZONE_SCORE_V1_FORBIDDEN_ZONE_KEYS.length).toBeGreaterThan(0);
    const z = longFixture();
    for (const k of ZONE_SCORE_V1_FORBIDDEN_ZONE_KEYS) {
      expect(k in z).toBe(true);
    }
  });
});

describe("zoneScoreV1: raw / z / bucket arithmetic", () => {
  it("raw equals Σ w_i * feature_i over present features", () => {
    const z = longFixture();
    const r = computeZoneScoreV1(z);
    const f = extractPreTriggerFeatures(z);
    let expected = 0;
    for (const k of ZONE_SCORE_V1_FEATURES) {
      const v = f[k];
      if (v !== undefined) expected += ZONE_SCORE_V1_WEIGHTS[k] * v;
    }
    expect(r.raw).toBeCloseTo(expected, 6);
    expect(r.z).toBeNull();   // no stats passed
    expect(r.bucket).toBeNull();
  });

  it("z is computed when stats are provided", () => {
    const z = longFixture();
    const r = computeZoneScoreV1(z, FIXTURE_STATS);
    expect(r.z).not.toBeNull();
    expect(["low", "mid", "high"]).toContain(r.bucket);
  });

  it("coverage reflects fraction of present features", () => {
    const z = longFixture();
    const r = computeZoneScoreV1(z);
    expect(r.coverage).toBe(1.0);

    // Drop the trigger stage -> coverage should drop
    z.reasons = z.reasons.filter((r) => r.stage !== "trigger");
    delete z.triggerTs;
    const r2 = computeZoneScoreV1(z);
    expect(r2.coverage).toBeLessThan(1.0);
  });
});

describe("zoneScoreV1: pure function", () => {
  it("does not mutate the zone object", () => {
    const z = longFixture();
    const snapshot = JSON.parse(JSON.stringify(z));
    computeZoneScoreV1(z, FIXTURE_STATS);
    expect(z).toEqual(snapshot);
  });
});

describe("zoneScoreV1: weights are frozen", () => {
  it("all 12 weights are present, finite, in [-1, +1]", () => {
    for (const k of ZONE_SCORE_V1_FEATURES) {
      const w = ZONE_SCORE_V1_WEIGHTS[k];
      expect(typeof w).toBe("number");
      expect(Number.isFinite(w)).toBe(true);
      expect(Math.abs(w)).toBeLessThanOrEqual(1);
    }
  });

  it("weights object is frozen against tampering", () => {
    expect(Object.isFrozen(ZONE_SCORE_V1_WEIGHTS)).toBe(true);
  });
});
