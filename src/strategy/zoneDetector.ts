// ZoneDetector - the heart of the strategy.
//
// Reads FeatureRows in time order and emits/maintains a list of zones with
// state transitions per the spec (§8). Both LONG-Accumulation and
// SHORT-Distribution zones are detected with mirrored conditions.
//
// All thresholds come from `StrategyConfig.zone.*`.

import type {
  FeatureRow,
  StrategyConfig,
  SuppressionRecord,
  Zone,
  ZoneDirection,
  ZoneReason,
} from "./types.js";
import { transition } from "./zoneStateMachine.js";
import { parseHorizon } from "../data/time.js";

let zoneSeq = 0;
function makeZoneId(symbol: string, dir: ZoneDirection, ts: number): string {
  zoneSeq += 1;
  return `${symbol}-${dir}-${ts}-${zoneSeq}`;
}

interface OpenZoneState {
  zone: Zone;
  // tracking for transitions
  candidateStart: number;
  cyclesSeen: number; // number of feature rows that meet candidate conditions
  defendedPersistenceMs: number;
  lastCycleTs: number;
  zoneLowAcc: number;
  zoneHighAcc: number;
  // baseline trade flow magnitude when candidate started, used for trigger ratio.
  baselineFlow: number;
}

export class ZoneDetector {
  private readonly cfg: StrategyConfig;
  private openZones: OpenZoneState[] = [];
  private resolvedZones: Zone[] = [];
  private readonly symbol: string;
  private readonly date: string;
  private readonly suppressionRecords: SuppressionRecord[] = [];
  private readonly maxHorizonMs: number;

  constructor(cfg: StrategyConfig, symbol: string, date: string) {
    this.cfg = cfg;
    this.symbol = symbol;
    this.date = date;
    let h = 0;
    for (const horizon of cfg.targetChecker?.horizons ?? []) {
      try {
        const v = parseHorizon(horizon);
        if (v > h) h = v;
      } catch {
        /* ignore unparseable */
      }
    }
    // Default to 24h if no horizons configured.
    this.maxHorizonMs = h > 0 ? h : 24 * 3_600_000;
  }

  /** Suppression log accessor — used by reports. */
  suppressions(): SuppressionRecord[] {
    return this.suppressionRecords.slice();
  }
  suppressionCount(): number {
    return this.suppressionRecords.length;
  }

  ingest(row: FeatureRow): void {
    this.maybeOpenCandidate(row, "LONG");
    this.maybeOpenCandidate(row, "SHORT");
    this.advanceOpenZones(row);
  }

