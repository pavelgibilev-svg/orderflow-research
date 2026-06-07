// Naive baseline probability of a 2% move within a horizon, computed from
// raw price walk on the day. This is a "what's the unconditional chance"
// number you can compare against zone hit rates — it intentionally does NOT
// know about zones.

import { parseHorizon } from "../data/time.js";
import type { TradePoint } from "./targetChecker.js";

export interface BaselineResult {
  horizon: string;
  targetPct: number;
  totalSamples: number;
  upHits: number;
  downHits: number;
  upRate: number;
  downRate: number;
}

/**
 * For every minute of the day, check whether price ever moved +/- targetPct
 * within `horizonMs` after that minute. Returns the empirical hit rates.
 */
export function computeBaseline(
  trades: TradePoint[],
  horizon: string,
  targetPct: number,
  stepSec = 60
): BaselineResult {
  const horMs = parseHorizon(horizon);
  if (trades.length === 0) {
    return { horizon, targetPct, totalSamples: 0, upHits: 0, downHits: 0, upRate: 0, downRate: 0 };
  }
  let total = 0,
    up = 0,
    dn = 0;
  const stepMs = stepSec * 1000;
  let nextSampleTs = trades[0].ts;
  let i = 0;
  while (nextSampleTs <= trades[trades.length - 1].ts - horMs) {
    while (i < trades.length && trades[i].ts < nextSampleTs) i++;
    if (i >= trades.length) break;
    const start = trades[i];
    const targetUp = start.price * (1 + targetPct / 100);
    const targetDn = start.price * (1 - targetPct / 100);
    let reachedUp = false,
      reachedDn = false;
    for (let j = i; j < trades.length; j++) {
      if (trades[j].ts > start.ts + horMs) break;
      if (!reachedUp && trades[j].price >= targetUp) reachedUp = true;
      if (!reachedDn && trades[j].price <= targetDn) reachedDn = true;
      if (reachedUp && reachedDn) break;
    }
    total += 1;
    if (reachedUp) up += 1;
    if (reachedDn) dn += 1;
    nextSampleTs += stepMs;
  }
  return {
    horizon,
    targetPct,
    totalSamples: total,
    upHits: up,
    downHits: dn,
    upRate: total > 0 ? up / total : 0,
    downRate: total > 0 ? dn / total : 0,
  };
}
