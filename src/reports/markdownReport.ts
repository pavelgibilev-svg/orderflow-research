// Plain markdown report generator. The report is the human-facing summary
// the spec demands at §10.

import type { Zone, ZoneStatus } from "../strategy/types.js";
import type { BaselineResult } from "../strategy/probabilityBaseline.js";

export interface ReportInputs {
  symbol: string;
  date: string;
  exchange: string;
  zones: Zone[];
  baselines: BaselineResult[];
  qualityNotes: string[];
  durationMs: number;
  rowsProcessed: { l2: number; trades: number; other: number };
  warnings: string[];
  /** Optional dedup accounting (added when ZoneDetector runs with cfg.deduplication.enabled). */
  dedup?: {
    enabled: boolean;
    cooldownMinutesAfterResolve: number;
    duplicateSuppressionCount: number;
    suppressionsByReason: { [reason: string]: number };
  };
  /** Optional unique-move clustering accounting. */
  moveClustering?: {
    enabled: boolean;
    moveClusterGapMinutes: number;
    reachedZonesRaw: number;
    uniqueReachedMoves: number;
    duplicateMoveCredits: number;
    rawTriggeredHitRate: number;
    uniqueMoveAdjustedHitRate: number;
    clusters: Array<{ uniqueMoveId: number; direction: string; size: number; zoneIds: string[]; primaryZoneId: string }>;
  };
}

