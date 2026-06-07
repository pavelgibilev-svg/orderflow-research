// Deduplication tests for ZoneDetector.
//
// A. New same-direction candidate is SUPPRESSED while an existing zone of
//    the same direction is still active (CANDIDATE / CONFIRMED / TRIGGERED)
//    AND price band overlaps.
// B. Opposite-direction candidate is ALLOWED in the same price area.
// C. Same-direction candidate is ALLOWED after cooldown elapses.
// D. With deduplication enabled, the synthetic absorption scenario that
//    used to produce many overlapping zones produces at most ONE same-
//    direction zone in the same price area.
// E. With dedup DISABLED, legacy behaviour is preserved (still no two
//    same-direction CANDIDATE zones at once, but TRIGGERED zones do not
//    block new candidates — same as the legacy code path).

import { describe, expect, it } from "vitest";
import { ZoneDetector } from "../src/strategy/zoneDetector.js";
import type { FeatureRow, StrategyConfig, Zone } from "../src/strategy/types.js";

function makeCfg(overrides: Partial<StrategyConfig> = {}): StrategyConfig {
  const base: StrategyConfig = {
    symbol: "BTCUSDT",
    exchange: "test",
    targetPct: 2,
    featureIntervalSec: 1,
    snapshotDepthLevels: 50,
    depthPctBuckets: [0.05, 0.5, 1, 2],
    tradeWindowsSec: [5, 60],
    zone: {
      // Permissive thresholds — let candidates form easily so we can isolate
      // dedup behaviour.
      minCandidateDurationMin: 0,
      minConfirmedDurationMin: 0,
      maxFormationDurationMin: 60,
      minAbsorptionCycles: 1,
      maxNoProgressPct: 5,
      minAbsorptionScore: 0.05,
      minLiquidityVoidScore: 0,
      minTriggerScore: 0,
      candidate: { minSidedPressure: 0.5, minRefillScore: 0.3, rangeCompressionPct: 5 },
      confirmed: { minDefendedPersistenceSec: 0, minOppositeThinningScore: 0 },
      trigger: { minBreakDistancePct: 0.05, minAggressiveFlowMultiplier: 1 },
    },
    targetChecker: { horizons: ["4h"], referencePrice: "triggerPrice" },
    quality: { maxSpreadPct: 5, maxGapMs: 60_000, requireBestBidAsk: false },
    replay: { warmupSeconds: 0, logEveryRows: 1_000_000 },
    deduplication: {
      enabled: true,
      sameDirectionOverlapSuppression: true,
      cooldownMinutesAfterResolve: 30,
      priceOverlapMinPct: 0.25,
    },
  };
  return { ...base, ...overrides };
}

function row(opts: {
  ts: number;
  mid: number;
  sellPressure?: number;
  buyPressure?: number;
  bidRefillScore?: number;
  askRefillScore?: number;
  buyAbsorptionScore?: number;
  sellAbsorptionScore?: number;
  priceProgressDownPct?: number;
  priceProgressUpPct?: number;
  voidUp?: number;
  voidDown?: number;
}): FeatureRow {
  const sellP = opts.sellPressure ?? 0;
  const buyP = opts.buyPressure ?? 0;
  return {
    ts: opts.ts,
    book: {
      ts: opts.ts,
      bestBid: opts.mid - 0.5,
      bestAsk: opts.mid + 0.5,
      mid: opts.mid,
      spread: 1,
      spreadPct: 1 / opts.mid,
      totalBid: 100,
      totalAsk: 100,
      depthBuckets: {
        "0.05": { bid: 1, ask: 1 },
        "0.5": { bid: 8, ask: 2 },
        "1": { bid: 5, ask: 5 },
        "2": { bid: 3, ask: 3 },
      },
      bidLevels: 5,
      askLevels: 5,
      qualityFlags: [],
    },
    trades: {
      ts: opts.ts,
      windows: {
        "5": { windowSec: 5, buyVolume: buyP * 10, sellVolume: sellP * 10, delta: 0, trades: 5, vwap: opts.mid, highPrice: opts.mid, lowPrice: opts.mid },
        "60": { windowSec: 60, buyVolume: buyP * 100, sellVolume: sellP * 100, delta: 0, trades: 50, vwap: opts.mid, highPrice: opts.mid, lowPrice: opts.mid },
      },
    },
    imbalance: { "0.05": 0, "0.5": 0.6, "1": 0, "2": 0 },
    pressure: { buyPressure: buyP, sellPressure: sellP, aggressiveFlowRatio: Math.max(buyP, sellP) },
    absorption: {
      buyAbsorptionScore: opts.buyAbsorptionScore ?? 0,
      sellAbsorptionScore: opts.sellAbsorptionScore ?? 0,
      priceProgressDownPct: opts.priceProgressDownPct ?? 0,
      priceProgressUpPct: opts.priceProgressUpPct ?? 0,
    },
    liquidityVoid: {
      voidUp2PctScore: opts.voidUp ?? 0.7,
      voidDown2PctScore: opts.voidDown ?? 0.7,
      askVolUpTo2Pct: 1,
      bidVolDownTo2Pct: 1,
    },
    liquidityEvents: {
      bidAddRate: 0,
      bidRemoveRate: 0,
      askAddRate: 0,
      askRemoveRate: 0,
      bidRefillScore: opts.bidRefillScore ?? 0,
      askRefillScore: opts.askRefillScore ?? 0,
      bidThinningScore: 0,
      askThinningScore: 0.5,
    },
    volatility: { realizedVolPct: 0.1, range1mPct: 0.1 },
    rangeCompression: true,
    forcedFlow: { liqBuyVol: 0, liqSellVol: 0 },
    qualityFlags: [],
  };
}

