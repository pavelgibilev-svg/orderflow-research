// Zone-quality audit for the full-day 2026-02-01 run.
//
// Purpose: 20 zones in a single day is suspicious — are they 20 independent
// signals or is the detector fragmenting the same market structure?
//
// Checks:
//   1. Temporal overlaps  — zones whose active intervals intersect.
//   2. Price overlaps     — zones whose [zoneLow, zoneHigh] intersect.
//   3. Direction clustering — LONG vs SHORT count and successful split.
//   4. Target duplication — do multiple zones share the same 2% move?
//   5. Cooldown gaps      — time gaps between same-direction zone starts.
//   6. Per-triggered-zone quality with overlap_group_id and unique_move_id.
//
// Output:
//   reports/ZONE_QUALITY_AUDIT_2026-02-01.md
//   reports/ZONE_QUALITY_AUDIT_2026-02-01.csv
//
// Strategy thresholds and detector logic are NOT modified.

import * as fs from "node:fs";
import * as path from "node:path";
import { writeCsv, type CsvColumn } from "../reports/csvWriter.js";
import type { Zone } from "../strategy/types.js";

const TARGET_DATE = "2026-02-01";
const PROJECT_ROOT = process.cwd();
const REPORTS = path.join(PROJECT_ROOT, "reports");
const ZONES_JSON = path.join(REPORTS, `full_day_${TARGET_DATE}`, "zones.json");
const OUT_MD = path.join(REPORTS, `ZONE_QUALITY_AUDIT_${TARGET_DATE}.md`);
const OUT_CSV = path.join(REPORTS, `ZONE_QUALITY_AUDIT_${TARGET_DATE}.csv`);

// ---------- helpers ----------

function isoOrDash(ts?: number): string {
  return ts === undefined || ts === null ? "-" : new Date(ts).toISOString();
}
function timeOnly(ts?: number): string {
  if (ts === undefined || ts === null) return "-";
  return new Date(ts).toISOString().slice(11, 19);
}
function fmtMs(ts: number | null): string {
  if (ts === null) return "-";
  return new Date(ts).toISOString().slice(11, 19);
}

interface ActiveInterval {
  startTs: number;
  endTs: number;
}

function activeInterval(z: Zone): ActiveInterval {
  // Start of the zone's "alive" window.
  const startTs = z.startTs;
  // End: prefer resolvedTs (set when REACHED, FAILED, INVALIDATED, EXPIRED, NO_TRIGGER).
  let endTs: number;
  if (z.resolvedTs !== undefined && z.resolvedTs !== null) endTs = z.resolvedTs;
  else if (z.triggerTs !== undefined) endTs = z.triggerTs;
  else if (z.confirmedTs !== undefined) endTs = z.confirmedTs;
  else endTs = startTs;
  // For RESOLVED_FAILED, resolvedTs is end-of-horizon (long forward); cap at end of day for the
  // "actively-formed" interval purposes — but we keep the original for the "footprint" interval.
  return { startTs, endTs };
}

/** "Detection" interval: from start of zone to confirmation/trigger.
 *  This is the period where the detector was actively looking at the same structure. */
function detectionInterval(z: Zone): ActiveInterval {
  const startTs = z.startTs;
  const endTs = z.triggerTs ?? z.confirmedTs ?? z.startTs;
  return { startTs, endTs };
}

function intervalsOverlap(a: ActiveInterval, b: ActiveInterval): boolean {
  return a.startTs <= b.endTs && b.startTs <= a.endTs;
}

function priceOverlap(a: Zone, b: Zone): { overlap: boolean; lo: number; hi: number; pct: number } {
  const lo = Math.max(a.zoneLow, b.zoneLow);
  const hi = Math.min(a.zoneHigh, b.zoneHigh);
  const overlap = lo <= hi;
  // Express overlap relative to the smaller zone's height.
  const aH = a.zoneHigh - a.zoneLow;
  const bH = b.zoneHigh - b.zoneLow;
  const refH = Math.max(1e-9, Math.min(aH, bH));
  const pct = overlap ? (hi - lo) / refH : 0;
  return { overlap, lo, hi, pct };
}

/** Union-Find */
class UF {
  parent: number[] = [];
  constructor(n: number) {
    for (let i = 0; i < n; i++) this.parent.push(i);
  }
  find(x: number): number {
    while (this.parent[x] !== x) {
      this.parent[x] = this.parent[this.parent[x]];
      x = this.parent[x];
    }
    return x;
  }
  union(a: number, b: number): void {
    const ra = this.find(a);
    const rb = this.find(b);
    if (ra !== rb) this.parent[ra] = rb;
  }
}

