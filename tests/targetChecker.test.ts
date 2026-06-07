import { describe, expect, it } from "vitest";
import { TargetChecker, type TradePoint } from "../src/strategy/targetChecker.js";
import type { StrategyConfig, Zone } from "../src/strategy/types.js";

const cfg: StrategyConfig = {
  symbol: "T",
  exchange: "x",
  targetPct: 2,
  featureIntervalSec: 1,
  snapshotDepthLevels: 50,
  depthPctBuckets: [0.5, 1, 2],
  tradeWindowsSec: [5, 60],
  zone: {
    minCandidateDurationMin: 1,
    minConfirmedDurationMin: 1,
    maxFormationDurationMin: 60,
    minAbsorptionCycles: 1,
    maxNoProgressPct: 5,
    minAbsorptionScore: 0,
    minLiquidityVoidScore: 0,
    minTriggerScore: 0,
    candidate: { minSidedPressure: 0, minRefillScore: 0, rangeCompressionPct: 100 },
    confirmed: { minDefendedPersistenceSec: 0, minOppositeThinningScore: 0 },
    trigger: { minBreakDistancePct: 0.05, minAggressiveFlowMultiplier: 1 },
  },
  targetChecker: { horizons: ["4h", "8h", "24h"], referencePrice: "triggerPrice" },
  quality: { maxSpreadPct: 5, maxGapMs: 60_000, requireBestBidAsk: false },
  replay: { warmupSeconds: 0, logEveryRows: 1_000_000 },
};

function baseZone(direction: "LONG" | "SHORT", triggerPrice: number, triggerTs: number): Zone {
  return {
    id: "z1",
    symbol: "T",
    date: "2020-02-01",
    direction,
    zoneType: direction === "LONG" ? "ACCUMULATION" : "DISTRIBUTION",
    status: "TRIGGERED",
    startTs: triggerTs - 10 * 60_000,
    triggerTs,
    triggerPrice,
    referencePrice: triggerPrice,
    targetPrice:
      direction === "LONG" ? triggerPrice * 1.02 : triggerPrice * 0.98,
    zoneLow: triggerPrice * 0.999,
    zoneHigh: triggerPrice * 1.001,
    scores: { absorptionScore: 0.5, liquidityVoidScore: 0.5, ofiScore: 0 },
    qualityFlags: [],
    targets: {},
    reasons: [],
  };
}

describe("TargetChecker", () => {
  it("LONG zone: detects 2% reach inside horizon and computes timeToTarget", () => {
    const trades: TradePoint[] = [];
    for (let i = 0; i < 100; i++) {
      // ramp: from 100 to 102.5 over 100 minutes
      trades.push({ ts: i * 60_000, price: 100 + (i / 100) * 2.5 });
    }
    const z = baseZone("LONG", 100, 0);
    new TargetChecker(cfg, trades).resolveZone(z);
    expect(z.status).toBe("RESOLVED_REACHED");
    const t4 = z.targets["4h"];
    expect(t4.outcome).toBe("reached");
    expect(t4.timeToTargetMin).toBeGreaterThan(0);
    expect(t4.timeToTargetMin).toBeLessThan(100);
  });

  it("LONG zone: failed_by_timeout when ramp doesn't reach 2% within 4h", () => {
    const trades: TradePoint[] = [];
    for (let i = 0; i < 60; i++) trades.push({ ts: i * 60_000, price: 100 + i * 0.005 }); // up to ~100.295
    const z = baseZone("LONG", 100, 0);
    // Use a config with only 4h
    const cfgShort: StrategyConfig = { ...cfg, targetChecker: { ...cfg.targetChecker, horizons: ["4h"] } };
    new TargetChecker(cfgShort, trades).resolveZone(z);
    expect(z.status).toBe("RESOLVED_FAILED");
    expect(z.targets["4h"].outcome).toBe("failed_by_timeout");
  });

  it("SHORT zone: detects -2% reach", () => {
    const trades: TradePoint[] = [];
    for (let i = 0; i < 100; i++) trades.push({ ts: i * 60_000, price: 100 - (i / 100) * 2.5 });
    const z = baseZone("SHORT", 100, 0);
    new TargetChecker(cfg, trades).resolveZone(z);
    expect(z.status).toBe("RESOLVED_REACHED");
    expect(z.targets["4h"].outcome).toBe("reached");
  });

  it("does not look beyond trigger time (no lookahead from trades before trigger)", () => {
    const trades: TradePoint[] = [
      { ts: 0, price: 100 },
      { ts: 60_000, price: 99 }, // below 100 — but BEFORE trigger
      { ts: 120_000, price: 100 }, // trigger ts = 120_000
      { ts: 130_000, price: 99 }, // hypothetical post-trigger move
    ];
    // SHORT zone triggered at ts=120000 with price 100; target = 98.
    const z = baseZone("SHORT", 100, 120_000);
    new TargetChecker(cfg, trades).resolveZone(z);
    expect(z.targets["4h"].outcome).not.toBe("reached"); // 99 is not <= 98
  });
});
