// Builds reports/MOVE_CLUSTERING_AUDIT_<date>.md from a per-day zones.json.
//
// Default target: full_day_2026-02-01_dedup. Override via VERIFY_DATE /
// DEDUP_VERSION env vars if needed. Pure post-processing — no thresholds
// touched, no detector changes.

import * as fs from "node:fs";
import * as path from "node:path";
import type { Zone } from "../strategy/types.js";
import {
  applyMoveClustering,
  DEFAULT_MOVE_CLUSTERING_CFG,
  type UniqueMoveCluster,
} from "../strategy/uniqueMoveClustering.js";

const TARGET_DATE = process.env.VERIFY_DATE ?? "2026-02-01";
const DEDUP_VARIANT = process.env.DEDUP_VARIANT ?? "_dedup";
const PROJECT_ROOT = process.cwd();
const REPORTS = path.join(PROJECT_ROOT, "reports");
const ZONES_JSON = path.join(REPORTS, `full_day_${TARGET_DATE}${DEDUP_VARIANT}`, "zones.json");
const OUT_MD = path.join(REPORTS, `MOVE_CLUSTERING_AUDIT_${TARGET_DATE}.md`);

function readZones(p: string): Zone[] {
  if (!fs.existsSync(p)) throw new Error(`Missing ${p}`);
  return JSON.parse(fs.readFileSync(p, "utf8")) as Zone[];
}
function isoOrDash(ts?: number): string {
  return ts === undefined || ts === null ? "-" : new Date(ts).toISOString();
}
function timeOnly(ts?: number): string {
  if (ts === undefined || ts === null) return "-";
  return new Date(ts).toISOString().slice(11, 19);
}
function pct(n: number): string {
  return `${(n * 100).toFixed(2)}%`;
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
function reachedAtOf(z: Zone): number | null {
  for (const t of Object.values(z.targets)) if (t.outcome === "reached" && t.reachedAt !== undefined) return t.reachedAt;
  return null;
}
function timeToTargetMin(z: Zone): number | null {
  for (const t of Object.values(z.targets)) {
    if (t.outcome === "reached" && t.timeToTargetMin !== undefined) return t.timeToTargetMin;
  }
  return null;
}

function build(): string {
  const zones = readZones(ZONES_JSON);
  const triggered = zones.filter((z) => z.triggerTs !== undefined).length;
  const result = applyMoveClustering(zones, DEFAULT_MOVE_CLUSTERING_CFG, triggered);

  const lines: string[] = [];
  lines.push(`# Move Clustering Audit — BTCUSDT ${TARGET_DATE}`);
  lines.push("");
  lines.push(`> Pure post-processing accounting fix. Strategy thresholds in \`config/strategy.default.json\` are unchanged. Detector logic untouched. Failed / no_trigger / invalidated zones remain in the zones list and never receive a \`uniqueMoveId\`.`);
  lines.push("");
  lines.push(`- Generated: ${new Date().toISOString()}`);
  lines.push(`- Source zones: \`reports/full_day_${TARGET_DATE}${DEDUP_VARIANT}/zones.json\``);
  lines.push(`- Total zones in source: ${zones.length}`);
  lines.push(`- Triggered: ${triggered}`);
  lines.push("");

  lines.push(`## 1. Algorithm`);
  lines.push("");
  lines.push(`Two RESOLVED_REACHED zones share a \`uniqueMoveId\` when they meet ALL of:`);
  lines.push(`- same direction (LONG / LONG or SHORT / SHORT);`);
  lines.push(`- their \`[triggerTs, reachedAt]\` time windows overlap, OR the next zone's \`triggerTs\` falls within \`moveClusterGapMinutes = ${DEFAULT_MOVE_CLUSTERING_CFG.moveClusterGapMinutes}\` minutes of the cluster's max \`reachedAt\`.`);
  lines.push("");
  lines.push(`Within a cluster, the zone with the earliest \`triggerTs\` is marked \`isPrimaryMoveZone = true\`. Ties are broken by composite score (absorption × void × trigger). Other reached zones in the same cluster get \`duplicateMoveCredit = true\`.`);
  lines.push("");

  // Headline metrics
  lines.push(`## 2. Headline metrics`);
  lines.push("");
  lines.push(`| Metric | Value |`);
  lines.push(`|---|---|`);
  lines.push(`| Triggered zones | ${triggered} |`);
  lines.push(`| Reached zones (raw) | ${result.reachedZonesRaw} |`);
  lines.push(`| Unique reached moves | ${result.uniqueReachedMoves} |`);
  lines.push(`| Duplicate move credits | ${result.duplicateMoveCredits} |`);
  lines.push(`| Raw triggered hit rate | ${pct(result.rawTriggeredHitRate)} |`);
  lines.push(`| **Unique-move-adjusted hit rate** | **${pct(result.uniqueMoveAdjustedHitRate)}** |`);
  lines.push("");

  // All reached zones with cluster info
  lines.push(`## 3. All reached zones`);
  lines.push("");
  const reached = zones.filter((z) => z.status === "RESOLVED_REACHED").sort((a, b) => (a.triggerTs ?? 0) - (b.triggerTs ?? 0));
  if (reached.length === 0) {
    lines.push(`No zones reached the 2 % target — nothing to cluster.`);
  } else {
    lines.push(`| # | Zone id | Dir | Trigger | Reached | TrigPx | TargetPx | Move id | Cluster size | Primary? | Dup credit | MFE % | MAE % | t→tgt min |`);
    lines.push(`|---|---|---|---|---|---|---|---|---|---|---|---|---|---|`);
    reached.forEach((z, idx) => {
      lines.push(
        `| ${idx + 1} | \`${z.id}\` | ${z.direction} | ${timeOnly(z.triggerTs)} | ${timeOnly(reachedAtOf(z) ?? undefined)} | ${z.triggerPrice?.toFixed(2) ?? "-"} | ${z.targetPrice?.toFixed(2) ?? "-"} | ${z.uniqueMoveId ?? "-"} | ${z.moveClusterSize ?? "-"} | ${z.isPrimaryMoveZone === true ? "**yes**" : z.isPrimaryMoveZone === false ? "no" : "-"} | ${z.duplicateMoveCredit === true ? "yes" : z.duplicateMoveCredit === false ? "no" : "-"} | ${bestMfe(z)?.toFixed(2) ?? "-"} | ${bestMae(z)?.toFixed(2) ?? "-"} | ${timeToTargetMin(z)?.toFixed(1) ?? "-"} |`
      );
    });
  }
  lines.push("");

  // Cluster details
  lines.push(`## 4. Unique moves`);
  lines.push("");
  if (result.clusters.length === 0) {
    lines.push(`No reached zones, so no moves to summarise.`);
  } else {
    lines.push(`Each row is one underlying directional move. The reached-zones inside it all caught the same continuing trend (overlapping or near-adjacent in time, same direction).`);
    lines.push("");
    lines.push(`| Move id | Dir | # Zones | Trigger window | Reached window | Primary zone | Members |`);
    lines.push(`|---|---|---|---|---|---|---|`);
    for (const cl of result.clusters) {
      lines.push(
        `| ${cl.uniqueMoveId} | ${cl.direction} | ${cl.size} | ${timeOnly(cl.triggerWindowStart)}–${timeOnly(cl.triggerWindowEnd)} | ${timeOnly(cl.reachedAtMin)}–${timeOnly(cl.reachedAtMax)} | \`${cl.primaryZoneId}\` | ${cl.zoneIds.join(", ")} |`
      );
    }
  }
  lines.push("");

  // Why N reached = K unique moves
  lines.push(`## 5. Why ${result.reachedZonesRaw} reached zones = ${result.uniqueReachedMoves} unique move${result.uniqueReachedMoves === 1 ? "" : "s"}`);
  lines.push("");
  if (result.uniqueReachedMoves === 0) {
    lines.push(`There are no reached zones to cluster.`);
  } else {
    for (const cl of result.clusters) {
      lines.push(`### Move ${cl.uniqueMoveId} (${cl.direction})`);
      lines.push("");
      lines.push(`Cluster size: ${cl.size} reached zone${cl.size === 1 ? "" : "s"}.`);
      lines.push("");
      lines.push(`Trigger times within this move: ${cl.zoneIds.map((id) => timeOnly(zones.find((z) => z.id === id)?.triggerTs)).join(" → ")}.`);
      lines.push(`Reached times: ${cl.zoneIds.map((id) => timeOnly(reachedAtOf(zones.find((z) => z.id === id) ?? ({} as Zone)) ?? undefined)).join(" / ")}.`);
      lines.push(`Target prices: ${cl.zoneIds.map((id) => zones.find((z) => z.id === id)?.targetPrice?.toFixed(2) ?? "-").join(" / ")}.`);
      lines.push("");
      if (cl.size > 1) {
        const ids = cl.zoneIds;
        const triggers = ids.map((id) => zones.find((z) => z.id === id)?.triggerTs ?? 0).filter(Boolean).sort();
        const reached = ids.map((id) => reachedAtOf(zones.find((z) => z.id === id) ?? ({} as Zone)) ?? 0).filter(Boolean).sort();
        const overlapMin = (Math.min(...reached) - Math.max(...triggers)) / 60_000;
        lines.push(`These ${cl.size} zones have **mutually overlapping trigger→reached windows** (min reachedAt = ${timeOnly(Math.min(...reached))}, max triggerTs = ${timeOnly(Math.max(...triggers))}, overlap of ${overlapMin.toFixed(0)} min). They all rode the same continuing ${cl.direction === "LONG" ? "upward" : "downward"} leg of the day. Crediting all ${cl.size} of them to the day's hit-rate would inflate the count: only ${cl.size - 1} of them are duplicate credits for one underlying directional event.`);
        lines.push("");
      } else {
        lines.push(`Single-member move — no duplicate-credit problem.`);
        lines.push("");
      }
    }
  }
  lines.push("");

  // Bottom line
  lines.push(`## 6. Honest verdict for ${TARGET_DATE}`);
  lines.push("");
  lines.push(`**Raw triggered hit rate:** ${pct(result.rawTriggeredHitRate)} (${result.reachedZonesRaw}/${triggered}).`);
  lines.push(`**Unique-move-adjusted hit rate:** ${pct(result.uniqueMoveAdjustedHitRate)} (${result.uniqueReachedMoves}/${triggered}).`);
  lines.push("");
  if (result.duplicateMoveCredits > 0) {
    lines.push(`The headline number that should be quoted is **${pct(result.uniqueMoveAdjustedHitRate)}**, not ${pct(result.rawTriggeredHitRate)}. The ${result.duplicateMoveCredits} duplicate-credit zones rode the same multi-hour ${result.clusters[0]?.direction === "LONG" ? "upward" : "downward"} leg as the primary zone in their cluster — they are technically distinct setups but caught the same underlying directional event.`);
  } else if (result.reachedZonesRaw === 0) {
    lines.push(`No reached zones to cluster on this day.`);
  } else {
    lines.push(`Each reached zone caught its own distinct move — no clustering adjustment needed for this day.`);
  }
  lines.push("");
  lines.push(`> The strategy thresholds in \`config/strategy.default.json\` are unchanged. The detector and target checker are unchanged. Failed / no_trigger / invalidated zones are still preserved in the zones list (they simply never enter clustering).`);
  lines.push("");

  return lines.join("\n");
}

function main(): void {
  const md = build();
  fs.writeFileSync(OUT_MD, md, "utf8");
  console.log(`Wrote: ${path.resolve(OUT_MD)}`);
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