function fmtPx(n: number | null | undefined): string {
  if (n === undefined || n === null) return "-";
  return n.toFixed(2);
}
function pct(n: number): string {
  return `${(n * 100).toFixed(2)}%`;
}

interface OverlapGroup {
  id: number;
  zoneIds: string[];
  direction: "LONG" | "SHORT" | "MIXED";
  startTs: number;
  endTs: number;
  zoneLow: number;
  zoneHigh: number;
}

interface MoveCluster {
  id: number; // unique_move_id
  direction: "LONG" | "SHORT";
  triggerWindowStart: number;
  triggerWindowEnd: number;
  refPriceMin: number;
  refPriceMax: number;
  targetPriceMin: number;
  targetPriceMax: number;
  reachedAtMin: number;
  reachedAtMax: number;
  zoneIds: string[];
}

function buildOverlapGroups(zones: Zone[]): { groups: OverlapGroup[]; zoneToGroup: Map<string, number> } {
  // Group zones by (temporal-overlap of "active interval" AND price-overlap AND same direction).
  // A pair belongs to the same group if all three conditions hold.
  const uf = new UF(zones.length);
  const intervals = zones.map(activeInterval);
  for (let i = 0; i < zones.length; i++) {
    for (let j = i + 1; j < zones.length; j++) {
      if (zones[i].direction !== zones[j].direction) continue;
      if (!intervalsOverlap(intervals[i], intervals[j])) continue;
      const po = priceOverlap(zones[i], zones[j]);
      if (!po.overlap) continue;
      uf.union(i, j);
    }
  }
  const byRoot = new Map<number, number[]>();
  for (let i = 0; i < zones.length; i++) {
    const r = uf.find(i);
    const arr = byRoot.get(r) ?? [];
    arr.push(i);
    byRoot.set(r, arr);
  }
  const groups: OverlapGroup[] = [];
  const zoneToGroup = new Map<string, number>();
  let gid = 1;
  for (const [, indices] of byRoot.entries()) {
    let startTs = +Infinity;
    let endTs = -Infinity;
    let lo = +Infinity;
    let hi = -Infinity;
    let dir: "LONG" | "SHORT" | "MIXED" = zones[indices[0]].direction;
    for (const idx of indices) {
      const z = zones[idx];
      if (z.direction !== dir) dir = "MIXED";
      const it = intervals[idx];
      if (it.startTs < startTs) startTs = it.startTs;
      if (it.endTs > endTs) endTs = it.endTs;
      if (z.zoneLow < lo) lo = z.zoneLow;
      if (z.zoneHigh > hi) hi = z.zoneHigh;
    }
    const group: OverlapGroup = {
      id: gid,
      zoneIds: indices.map((i) => zones[i].id),
      direction: dir,
      startTs,
      endTs,
      zoneLow: lo,
      zoneHigh: hi,
    };
    for (const idx of indices) zoneToGroup.set(zones[idx].id, gid);
    groups.push(group);
    gid++;
  }
  groups.sort((a, b) => a.startTs - b.startTs);
  return { groups, zoneToGroup };
}

/** Cluster successful zones (RESOLVED_REACHED) by the actual 2% move they caught.
 *  Two successful zones belong to the same "move" if:
 *    - same direction
 *    - their [triggerTs, reachedAt] windows overlap in time, OR
 *    - their target prices are within ~0.5% of each other AND the trigger times
 *      are within 6 hours.
 */