  private maybeOpenCandidate(row: FeatureRow, dir: ZoneDirection): void {
    const c = this.cfg.zone.candidate;
    if (row.qualityFlags.includes("EMPTY_BOOK") || row.qualityFlags.includes("NO_BBO")) return;

    const sellPressure = row.pressure.sellPressure;
    const buyPressure = row.pressure.buyPressure;
    const refillBid = row.liquidityEvents.bidRefillScore;
    const refillAsk = row.liquidityEvents.askRefillScore;
    const absLong = row.absorption.buyAbsorptionScore;
    const absShort = row.absorption.sellAbsorptionScore;
    const downMove = row.absorption.priceProgressDownPct;
    const upMove = row.absorption.priceProgressUpPct;

    const hits: Record<string, number | boolean> = {};
    let pass = false;
    if (dir === "LONG") {
      hits["sellPressure"] = sellPressure;
      hits["bidRefillScore"] = refillBid;
      hits["downMovePct"] = downMove;
      hits["absorbScore"] = absLong;
      hits["rangeCompression"] = row.rangeCompression;
      pass =
        sellPressure >= c.minSidedPressure &&
        refillBid >= c.minRefillScore &&
        downMove <= this.cfg.zone.maxNoProgressPct &&
        absLong >= this.cfg.zone.minAbsorptionScore &&
        row.rangeCompression;
    } else {
      hits["buyPressure"] = buyPressure;
      hits["askRefillScore"] = refillAsk;
      hits["upMovePct"] = upMove;
      hits["absorbScore"] = absShort;
      hits["rangeCompression"] = row.rangeCompression;
      pass =
        buyPressure >= c.minSidedPressure &&
        refillAsk >= c.minRefillScore &&
        upMove <= this.cfg.zone.maxNoProgressPct &&
        absShort >= this.cfg.zone.minAbsorptionScore &&
        row.rangeCompression;
    }

    if (!pass) return;
    const mid = row.book.mid ?? row.book.bestBid ?? row.book.bestAsk ?? 0;
    if (mid <= 0) return;
    const halfWidth = mid * 0.0005; // initial half-width 0.05% — grows with absorption cycles.

    // Deduplication: same-direction overlap suppression + cooldown.
    // Replaces the previous coarse "any same-direction open zone blocks" rule
    // with a finer rule that also considers TRIGGERED zones still tracking
    // their target, and a cooldown after termination. NOT a threshold change.
    // When dedup is disabled, the legacy openZones-only block is preserved
    // silently (no record) for backward compatibility.
    const suppression = this.checkDedup(dir, mid - halfWidth, mid + halfWidth, row.ts);
    if (suppression) {
      if (this.cfg.deduplication?.enabled) {
        this.suppressionRecords.push(suppression);
      }
      return;
    }
    const zone: Zone = {
      id: makeZoneId(this.symbol, dir, row.ts),
      symbol: this.symbol,
      date: this.date,
      direction: dir,
      zoneType: dir === "LONG" ? "ACCUMULATION" : "DISTRIBUTION",
      status: "CANDIDATE",
      startTs: row.ts,
      zoneLow: mid - halfWidth,
      zoneHigh: mid + halfWidth,
      scores: {
        absorptionScore: dir === "LONG" ? absLong : absShort,
        liquidityVoidScore: dir === "LONG" ? row.liquidityVoid.voidUp2PctScore : row.liquidityVoid.voidDown2PctScore,
        ofiScore: row.imbalance["0.5"] ?? 0,
        refillScore: dir === "LONG" ? refillBid : refillAsk,
      },
      qualityFlags: row.qualityFlags.slice(),
      targets: {},
      reasons: [
        {
          stage: "candidate",
          ts: row.ts,
          conditions: hits,
          notes: dir === "LONG" ? "Long Accumulation candidate" : "Short Distribution candidate",
        },
      ],
    };
    const refKey = this.cfg.tradeWindowsSec[this.cfg.tradeWindowsSec.length - 1].toString();
    const refTrades = row.trades.windows[refKey];
    const baselineFlow = (refTrades?.buyVolume ?? 0) + (refTrades?.sellVolume ?? 0);
    this.openZones.push({
      zone,
      candidateStart: row.ts,
      cyclesSeen: 1,
      defendedPersistenceMs: 0,
      lastCycleTs: row.ts,
      zoneLowAcc: zone.zoneLow,
      zoneHighAcc: zone.zoneHigh,
      baselineFlow,
    });
  }