function longCandidateRow(ts: number, mid: number): FeatureRow {
  return row({
    ts,
    mid,
    sellPressure: 0.7,
    bidRefillScore: 0.7,
    buyAbsorptionScore: 0.8,
    voidUp: 0.8,
  });
}
function shortCandidateRow(ts: number, mid: number): FeatureRow {
  return row({
    ts,
    mid,
    buyPressure: 0.7,
    askRefillScore: 0.7,
    sellAbsorptionScore: 0.8,
    voidDown: 0.8,
  });
}

const T0 = 1_580_515_200_000; // 2020-02-01

describe("Dedup A: same-direction zone suppressed while previous active", () => {
  it("does NOT open a second LONG candidate while the first is still in openZones", () => {
    const cfg = makeCfg();
    const det = new ZoneDetector(cfg, "BTCUSDT", "2020-02-01");
    det.ingest(longCandidateRow(T0, 100));
    // Same price, immediately after — same direction, fully overlapping.
    det.ingest(longCandidateRow(T0 + 1000, 100));
    det.ingest(longCandidateRow(T0 + 2000, 100));
    det.finalize(T0 + 3000);
    const zones = det.zones();
    const longZones = zones.filter((z) => z.direction === "LONG");
    expect(longZones.length).toBe(1);
    expect(det.suppressionCount()).toBeGreaterThanOrEqual(2);
    expect(det.suppressions().every((s) => s.direction === "LONG")).toBe(true);
  });

  it("blocks new LONG candidate while previous LONG is TRIGGERED (not just CANDIDATE/CONFIRMED)", () => {
    const cfg = makeCfg();
    const det = new ZoneDetector(cfg, "BTCUSDT", "2020-02-01");
    // 1) Build a candidate.
    det.ingest(longCandidateRow(T0, 100));
    // 2) Push enough additional rows to confirm + trigger the zone.
    //    The zoneDetector trigger requires (mid > zoneHigh) + flow burst.
    for (let i = 1; i <= 30; i++) det.ingest(longCandidateRow(T0 + i * 60_000, 100));
    // Now break out (mid significantly above zoneHigh, with large flow):
    const triggerRow = row({
      ts: T0 + 31 * 60_000,
      mid: 102, // 2% breakout
      buyPressure: 0.8,
      bidRefillScore: 0.6,
      buyAbsorptionScore: 0.6,
      voidUp: 0.8,
    });
    // Inflate flow to satisfy the trigger flow-multiplier.
    triggerRow.trades.windows["60"].buyVolume = 1_000_000;
    triggerRow.trades.windows["60"].sellVolume = 100;
    det.ingest(triggerRow);
    const zonesAfterTrigger = det.zones();
    const triggered = zonesAfterTrigger.find((z) => z.triggerTs !== undefined && z.direction === "LONG");
    expect(triggered).toBeTruthy();
    // 3) Try to open a new LONG candidate at a price that overlaps the triggered zone's band.
    det.ingest(longCandidateRow(T0 + 32 * 60_000, 100));
    det.ingest(longCandidateRow(T0 + 33 * 60_000, 100));
    det.finalize(T0 + 35 * 60_000);
    // Should NOT have opened a second LONG zone.
    const longCount = det.zones().filter((z) => z.direction === "LONG").length;
    expect(longCount).toBe(1);
    const triggeredSup = det.suppressions().filter((s) => s.reason === "active_triggered");
    expect(triggeredSup.length).toBeGreaterThan(0);
  });
});

describe("Dedup B: opposite-direction zone is allowed in the same area", () => {
  it("LONG and SHORT can coexist on the same price band", () => {
    const cfg = makeCfg();
    const det = new ZoneDetector(cfg, "BTCUSDT", "2020-02-01");
    det.ingest(longCandidateRow(T0, 100));
    det.ingest(shortCandidateRow(T0 + 1000, 100));
    det.finalize(T0 + 2000);
    const zones = det.zones();
    expect(zones.filter((z) => z.direction === "LONG").length).toBe(1);
    expect(zones.filter((z) => z.direction === "SHORT").length).toBe(1);
    // No suppressions because dedup only restricts same-direction overlap.
    expect(det.suppressionCount()).toBe(0);
  });
});

