// Unit tests for src/research/canonicalLedger.ts.
//
// Critical invariants exercised here:
//   1. Position closes after STOP; next signal is admitted after exit.
//   2. Position closes after TARGET; next signal is admitted after exit.
//   3. While position is open, intervening signals are skipped.
//   4. Timeout (24h) blocks until 24h ONLY if no target/stop hit.
//   5. Same-bucket target + stop => stop first (conservative).
//   6. Regression: the "blind 24h hold" bug must NOT reappear.

import { describe, expect, it } from "vitest";
import {
  type Bucket,
  type Signal,
  canonicalLedgerWalk,
  simulateCanonicalTrade,
  aggregate,
} from "../src/research/canonicalLedger.js";

// ---------------------------------------------------------------------------
// Helpers to build deterministic synthetic price paths.
// 1 bucket per second.
// ---------------------------------------------------------------------------

function flatBuckets(startSec: number, durationSec: number, price: number): Bucket[] {
  return Array.from({ length: durationSec }, (_, i) => ({
    sec: startSec + i,
    high: price,
    low: price,
    last: price,
  }));
}

function spikedBuckets(opts: {
  startSec: number;
  durationSec: number;
  basePrice: number;
  /** seconds (relative to startSec) at which a spike fires */
  spikes: Array<{ relSec: number; high?: number; low?: number; last?: number }>;
}): Bucket[] {
  const buckets = flatBuckets(opts.startSec, opts.durationSec, opts.basePrice);
  for (const s of opts.spikes) {
    const idx = s.relSec;
    if (idx < 0 || idx >= buckets.length) continue;
    const b = buckets[idx];
    if (s.high !== undefined) b.high = s.high;
    if (s.low !== undefined) b.low = s.low;
    if (s.last !== undefined) b.last = s.last;
  }
  return buckets;
}

// ---------------------------------------------------------------------------
// Scenario 1: position closes after STOP, next signal admitted.
// ---------------------------------------------------------------------------

