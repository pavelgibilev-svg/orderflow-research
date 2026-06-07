// Unique-move clustering tests.
//
// A. 4 reached SHORT zones whose [trigger, reachedAt] windows overlap → one uniqueMoveId.
// B. 2 reached zones same direction, separated by > moveClusterGapMinutes → two uniqueMoveIds.
// C. LONG and SHORT never cluster together.
// D. Primary zone = earliest triggerTs (composite-score breaks ties).
// E. Failed / no_trigger zones never receive duplicateMoveCredit / uniqueMoveId.
// F. (Implicit — old tests still pass.)

import { describe, expect, it } from "vitest";
import { applyMoveClustering } from "../src/strategy/uniqueMoveClustering.js";
import type { MoveClusteringConfig, Zone } from "../src/strategy/types.js";

function reachedZone(opts: {
  id: string;
  direction: "LONG" | "SHORT";
  triggerTs: number;
  reachedAt: number;
  triggerPrice?: number;
  targetPrice?: number;
  composite?: number;
}): Zone {
  return {
    id: opts.id,
    symbol: "BTCUSDT",
    date: "2026-02-01",
    direction: opts.direction,
    zoneType: opts.direction === "LONG" ? "ACCUMULATION" : "DISTRIBUTION",
    status: "RESOLVED_REACHED",
    startTs: opts.triggerTs - 10 * 60_000,
    confirmedTs: opts.triggerTs - 5 * 60_000,
    triggerTs: opts.triggerTs,
    resolvedTs: opts.reachedAt,
    zoneLow: (opts.triggerPrice ?? 100) - 1,
    zoneHigh: (opts.triggerPrice ?? 100) + 1,
    triggerPrice: opts.triggerPrice ?? 100,
    referencePrice: opts.triggerPrice ?? 100,
    targetPrice:
      opts.targetPrice ?? (opts.direction === "LONG" ? (opts.triggerPrice ?? 100) * 1.02 : (opts.triggerPrice ?? 100) * 0.98),
    scores: {
      absorptionScore: opts.composite ?? 0.5,
      liquidityVoidScore: opts.composite ?? 0.5,
      ofiScore: 0,
      triggerScore: opts.composite ?? 0.5,
    },
    qualityFlags: [],
    targets: {
      "4h": { horizon: "4h", outcome: "failed_by_timeout" },
      "8h": { horizon: "8h", outcome: "failed_by_timeout" },
      "24h": {
        horizon: "24h",
        outcome: "reached",
        reachedAt: opts.reachedAt,
        timeToTargetMin: (opts.reachedAt - opts.triggerTs) / 60_000,
      },
    },
    reasons: [],
  };
}

function nonReachedZone(opts: {
  id: string;
  direction: "LONG" | "SHORT";
  status: "RESOLVED_FAILED" | "NO_TRIGGER" | "INVALIDATED" | "EXPIRED";
  triggerTs?: number;
}): Zone {
  return {
    id: opts.id,
    symbol: "BTCUSDT",
    date: "2026-02-01",
    direction: opts.direction,
    zoneType: opts.direction === "LONG" ? "ACCUMULATION" : "DISTRIBUTION",
    status: opts.status,
    startTs: 1_000_000,
    triggerTs: opts.triggerTs,
    zoneLow: 99,
    zoneHigh: 101,
    scores: { absorptionScore: 0.5, liquidityVoidScore: 0.5, ofiScore: 0 },
    qualityFlags: [],
    targets: {},
    reasons: [],
  };
}

const cfg: MoveClusteringConfig = {
  enabled: true,
  clusterReachedZones: true,
  moveClusterGapMinutes: 120,
  sameDirectionOnly: true,
};
const T0 = 1769904037000;
const HOUR = 3600 * 1000;