  private advanceOpenZones(row: FeatureRow): void {
    const cfgZ = this.cfg.zone;
    const stillOpen: OpenZoneState[] = [];
    for (const o of this.openZones) {
      const z = o.zone;
      const mid = row.book.mid ?? null;
      if (mid !== null) {
        // Keep zone bounds wider as cycles continue (until confirmed).
        if (mid < o.zoneLowAcc) o.zoneLowAcc = mid;
        if (mid > o.zoneHighAcc) o.zoneHighAcc = mid;
      }
      const dwellMin = (row.ts - z.startTs) / 60_000;
      if (dwellMin > cfgZ.maxFormationDurationMin && z.status === "CANDIDATE") {
        transition(z, "EXPIRED", {
          stage: "expire",
          ts: row.ts,
          conditions: { dwellMin, maxFormationDurationMin: cfgZ.maxFormationDurationMin },
          notes: "Candidate aged out without confirmation",
        });
        z.zoneLow = o.zoneLowAcc;
        z.zoneHigh = o.zoneHighAcc;
        this.resolvedZones.push(z);
        continue;
      }

      // CANDIDATE -> CONFIRMED
      if (z.status === "CANDIDATE") {
        const refillKey = z.direction === "LONG" ? row.liquidityEvents.bidRefillScore : row.liquidityEvents.askRefillScore;
        const absKey = z.direction === "LONG" ? row.absorption.buyAbsorptionScore : row.absorption.sellAbsorptionScore;
        const conditionMet =
          refillKey >= cfgZ.candidate.minRefillScore &&
          absKey >= cfgZ.minAbsorptionScore &&
          (z.direction === "LONG"
            ? row.absorption.priceProgressDownPct <= cfgZ.maxNoProgressPct
            : row.absorption.priceProgressUpPct <= cfgZ.maxNoProgressPct);
        if (conditionMet) {
          o.cyclesSeen += 1;
          if (row.ts - o.lastCycleTs > 0) o.defendedPersistenceMs += row.ts - o.lastCycleTs;
          o.lastCycleTs = row.ts;
        }
        const ageMin = (row.ts - z.startTs) / 60_000;
        const oppositeThinning =
          z.direction === "LONG" ? row.liquidityEvents.askThinningScore : row.liquidityEvents.bidThinningScore;
        const voidScore =
          z.direction === "LONG" ? row.liquidityVoid.voidUp2PctScore : row.liquidityVoid.voidDown2PctScore;
        const canConfirm =
          o.cyclesSeen >= cfgZ.minAbsorptionCycles &&
          ageMin >= cfgZ.minCandidateDurationMin &&
          o.defendedPersistenceMs / 1000 >= cfgZ.confirmed.minDefendedPersistenceSec &&
          (oppositeThinning >= cfgZ.confirmed.minOppositeThinningScore ||
            voidScore >= cfgZ.minLiquidityVoidScore);
        if (canConfirm) {
          z.zoneLow = o.zoneLowAcc;
          z.zoneHigh = o.zoneHighAcc;
          z.scores.absorptionScore = absKey;
          z.scores.liquidityVoidScore = voidScore;
          z.scores.refillScore = refillKey;
          transition(z, "CONFIRMED", {
            stage: "confirmed",
            ts: row.ts,
            conditions: {
              cyclesSeen: o.cyclesSeen,
              ageMin,
              defendedPersistenceSec: o.defendedPersistenceMs / 1000,
              oppositeThinning,
              voidScore,
            },
            notes: "Candidate matured into confirmed zone",
          });
        }
      }

      // CONFIRMED -> TRIGGERED
      if (z.status === "CONFIRMED") {
        const refKey = this.cfg.tradeWindowsSec[this.cfg.tradeWindowsSec.length - 1].toString();
        const w = row.trades.windows[refKey];
        const flow = (w?.buyVolume ?? 0) + (w?.sellVolume ?? 0);
        const flowMultiplier = o.baselineFlow > 0 ? flow / o.baselineFlow : 0;
        const minBreak = this.cfg.zone.trigger.minBreakDistancePct / 100;
        const breakDistLong = mid !== null ? (mid - z.zoneHigh) / Math.max(1e-9, z.zoneHigh) : 0;
        const breakDistShort = mid !== null ? (z.zoneLow - mid) / Math.max(1e-9, z.zoneLow) : 0;
        const sideFlowOK =
          z.direction === "LONG" ? row.pressure.buyPressure >= 0.55 : row.pressure.sellPressure >= 0.55;
        const triggerOK =
          z.direction === "LONG"
            ? breakDistLong >= minBreak && sideFlowOK && flowMultiplier >= this.cfg.zone.trigger.minAggressiveFlowMultiplier
            : breakDistShort >= minBreak && sideFlowOK && flowMultiplier >= this.cfg.zone.trigger.minAggressiveFlowMultiplier;
        if (triggerOK && mid !== null) {
          z.triggerPrice = mid;
          z.referencePrice = mid;
          z.targetPrice =
            z.direction === "LONG" ? mid * (1 + this.cfg.targetPct / 100) : mid * (1 - this.cfg.targetPct / 100);
          z.scores.triggerScore = clamp01(flowMultiplier / 3 + (z.direction === "LONG" ? row.liquidityEvents.askThinningScore : row.liquidityEvents.bidThinningScore));
          transition(z, "TRIGGERED", {
            stage: "trigger",
            ts: row.ts,
            conditions: {
              breakPct: z.direction === "LONG" ? breakDistLong * 100 : breakDistShort * 100,
              flowMultiplier,
              sideFlowOK,
              triggerPrice: mid,
              targetPrice: z.targetPrice,
            },
            notes: "Triggered: break + flow + opposite-side thinning",
          });
          this.resolvedZones.push(z); // zone leaves "open" set; TargetChecker resolves later
          continue;
        }
        // Invalidate if price moves strongly against zone.
        if (mid !== null) {
          const adverse =
            z.direction === "LONG" ? mid < z.zoneLow * 0.995 : mid > z.zoneHigh * 1.005;
          if (adverse) {
            transition(z, "INVALIDATED", {
              stage: "invalidate",
              ts: row.ts,
              conditions: { mid, zoneLow: z.zoneLow, zoneHigh: z.zoneHigh },
              notes: "Price moved through defended side without trigger",
            });
            this.resolvedZones.push(z);
            continue;
          }
        }
      }
      stillOpen.push(o);
    }
    this.openZones = stillOpen;
  }

  finalize(lastTs: number): void {
    for (const o of this.openZones) {
      const z = o.zone;
      // Mark unfinished candidates / confirmed as NO_TRIGGER so they appear
      // in the report, per spec §13: "save all zones".
      if (z.status === "CANDIDATE" || z.status === "CONFIRMED") {
        transition(z, "NO_TRIGGER", {
          stage: "expire",
          ts: lastTs,
          conditions: { reason: "End of replay; no trigger seen" },
        });
        z.zoneLow = o.zoneLowAcc;
        z.zoneHigh = o.zoneHighAcc;
        this.resolvedZones.push(z);
      }
    }
    this.openZones = [];
  }