describe("canonicalLedgerWalk - position closes after STOP, next signal admitted", () => {
  it("admits a later signal once the prior position stopped", () => {
    const date = "2025-01-01";
    const day0 = 1735689600; // 2025-01-01T00:00:00Z unix seconds
    // Signal A LONG at 00:00:00, entry price 100, stop=99 hit 1h later (3600s),
    // Signal B LONG at 02:00:00.
    const buckets: Bucket[] = [];
    // 00:00:00 .. 01:00:00 — flat 100
    for (let i = 0; i < 3600; i++) buckets.push({ sec: day0 + i, high: 100, low: 100, last: 100 });
    // 01:00:00 — drop to 98.5 to trigger stop at 99 for LONG
    buckets.push({ sec: day0 + 3600, high: 100, low: 98.5, last: 99 });
    // 01:00:01 .. 04:00:00 — recover to 100
    for (let i = 3601; i < 4 * 3600; i++) buckets.push({ sec: day0 + i, high: 100, low: 100, last: 100 });
    const signals: Signal[] = [
      { id: "A", date, triggerTs: day0 * 1000, direction: "LONG" },
      { id: "B", date, triggerTs: (day0 + 2 * 3600) * 1000, direction: "LONG" },
    ];
    const map = new Map([[date, buckets]]);
    const res = canonicalLedgerWalk(signals, map, { entryStrategy: "trigger", stopPct: 1 });
    expect(res.trades.length).toBe(2);
    expect(res.trades[0].zoneId).toBe("A");
    expect(res.trades[0].exitReason).toBe("stop");
    expect(res.trades[1].zoneId).toBe("B");
    expect(res.skippedDueToPosition).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Scenario 2: position closes after TARGET, next signal admitted.
// ---------------------------------------------------------------------------

describe("canonicalLedgerWalk - position closes after TARGET", () => {
  it("admits a later signal once the prior position hit target", () => {
    const date = "2025-01-01";
    const day0 = 1735689600;
    // Signal A LONG at 00:00, target=102 hit at 03:00.
    // Signal B LONG at 04:00.
    const buckets: Bucket[] = [];
    for (let i = 0; i < 3 * 3600; i++) buckets.push({ sec: day0 + i, high: 100, low: 100, last: 100 });
    // 03:00 - spike to 102.5 -> hits target 102
    buckets.push({ sec: day0 + 3 * 3600, high: 102.5, low: 100, last: 102 });
    for (let i = 3 * 3600 + 1; i < 5 * 3600; i++) buckets.push({ sec: day0 + i, high: 100, low: 100, last: 100 });
    const signals: Signal[] = [
      { id: "A", date, triggerTs: day0 * 1000, direction: "LONG" },
      { id: "B", date, triggerTs: (day0 + 4 * 3600) * 1000, direction: "LONG" },
    ];
    const map = new Map([[date, buckets]]);
    const res = canonicalLedgerWalk(signals, map, { entryStrategy: "trigger", stopPct: 1 });
    expect(res.trades.length).toBe(2);
    expect(res.trades[0].exitReason).toBe("target_2pct");
    expect(res.trades[1].zoneId).toBe("B");
    expect(res.skippedDueToPosition).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Scenario 3: while position open, intervening signal SKIPPED.
// ---------------------------------------------------------------------------

describe("canonicalLedgerWalk - intervening signal while position open is skipped", () => {
  it("skips signal B when A has not exited yet", () => {
    const date = "2025-01-01";
    const day0 = 1735689600;
    // Signal A LONG at 00:00, NO exit until 10:00 (flat).
    // Signal B LONG at 02:00 - should be SKIPPED.
    const buckets: Bucket[] = flatBuckets(day0, 11 * 3600, 100);
    const signals: Signal[] = [
      { id: "A", date, triggerTs: day0 * 1000, direction: "LONG" },
      { id: "B", date, triggerTs: (day0 + 2 * 3600) * 1000, direction: "LONG" },
    ];
    const map = new Map([[date, buckets]]);
    const res = canonicalLedgerWalk(signals, map, { entryStrategy: "trigger", stopPct: 1 });
    // Only A goes through; A times out after 24h, but there are no buckets that far,
    // so A still uses the last bucket as timeout exit price.
    expect(res.trades.length).toBe(1);
    expect(res.trades[0].zoneId).toBe("A");
    expect(res.trades[0].exitReason).toBe("timeout");
    expect(res.skippedDueToPosition).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Scenario 4: timeout blocks until 24h IF no target/stop. Signal after 24h allowed.
// ---------------------------------------------------------------------------

describe("canonicalLedgerWalk - timeout blocks for 24h ONLY if no target/stop", () => {
  it("blocks B at 23:00 (within open trade A) and admits C at 25:00", () => {
    const date = "2025-01-01";
    const day0 = 1735689600;
    // Signal A LONG at 00:00 — flat 100 forever => timeout at 24:00.
    // Signal B at 23:00 — within open position, skipped.
    // Signal C at 25:00 — after A's timeout exit, admitted.
    const buckets: Bucket[] = flatBuckets(day0, 30 * 3600, 100);
    const signals: Signal[] = [
      { id: "A", date, triggerTs: day0 * 1000, direction: "LONG" },
      { id: "B", date, triggerTs: (day0 + 23 * 3600) * 1000, direction: "LONG" },
      { id: "C", date, triggerTs: (day0 + 25 * 3600) * 1000, direction: "LONG" },
    ];
    const map = new Map([[date, buckets]]);
    const res = canonicalLedgerWalk(signals, map, { entryStrategy: "trigger", stopPct: 1 });
    expect(res.trades.length).toBe(2);
    expect(res.trades[0].zoneId).toBe("A");
    expect(res.trades[0].exitReason).toBe("timeout");
    expect(res.trades[1].zoneId).toBe("C");
    expect(res.skippedDueToPosition).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Scenario 5: same-bucket target+stop => stop first (conservative).
// ---------------------------------------------------------------------------

describe("simulateCanonicalTrade - same-bucket target+stop tiebreak", () => {
  it("returns stop when one bucket touches both target and stop", () => {
    const date = "2025-01-01";
    const day0 = 1735689600;
    // Bucket at 01:00 has high=102 (target) AND low=99 (stop) AND last=100.
    const buckets: Bucket[] = [];
    for (let i = 0; i < 3600; i++) buckets.push({ sec: day0 + i, high: 100, low: 100, last: 100 });
    buckets.push({ sec: day0 + 3600, high: 102, low: 99, last: 100 });
    for (let i = 3601; i < 3 * 3600; i++) buckets.push({ sec: day0 + i, high: 100, low: 100, last: 100 });
    const sig: Signal = { id: "X", date, triggerTs: day0 * 1000, direction: "LONG" };
    const sim = simulateCanonicalTrade(sig, buckets, { entryStrategy: "trigger", stopPct: 1 });
    expect(sim.exitReason).toBe("stop");
  });
});

// ---------------------------------------------------------------------------
// Regression test: ensure the "blind 24h hold" bug does NOT come back.
// If position correctly exits at actual exit_sec, then a later signal whose
// triggerTs is AFTER exit_sec must be admitted even though it's < trigSecA+24h.
// ---------------------------------------------------------------------------

describe("REGRESSION - blind 24h hold bug must not return", () => {
  it("admits subsequent signal that arrives AFTER actual exit but BEFORE trigA+24h", () => {
    const date = "2025-01-01";
    const day0 = 1735689600;
    // Signal A LONG at 00:00; stops at 01:00.
    // Signal B at 02:00. trigA + 24h = 24:00 — far past. Old buggy code would skip B.
    const buckets: Bucket[] = [];
    for (let i = 0; i < 3600; i++) buckets.push({ sec: day0 + i, high: 100, low: 100, last: 100 });
    buckets.push({ sec: day0 + 3600, high: 100, low: 98.5, last: 99 });
    for (let i = 3601; i < 5 * 3600; i++) buckets.push({ sec: day0 + i, high: 100, low: 100, last: 100 });
    const signals: Signal[] = [
      { id: "A", date, triggerTs: day0 * 1000, direction: "LONG" },
      { id: "B", date, triggerTs: (day0 + 2 * 3600) * 1000, direction: "LONG" },
    ];
    const map = new Map([[date, buckets]]);
    const res = canonicalLedgerWalk(signals, map, { entryStrategy: "trigger", stopPct: 1 });
    expect(res.trades.length).toBe(2);   // BUGFIX: must be 2, NOT 1.
    expect(res.skippedDueToPosition).toBe(0); // BUGFIX: must be 0, NOT 1.
  });
});

// ---------------------------------------------------------------------------
// SHORT direction sanity
// ---------------------------------------------------------------------------

describe("simulateCanonicalTrade - SHORT direction symmetry", () => {
  it("hits target_2pct when price drops 2% for SHORT", () => {
    const date = "2025-01-01";
    const day0 = 1735689600;
    const buckets: Bucket[] = [];
    for (let i = 0; i < 3600; i++) buckets.push({ sec: day0 + i, high: 100, low: 100, last: 100 });
    buckets.push({ sec: day0 + 3600, high: 100, low: 97.5, last: 98 });   // hits 98 target for SHORT
    for (let i = 3601; i < 3 * 3600; i++) buckets.push({ sec: day0 + i, high: 100, low: 100, last: 100 });
    const sig: Signal = { id: "S", date, triggerTs: day0 * 1000, direction: "SHORT" };
    const sim = simulateCanonicalTrade(sig, buckets, { entryStrategy: "trigger", stopPct: 1 });
    expect(sim.exitReason).toBe("target_2pct");
  });
});

// ---------------------------------------------------------------------------
// Aggregate sanity
// ---------------------------------------------------------------------------

describe("aggregate - basic counts and PF math", () => {
  it("computes wins/losses/expectancy correctly", () => {
    const trades = [
      { zoneId: "A", date: "d", direction: "LONG", triggerTs: 0, entrySec: 0, exitSec: 1,
        entryPrice: 100, exitPrice: 102, exitReason: "target_2pct", pnlPct: 2, mfePct: 2,
        maePct: 0, timeInTradeH: 0, usedStopPct: 1 } as const,
      { zoneId: "B", date: "d", direction: "LONG", triggerTs: 0, entrySec: 0, exitSec: 1,
        entryPrice: 100, exitPrice: 99, exitReason: "stop", pnlPct: -1, mfePct: 0,
        maePct: 1, timeInTradeH: 0, usedStopPct: 1 } as const,
      { zoneId: "C", date: "d", direction: "SHORT", triggerTs: 0, entrySec: 0, exitSec: 1,
        entryPrice: 100, exitPrice: 98, exitReason: "target_2pct", pnlPct: 2, mfePct: 2,
        maePct: 0, timeInTradeH: 0, usedStopPct: 1 } as const,
    ];
    const agg = aggregate(trades);
    expect(agg.nTrades).toBe(3);
    expect(agg.wins).toBe(2);
    expect(agg.losses).toBe(1);
    expect(agg.timeouts).toBe(0);
    expect(agg.winratePct).toBeCloseTo(66.67, 1);
    expect(agg.expectancyPctPerTrade).toBeCloseTo(1, 4);   // (2+2-1)/3 = 1
    expect(agg.profitFactor).toBeCloseTo(4, 2);            // 4/1
  });
});
