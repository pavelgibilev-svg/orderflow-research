// Unique-move clustering — post-processing accounting fix.
//
// Why: after deduplication, multiple RESOLVED_REACHED zones can still get
// credited for the same underlying directional move (e.g. four SHORT zones
// at progressively lower prices that all reach the same low during one
// multi-hour bear leg). This module groups such zones into a single
// `uniqueMoveId` so the headline hit rate counts moves, not zone-credits.
//
// Pure function — does NOT change strategy thresholds, the detector, or
// target-checker logic. It just augments each zone with bookkeeping fields:
//   - uniqueMoveId
//   - moveClusterSize
//   - isPrimaryMoveZone   (true only on the earliest-trigger zone in a cluster)
//   - duplicateMoveCredit (true on the others in the same cluster)
//
// Failed / no_trigger / invalidated / expired zones are intentionally left
// untouched; the four bookkeeping fields stay undefined.
//
// Algorithm (`sameDirectionOnly=true` mode):
//   1. Filter to zones with status RESOLVED_REACHED and a defined triggerTs.
//   2. Compute reachedAt per zone (earliest target.reachedAt).
//   3. Sort within each direction by triggerTs ascending.
//   4. Sweep: start a new cluster with the first zone; for each subsequent
//      zone, attach to the most-recent cluster if its triggerTs falls within
//      `cluster.maxReachedAt + gapMs`; otherwise open a new cluster.
//   5. In each cluster pick the primary zone = earliest triggerTs (then
//      highest absorption × void × trigger composite score as tie-break).

import type { MoveClusteringConfig, Zone, ZoneDirection } from "./types.js";

export interface UniqueMoveCluster {
  uniqueMoveId: number;
  direction: ZoneDirection;
  triggerWindowStart: number;
  triggerWindowEnd: number;
  reachedAtMin: number;
  reachedAtMax: number;
  zoneIds: string[];
  primaryZoneId: string;
  size: number;
}

export interface MoveClusteringResult {
  clusters: UniqueMoveCluster[];
  reachedZonesRaw: number;
  uniqueReachedMoves: number;
  duplicateMoveCredits: number;
  /** raw / triggered. Same number as the previous "triggered hit rate". */
  rawTriggeredHitRate: number;
  /** uniqueReachedMoves / triggered. The honest headline metric. */
  uniqueMoveAdjustedHitRate: number;
}

const DEFAULT_CFG: MoveClusteringConfig = {
  enabled: true,
  clusterReachedZones: true,
  moveClusterGapMinutes: 120,
  sameDirectionOnly: true,
};

function reachedAtOf(z: Zone): number {
  for (const t of Object.values(z.targets)) {
    if (t.outcome === "reached" && t.reachedAt !== undefined) return t.reachedAt;
  }
  return z.resolvedTs ?? z.triggerTs ?? 0;
}

function compositeScore(z: Zone): number {
  const a = z.scores.absorptionScore ?? 0;
  const v = z.scores.liquidityVoidScore ?? 0;
  const t = z.scores.triggerScore ?? a;
  return a * v * t;
}

/**
 * Apply unique-move clustering in place.
 *   - Mutates zones with RESOLVED_REACHED status to set the four bookkeeping fields.
 *   - Returns a `MoveClusteringResult` summary for reports.
 *   - When `cfg.enabled === false` (or undefined), returns an empty result and
 *     leaves the zones untouched.
 *
 * The function is idempotent: calling it twice with the same input produces
 * the same output.
 */
