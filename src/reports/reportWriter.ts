// Top-level report writer: produces all five required output artefacts.

import * as fs from "node:fs";
import * as path from "node:path";
import type { Zone } from "../strategy/types.js";
import { writeCsv, type CsvColumn } from "./csvWriter.js";
import { writeJson } from "./jsonWriter.js";
import { buildMarkdownReport, type ReportInputs } from "./markdownReport.js";

export interface WriteAllOpts {
  outDir: string;
  zones: Zone[];
  reportInputs: ReportInputs;
  config: unknown;
}

export function writeAllReports(opts: WriteAllOpts): string[] {
  fs.mkdirSync(opts.outDir, { recursive: true });
  const written: string[] = [];

  const zonesCsvCols: CsvColumn<Zone>[] = [
    { name: "symbol", get: (z) => z.symbol },
    { name: "date", get: (z) => z.date },
    { name: "id", get: (z) => z.id },
    { name: "direction", get: (z) => z.direction },
    { name: "zone_type", get: (z) => z.zoneType },
    { name: "status", get: (z) => z.status },
    { name: "zone_start", get: (z) => isoOrEmpty(z.startTs) },
    { name: "zone_confirmed", get: (z) => isoOrEmpty(z.confirmedTs) },
    { name: "trigger_time", get: (z) => isoOrEmpty(z.triggerTs) },
    { name: "resolved_time", get: (z) => isoOrEmpty(z.resolvedTs) },
    { name: "zone_low", get: (z) => z.zoneLow },
    { name: "zone_high", get: (z) => z.zoneHigh },
    { name: "trigger_price", get: (z) => z.triggerPrice ?? "" },
    { name: "target_price", get: (z) => z.targetPrice ?? "" },
    { name: "absorption_score", get: (z) => z.scores.absorptionScore.toFixed(4) },
    { name: "liquidity_void_score", get: (z) => z.scores.liquidityVoidScore.toFixed(4) },
    { name: "ofi_score", get: (z) => z.scores.ofiScore.toFixed(4) },
    { name: "trigger_score", get: (z) => z.scores.triggerScore?.toFixed(4) ?? "" },
    { name: "horizons", get: (z) => Object.keys(z.targets).join("|") },
    {
      name: "outcome_summary",
      get: (z) =>
        Object.values(z.targets)
          .map((t) => `${t.horizon}:${t.outcome}`)
          .join("|"),
    },
    {
      name: "time_to_target_min",
      get: (z) => {
        const reached = Object.values(z.targets).find((t) => t.outcome === "reached");
        return reached?.timeToTargetMin?.toFixed(2) ?? "";
      },
    },
    {
      name: "mfe_pct",
      get: (z) => {
        const vals = Object.values(z.targets).map((t) => t.mfePct ?? -Infinity);
        const max = Math.max(...vals);
        return Number.isFinite(max) ? max.toFixed(3) : "";
      },
    },
    {
      name: "mae_pct",
      get: (z) => {
        const vals = Object.values(z.targets).map((t) => t.maePct ?? -Infinity);
        const max = Math.max(...vals);
        return Number.isFinite(max) ? max.toFixed(3) : "";
      },
    },
    { name: "quality_flags", get: (z) => z.qualityFlags.join("|") },
    { name: "uniqueMoveId", get: (z) => z.uniqueMoveId ?? "" },
    { name: "moveClusterSize", get: (z) => z.moveClusterSize ?? "" },
    { name: "isPrimaryMoveZone", get: (z) => (z.isPrimaryMoveZone === undefined ? "" : z.isPrimaryMoveZone ? "yes" : "no") },
    { name: "duplicateMoveCredit", get: (z) => (z.duplicateMoveCredit === undefined ? "" : z.duplicateMoveCredit ? "yes" : "no") },
    { name: "reasons", get: (z) => z.reasons.map((r) => `${r.stage}@${new Date(r.ts).toISOString()}`).join("|") },
  ];

  const zonesCsvPath = path.join(opts.outDir, "zones.csv");
  writeCsv(zonesCsvPath, zonesCsvCols, opts.zones);
  written.push(zonesCsvPath);

  const zonesJsonPath = path.join(opts.outDir, "zones.json");
  writeJson(zonesJsonPath, opts.zones);
  written.push(zonesJsonPath);

  // Daily summary
  const ds = computeDailySummary(opts.zones, opts.reportInputs.dedup, opts.reportInputs.moveClustering);
  const summaryPath = path.join(opts.outDir, "daily_summary.csv");
  writeCsv(
    summaryPath,
    [
      { name: "metric", get: (r: { metric: string; value: number }) => r.metric },
      { name: "value", get: (r) => r.value },
    ] as CsvColumn<{ metric: string; value: number }>[],
    ds
  );
  written.push(summaryPath);

  const reportPath = path.join(opts.outDir, "report.md");
  fs.writeFileSync(reportPath, buildMarkdownReport(opts.reportInputs), "utf8");
  written.push(reportPath);

  const annotPath = path.join(opts.outDir, "chart_annotations.json");
  writeJson(annotPath, buildAnnotations(opts.zones));
  written.push(annotPath);

  const cfgEcho = path.join(opts.outDir, "config.echo.json");
  writeJson(cfgEcho, opts.config);
  written.push(cfgEcho);

  return written;
}