function buildMoveClusters(zones: Zone[]): { moves: MoveCluster[]; zoneToMove: Map<string, number> } {
  const successful = zones.filter((z) => z.status === "RESOLVED_REACHED" && z.triggerTs !== undefined);
  if (successful.length === 0) return { moves: [], zoneToMove: new Map() };
  const uf = new UF(successful.length);

  const reachedAt = (z: Zone): number => {
    for (const t of Object.values(z.targets)) if (t.outcome === "reached" && t.reachedAt !== undefined) return t.reachedAt;
    return z.resolvedTs ?? z.triggerTs ?? 0;
  };

  for (let i = 0; i < successful.length; i++) {
    for (let j = i + 1; j < successful.length; j++) {
      const a = successful[i];
      const b = successful[j];
      if (a.direction !== b.direction) continue;
      const aTrig = a.triggerTs!;
      const bTrig = b.triggerTs!;
      const aReached = reachedAt(a);
      const bReached = reachedAt(b);
      // Time-window overlap of [trig, reached]:
      const overlap = aTrig <= bReached && bTrig <= aReached;
      // OR target prices close (within 0.5%) AND trigger times within 6h:
      const refPx = (a.referencePrice ?? a.triggerPrice ?? 1) || 1;
      const targetClose = Math.abs((a.targetPrice ?? 0) - (b.targetPrice ?? 0)) / Math.abs(refPx) < 0.005;
      const trigClose = Math.abs(aTrig - bTrig) <= 6 * 3600 * 1000;
      if (overlap || (targetClose && trigClose)) uf.union(i, j);
    }
  }
  const byRoot = new Map<number, number[]>();
  for (let i = 0; i < successful.length; i++) {
    const r = uf.find(i);
    const arr = byRoot.get(r) ?? [];
    arr.push(i);
    byRoot.set(r, arr);
  }
  const moves: MoveCluster[] = [];
  const zoneToMove = new Map<string, number>();
  let mid = 1;
  for (const [, indices] of byRoot.entries()) {
    let twStart = +Infinity, twEnd = -Infinity;
    let refMin = +Infinity, refMax = -Infinity;
    let tgtMin = +Infinity, tgtMax = -Infinity;
    let reachedMin = +Infinity, reachedMax = -Infinity;
    const dir = successful[indices[0]].direction;
    for (const idx of indices) {
      const z = successful[idx];
      const trig = z.triggerTs!;
      const reach = reachedAt(z);
      if (trig < twStart) twStart = trig;
      if (trig > twEnd) twEnd = trig;
      if (reach < reachedMin) reachedMin = reach;
      if (reach > reachedMax) reachedMax = reach;
      const ref = z.referencePrice ?? z.triggerPrice ?? 0;
      if (ref < refMin) refMin = ref;
      if (ref > refMax) refMax = ref;
      const tgt = z.targetPrice ?? 0;
      if (tgt < tgtMin) tgtMin = tgt;
      if (tgt > tgtMax) tgtMax = tgt;
    }
    const m: MoveCluster = {
      id: mid,
      direction: dir,
      triggerWindowStart: twStart,
      triggerWindowEnd: twEnd,
      refPriceMin: refMin,
      refPriceMax: refMax,
      targetPriceMin: tgtMin,
      targetPriceMax: tgtMax,
      reachedAtMin: reachedMin,
      reachedAtMax: reachedMax,
      zoneIds: indices.map((i) => successful[i].id),
    };
    for (const idx of indices) zoneToMove.set(successful[idx].id, mid);
    moves.push(m);
    mid++;
  }
  moves.sort((a, b) => a.triggerWindowStart - b.triggerWindowStart);
  return { moves, zoneToMove };
}

interface CooldownGap {
  prevZoneId: string;
  nextZoneId: string;
  direction: "LONG" | "SHORT";
  prevStartTs: number;
  prevEndTs: number;
  nextStartTs: number;
  gapMs: number;
  gapMin: number;
  prevWasActive: boolean; // did the next zone start before the prev was resolved?
}

function buildCooldownGaps(zones: Zone[]): CooldownGap[] {
  const sorted = zones.slice().sort((a, b) => a.startTs - b.startTs);
  const gaps: CooldownGap[] = [];
  for (const dir of ["LONG", "SHORT"] as const) {
    const same = sorted.filter((z) => z.direction === dir);
    for (let i = 1; i < same.length; i++) {
      const prev = same[i - 1];
      const next = same[i];
      const prevAct = activeInterval(prev);
      const gap: CooldownGap = {
        prevZoneId: prev.id,
        nextZoneId: next.id,
        direction: dir,
        prevStartTs: prev.startTs,
        prevEndTs: prevAct.endTs,
        nextStartTs: next.startTs,
        gapMs: next.startTs - prevAct.endTs,
        gapMin: (next.startTs - prevAct.endTs) / 60_000,
        prevWasActive: next.startTs <= prevAct.endTs,
      };
      gaps.push(gap);
    }
  }
  return gaps;
}

interface QualityCsvRow {
  zoneId: string;
  direction: "LONG" | "SHORT";
  status: string;
  startTs: string;
  confirmedTs: string;
  triggerTs: string;
  resolvedTs: string;
  zoneLow: number;
  zoneHigh: number;
  triggerPrice: number | null;
  targetPrice: number | null;
  reached: string;
  earliestHorizonReached: string;
  mfePct: number | null;
  maePct: number | null;
  timeToTargetMin: number | null;
  overlapGroupId: number;
  uniqueMoveId: number | null;
  isTriggered: string;
}

function bestMfe(z: Zone): number | null {
  let max = -Infinity;
  for (const t of Object.values(z.targets)) if (t.mfePct !== undefined && t.mfePct > max) max = t.mfePct;
  return Number.isFinite(max) ? max : null;
}
function bestMae(z: Zone): number | null {
  let max = -Infinity;
  for (const t of Object.values(z.targets)) if (t.maePct !== undefined && t.maePct > max) max = t.maePct;
  return Number.isFinite(max) ? max : null;
}
function timeToTargetMin(z: Zone): number | null {
  for (const t of Object.values(z.targets)) {
    if (t.outcome === "reached" && t.timeToTargetMin !== undefined) return t.timeToTargetMin;
  }
  return null;
}
function earliestReachedHorizon(z: Zone): string {
  const order = ["4h", "8h", "24h"];
  for (const h of order) if (z.targets[h]?.outcome === "reached") return h;
  return "-";
}