describe("Move clustering A: 4 overlapping SHORT reached zones → 1 uniqueMoveId", () => {
  it("clusters all four into one move", () => {
    const zones: Zone[] = [
      reachedZone({ id: "Z1", direction: "SHORT", triggerTs: T0 + 1 * HOUR, reachedAt: T0 + 15 * HOUR }),
      reachedZone({ id: "Z2", direction: "SHORT", triggerTs: T0 + 6 * HOUR, reachedAt: T0 + 15 * HOUR }),
      reachedZone({ id: "Z3", direction: "SHORT", triggerTs: T0 + 7 * HOUR, reachedAt: T0 + 15 * HOUR }),
      reachedZone({ id: "Z4", direction: "SHORT", triggerTs: T0 + 10 * HOUR, reachedAt: T0 + 15 * HOUR }),
    ];
    const result = applyMoveClustering(zones, cfg, 4);
    expect(result.uniqueReachedMoves).toBe(1);
    expect(result.duplicateMoveCredits).toBe(3);
    expect(result.reachedZonesRaw).toBe(4);
    expect(result.rawTriggeredHitRate).toBe(1);
    expect(result.uniqueMoveAdjustedHitRate).toBe(0.25);
    const ids = new Set(zones.map((z) => z.uniqueMoveId));
    expect(ids.size).toBe(1);
    // Exactly one zone is the primary; the other three are duplicate credits.
    expect(zones.filter((z) => z.isPrimaryMoveZone === true)).toHaveLength(1);
    expect(zones.filter((z) => z.duplicateMoveCredit === true)).toHaveLength(3);
  });
});

describe("Move clustering B: same-direction zones spaced > gap → distinct moves", () => {
  it("two SHORTs separated by > 120 min get different uniqueMoveIds", () => {
    const zones: Zone[] = [
      // first move resolves at T0 + 2h, next trigger at T0 + 5h (gap > 2h)
      reachedZone({ id: "A", direction: "SHORT", triggerTs: T0, reachedAt: T0 + 2 * HOUR }),
      reachedZone({ id: "B", direction: "SHORT", triggerTs: T0 + 5 * HOUR, reachedAt: T0 + 7 * HOUR }),
    ];
    const result = applyMoveClustering(zones, cfg, 2);
    expect(result.uniqueReachedMoves).toBe(2);
    expect(result.duplicateMoveCredits).toBe(0);
    const a = zones.find((z) => z.id === "A")!;
    const b = zones.find((z) => z.id === "B")!;
    expect(a.uniqueMoveId).not.toBe(b.uniqueMoveId);
    expect(a.isPrimaryMoveZone).toBe(true);
    expect(b.isPrimaryMoveZone).toBe(true);
  });
});

describe("Move clustering C: LONG and SHORT never cluster together", () => {
  it("a SHORT and a LONG with overlapping windows get separate moves", () => {
    const zones: Zone[] = [
      reachedZone({ id: "S", direction: "SHORT", triggerTs: T0, reachedAt: T0 + 5 * HOUR }),
      reachedZone({ id: "L", direction: "LONG", triggerTs: T0 + HOUR, reachedAt: T0 + 4 * HOUR }),
    ];
    const result = applyMoveClustering(zones, cfg, 2);
    expect(result.uniqueReachedMoves).toBe(2);
    const s = zones.find((z) => z.id === "S")!;
    const l = zones.find((z) => z.id === "L")!;
    expect(s.uniqueMoveId).not.toBe(l.uniqueMoveId);
    expect(s.isPrimaryMoveZone).toBe(true);
    expect(l.isPrimaryMoveZone).toBe(true);
  });
});

describe("Move clustering D: primary zone = earliest triggerTs", () => {
  it("earliest-triggered zone in a cluster is the primary", () => {
    const zones: Zone[] = [
      reachedZone({ id: "EARLY", direction: "SHORT", triggerTs: T0, reachedAt: T0 + 10 * HOUR, composite: 0.3 }),
      reachedZone({ id: "MIDDLE", direction: "SHORT", triggerTs: T0 + 2 * HOUR, reachedAt: T0 + 11 * HOUR, composite: 0.9 }),
      reachedZone({ id: "LATE", direction: "SHORT", triggerTs: T0 + 4 * HOUR, reachedAt: T0 + 12 * HOUR, composite: 0.6 }),
    ];
    const result = applyMoveClustering(zones, cfg, 3);
    expect(result.uniqueReachedMoves).toBe(1);
    const early = zones.find((z) => z.id === "EARLY")!;
    expect(early.isPrimaryMoveZone).toBe(true);
    // Despite higher composite score, MIDDLE/LATE are duplicates because EARLY came first.
    expect(zones.find((z) => z.id === "MIDDLE")!.duplicateMoveCredit).toBe(true);
    expect(zones.find((z) => z.id === "LATE")!.duplicateMoveCredit).toBe(true);
  });

  it("when triggerTs ties, the higher composite score wins", () => {
    const zones: Zone[] = [
      reachedZone({ id: "TIED_LOW", direction: "LONG", triggerTs: T0, reachedAt: T0 + 6 * HOUR, composite: 0.3 }),
      reachedZone({ id: "TIED_HIGH", direction: "LONG", triggerTs: T0, reachedAt: T0 + 5 * HOUR, composite: 0.9 }),
    ];
    const result = applyMoveClustering(zones, cfg, 2);
    expect(result.uniqueReachedMoves).toBe(1);
    expect(zones.find((z) => z.id === "TIED_HIGH")!.isPrimaryMoveZone).toBe(true);
    expect(zones.find((z) => z.id === "TIED_LOW")!.duplicateMoveCredit).toBe(true);
  });
});

