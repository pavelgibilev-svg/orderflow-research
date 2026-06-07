// Toy absorption scenario.
//
// Goal: synthesise an order-book + trade sequence in which a wall of bid
// liquidity is being hit by aggressive sells but keeps refilling — the kind
// of structure a Long Accumulation candidate is supposed to fire on. We
// drive the FeatureEngine + ZoneDetector with very permissive thresholds
// and assert that AT LEAST one Long candidate appears.

import { describe, expect, it } from "vitest";
import { OrderBook } from "../src/replay/orderBook.js";
import { FeatureEngine } from "../src/features/featureEngine.js";
import { ZoneDetector } from "../src/strategy/zoneDetector.js";
import type { StrategyConfig } from "../src/strategy/types.js";
import { computeAbsorption } from "../src/features/absorption.js";

const cfg: StrategyConfig = {
  symbol: "BTCUSDT",
  exchange: "test",
  targetPct: 2,
  featureIntervalSec: 1,
  snapshotDepthLevels: 50,
  depthPctBuckets: [0.05, 0.5, 1, 2],
  tradeWindowsSec: [5, 60],
  zone: {
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
};

describe("Absorption scoring", () => {
  it("rewards heavy sell volume with little down progress", () => {
    const heavySellNoProgress = computeAbsorption({
      sellVolumeWindow: 100,
      buyVolumeWindow: 5,
      priceProgressDownPct: 0.01,
      priceProgressUpPct: 0,
      totalTradeVolumeWindow: 105,
    });
    const heavySellBigProgress = computeAbsorption({
      sellVolumeWindow: 100,
      buyVolumeWindow: 5,
      priceProgressDownPct: 1.0,
      priceProgressUpPct: 0,
      totalTradeVolumeWindow: 105,
    });
    expect(heavySellNoProgress.buyAbsorptionScore).toBeGreaterThan(
      heavySellBigProgress.buyAbsorptionScore
    );
  });
});

describe("Toy absorption scenario yields a Long candidate", () => {
  it("creates a candidate after sell pressure with bid refill and small downside", () => {
    const ob = new OrderBook();
    const fe = new FeatureEngine(cfg, ob);
    const det = new ZoneDetector(cfg, "BTCUSDT", "2020-02-01");
    const startTs = 1_580_515_200_000; // 2020-02-01

    // Initialise book around 100.
    const seedBids = [99, 99.5, 99.8, 100];
    const seedAsks = [100.2, 100.5, 101, 101.5];
    for (const p of seedBids) ob.apply({ ts: startTs - 1000, isSnapshot: true, side: "bid", price: p, amount: 5 });
    for (const p of seedAsks) ob.apply({ ts: startTs - 1000, isSnapshot: true, side: "ask", price: p, amount: 5 });

    // Loop 90 ticks: every tick has a chunk of aggressive SELLS hitting bids,
    // bid refills almost instantly, mid stays roughly flat.
    for (let i = 0; i < 90; i++) {
      const ts = startTs + i * 1000;
      // Sell trade chews through bid level 100.
      fe.onTrade({ source: "trades", ts, localTs: ts, id: `t${i}`, side: "sell", price: 99.95, amount: 1 });
      // Reduce best bid, then refill.
      ob.apply({ ts, isSnapshot: false, side: "bid", price: 100, amount: 0 });
      fe.onL2({ source: "incremental_book_L2", ts, localTs: ts, isSnapshot: false, side: "bid", price: 100, amount: 0 });
      ob.apply({ ts: ts + 50, isSnapshot: false, side: "bid", price: 99.99, amount: 5 });
      fe.onL2({ source: "incremental_book_L2", ts: ts + 50, localTs: ts + 50, isSnapshot: false, side: "bid", price: 99.99, amount: 5 });
      ob.apply({ ts: ts + 100, isSnapshot: false, side: "bid", price: 100, amount: 5 });
      fe.onL2({ source: "incremental_book_L2", ts: ts + 100, localTs: ts + 100, isSnapshot: false, side: "bid", price: 100, amount: 5 });
      // Build a feature row each tick.
      const row = fe.buildFeatureRow(ts + 200, []);
      det.ingest(row);
    }
    det.finalize(startTs + 100 * 1000);

    const zones = det.zones();
    // Expect at least one long zone (CANDIDATE / CONFIRMED / TRIGGERED / NO_TRIGGER).
    const longs = zones.filter((z) => z.direction === "LONG");
    expect(longs.length).toBeGreaterThan(0);
    // And every zone must carry a reason chain (debug fields per spec §13).
    for (const z of zones) {
      expect(z.reasons.length).toBeGreaterThan(0);
      expect(z.reasons[0].stage).toBe("candidate");
    }
  });
});