function buildCsvRows(zones: Zone[], zoneToGroup: Map<string, number>, zoneToMove: Map<string, number>): QualityCsvRow[] {
  return zones.map((z) => ({
    zoneId: z.id,
    direction: z.direction,
    status: z.status,
    startTs: isoOrDash(z.startTs),
    confirmedTs: isoOrDash(z.confirmedTs),
    triggerTs: isoOrDash(z.triggerTs),
    resolvedTs: isoOrDash(z.resolvedTs),
    zoneLow: z.zoneLow,
    zoneHigh: z.zoneHigh,
    triggerPrice: z.triggerPrice ?? null,
    targetPrice: z.targetPrice ?? null,
    reached: z.status === "RESOLVED_REACHED" ? "yes" : "no",
    earliestHorizonReached: earliestReachedHorizon(z),
    mfePct: bestMfe(z),
    maePct: bestMae(z),
    timeToTargetMin: timeToTargetMin(z),
    overlapGroupId: zoneToGroup.get(z.id) ?? 0,
    uniqueMoveId: zoneToMove.get(z.id) ?? null,
    isTriggered: z.triggerTs !== undefined ? "yes" : "no",
  }));
}

function csvCols(): CsvColumn<QualityCsvRow>[] {
  return [
    { name: "zoneId", get: (r) => r.zoneId },
    { name: "direction", get: (r) => r.direction },
    { name: "status", get: (r) => r.status },
    { name: "startTs", get: (r) => r.startTs },
    { name: "confirmedTs", get: (r) => r.confirmedTs },
    { name: "triggerTs", get: (r) => r.triggerTs },
    { name: "resolvedTs", get: (r) => r.resolvedTs },
    { name: "zoneLow", get: (r) => r.zoneLow },
    { name: "zoneHigh", get: (r) => r.zoneHigh },
    { name: "triggerPrice", get: (r) => r.triggerPrice ?? "" },
    { name: "targetPrice", get: (r) => r.targetPrice ?? "" },
    { name: "isTriggered", get: (r) => r.isTriggered },
    { name: "reached", get: (r) => r.reached },
    { name: "earliestHorizonReached", get: (r) => r.earliestHorizonReached },
    { name: "mfePct", get: (r) => (r.mfePct !== null ? r.mfePct.toFixed(3) : "") },
    { name: "maePct", get: (r) => (r.maePct !== null ? r.maePct.toFixed(3) : "") },
    { name: "timeToTargetMin", get: (r) => (r.timeToTargetMin !== null ? r.timeToTargetMin.toFixed(2) : "") },
    { name: "overlapGroupId", get: (r) => r.overlapGroupId },
    { name: "uniqueMoveId", get: (r) => r.uniqueMoveId ?? "" },
  ];
}

