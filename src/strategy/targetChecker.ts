// TargetChecker
//
// For every zone with status TRIGGERED, scan trade prices forward from the
// trigger time and answer the only question that matters in the spec:
//   "Did price reach +2% (long) or -2% (short) within horizon?"
//
// We compute, per horizon:
//   - outcome (reached / failed_by_timeout / invalid_data / no_trigger /
//     invalidated_before_trigger)
//   - timeToTargetMin, MFE, MAE, maxDrawdownBeforeTarget
//
// All metrics are based on observed trade prices. We do NOT use mid-prices
// because Tardis trades reflect actual transacted prices.

import type {
  StrategyConfig,
  TargetOutcome,
  Zone,
  ZoneTargetMetrics,
} from "./types.js";
import { parseHorizon } from "../data/time.js";

export interface TradePoint {
  ts: number;
  price: number;
}

export class TargetChecker {
  private readonly cfg: StrategyConfig;
  private readonly trades: TradePoint[];
  constructor(cfg: StrategyConfig, trades: TradePoint[]) {
    this.cfg = cfg;
    // Trades MUST be sorted by ts; copy to avoid mutating caller.
    this.trades = trades;
  }

  resolveZone(zone: Zone): void {
    if (zone.status === "INVALIDATED") {
      for (const h of this.cfg.targetChecker.horizons) {
        zone.targets[h] = { horizon: h, outcome: "invalidated_before_trigger" };
      }
      // status stays INVALIDATED
      return;
    }
    if (zone.status !== "TRIGGERED") {
      for (const h of this.cfg.targetChecker.horizons) {
        zone.targets[h] = { horizon: h, outcome: "no_trigger" };
      }
      return;
    }
    if (zone.triggerTs === undefined || zone.triggerPrice === undefined) {
      for (const h of this.cfg.targetChecker.horizons) {
        zone.targets[h] = { horizon: h, outcome: "invalid_data" };
      }
      return;
    }

    const direction = zone.direction;
    const ref = zone.referencePrice ?? zone.triggerPrice;
    const targetPct = this.cfg.targetPct / 100;
    const targetPrice = direction === "LONG" ? ref * (1 + targetPct) : ref * (1 - targetPct);

    // Find first trade index >= triggerTs (binary search).
    const i0 = lowerBound(this.trades, zone.triggerTs!);

    let anyReached = false;
    let earliestReachedHorizon: string | null = null;
    for (const h of this.cfg.targetChecker.horizons) {
      const horMs = parseHorizon(h);
      const endTs = zone.triggerTs! + horMs;
      let mfeAbs = -Infinity;
      let maeAbs = +Infinity;
      let maxDDBeforeTargetPct = 0;
      let reachedAt: number | null = null;
      let endPrice = ref;

      for (let i = i0; i < this.trades.length; i++) {
        const t = this.trades[i];
        if (t.ts > endTs) break;
        if (direction === "LONG") {
          if (t.price > mfeAbs) mfeAbs = t.price;
          if (t.price < maeAbs) maeAbs = t.price;
        } else {
          if (t.price < mfeAbs || mfeAbs === -Infinity) mfeAbs = t.price; // for short MFE = lowest low
          if (t.price > maeAbs || maeAbs === +Infinity) maeAbs = t.price; // for short MAE = highest high
        }
        if (reachedAt === null) {
          // Track running drawdown against direction.
          if (direction === "LONG") {
            const dd = ((ref - t.price) / ref) * 100;
            if (dd > maxDDBeforeTargetPct) maxDDBeforeTargetPct = dd;
            if (t.price >= targetPrice) reachedAt = t.ts;
          } else {
            const dd = ((t.price - ref) / ref) * 100;
            if (dd > maxDDBeforeTargetPct) maxDDBeforeTargetPct = dd;
            if (t.price <= targetPrice) reachedAt = t.ts;
          }
        }
        endPrice = t.price;
      }

      let outcome: TargetOutcome = "failed_by_timeout";
      if (reachedAt !== null) {
        outcome = "reached";
        anyReached = true;
        if (earliestReachedHorizon === null) earliestReachedHorizon = h;
      }
      const m: ZoneTargetMetrics = {
        horizon: h,
        outcome,
        endPrice,
        endTs,
      };
      if (reachedAt !== null) {
        m.reachedAt = reachedAt;
        m.timeToTargetMin = (reachedAt - zone.triggerTs!) / 60_000;
      }
      if (Number.isFinite(mfeAbs) && mfeAbs !== -Infinity) {
        m.mfePct = direction === "LONG" ? ((mfeAbs - ref) / ref) * 100 : ((ref - mfeAbs) / ref) * 100;
      }
      if (Number.isFinite(maeAbs) && maeAbs !== +Infinity) {
        m.maePct =
          direction === "LONG" ? ((ref - maeAbs) / ref) * 100 : ((maeAbs - ref) / ref) * 100;
      }
      m.maxDrawdownBeforeTargetPct = maxDDBeforeTargetPct;
      zone.targets[h] = m;
    }

    if (anyReached) {
      zone.status = "RESOLVED_REACHED";
      zone.resolvedTs = zone.targets[earliestReachedHorizon!].reachedAt;
      zone.reasons.push({
        stage: "expire",
        ts: zone.resolvedTs ?? zone.triggerTs!,
        conditions: { earliestReachedHorizon, targetPrice },
        notes: `Target reached on horizon ${earliestReachedHorizon}`,
      });
    } else {
      zone.status = "RESOLVED_FAILED";
      zone.resolvedTs = zone.triggerTs! + parseHorizon(this.cfg.targetChecker.horizons[this.cfg.targetChecker.horizons.length - 1]);
      zone.reasons.push({
        stage: "expire",
        ts: zone.resolvedTs,
        conditions: { allHorizonsFailed: true, targetPrice },
        notes: "No horizon reached the target",
      });
    }
  }
}

function lowerBound(arr: TradePoint[], ts: number): number {
  let lo = 0,
    hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (arr[mid].ts < ts) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}
