// Canonical strict ledger for OKX/Binance research backtests (post-hoc only).
//
// Hard rules:
//   - One trade at a time.
//   - Position closes at FIRST of: target hit, stop hit, timeout.
//   - The "next signal allowed" timestamp is the ACTUAL exit timestamp,
//     NOT triggerTs + 24h.  (Fixing the prior 41-vs-13 bug.)
//   - Max holding = 24h from entry.
//   - If target and stop occur in same 1s bucket: conservative = STOP FIRST.
//   - Target strict 2 %. Stop / entry are configurable variants.
//   - No strategy / threshold / engine change. No future-leak (entry timestamp
//     is the signal's triggerTs or a +N-min delay; stops/targets use prices
//     only at or after the entry).
//
// This module is research / analytical only. It does NOT modify zoneDetector,
// thresholds, or any production code.

export type Direction = "LONG" | "SHORT";

export interface Bucket {
  /** unix seconds */
  sec: number;
  high: number;
  low: number;
  /** last trade price within that second (entry / timeout exit price) */
  last: number;
}

export interface Signal {
  id: string;
  date: string;
  /** Unix milliseconds */
  triggerTs: number;
  direction: Direction;
  zoneLow?: number;
  zoneHigh?: number;
}

export type EntryStrategy =
  | "trigger"
  | "delay_5m"
  | "delay_10m"
  | "delay_15m"
  | "delay_30m"
  | "retest";

export interface ExecutionConfig {
  entryStrategy: EntryStrategy;
  /** Stop in percent (e.g. 1.0). Ignored if zoneBoundaryStop is true. */
  stopPct: number;
  /** If true, stop is the zoneLow (LONG) / zoneHigh (SHORT). */
  zoneBoundaryStop?: boolean;
  /** If set and zoneBoundaryStop is false, stop distance = max(zoneBoundaryDist, this). */
  maxZoneBoundaryOrPct?: number;
  /** Max minutes to wait for retest (only for retest entry). */
  retestMaxMin?: number;
  /** Target percent. Default 2 (strict). */
  targetPct?: number;
  /** Timeout hours. Default 24. */
  timeoutHours?: number;
}

export interface TradeRecord {
  zoneId: string;
  date: string;
  direction: Direction;
  triggerTs: number;
  /** Bucket second at entry */
  entrySec: number;
  /** Bucket second at exit (target/stop/timeout) */
  exitSec: number;
  entryPrice: number;
  exitPrice: number;
  exitReason: "target_2pct" | "stop" | "timeout";
  pnlPct: number;
  mfePct: number;
  maePct: number;
  timeInTradeH: number;
  usedStopPct: number;
}

export interface LedgerResult {
  trades: TradeRecord[];
  skippedDueToPosition: number;
  skippedNoData: number;
  skippedNoRetest: number;
}

const DEFAULT_TARGET_PCT = 2.0;
const DEFAULT_TIMEOUT_H = 24;