function buildMarkdown(zones: Zone[], groups: OverlapGroup[], zoneToGroup: Map<string, number>, moves: MoveCluster[], zoneToMove: Map<string, number>, gaps: CooldownGap[]): string {
  const lines: string[] = [];
  const totalZones = zones.length;
  const longZones = zones.filter((z) => z.direction === "LONG");
  const shortZones = zones.filter((z) => z.direction === "SHORT");
  const triggered = zones.filter((z) => z.triggerTs !== undefined);
  const successful = zones.filter((z) => z.status === "RESOLVED_REACHED");
  const successfulLong = successful.filter((z) => z.direction === "LONG").length;
  const successfulShort = successful.filter((z) => z.direction === "SHORT").length;

  lines.push(`# Zone Quality Audit — BTCUSDT ${TARGET_DATE}`);
  lines.push("");
  lines.push(`> Audit of the full-day backtest output for ${TARGET_DATE}: are 20 zones in one day independent signals, or is the detector fragmenting the same market structure?`);
  lines.push("");
  lines.push(`- Generated: ${new Date().toISOString()}`);
  lines.push(`- Source zones: \`reports/full_day_${TARGET_DATE}/zones.json\``);
  lines.push(`- Strategy thresholds NOT modified.`);
  lines.push(`- Detector logic NOT modified.`);
  lines.push("");

  // ----- Section 1: temporal overlaps -----
  lines.push(`## 1. Temporal overlaps`);
  lines.push("");
  lines.push(`Active interval per zone is defined as **\`[startTs … min(resolvedTs, triggerTs, confirmedTs, startTs)]\`** — the period where the zone was actively forming or being tracked. Two zones overlap temporally when these intervals intersect.`);
  lines.push("");
  // Pairwise temporal-overlap matrix (only same-direction pairs flagged).
  const intervals = zones.map(activeInterval);
  const tempPairs: Array<[Zone, Zone]> = [];
  for (let i = 0; i < zones.length; i++) {
    for (let j = i + 1; j < zones.length; j++) {
      if (intervalsOverlap(intervals[i], intervals[j])) tempPairs.push([zones[i], zones[j]]);
    }
  }
  lines.push(`Temporally overlapping pairs (any direction): **${tempPairs.length}**.`);
  // Same-direction temporal overlaps:
  const sameDirTemp = tempPairs.filter(([a, b]) => a.direction === b.direction);
  lines.push(`Of those, same-direction: **${sameDirTemp.length}**.`);
  lines.push("");
  if (sameDirTemp.length > 0) {
    lines.push(`Same-direction temporal overlaps (the suspicious ones for fragmentation):`);
    lines.push("");
    lines.push(`| A id | B id | Dir | A active | B active | Overlap |`);
    lines.push(`|---|---|---|---|---|---|`);
    for (const [a, b] of sameDirTemp.slice(0, 30)) {
      const ai = activeInterval(a);
      const bi = activeInterval(b);
      const start = Math.max(ai.startTs, bi.startTs);
      const end = Math.min(ai.endTs, bi.endTs);
      lines.push(`| ${a.id} | ${b.id} | ${a.direction} | ${timeOnly(ai.startTs)}–${timeOnly(ai.endTs)} | ${timeOnly(bi.startTs)}–${timeOnly(bi.endTs)} | ${timeOnly(start)}–${timeOnly(end)} |`);
    }
  }
  lines.push("");

  // ----- Section 2: price overlaps -----
  lines.push(`## 2. Price overlaps`);
  lines.push("");
  lines.push(`Two zones price-overlap when their [zoneLow, zoneHigh] intervals intersect.`);
  lines.push("");
  let priceOverlapPairs = 0;
  let sameDirPriceOverlapPairs = 0;
  let bothTempAndPrice = 0;
  for (let i = 0; i < zones.length; i++) {
    for (let j = i + 1; j < zones.length; j++) {
      const po = priceOverlap(zones[i], zones[j]);
      if (po.overlap) {
        priceOverlapPairs++;
        if (zones[i].direction === zones[j].direction) sameDirPriceOverlapPairs++;
        if (intervalsOverlap(intervals[i], intervals[j])) bothTempAndPrice++;
      }
    }
  }
  lines.push(`Price-overlapping pairs (any direction): **${priceOverlapPairs}**.`);
  lines.push(`Of those, same-direction: **${sameDirPriceOverlapPairs}**.`);
  lines.push(`Pairs that overlap in BOTH time AND price: **${bothTempAndPrice}**.`);
  lines.push("");

  // ----- Section 3: overlap groups (clusters of suspicious-fragmentation zones) -----
  lines.push(`## 3. Overlap groups (same direction + temporal + price)`);
  lines.push("");
  lines.push(`A zone group merges zones that are pairwise (same direction) ∧ (temporal overlap) ∧ (price overlap). If group size > 1, the detector is producing several zones over the same market structure.`);
  lines.push("");
  lines.push(`Total groups: **${groups.length}** (${groups.filter((g) => g.zoneIds.length > 1).length} with ≥ 2 zones, ${groups.filter((g) => g.zoneIds.length === 1).length} singletons).`);
  lines.push("");
  lines.push(`| Group | Dir | Zones | Active window | Price band | Zone IDs |`);
  lines.push(`|---|---|---|---|---|---|`);
  for (const g of groups) {
    lines.push(`| ${g.id} | ${g.direction} | ${g.zoneIds.length} | ${timeOnly(g.startTs)}–${timeOnly(g.endTs)} | ${g.zoneLow.toFixed(2)}–${g.zoneHigh.toFixed(2)} | ${g.zoneIds.join(", ")} |`);
  }
  lines.push("");
  // Successful zones per group:
  const groupReached = new Map<number, number>();
  for (const z of successful) {
    const gid = zoneToGroup.get(z.id);
    if (gid !== undefined) groupReached.set(gid, (groupReached.get(gid) ?? 0) + 1);
  }
  if (successful.length > 0) {
    lines.push(`Successful zones per group: ${Array.from(groupReached.entries()).map(([gid, n]) => `group ${gid}: ${n}`).join(" · ") || "none"}`);
    lines.push("");
  }

  // ----- Section 4: direction clustering -----
  lines.push(`## 4. Direction clustering`);
  lines.push("");
  lines.push(`| Metric | LONG | SHORT |`);
  lines.push(`|---|---|---|`);
  lines.push(`| Zones found | ${longZones.length} | ${shortZones.length} |`);
  lines.push(`| Triggered | ${triggered.filter((z) => z.direction === "LONG").length} | ${triggered.filter((z) => z.direction === "SHORT").length} |`);
  lines.push(`| RESOLVED_REACHED | ${successfulLong} | ${successfulShort} |`);
  lines.push(`| RESOLVED_FAILED | ${zones.filter((z) => z.direction === "LONG" && z.status === "RESOLVED_FAILED").length} | ${zones.filter((z) => z.direction === "SHORT" && z.status === "RESOLVED_FAILED").length} |`);
  lines.push(`| INVALIDATED | ${zones.filter((z) => z.direction === "LONG" && z.status === "INVALIDATED").length} | ${zones.filter((z) => z.direction === "SHORT" && z.status === "INVALIDATED").length} |`);
  lines.push(`| NO_TRIGGER | ${zones.filter((z) => z.direction === "LONG" && z.status === "NO_TRIGGER").length} | ${zones.filter((z) => z.direction === "SHORT" && z.status === "NO_TRIGGER").length} |`);
  lines.push(`| EXPIRED | ${zones.filter((z) => z.direction === "LONG" && z.status === "EXPIRED").length} | ${zones.filter((z) => z.direction === "SHORT" && z.status === "EXPIRED").length} |`);
  lines.push("");
  if (successful.length > 0) {
    const dirsOfSuccess = new Set(successful.map((z) => z.direction));
    if (dirsOfSuccess.size === 1) {
      const onlyDir = [...dirsOfSuccess][0];
      lines.push(`**All ${successful.length} successful zones are ${onlyDir}**. They are part of one or more ${onlyDir === "LONG" ? "upward" : "downward"} moves on this day. The day's net return was directional, so this matches a directional-tailwind explanation.`);
    } else {
      lines.push(`Successful zones are split across LONG and SHORT — not purely one direction.`);
    }
    lines.push("");
  }

  // ----- Section 5: target duplication / unique 2% moves -----
  lines.push(`## 5. Target duplication — how many unique 2% moves are there?`);
  lines.push("");
  lines.push(`Two successful zones are considered to have caught the **same** 2% move when:`);
  lines.push(`- they are the same direction, AND`);
  lines.push(`- their \`[triggerTs … reachedAt]\` time windows overlap, OR`);
  lines.push(`- their target prices are within 0.5% AND their trigger times are within 6 hours.`);
  lines.push("");
  lines.push(`Successful zones: **${successful.length}**`);
  lines.push(`Unique 2% moves: **${moves.length}**`);
  lines.push("");
  if (moves.length > 0) {
    lines.push(`| Move | Dir | Trigger window | Trigger px range | Target px range | Reached window | Zones in this move |`);
    lines.push(`|---|---|---|---|---|---|---|`);
    for (const m of moves) {
      lines.push(`| ${m.id} | ${m.direction} | ${timeOnly(m.triggerWindowStart)}–${timeOnly(m.triggerWindowEnd)} | ${m.refPriceMin.toFixed(2)}–${m.refPriceMax.toFixed(2)} | ${m.targetPriceMin.toFixed(2)}–${m.targetPriceMax.toFixed(2)} | ${timeOnly(m.reachedAtMin)}–${timeOnly(m.reachedAtMax)} | ${m.zoneIds.length} (${m.zoneIds.join(", ")}) |`);
    }
    lines.push("");
    if (moves.length === 1) {
      lines.push(`**All ${successful.length} "successful" zones share a single 2% move.** The hit-rate of ${pct(successful.length / triggered.length)} reflects ${successful.length} zone-credits for what is fundamentally **1 directional event**.`);
    } else if (moves.length < successful.length) {
      const dup = successful.length - moves.length;
      lines.push(`The ${successful.length} successful zones come from only **${moves.length} distinct moves** — ${dup} of the successes are duplicate credits for the same underlying price action.`);
    } else {
      lines.push(`Each successful zone caught a separate 2% move — no obvious duplication.`);
    }
    lines.push("");
  }

  // ----- Section 6: cooldown / duplicate detection -----
  lines.push(`## 6. Cooldown / duplicate detection`);
  lines.push("");
  lines.push(`For each consecutive pair of same-direction zones, we measure the gap between when the previous zone's active window closed and the next zone's start. Negative gaps mean the new zone started while the previous one was still active.`);
  lines.push("");
  lines.push(`| Direction | Pair count | Gap min (median, min, max) | Pairs where prev was still active |`);
  lines.push(`|---|---|---|---|`);
  for (const dir of ["LONG", "SHORT"] as const) {
    const dirGaps = gaps.filter((g) => g.direction === dir);
    if (dirGaps.length === 0) {
      lines.push(`| ${dir} | 0 | - | 0 |`);
      continue;
    }
    const sorted = dirGaps.map((g) => g.gapMin).sort((a, b) => a - b);
    const med = sorted[Math.floor(sorted.length / 2)];
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const overlapping = dirGaps.filter((g) => g.prevWasActive).length;
    lines.push(`| ${dir} | ${dirGaps.length} | ${med.toFixed(1)} / ${min.toFixed(1)} / ${max.toFixed(1)} | ${overlapping} |`);
  }
  lines.push("");
  // List the worst-overlapping pairs:
  const overlappingGaps = gaps.filter((g) => g.prevWasActive).sort((a, b) => a.gapMin - b.gapMin);
  if (overlappingGaps.length > 0) {
    lines.push(`### Same-direction zones started while a previous one was still active`);
    lines.push("");
    lines.push(`| Prev id | Next id | Dir | Prev active | Next start | Gap (min) |`);
    lines.push(`|---|---|---|---|---|---|`);
    for (const g of overlappingGaps.slice(0, 30)) {
      lines.push(`| ${g.prevZoneId} | ${g.nextZoneId} | ${g.direction} | ${timeOnly(g.prevStartTs)}–${timeOnly(g.prevEndTs)} | ${timeOnly(g.nextStartTs)} | ${g.gapMin.toFixed(1)} |`);
    }
    lines.push("");
  }

  // Proposal:
  lines.push(`### Proposed deduplication rule`);
  lines.push("");
  if (overlappingGaps.length > 0 || groups.some((g) => g.zoneIds.length > 1)) {
    lines.push(`The detector is producing multiple same-direction zones over the same active window and price band. A simple, conservative rule that does **not** require touching strategy thresholds:`);
    lines.push("");
    lines.push("```text");
    lines.push("Before opening a new candidate of direction D at time T, price band [L, H]:");
    lines.push("  if there exists an existing zone Z' of direction D with:");
    lines.push("    Z'.status in {CANDIDATE, CONFIRMED, TRIGGERED}");
    lines.push("    AND Z'.startTs <= T <= max(Z'.resolvedTs, Z'.triggerTs, Z'.confirmedTs, Z'.startTs)");
    lines.push("    AND price band [L, H] intersects [Z'.zoneLow, Z'.zoneHigh]");
    lines.push("  then DO NOT open the new candidate.");
    lines.push("");
    lines.push("Optional cooldown: even after Z' resolves, suppress new same-direction");
    lines.push("candidates within Z's price band for `cooldownMin` minutes.");
    lines.push("```");
    lines.push("");
    lines.push(`This is a deduplication rule, not a threshold tune. It belongs in \`zoneDetector.ts\` — the change is in detector logic but the **strategy thresholds in \`config/strategy.default.json\` stay identical**.`);
  } else {
    lines.push(`No suspicious same-direction overlaps found — current behaviour is acceptable.`);
  }
  lines.push("");

  // ----- Section 7: triggered-zone quality table -----
  lines.push(`## 7. Triggered-zone quality (per zone)`);
  lines.push("");
  lines.push(`| Zone id | Dir | Trigger | MFE % | MAE % | Reached 2 %? | t→target min | overlap_group | unique_move |`);
  lines.push(`|---|---|---|---|---|---|---|---|---|`);
  for (const z of triggered) {
    const gid = zoneToGroup.get(z.id) ?? "-";
    const mid = zoneToMove.get(z.id);
    lines.push(`| ${z.id} | ${z.direction} | ${timeOnly(z.triggerTs)} | ${bestMfe(z)?.toFixed(2) ?? "-"} | ${bestMae(z)?.toFixed(2) ?? "-"} | ${z.status === "RESOLVED_REACHED" ? "**yes**" : "no"} | ${timeToTargetMin(z)?.toFixed(1) ?? "-"} | ${gid} | ${mid ?? "-"} |`);
  }
  lines.push("");

  // ----- Verdict -----
  lines.push(`## 8. Honest verdict`);
  lines.push("");
  const groupsWithMulti = groups.filter((g) => g.zoneIds.length > 1).length;
  const fragmentationFound = groupsWithMulti > 0 || overlappingGaps.length > 0;
  const oneMove = moves.length === 1 && successful.length > 1;

  lines.push(`**Are 20 zones really 20 independent zones?**`);
  lines.push("");
  if (fragmentationFound) {
    lines.push(`No. The 20 zones cluster into **${groups.length} overlap groups**, of which **${groupsWithMulti} contain more than one zone**. ${overlappingGaps.length} same-direction zones started while a previous zone of the same direction was still active. The detector is fragmenting the same market structure into multiple zones.`);
  } else {
    lines.push(`Yes — the ${groups.length} groups are all singletons (no same-direction zone overlapped another). The 20 zones look like 20 independent attempts.`);
  }
  lines.push("");

  lines.push(`**Are the ${successful.length} successful zones ${successful.length} independent successes, or 1–2 large moves?**`);
  lines.push("");
  if (oneMove) {
    lines.push(`**1 move.** All ${successful.length} successful zones cluster into a single unique 2% move (move 1 in the table above). The 54.55% triggered hit rate on ${TARGET_DATE} reflects ${successful.length} zone-credits for fundamentally **one directional event** — not ${successful.length} independent edge instances.`);
  } else if (moves.length === 0) {
    lines.push(`No successful zones, so no moves to count.`);
  } else if (moves.length === successful.length) {
    lines.push(`${successful.length} distinct moves — every successful zone caught a separate 2% event.`);
  } else {
    lines.push(`${moves.length} distinct moves for ${successful.length} successful zones — some duplication, but not all collapsed to 1.`);
  }
  lines.push("");

  lines.push(`**Should we add cooldown / deduplication?**`);
  lines.push("");
  if (fragmentationFound) {
    lines.push(`Yes. The "no same-direction zone may open inside an active same-direction zone's price band" rule above should be added to \`zoneDetector.ts\` before the next full-day run. It is a behaviour fix, not a threshold tune.`);
  } else {
    lines.push(`Not strictly required, but a small cooldown (5–15 min) could still help robustness on noisy days.`);
  }
  lines.push("");

  lines.push(`**Can today's 54.55% hit rate be quoted as an honest hit rate?**`);
  lines.push("");
  if (fragmentationFound || oneMove) {
    lines.push(`**No.** The denominator (11 triggered) is inflated by fragmentation; the numerator (6 reached) is inflated by multiple zones being credited for the same 2% move. After collapsing to unique moves, the honest "events that hit 2%" count for ${TARGET_DATE} is **${moves.length}**, not 6. Reporting 54.55% without that caveat overstates the strategy's real edge.`);
  } else {
    lines.push(`Yes — the zones are independent and each successful zone caught a different move.`);
  }
  lines.push("");

  lines.push(`**What needs to change before the next full-day run?**`);
  lines.push("");
  lines.push(`1. Add the same-direction overlap deduplication rule in \`zoneDetector.ts\` (no threshold change).`);
  lines.push(`2. After the rule lands, re-run ${TARGET_DATE} full-day and report:`);
  lines.push(`   - new zone count (expected to drop materially);`);
  lines.push(`   - new triggered count;`);
  lines.push(`   - new hit rate (likely lower, but more honest);`);
  lines.push(`   - confirm that group sizes are all 1.`);
  lines.push(`3. Then repeat the regime-comparison run on 2026-01-01.`);
  lines.push(`4. Only after dedup, with multiple paid days, consider any threshold tuning.`);
  lines.push("");

  return lines.join("\n");
}

