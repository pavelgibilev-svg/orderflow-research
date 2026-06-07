import { describe, expect, it } from "vitest";
import { OrderBook } from "../src/replay/orderBook.js";
import { FeatureEngine } from "../src/features/featureEngine.js";
import type { StrategyConfig } from "../src/strategy/types.js";
import { computeImbalance } from "../src/features/orderflowImbalance.js";

const cfg: StrategyConfig = {
  symbol: "T",
  exchange: "x",
  targetPct: 2,
  featureIntervalSec: 1,
  snapshotDepthLevels: 50,
  depthPctBuckets: [0.05, 0.5, 1, 2],
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
  targetChecker: { horizons: ["4h"], referencePrice: "triggerPrice" },
  quality: { maxSpreadPct: 5, maxGapMs: 60_000, requireBestBidAsk: false },
  replay: { warmupSeconds: 0, logEveryRows: 1_000_000 },
};

describe("FeatureEngine trade aggregation", () => {
  it("aggregates buy/sell volume with no lookahead", () => {
    const ob = new OrderBook();
    ob.apply({ ts: 0, isSnapshot: true, side: "bid", price: 100, amount: 5 });
    ob.apply({ ts: 0, isSnapshot: true, side: "ask", price: 101, amount: 5 });
    const fe = new FeatureEngine(cfg, ob);

    fe.onTrade({ source: "trades", ts: 1000, localTs: 1000, id: "1", side: "buy", price: 100.5, amount: 1 });
    fe.onTrade({ source: "trades", ts: 2000, localTs: 2000, id: "2", side: "sell", price: 100.4, amount: 2 });
    // Build a row at ts=2500 — both trades inside the 5s window.
    const row = fe.buildFeatureRow(2500, []);
    const w5 = row.trades.windows["5"];
    expect(w5.buyVolume).toBe(1);
    expect(w5.sellVolume).toBe(2);
    expect(w5.delta).toBe(-1);
    expect(w5.trades).toBe(2);

    // Build a row at ts=8000 — both trades fall outside 5s window.
    const row2 = fe.buildFeatureRow(8000, []);
    expect(row2.trades.windows["5"].trades).toBe(0);
    // But still inside the 60s window.
    expect(row2.trades.windows["60"].trades).toBe(2);
  });
});

describe("Order book imbalance", () => {
  it("computes (bid-ask)/(bid+ask) per pct bucket", () => {
    const state = {
      ts: 0,
      bestBid: 100,
      bestAsk: 101,
      mid: 100.5,
      spread: 1,
      spreadPct: 1,
      totalBid: 0,
      totalAsk: 0,
      depthBuckets: { "0.5": { bid: 8, ask: 2 }, "1": { bid: 5, ask: 5 } },
      bidLevels: 0,
      askLevels: 0,
      qualityFlags: [],
    };
    const imb = computeImbalance(state as any);
    expect(imb["0.5"]).toBeCloseTo(0.6, 6);
    expect(imb["1"]).toBe(0);
  });
});