function isoOrEmpty(ts?: number): string {
  if (ts === undefined || ts === null) return "";
  return new Date(ts).toISOString();
}

function computeDailySummary(
  zones: Zone[],
  dedup?: { enabled: boolean; cooldownMinutesAfterResolve: number; duplicateSuppressionCount: number; suppressionsByReason: { [reason: string]: number } },
  moveClustering?: { enabled: boolean; moveClusterGapMinutes: number; reachedZonesRaw: number; uniqueReachedMoves: number; duplicateMoveCredits: number; rawTriggeredHitRate: number; uniqueMoveAdjustedHitRate: number }
): Array<{ metric: string; value: number }> {
  const counts: Record<string, number> = {};
  for (const z of zones) {
    counts[`status_${z.status}`] = (counts[`status_${z.status}`] ?? 0) + 1;
    counts[`direction_${z.direction}`] = (counts[`direction_${z.direction}`] ?? 0) + 1;
  }
  const total = zones.length;
  const triggered = zones.filter((z) => z.triggerTs !== undefined).length;
  const reached = zones.filter((z) => z.status === "RESOLVED_REACHED").length;
  const out: Array<{ metric: string; value: number }> = [];
  out.push({ metric: "zones_total", value: total });
  out.push({ metric: "zones_triggered", value: triggered });
  out.push({ metric: "zones_reached", value: reached });
  out.push({ metric: "hit_rate_among_triggered", value: triggered > 0 ? reached / triggered : 0 });
  if (dedup) {
    out.push({ metric: "deduplication_enabled", value: dedup.enabled ? 1 : 0 });
    out.push({ metric: "cooldown_minutes_after_resolve", value: dedup.cooldownMinutesAfterResolve });
    out.push({ metric: "duplicate_suppression_count", value: dedup.duplicateSuppressionCount });
    for (const [k, v] of Object.entries(dedup.suppressionsByReason)) {
      out.push({ metric: `suppressions_${k}`, value: v });
    }
  }
  if (moveClustering) {
    out.push({ metric: "move_clustering_enabled", value: moveClustering.enabled ? 1 : 0 });
    out.push({ metric: "move_cluster_gap_minutes", value: moveClustering.moveClusterGapMinutes });
    out.push({ metric: "reached_zones_raw", value: moveClustering.reachedZonesRaw });
    out.push({ metric: "unique_reached_moves", value: moveClustering.uniqueReachedMoves });
    out.push({ metric: "duplicate_move_credits", value: moveClustering.duplicateMoveCredits });
    out.push({ metric: "raw_triggered_hit_rate", value: moveClustering.rawTriggeredHitRate });
    out.push({ metric: "unique_move_adjusted_hit_rate", value: moveClustering.uniqueMoveAdjustedHitRate });
  }
  for (const [k, v] of Object.entries(counts)) out.push({ metric: k, value: v });
  return out;
}

function buildAnnotations(zones: Zone[]): unknown {
  return {
    type: "orderflow_zones_v1",
    rectangles: zones.map((z) => ({
      id: z.id,
      direction: z.direction,
      status: z.status,
      from: z.startTs,
      to: z.resolvedTs ?? z.triggerTs ?? z.startTs,
      low: z.zoneLow,
      high: z.zoneHigh,
      reasonChain: z.reasons.map((r) => r.stage),
    })),
    triggers: zones
      .filter((z) => z.triggerTs !== undefined && z.triggerPrice !== undefined)
      .map((z) => ({ id: z.id, ts: z.triggerTs, price: z.triggerPrice, direction: z.direction })),
    targets: zones
      .filter((z) => z.targetPrice !== undefined)
      .map((z) => ({ id: z.id, price: z.targetPrice, direction: z.direction })),
  };
}