function main(): void {
  if (!fs.existsSync(ZONES_JSON)) {
    throw new Error(`Missing ${ZONES_JSON}. Run the full-day backtest for ${TARGET_DATE} first.`);
  }
  const zones: Zone[] = JSON.parse(fs.readFileSync(ZONES_JSON, "utf8"));
  zones.sort((a, b) => a.startTs - b.startTs);

  const { groups, zoneToGroup } = buildOverlapGroups(zones);
  const { moves, zoneToMove } = buildMoveClusters(zones);
  const gaps = buildCooldownGaps(zones);

  fs.writeFileSync(OUT_MD, buildMarkdown(zones, groups, zoneToGroup, moves, zoneToMove, gaps), "utf8");
  writeCsv(OUT_CSV, csvCols(), buildCsvRows(zones, zoneToGroup, zoneToMove));

  console.log(`Audit report : ${path.resolve(OUT_MD)}`);
  console.log(`Audit CSV    : ${path.resolve(OUT_CSV)}`);
  console.log("");
  console.log(`zones                  : ${zones.length}`);
  console.log(`overlap groups         : ${groups.length} (${groups.filter((g) => g.zoneIds.length > 1).length} with ≥ 2 zones)`);
  console.log(`successful zones       : ${zones.filter((z) => z.status === "RESOLVED_REACHED").length}`);
  console.log(`unique 2% moves        : ${moves.length}`);
  console.log(`overlapping same-dir   : ${gaps.filter((g) => g.prevWasActive).length}`);
}

import { pathToFileURL } from "node:url";
const __isMain =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href;
if (__isMain) {
  try {
    main();
  } catch (e) {
    console.error(e);
    process.exit(1);
  }
}