/** Binary-search index of first bucket with sec >= targetSec. */
export function getBucketIdxAtOrAfter(buckets: ReadonlyArray<Bucket>, targetSec: number): number {
  let lo = 0;
  let hi = buckets.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (buckets[mid].sec < targetSec) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export type SimOutcome =
  | { exitReason: "target_2pct" | "stop" | "timeout"; entrySec: number; exitSec: number; entryPrice: number; exitPrice: number; pnlPct: number; mfePct: number; maePct: number; usedStopPct: number }
  | { exitReason: "skip_no_retest" | "no_data" };

/**
 * Simulate one trade under the canonical model.
 * Walks `buckets` forward from the entry timestamp, exits at first of
 * (target, stop, timeout). Stop-first tie-break inside a single bucket.
 */
export function simulateCanonicalTrade(
  signal: Signal,
  buckets: ReadonlyArray<Bucket>,
  cfg: ExecutionConfig,
): SimOutcome {
  if (!buckets.length) return { exitReason: "no_data" };

  const targetPct = cfg.targetPct ?? DEFAULT_TARGET_PCT;
  const timeoutH = cfg.timeoutHours ?? DEFAULT_TIMEOUT_H;
  const trigSec = Math.floor(signal.triggerTs / 1000);

  // ---- 1. Determine entry sec ----
  let enterIdx = getBucketIdxAtOrAfter(buckets, trigSec);
  if (cfg.entryStrategy === "trigger") {
    // nothing extra
  } else if (cfg.entryStrategy.startsWith("delay_")) {
    const m = parseInt(cfg.entryStrategy.split("_")[1].replace("m", ""), 10);
    if (!Number.isFinite(m)) return { exitReason: "no_data" };
    enterIdx = getBucketIdxAtOrAfter(buckets, trigSec + m * 60);
  } else if (cfg.entryStrategy === "retest") {
    if (signal.zoneLow === undefined || signal.zoneHigh === undefined) {
      return { exitReason: "no_data" };
    }
    const gateEnd = trigSec + (cfg.retestMaxMin ?? 60) * 60;
    let found = -1;
    for (let idx = enterIdx; idx < buckets.length; idx++) {
      const b = buckets[idx];
      if (b.sec < trigSec) continue;
      if (b.sec > gateEnd) break;
      if (b.high >= signal.zoneLow && b.low <= signal.zoneHigh) {
        found = idx;
        break;
      }
    }
    if (found < 0) return { exitReason: "skip_no_retest" };
    enterIdx = found;
  } else {
    return { exitReason: "no_data" };
  }
  if (enterIdx >= buckets.length) return { exitReason: "no_data" };

  const entryBucket = buckets[enterIdx];
  const entrySec = entryBucket.sec;
  const entryPrice = entryBucket.last;
  if (!Number.isFinite(entryPrice) || entryPrice <= 0) return { exitReason: "no_data" };

  // ---- 2. Determine stop distance ----
  let usedStopPct: number;
  if (cfg.zoneBoundaryStop) {
    if (signal.direction === "LONG") {
      if (signal.zoneLow === undefined) return { exitReason: "no_data" };
      usedStopPct = ((entryPrice - signal.zoneLow) / entryPrice) * 100;
    } else {
      if (signal.zoneHigh === undefined) return { exitReason: "no_data" };
      usedStopPct = ((signal.zoneHigh - entryPrice) / entryPrice) * 100;
    }
  } else if (cfg.maxZoneBoundaryOrPct !== undefined) {
    let zbDist: number;
    if (signal.direction === "LONG" && signal.zoneLow !== undefined) {
      zbDist = ((entryPrice - signal.zoneLow) / entryPrice) * 100;
    } else if (signal.direction === "SHORT" && signal.zoneHigh !== undefined) {
      zbDist = ((signal.zoneHigh - entryPrice) / entryPrice) * 100;
    } else {
      zbDist = cfg.maxZoneBoundaryOrPct;
    }
    usedStopPct = Math.max(zbDist, cfg.maxZoneBoundaryOrPct);
  } else {
    usedStopPct = cfg.stopPct;
  }

  const target =
    signal.direction === "LONG"
      ? entryPrice * (1 + targetPct / 100)
      : entryPrice * (1 - targetPct / 100);
  const stop =
    signal.direction === "LONG"
      ? entryPrice * (1 - usedStopPct / 100)
      : entryPrice * (1 + usedStopPct / 100);
  const timeoutSec = entrySec + timeoutH * 3600;

  // ---- 3. Walk forward ----
  let mfe = 0;
  let mae = 0;
  let exitReason: "target_2pct" | "stop" | "timeout" = "timeout";
  let exitSec = timeoutSec;
  let exitPrice: number | undefined;

  for (let idx = enterIdx; idx < buckets.length; idx++) {
    const b = buckets[idx];
    if (b.sec > timeoutSec) break;
    let upPct: number;
    let dnPct: number;
    let targetHit: boolean;
    let stopHit: boolean;
    if (signal.direction === "LONG") {
      upPct = ((b.high - entryPrice) / entryPrice) * 100;
      dnPct = ((entryPrice - b.low) / entryPrice) * 100;
      targetHit = b.high >= target;
      stopHit = b.low <= stop;
    } else {
      upPct = ((entryPrice - b.low) / entryPrice) * 100;
      dnPct = ((b.high - entryPrice) / entryPrice) * 100;
      targetHit = b.low <= target;
      stopHit = b.high >= stop;
    }
    if (upPct > mfe) mfe = upPct;
    if (dnPct > mae) mae = dnPct;
    // Same-bucket tie-break: stop first (conservative)
    if (targetHit && stopHit) {
      exitReason = "stop";
      exitSec = b.sec;
      exitPrice = stop;
      break;
    }
    if (targetHit) {
      exitReason = "target_2pct";
      exitSec = b.sec;
      exitPrice = target;
      break;
    }
    if (stopHit) {
      exitReason = "stop";
      exitSec = b.sec;
      exitPrice = stop;
      break;
    }
  }
  if (exitReason === "timeout") {
    // Use bucket at or before timeout
    let lastIdx = enterIdx;
    for (let idx = enterIdx; idx < buckets.length; idx++) {
      if (buckets[idx].sec > timeoutSec) break;
      lastIdx = idx;
    }
    exitPrice = buckets[lastIdx].last;
    exitSec = buckets[lastIdx].sec;
  }
  if (exitPrice === undefined) return { exitReason: "no_data" };
  const sgn = signal.direction === "LONG" ? 1 : -1;
  const pnlPct = (sgn * (exitPrice - entryPrice)) / entryPrice * 100;
  return {
    exitReason,
    entrySec,
    exitSec,
    entryPrice,
    exitPrice,
    pnlPct: Number(pnlPct.toFixed(6)),
    mfePct: Number(mfe.toFixed(6)),
    maePct: Number(mae.toFixed(6)),
    usedStopPct,
  };
}

/**
 * Walk signals chronologically. One trade at a time.
 * KEY GUARANTEE: next signal allowed only when actual exit timestamp passes;
 *                NOT trigSec + 24h.
 */
export function canonicalLedgerWalk(
  signals: ReadonlyArray<Signal>,
  bucketsByDate: ReadonlyMap<string, ReadonlyArray<Bucket>>,
  cfg: ExecutionConfig,
): LedgerResult {
  const sorted = [...signals].sort((a, b) => a.triggerTs - b.triggerTs);
  const trades: TradeRecord[] = [];
  let openUntilSec = -1; // exclusive: signals at sec >= openUntilSec are allowed
  let skippedDueToPosition = 0;
  let skippedNoData = 0;
  let skippedNoRetest = 0;
  for (const sig of sorted) {
    const trigSec = Math.floor(sig.triggerTs / 1000);
    if (trigSec < openUntilSec) {
      skippedDueToPosition++;
      continue;
    }
    const buckets = bucketsByDate.get(sig.date);
    if (!buckets || buckets.length === 0) {
      skippedNoData++;
      continue;
    }
    const sim = simulateCanonicalTrade(sig, buckets, cfg);
    if (sim.exitReason === "skip_no_retest") {
      skippedNoRetest++;
      continue;
    }
    if (sim.exitReason === "no_data") {
      skippedNoData++;
      continue;
    }
    // Narrow to the success branch (TS discriminated union).
    const s = sim as Extract<typeof sim, { exitReason: "target_2pct" | "stop" | "timeout" }>;
    const timeInTradeH = (s.exitSec - s.entrySec) / 3600;
    trades.push({
      zoneId: sig.id,
      date: sig.date,
      direction: sig.direction,
      triggerTs: sig.triggerTs,
      entrySec: s.entrySec,
      exitSec: s.exitSec,
      entryPrice: s.entryPrice,
      exitPrice: s.exitPrice,
      exitReason: s.exitReason,
      pnlPct: s.pnlPct,
      mfePct: s.mfePct,
      maePct: s.maePct,
      timeInTradeH: Number(timeInTradeH.toFixed(4)),
      usedStopPct: s.usedStopPct,
    });
    // CRITICAL: actual exit, NOT trigSec + 24h.
    openUntilSec = s.exitSec;
  }
  return { trades, skippedDueToPosition, skippedNoData, skippedNoRetest };
}

export interface AggregateMetrics {
  nTrades: number;
  wins: number;
  losses: number;
  timeouts: number;
  winratePct: number | null;
  avgWinPct: number | null;
  avgLossPct: number | null;
  expectancyPctPerTrade: number | null;
  totalReturnPct1Unit: number | null;
  profitFactor: number | null;
  maxConsecutiveLosses: number;
  longN: number;
  longExpectancyPct: number | null;
  shortN: number;
  shortExpectancyPct: number | null;
}

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

export function aggregate(trades: ReadonlyArray<TradeRecord>): AggregateMetrics {
  const n = trades.length;
  const wins = trades.filter((t) => t.exitReason === "target_2pct").length;
  const losses = trades.filter((t) => t.exitReason === "stop").length;
  const timeouts = trades.filter((t) => t.exitReason === "timeout").length;
  const pnls = trades.map((t) => t.pnlPct);
  const winsPnls = pnls.filter((p) => p > 0);
  const lossesPnls = pnls.filter((p) => p < 0);
  const grossW = winsPnls.reduce((a, b) => a + b, 0);
  const grossL = lossesPnls.reduce((a, b) => a + -b, 0);
  let maxConsLosses = 0;
  let cur = 0;
  for (const t of trades) {
    if (t.pnlPct < 0) {
      cur++;
      if (cur > maxConsLosses) maxConsLosses = cur;
    } else {
      cur = 0;
    }
  }
  const longP = trades.filter((t) => t.direction === "LONG").map((t) => t.pnlPct);
  const shortP = trades.filter((t) => t.direction === "SHORT").map((t) => t.pnlPct);
  return {
    nTrades: n,
    wins,
    losses,
    timeouts,
    winratePct: n ? Number(((100 * wins) / n).toFixed(2)) : null,
    avgWinPct: winsPnls.length ? Number(mean(winsPnls).toFixed(4)) : null,
    avgLossPct: lossesPnls.length ? Number(mean(lossesPnls).toFixed(4)) : null,
    expectancyPctPerTrade: pnls.length ? Number(mean(pnls).toFixed(4)) : null,
    totalReturnPct1Unit: pnls.length ? Number(pnls.reduce((a, b) => a + b, 0).toFixed(4)) : null,
    profitFactor: grossL > 0 ? Number((grossW / grossL).toFixed(3)) : grossW === 0 ? null : Infinity,
    maxConsecutiveLosses: maxConsLosses,
    longN: longP.length,
    longExpectancyPct: longP.length ? Number(mean(longP).toFixed(4)) : null,
    shortN: shortP.length,
    shortExpectancyPct: shortP.length ? Number(mean(shortP).toFixed(4)) : null,
  };
}