  zones(): Zone[] {
    return this.resolvedZones.slice();
  }

  /**
   * Returns a suppression record if a new same-direction candidate at
   * [proposedLow, proposedHigh] / time `ts` should be SUPPRESSED, or null
   * to allow.
   *
   * Rules (only applied when cfg.deduplication.enabled === true and
   * cfg.deduplication.sameDirectionOverlapSuppression === true):
   *   1. If any zone in `openZones` (status CANDIDATE/CONFIRMED) has the
   *      same direction and price-overlaps the proposed band by at least
   *      cfg.deduplication.priceOverlapMinPct → suppress (active_open).
   *   2. If any zone in `resolvedZones` with status TRIGGERED has the same
   *      direction, price-overlaps, and (ts - z.triggerTs) <= maxHorizonMs
   *      (the zone is still tracking its 2% target) → suppress
   *      (active_triggered).
   *   3. If any zone in `resolvedZones` with terminal status (INVALIDATED,
   *      EXPIRED, NO_TRIGGER, RESOLVED_*) has the same direction,
   *      price-overlaps, and (ts - z.resolvedTs) <= cooldownMs → suppress
   *      (cooldown).
   */
  private checkDedup(
    direction: ZoneDirection,
    proposedLow: number,
    proposedHigh: number,
    ts: number
  ): SuppressionRecord | null {
    const dd = this.cfg.deduplication;
    if (!dd || !dd.enabled || !dd.sameDirectionOverlapSuppression) {
      // Legacy fallback: still suppress duplicates inside openZones to
      // avoid emitting the same active candidate twice.
      for (const o of this.openZones) {
        if (
          o.zone.direction === direction &&
          (o.zone.status === "CANDIDATE" || o.zone.status === "CONFIRMED")
        ) {
          return {
            ts,
            direction,
            proposedLow,
            proposedHigh,
            suppressedByZoneId: o.zone.id,
            reason: "active_open",
            overlapPct: 1,
          };
        }
      }
      return null;
    }

    const minOverlap = dd.priceOverlapMinPct ?? 0.25;
    const cooldownMs = (dd.cooldownMinutesAfterResolve ?? 30) * 60_000;

    // 1. Active CANDIDATE / CONFIRMED zones in openZones.
    for (const o of this.openZones) {
      const z = o.zone;
      if (z.direction !== direction) continue;
      if (z.status !== "CANDIDATE" && z.status !== "CONFIRMED") continue;
      const op = priceOverlapPct(proposedLow, proposedHigh, z.zoneLow, z.zoneHigh);
      if (op < minOverlap) continue;
      return {
        ts,
        direction,
        proposedLow,
        proposedHigh,
        suppressedByZoneId: z.id,
        reason: "active_open",
        overlapPct: op,
      };
    }

    // 2 & 3. Triggered (still tracking target) and terminated zones in resolvedZones.
    for (const z of this.resolvedZones) {
      if (z.direction !== direction) continue;
      const op = priceOverlapPct(proposedLow, proposedHigh, z.zoneLow, z.zoneHigh);
      if (op < minOverlap) continue;
      if (z.status === "TRIGGERED" && z.triggerTs !== undefined) {
        if (ts - z.triggerTs <= this.maxHorizonMs) {
          return {
            ts,
            direction,
            proposedLow,
            proposedHigh,
            suppressedByZoneId: z.id,
            reason: "active_triggered",
            overlapPct: op,
          };
        }
        continue;
      }
      // Terminal statuses → cooldown applies for cooldownMs after resolvedTs.
      const endTs = z.resolvedTs ?? z.triggerTs ?? z.confirmedTs ?? z.startTs;
      if (ts - endTs <= cooldownMs) {
        return {
          ts,
          direction,
          proposedLow,
          proposedHigh,
          suppressedByZoneId: z.id,
          reason: "cooldown",
          overlapPct: op,
        };
      }
    }
    return null;
  }
}

/** Overlap fraction relative to the smaller zone's price height. */
function priceOverlapPct(aLow: number, aHigh: number, bLow: number, bHigh: number): number {
  const lo = Math.max(aLow, bLow);
  const hi = Math.min(aHigh, bHigh);
  if (hi <= lo) return 0;
  const overlap = hi - lo;
  const aH = Math.max(0, aHigh - aLow);
  const bH = Math.max(0, bHigh - bLow);
  const refH = Math.max(1e-9, Math.min(aH, bH));
  return overlap / refH;
}

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}