export function buildMarkdownReport(input: ReportInputs): string {
  const total = input.zones.length;
  const byStatus = new Map<ZoneStatus, number>();
  for (const z of input.zones) byStatus.set(z.status, (byStatus.get(z.status) ?? 0) + 1);
  const longCount = input.zones.filter((z) => z.direction === "LONG").length;
  const shortCount = input.zones.filter((z) => z.direction === "SHORT").length;
  const triggered = input.zones.filter((z) => z.triggerTs !== undefined);
  const reached = input.zones.filter((z) => z.status === "RESOLVED_REACHED").length;
  const failed = input.zones.filter((z) => z.status === "RESOLVED_FAILED").length;
  const noTrigger = input.zones.filter((z) => z.status === "NO_TRIGGER").length;
  const invalid = input.zones.filter((z) => z.status === "INVALIDATED").length;
  const expired = input.zones.filter((z) => z.status === "EXPIRED").length;

  const hitRateTriggered = triggered.length > 0 ? reached / triggered.length : 0;

  const lines: string[] = [];
  lines.push(`# Orderflow L2 Strategy — Daily Report`);
  lines.push("");
  lines.push(`- **Symbol:** ${input.symbol}`);
  lines.push(`- **Exchange:** ${input.exchange}`);
  lines.push(`- **Date (UTC):** ${input.date}`);
  lines.push(`- **Replay duration:** ${(input.durationMs / 1000).toFixed(1)}s`);
  lines.push(`- **Rows processed:** L2=${input.rowsProcessed.l2.toLocaleString()}  trades=${input.rowsProcessed.trades.toLocaleString()}  other=${input.rowsProcessed.other.toLocaleString()}`);
  lines.push("");
  lines.push(`## Zone summary`);
  lines.push("");
  lines.push(`| Metric | Value |`);
  lines.push(`|---|---|`);
  lines.push(`| Total zones | ${total} |`);
  lines.push(`| LONG / SHORT | ${longCount} / ${shortCount} |`);
  lines.push(`| Triggered | ${triggered.length} |`);
  lines.push(`| Reached target | ${reached} |`);
  lines.push(`| Failed by timeout | ${failed} |`);
  lines.push(`| Invalidated before trigger | ${invalid} |`);
  lines.push(`| Expired (formation aged out) | ${expired} |`);
  lines.push(`| No trigger by end of day | ${noTrigger} |`);
  lines.push(`| Hit rate among triggered | ${(hitRateTriggered * 100).toFixed(2)}% |`);
  lines.push("");
  lines.push(`> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.`);
  lines.push("");

  if (input.baselines.length > 0) {
    lines.push(`## Unconditional baseline (price walk only, no zone signal)`);
    lines.push("");
    lines.push(`| Horizon | Up rate | Down rate | Samples |`);
    lines.push(`|---|---|---|---|`);
    for (const b of input.baselines) {
      lines.push(`| ${b.horizon} | ${(b.upRate * 100).toFixed(2)}% | ${(b.downRate * 100).toFixed(2)}% | ${b.totalSamples} |`);
    }
    lines.push("");
    lines.push(`> Compare zone hit rate against this baseline to see whether the signal adds anything.`);
    lines.push("");
  }

  // Top 5 zones by absorption*void score, only triggered ones.
  const ranked = triggered
    .slice()
    .sort((a, b) => b.scores.absorptionScore * b.scores.liquidityVoidScore - a.scores.absorptionScore * a.scores.liquidityVoidScore)
    .slice(0, 5);
  if (ranked.length > 0) {
    lines.push(`## Top zones by absorption × void score`);
    lines.push("");
    lines.push(`| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |`);
    lines.push(`|---|---|---|---|---|---|---|`);
    for (const z of ranked) {
      const reachedH = Object.keys(z.targets).find((h) => z.targets[h].outcome === "reached") ?? "-";
      lines.push(
        `| ${z.id} | ${z.direction} | ${z.triggerTs ? new Date(z.triggerTs).toISOString() : "-"} | ${z.triggerPrice?.toFixed(2) ?? "-"} | ${z.targetPrice?.toFixed(2) ?? "-"} | ${z.status} | ${reachedH} |`
      );
    }
    lines.push("");
  }

  if (input.moveClustering) {
    const mc = input.moveClustering;
    lines.push(`## Move clustering accounting`);
    lines.push("");
    lines.push(`Pure post-processing. Two RESOLVED_REACHED zones share a \`uniqueMoveId\` when they are the same direction and their \`[triggerTs, reachedAt]\` windows overlap or sit within \`${mc.moveClusterGapMinutes}\` minutes of each other.`);
    lines.push("");
    lines.push(`| Metric | Value |`);
    lines.push(`|---|---|`);
    lines.push(`| Move clustering enabled | ${mc.enabled ? "yes" : "no"} |`);
    lines.push(`| Reached zones (raw) | ${mc.reachedZonesRaw} |`);
    lines.push(`| Unique reached moves | ${mc.uniqueReachedMoves} |`);
    lines.push(`| Duplicate move credits | ${mc.duplicateMoveCredits} |`);
    lines.push(`| Raw triggered hit rate | ${(mc.rawTriggeredHitRate * 100).toFixed(2)}% |`);
    lines.push(`| **Unique-move adjusted hit rate** | **${(mc.uniqueMoveAdjustedHitRate * 100).toFixed(2)}%** |`);
    lines.push("");
    if (mc.clusters.length > 0) {
      lines.push(`| Move | Dir | Size | Primary zone | Members |`);
      lines.push(`|---|---|---|---|---|`);
      for (const cl of mc.clusters) {
        lines.push(`| ${cl.uniqueMoveId} | ${cl.direction} | ${cl.size} | \`${cl.primaryZoneId}\` | ${cl.zoneIds.join(", ")} |`);
      }
      lines.push("");
    }
    lines.push(`> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.`);
    lines.push("");
  }

  if (input.dedup) {
    lines.push(`## Deduplication accounting`);
    lines.push("");
    lines.push(`- Deduplication enabled: **${input.dedup.enabled ? "yes" : "no"}**`);
    lines.push(`- Cooldown after resolve: **${input.dedup.cooldownMinutesAfterResolve} min**`);
    lines.push(`- Duplicate same-direction candidates suppressed during this run: **${input.dedup.duplicateSuppressionCount}**`);
    if (input.dedup.duplicateSuppressionCount > 0) {
      lines.push(`- Suppressions by reason:`);
      for (const [k, v] of Object.entries(input.dedup.suppressionsByReason)) {
        lines.push(`  - \`${k}\`: ${v}`);
      }
    }
    lines.push("");
    lines.push(`> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in \`config/strategy.default.json\`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.`);
    lines.push("");
  }

  if (input.qualityNotes.length > 0) {
    lines.push(`## Data quality notes`);
    lines.push("");
    for (const n of input.qualityNotes) lines.push(`- ${n}`);
    lines.push("");
  }
  if (input.warnings.length > 0) {
    lines.push(`## Warnings`);
    lines.push("");
    for (const w of input.warnings) lines.push(`- ${w}`);
    lines.push("");
  }

  lines.push(`## Methodology recap`);
  lines.push("");
  lines.push("1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.");
  lines.push("2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.");
  lines.push("3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.");
  lines.push("4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.");
  lines.push("5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.");
  lines.push("");

  return lines.join("\n");
}