export function applyMoveClustering(
  zones: Zone[],
  cfg: MoveClusteringConfig | undefined,
  triggeredCount?: number
): MoveClusteringResult {
  // Reset any prior clustering bookkeeping so this is idempotent.
  for (const z of zones) {
    z.uniqueMoveId = undefined;
    z.moveClusterSize = undefined;
    z.isPrimaryMoveZone = undefined;
    z.duplicateMoveCredit = undefined;
  }

  const reachedZonesRaw = zones.filter((z) => z.status === "RESOLVED_REACHED" && z.triggerTs !== undefined).length;
  const triggered = triggeredCount ?? zones.filter((z) => z.triggerTs !== undefined).length;

  const empty: MoveClusteringResult = {
    clusters: [],
    reachedZonesRaw,
    uniqueReachedMoves: reachedZonesRaw,
    duplicateMoveCredits: 0,
    rawTriggeredHitRate: triggered > 0 ? reachedZonesRaw / triggered : 0,
    uniqueMoveAdjustedHitRate: triggered > 0 ? reachedZonesRaw / triggered : 0,
  };

  const c = cfg && cfg.enabled && cfg.clusterReachedZones ? cfg : null;
  if (c === null) return empty;

  const reached = zones
    .filter((z) => z.status === "RESOLVED_REACHED" && z.triggerTs !== undefined)
    .map((z) => ({ z, trig: z.triggerTs!, reached: reachedAtOf(z) }));

  if (reached.length === 0) {
    return {
      ...empty,
      uniqueReachedMoves: 0,
      uniqueMoveAdjustedHitRate: triggered > 0 ? 0 : 0,
    };
  }

  const gapMs = c.moveClusterGapMinutes * 60_000;
  const directions: ZoneDirection[] = c.sameDirectionOnly
    ? (Array.from(new Set(reached.map((r) => r.z.direction))) as ZoneDirection[])
    : ["LONG"]; // when sameDirectionOnly=false we still split into one virtual bucket;
                // current behavior in the codebase always honours sameDirectionOnly.

  const clusters: UniqueMoveCluster[] = [];
  let nextId = 1;

  for (const dir of directions) {
    const dirReached = c.sameDirectionOnly
      ? reached.filter((r) => r.z.direction === dir)
      : reached;
    if (dirReached.length === 0) continue;
    dirReached.sort((a, b) => a.trig - b.trig);

    interface ActiveCluster {
      id: number;
      direction: ZoneDirection;
      members: Array<{ z: Zone; trig: number; reached: number }>;
      triggerWindowStart: number;
      triggerWindowEnd: number;
      reachedAtMin: number;
      reachedAtMax: number;
    }

    let active: ActiveCluster | null = null;
    const finishedClusters: ActiveCluster[] = [];

    for (const r of dirReached) {
      if (active === null) {
        active = {
          id: nextId++,
          direction: r.z.direction,
          members: [r],
          triggerWindowStart: r.trig,
          triggerWindowEnd: r.trig,
          reachedAtMin: r.reached,
          reachedAtMax: r.reached,
        };
        continue;
      }
      // Cluster on EITHER:
      //   (a) [trigger,reached] windows overlap, OR
      //   (b) the new triggerTs is within `gap` of the cluster's max reached time.
      const overlap = r.trig <= active.reachedAtMax && active.triggerWindowStart <= r.reached;
      const withinGap = r.trig <= active.reachedAtMax + gapMs;
      if (overlap || withinGap) {
        active.members.push(r);
        if (r.trig < active.triggerWindowStart) active.triggerWindowStart = r.trig;
        if (r.trig > active.triggerWindowEnd) active.triggerWindowEnd = r.trig;
        if (r.reached < active.reachedAtMin) active.reachedAtMin = r.reached;
        if (r.reached > active.reachedAtMax) active.reachedAtMax = r.reached;
      } else {
        finishedClusters.push(active);
        active = {
          id: nextId++,
          direction: r.z.direction,
          members: [r],
          triggerWindowStart: r.trig,
          triggerWindowEnd: r.trig,
          reachedAtMin: r.reached,
          reachedAtMax: r.reached,
        };
      }
    }
    if (active !== null) finishedClusters.push(active);

    for (const cluster of finishedClusters) {
      // Primary = earliest triggerTs; tiebreak by composite score descending.
      const sortedByPriority = cluster.members.slice().sort((a, b) => {
        if (a.trig !== b.trig) return a.trig - b.trig;
        return compositeScore(b.z) - compositeScore(a.z);
      });
      const primaryId = sortedByPriority[0].z.id;

      for (const m of cluster.members) {
        m.z.uniqueMoveId = cluster.id;
        m.z.moveClusterSize = cluster.members.length;
        m.z.isPrimaryMoveZone = m.z.id === primaryId;
        m.z.duplicateMoveCredit = m.z.id !== primaryId;
      }

      clusters.push({
        uniqueMoveId: cluster.id,
        direction: cluster.direction,
        triggerWindowStart: cluster.triggerWindowStart,
        triggerWindowEnd: cluster.triggerWindowEnd,
        reachedAtMin: cluster.reachedAtMin,
        reachedAtMax: cluster.reachedAtMax,
        zoneIds: cluster.members.map((m) => m.z.id),
        primaryZoneId: primaryId,
        size: cluster.members.length,
      });
    }
  }

  // Stable order: by direction, then by triggerWindowStart.
  clusters.sort((a, b) => {
    if (a.direction !== b.direction) return a.direction < b.direction ? -1 : 1;
    return a.triggerWindowStart - b.triggerWindowStart;
  });
  // Re-number clusters so primary IDs match sort order — easier to read in reports.
  const remap = new Map<number, number>();
  clusters.forEach((cl, idx) => remap.set(cl.uniqueMoveId, idx + 1));
  for (const cluster of clusters) {
    cluster.uniqueMoveId = remap.get(cluster.uniqueMoveId) ?? cluster.uniqueMoveId;
    for (const zid of cluster.zoneIds) {
      const z = zones.find((zz) => zz.id === zid);
      if (z) z.uniqueMoveId = cluster.uniqueMoveId;
    }
  }

  const uniqueReachedMoves = clusters.length;
  const duplicateMoveCredits = reachedZonesRaw - uniqueReachedMoves;
  return {
    clusters,
    reachedZonesRaw,
    uniqueReachedMoves,
    duplicateMoveCredits,
    rawTriggeredHitRate: triggered > 0 ? reachedZonesRaw / triggered : 0,
    uniqueMoveAdjustedHitRate: triggered > 0 ? uniqueReachedMoves / triggered : 0,
  };
}

export const DEFAULT_MOVE_CLUSTERING_CFG = DEFAULT_CFG;