describe("Move clustering E: failed / no_trigger zones never receive cluster fields", () => {
  it("non-reached zones are untouched", () => {
    const zones: Zone[] = [
      reachedZone({ id: "OK", direction: "SHORT", triggerTs: T0, reachedAt: T0 + 5 * HOUR }),
      nonReachedZone({ id: "FAIL", direction: "SHORT", status: "RESOLVED_FAILED", triggerTs: T0 + 1 * HOUR }),
      nonReachedZone({ id: "NOTRIG", direction: "SHORT", status: "NO_TRIGGER" }),
      nonReachedZone({ id: "INV", direction: "LONG", status: "INVALIDATED" }),
      nonReachedZone({ id: "EXP", direction: "LONG", status: "EXPIRED" }),
    ];
    const result = applyMoveClustering(zones, cfg, 2);
    expect(result.reachedZonesRaw).toBe(1);
    expect(result.uniqueReachedMoves).toBe(1);
    expect(result.duplicateMoveCredits).toBe(0);
    for (const id of ["FAIL", "NOTRIG", "INV", "EXP"]) {
      const z = zones.find((zz) => zz.id === id)!;
      expect(z.uniqueMoveId).toBeUndefined();
      expect(z.moveClusterSize).toBeUndefined();
      expect(z.isPrimaryMoveZone).toBeUndefined();
      expect(z.duplicateMoveCredit).toBeUndefined();
    }
    const ok = zones.find((z) => z.id === "OK")!;
    expect(ok.uniqueMoveId).toBe(1);
    expect(ok.isPrimaryMoveZone).toBe(true);
  });
});

describe("Move clustering: disabled cfg returns raw counts and untouched zones", () => {
  it("with cfg.enabled=false, no zone gets cluster fields", () => {
    const zones: Zone[] = [
      reachedZone({ id: "A", direction: "SHORT", triggerTs: T0, reachedAt: T0 + 5 * HOUR }),
      reachedZone({ id: "B", direction: "SHORT", triggerTs: T0 + HOUR, reachedAt: T0 + 6 * HOUR }),
    ];
    const result = applyMoveClustering(zones, { ...cfg, enabled: false }, 2);
    expect(result.uniqueReachedMoves).toBe(result.reachedZonesRaw);
    expect(result.duplicateMoveCredits).toBe(0);
    for (const z of zones) {
      expect(z.uniqueMoveId).toBeUndefined();
    }
  });
});

describe("Move clustering: idempotency", () => {
  it("running twice produces the same fields", () => {
    const zones: Zone[] = [
      reachedZone({ id: "Z1", direction: "SHORT", triggerTs: T0, reachedAt: T0 + 5 * HOUR }),
      reachedZone({ id: "Z2", direction: "SHORT", triggerTs: T0 + 2 * HOUR, reachedAt: T0 + 6 * HOUR }),
    ];
    applyMoveClustering(zones, cfg, 2);
    const firstRunIds = zones.map((z) => z.uniqueMoveId);
    applyMoveClustering(zones, cfg, 2);
    const secondRunIds = zones.map((z) => z.uniqueMoveId);
    expect(secondRunIds).toEqual(firstRunIds);
  });
});