describe("Dedup C: cooldown after a zone resolves", () => {
  it("blocks a same-direction candidate within cooldown after invalidation", () => {
    const cfg = makeCfg({
      deduplication: {
        enabled: true,
        sameDirectionOverlapSuppression: true,
        cooldownMinutesAfterResolve: 30,
        priceOverlapMinPct: 0.25,
      },
    });
    const det = new ZoneDetector(cfg, "BTCUSDT", "2020-02-01");
    // Open + immediately confirm (cfg has minCandidateDurationMin=0).
    det.ingest(longCandidateRow(T0, 100));
    // Invalidate the zone: drive mid below zoneLow * 0.995 (~99.45).
    const invalidateRow = row({ ts: T0 + 60_000, mid: 95 });
    det.ingest(invalidateRow);
    const zonesAfterInvalidate = det.zones();
    expect(zonesAfterInvalidate.length).toBe(1);
    expect(zonesAfterInvalidate[0].status).toBe("INVALIDATED");
    // Try to open a new LONG candidate within cooldown — should be SUPPRESSED.
    det.ingest(longCandidateRow(T0 + 5 * 60_000, 100));
    det.finalize(T0 + 6 * 60_000);
    const longZones = det.zones().filter((z) => z.direction === "LONG");
    expect(longZones.length).toBe(1);
    const cooldownSup = det.suppressions().filter((s) => s.reason === "cooldown");
    expect(cooldownSup.length).toBeGreaterThan(0);
  });

  it("ALLOWS a same-direction candidate after cooldown elapses", () => {
    const cfg = makeCfg({
      deduplication: {
        enabled: true,
        sameDirectionOverlapSuppression: true,
        cooldownMinutesAfterResolve: 5, // 5-minute cooldown
        priceOverlapMinPct: 0.25,
      },
    });
    const det = new ZoneDetector(cfg, "BTCUSDT", "2020-02-01");
    det.ingest(longCandidateRow(T0, 100));
    // Invalidate at T0 + 1min.
    det.ingest(row({ ts: T0 + 60_000, mid: 95 }));
    // Wait past cooldown — invalidate happened at T0+60_000, cooldown is 5 min,
    // so at T0+10min cooldown is over.
    det.ingest(longCandidateRow(T0 + 10 * 60_000, 100));
    det.finalize(T0 + 11 * 60_000);
    const longZones = det.zones().filter((z) => z.direction === "LONG");
    expect(longZones.length).toBe(2);
  });
});

describe("Dedup D: with dedup ON, a 'one move' fires at most one same-direction zone", () => {
  it("multiple identical LONG candidate signals collapse into a single zone", () => {
    const cfg = makeCfg();
    const det = new ZoneDetector(cfg, "BTCUSDT", "2020-02-01");
    // Push 10 identical LONG candidate signals over ~15 minutes:
    for (let i = 0; i < 10; i++) det.ingest(longCandidateRow(T0 + i * 90_000, 100));
    det.finalize(T0 + 10 * 90_000);
    const longZones = det.zones().filter((z) => z.direction === "LONG");
    expect(longZones.length).toBe(1);
    expect(det.suppressionCount()).toBe(9);
    // All suppressions should reference the original zone:
    const ids = new Set(det.suppressions().map((s) => s.suppressedByZoneId));
    expect(ids.size).toBe(1);
    expect([...ids][0]).toBe(longZones[0].id);
  });
});

describe("Dedup E: dedup DISABLED falls back to legacy active-only block", () => {
  it("with dedup off, opens a second LONG candidate after the first triggers", () => {
    const cfg = makeCfg({
      deduplication: {
        enabled: false,
        sameDirectionOverlapSuppression: false,
        cooldownMinutesAfterResolve: 0,
        priceOverlapMinPct: 0.25,
      },
    });
    const det = new ZoneDetector(cfg, "BTCUSDT", "2020-02-01");
    // Build LONG to TRIGGERED.
    det.ingest(longCandidateRow(T0, 100));
    for (let i = 1; i <= 30; i++) det.ingest(longCandidateRow(T0 + i * 60_000, 100));
    const triggerRow = row({
      ts: T0 + 31 * 60_000,
      mid: 102,
      buyPressure: 0.8,
      bidRefillScore: 0.6,
      buyAbsorptionScore: 0.6,
      voidUp: 0.8,
    });
    triggerRow.trades.windows["60"].buyVolume = 1_000_000;
    triggerRow.trades.windows["60"].sellVolume = 100;
    det.ingest(triggerRow);
    const triggered = det.zones().find((z) => z.triggerTs !== undefined && z.direction === "LONG");
    expect(triggered).toBeTruthy();
    // Now open a new LONG candidate at the same level — legacy allows because the
    // first zone is no longer in openZones, it's TRIGGERED in resolvedZones.
    det.ingest(longCandidateRow(T0 + 32 * 60_000, 100));
    det.finalize(T0 + 35 * 60_000);
    const longCount = det.zones().filter((z) => z.direction === "LONG").length;
    expect(longCount).toBeGreaterThanOrEqual(2);
    expect(det.suppressionCount()).toBe(0);
  });
});
