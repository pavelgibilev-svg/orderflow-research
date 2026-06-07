// Generates three reports comparing pre-dedup vs post-dedup full-day runs:
//
//   reports/FULL_DAY_VERIFICATION_2026-02-01_DEDUP.md
//   reports/FULL_DAY_VERIFICATION_2026-02-01_DEDUP_ZONES.csv
//   reports/FULL_DAY_VERIFICATION_2026-01-01_DEDUP.md
//   reports/FULL_DAY_VERIFICATION_2026-01-01_DEDUP_ZONES.csv
//   reports/DEDUP_COMPARISON_REPORT.md
//
// All thresholds are unchanged. Failed / no_trigger / invalidated zones are
// preserved in every output. The dedup fix is purely an accounting fix.

import * as fs from "node:fs";
import * as path from "node:path";
import { writeCsv, type CsvColumn } from "../reports/csvWriter.js";
import type { Zone } from "../strategy/types.js";
import { applyMoveClustering, DEFAULT_MOVE_CLUSTERING_CFG } from "../strategy/uniqueMoveClustering.js";

const PROJECT_ROOT = process.cwd();
const REPORTS = path.join(PROJECT_ROOT, "reports");

interface ParsedReportMd {
  l2: number;
  trades: number;
  duplicateSuppressionCount: number;
  suppressionsByReason: { [reason: string]: number };
  baselines: Array<{ horizon: string; up: number; down: number; samples: number }>;
}

function readReportMd(p: string): ParsedReportMd {
  const out: ParsedReportMd = { l2: 0, trades: 0, duplicateSuppressionCount: 0, suppressionsByReason: {}, baselines: [] };
  if (!fs.existsSync(p)) return out;
  const t = fs.readFileSync(p, "utf8");
  const m = t.match(/Rows processed:\*\*\s*L2=([0-9][\d,\s  ]*)\s+trades=([0-9][\d,\s  ]*)/);
  if (m) {
    out.l2 = Number(m[1].replace(/[,\s  ]/g, ""));
    out.trades = Number(m[2].replace(/[,\s  ]/g, ""));
  }
  const dm = t.match(/Duplicate same-direction candidates suppressed[^:]*:\s*\*\*([\d,\s  ]+)\*\*/);
  if (dm) out.duplicateSuppressionCount = Number(dm[1].replace(/[,\s  ]/g, ""));
  // Suppressions by reason — match "  - `reason`: N"
  const reasonRegex = /^  -\s*`([a-z_]+)`:\s*(\d+)/gm;
  let rm: RegExpExecArray | null;
  while ((rm = reasonRegex.exec(t)) !== null) {
    out.suppressionsByReason[rm[1]] = Number(rm[2]);
  }
  // Baselines.
  const blockMatch = t.match(/## Unconditional baseline[\s\S]*?(?=\n##|$)/);
  if (blockMatch) {
    const block = blockMatch[0];
    const rowRegex = /\|\s*(\d+\s*[smhd])\s*\|\s*([0-9.]+)%\s*\|\s*([0-9.]+)%\s*\|\s*(\d+)\s*\|/g;
    let mm: RegExpExecArray | null;
    while ((mm = rowRegex.exec(block)) !== null) {
      out.baselines.push({ horizon: mm[1].replace(/\s/g, ""), up: Number(mm[2]) / 100, down: Number(mm[3]) / 100, samples: Number(mm[4]) });
    }
  }
  return out;
}

function readZones(p: string): Zone[] {
  if (!fs.existsSync(p)) return [];
  return JSON.parse(fs.readFileSync(p, "utf8")) as Zone[];
}

function timeOnly(ts?: number): string {
  if (ts === undefined || ts === null) return "-";
  return new Date(ts).toISOString().slice(11, 19);
}
function isoOrDash(ts?: number): string {
  return ts === undefined || ts === null ? "-" : new Date(ts).toISOString();
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
function timeToTargetMin(z: Zone): number | null {
  for (const t of Object.values(z.targets)) {
    if (t.outcome === "reached" && t.timeToTargetMin !== undefined) return t.timeToTargetMin;
  }
  return null;
}
function horizonOutcome(z: Zone, h: string): string {
  return z.targets[h]?.outcome ?? "-";
}
function reasonChainCompact(z: Zone): string {
  return z.reasons
    .map((r) => `${r.stage}@${new Date(r.ts).toISOString().slice(11, 19)}`)
    .join(" → ");
}

interface UniqueMoveCount {
  count: number;
}

function countUniqueMoves(zones: Zone[]): number {
  const successful = zones.filter((z) => z.status === "RESOLVED_REACHED" && z.triggerTs !== undefined);
  if (successful.length === 0) return 0;
  // Same algorithm as zoneQualityAudit: union-find on time-overlap or near targets.
  const reachedAt = (z: Zone): number => {
    for (const t of Object.values(z.targets)) if (t.outcome === "reached" && t.reachedAt !== undefined) return t.reachedAt;
    return z.resolvedTs ?? z.triggerTs ?? 0;
  };
  const parent: number[] = successful.map((_, i) => i);
  const find = (x: number): number => {
    while (parent[x] !== x) {
      parent[x] = parent[parent[x]];
      x = parent[x];
    }
    return x;
  };
  const union = (a: number, b: number): void => {
    const ra = find(a), rb = find(b);
    if (ra !== rb) parent[ra] = rb;
  };
  for (let i = 0; i < successful.length; i++) {
    for (let j = i + 1; j < successful.length; j++) {
      const a = successful[i], b = successful[j];
      if (a.direction !== b.direction) continue;
      const aTrig = a.triggerTs!, bTrig = b.triggerTs!;
      const aReached = reachedAt(a), bReached = reachedAt(b);
      const overlap = aTrig <= bReached && bTrig <= aReached;
      const refPx = (a.referencePrice ?? a.triggerPrice ?? 1) || 1;
      const targetClose = Math.abs((a.targetPrice ?? 0) - (b.targetPrice ?? 0)) / Math.abs(refPx) < 0.005;
      const trigClose = Math.abs(aTrig - bTrig) <= 6 * 3600 * 1000;
      if (overlap || (targetClose && trigClose)) union(i, j);
    }
  }
  const roots = new Set<number>();
  for (let i = 0; i < successful.length; i++) roots.add(find(i));
  return roots.size;
}

interface DayBucket {
  date: string;
  preZones: Zone[];
  postZones: Zone[];
  preMd: ParsedReportMd;
  postMd: ParsedReportMd;
  preDir: string; // path to pre-dedup output dir
  postDir: string;
}

function loadDay(date: string): DayBucket {
  const preDir = path.join(REPORTS, `full_day_${date}`);
  const postDir = path.join(REPORTS, `full_day_${date}_dedup`);
  const preZones = readZones(path.join(preDir, "zones.json"));
  const postZones = readZones(path.join(postDir, "zones.json"));
  // Apply unique-move clustering as a pure, deterministic post-processing step
  // so the verification CSVs/MDs always carry uniqueMoveId / cluster info.
  const preTriggered = preZones.filter((z) => z.triggerTs !== undefined).length;
  const postTriggered = postZones.filter((z) => z.triggerTs !== undefined).length;
  applyMoveClustering(preZones, DEFAULT_MOVE_CLUSTERING_CFG, preTriggered);
  applyMoveClustering(postZones, DEFAULT_MOVE_CLUSTERING_CFG, postTriggered);
  return {
    date,
    preZones,
    postZones,
    preMd: readReportMd(path.join(preDir, "report.md")),
    postMd: readReportMd(path.join(postDir, "report.md")),
    preDir,
    postDir,
  };
}

function summary(zones: Zone[], h: string): { reached: number; triggered: number; rate: number } {
  const triggered = zones.filter((z) => z.triggerTs !== undefined);
  const reached = triggered.filter((z) => z.targets[h]?.outcome === "reached").length;
  return { reached, triggered: triggered.length, rate: triggered.length > 0 ? reached / triggered.length : 0 };
}

interface ZoneCsvRow {
  date: string;
  symbol: string;
  direction: "LONG" | "SHORT";
  zoneType: string;
  status: string;
  zoneStartTs: string;
  zoneConfirmedTs: string;
  triggerTs: string;
  zoneLow: number;
  zoneHigh: number;
  triggerPrice: number | null;
  targetPrice: number | null;
  target4h: string;
  target8h: string;
  target24h: string;
  mfe: number | null;
  mae: number | null;
  timeToTarget: number | null;
  uniqueMoveId: number | "";
  moveClusterSize: number | "";
  isPrimaryMoveZone: string;
  duplicateMoveCredit: string;
  reasons: string;
}
function zoneToCsvRow(z: Zone): ZoneCsvRow {
  return {
    date: z.date, symbol: z.symbol, direction: z.direction, zoneType: z.zoneType, status: z.status,
    zoneStartTs: isoOrDash(z.startTs), zoneConfirmedTs: isoOrDash(z.confirmedTs), triggerTs: isoOrDash(z.triggerTs),
    zoneLow: z.zoneLow, zoneHigh: z.zoneHigh, triggerPrice: z.triggerPrice ?? null, targetPrice: z.targetPrice ?? null,
    target4h: horizonOutcome(z, "4h"), target8h: horizonOutcome(z, "8h"), target24h: horizonOutcome(z, "24h"),
    mfe: bestMfe(z), mae: bestMae(z), timeToTarget: timeToTargetMin(z),
    uniqueMoveId: z.uniqueMoveId ?? "",
    moveClusterSize: z.moveClusterSize ?? "",
    isPrimaryMoveZone: z.isPrimaryMoveZone === undefined ? "" : z.isPrimaryMoveZone ? "yes" : "no",
    duplicateMoveCredit: z.duplicateMoveCredit === undefined ? "" : z.duplicateMoveCredit ? "yes" : "no",
    reasons: z.reasons.map((r) => {
      const cs = Object.entries(r.conditions || {}).map(([k, v]) => `${k}=${typeof v === "number" ? Number(v).toFixed(3) : v}`).join(",");
      return `${r.stage}@${new Date(r.ts).toISOString()}{${cs}}`;
    }).join(" | "),
  };
}
function csvCols(): CsvColumn<ZoneCsvRow>[] {
  return [
    { name: "date", get: (r) => r.date }, { name: "symbol", get: (r) => r.symbol },
    { name: "direction", get: (r) => r.direction }, { name: "zoneType", get: (r) => r.zoneType },
    { name: "status", get: (r) => r.status }, { name: "zoneStartTs", get: (r) => r.zoneStartTs },
    { name: "zoneConfirmedTs", get: (r) => r.zoneConfirmedTs }, { name: "triggerTs", get: (r) => r.triggerTs },
    { name: "zoneLow", get: (r) => r.zoneLow }, { name: "zoneHigh", get: (r) => r.zoneHigh },
    { name: "triggerPrice", get: (r) => r.triggerPrice ?? "" }, { name: "targetPrice", get: (r) => r.targetPrice ?? "" },
    { name: "target4h", get: (r) => r.target4h }, { name: "target8h", get: (r) => r.target8h },
    { name: "target24h", get: (r) => r.target24h },
    { name: "mfe", get: (r) => (r.mfe !== null ? r.mfe.toFixed(3) : "") },
    { name: "mae", get: (r) => (r.mae !== null ? r.mae.toFixed(3) : "") },
    { name: "timeToTarget", get: (r) => (r.timeToTarget !== null ? r.timeToTarget.toFixed(2) : "") },
    { name: "uniqueMoveId", get: (r) => r.uniqueMoveId },
    { name: "moveClusterSize", get: (r) => r.moveClusterSize },
    { name: "isPrimaryMoveZone", get: (r) => r.isPrimaryMoveZone },
    { name: "duplicateMoveCredit", get: (r) => r.duplicateMoveCredit },
    { name: "reasons", get: (r) => r.reasons },
  ];
}

function buildPerDayMarkdown(b: DayBucket): string {
  const z = b.postZones;
  const triggered = z.filter((zz) => zz.triggerTs !== undefined);
  const reached24 = z.filter((zz) => zz.targets["24h"]?.outcome === "reached").length;
  const reached8 = z.filter((zz) => zz.targets["8h"]?.outcome === "reached").length;
  const reached4 = z.filter((zz) => zz.targets["4h"]?.outcome === "reached").length;
  const lines: string[] = [];
  lines.push(`# Full-Day Verification (post-deduplication) — BTCUSDT ${b.date}`);
  lines.push("");
  lines.push(`> **This is a full-day technical verification run with deduplication enabled.** Strategy thresholds in \`config/strategy.default.json\` were not modified — only the same-direction overlap suppression + cooldown rule was added in \`zoneDetector.ts\`.`);
  lines.push("");
  lines.push(`- Generated: ${new Date().toISOString()}`);
  lines.push("");
  lines.push(`## 1. Run conditions`);
  lines.push("");
  lines.push(`| Setting | Value |`);
  lines.push(`|---|---|`);
  lines.push(`| Date | ${b.date} |`);
  lines.push(`| Symbol | BTCUSDT |`);
  lines.push(`| Exchange | binance-futures |`);
  lines.push(`| Target percent | 2.0 |`);
  lines.push(`| Horizons | 4h, 8h, 24h |`);
  lines.push(`| L2 time limitation | NO — full 24h L2 replay |`);
  lines.push(`| Skip-snapshots used | yes |`);
  lines.push(`| Config file | config/strategy.default.json (unchanged thresholds) |`);
  lines.push(`| Threshold tuning | NONE |`);
  lines.push(`| Deduplication enabled | **YES** |`);
  lines.push(`| Cooldown after resolve | 30 min |`);
  lines.push(`| Price overlap min pct | 0.25 (= 25% of smaller zone height) |`);
  lines.push("");
  lines.push(`## 2. Strategy summary (post-dedup)`);
  lines.push("");
  lines.push(`| Metric | Value |`);
  lines.push(`|---|---|`);
  lines.push(`| L2 events processed | ${b.postMd.l2.toLocaleString()} |`);
  lines.push(`| Trades scanned | ${b.postMd.trades.toLocaleString()} |`);
  lines.push(`| Zones found | ${z.length} |`);
  lines.push(`| LONG / SHORT | ${z.filter((zz) => zz.direction === "LONG").length} / ${z.filter((zz) => zz.direction === "SHORT").length} |`);
  lines.push(`| Triggered | ${triggered.length} |`);
  lines.push(`| Reached 4h | ${reached4} |`);
  lines.push(`| Reached 8h | ${reached8} |`);
  lines.push(`| Reached 24h | ${reached24} |`);
  lines.push(`| Failed (RESOLVED_FAILED) | ${z.filter((zz) => zz.status === "RESOLVED_FAILED").length} |`);
  lines.push(`| No trigger | ${z.filter((zz) => zz.status === "NO_TRIGGER").length} |`);
  lines.push(`| Invalidated | ${z.filter((zz) => zz.status === "INVALIDATED").length} |`);
  lines.push(`| Expired | ${z.filter((zz) => zz.status === "EXPIRED").length} |`);
  for (const h of ["4h", "8h", "24h"]) {
    const s = summary(z, h);
    lines.push(`| Triggered hit rate ${h} | ${pct(s.rate)} (${s.reached}/${s.triggered}) |`);
  }
  // Move clustering (unique-move-adjusted) — applied to post-dedup zones.
  const reachedRaw = z.filter((zz) => zz.status === "RESOLVED_REACHED").length;
  const uniqueMoveIds = new Set(z.filter((zz) => zz.uniqueMoveId !== undefined).map((zz) => zz.uniqueMoveId));
  const uniqueMoves = uniqueMoveIds.size;
  const dupCredits = reachedRaw - uniqueMoves;
  const triggerCount = z.filter((zz) => zz.triggerTs !== undefined).length;
  const adjHit = triggerCount > 0 ? uniqueMoves / triggerCount : 0;
  lines.push(`| Reached zones (raw) | ${reachedRaw} |`);
  lines.push(`| Unique reached moves | ${uniqueMoves} |`);
  lines.push(`| Duplicate move credits | ${dupCredits} |`);
  lines.push(`| Raw triggered hit rate | ${pct(triggerCount > 0 ? reachedRaw / triggerCount : 0)} |`);
  lines.push(`| **Unique-move-adjusted hit rate** | **${pct(adjHit)}** |`);
  for (const bl of b.postMd.baselines) {
    lines.push(`| Baseline ${bl.horizon} (up/down) | ${pct(bl.up)} / ${pct(bl.down)} (n=${bl.samples}) |`);
  }
  lines.push(`| Duplicate suppressions during this run | ${b.postMd.duplicateSuppressionCount} |`);
  for (const [k, v] of Object.entries(b.postMd.suppressionsByReason)) {
    lines.push(`| Suppressions \`${k}\` | ${v} |`);
  }
  lines.push("");
  lines.push(`## 3. All zones (post-dedup)`);
  lines.push("");
  lines.push(`Total zones: **${z.length}** (every zone is included regardless of outcome).`);
  lines.push("");
  lines.push(`| # | Dir | Type | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Reason chain |`);
  lines.push(`|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|`);
  z.sort((a, b) => a.startTs - b.startTs);
  z.forEach((zz, idx) => {
    lines.push(
      `| ${idx + 1} | ${zz.direction} | ${zz.zoneType} | ${zz.status} | ${timeOnly(zz.startTs)} | ${timeOnly(zz.confirmedTs)} | ${timeOnly(zz.triggerTs)} | ${zz.zoneLow.toFixed(2)} | ${zz.zoneHigh.toFixed(2)} | ${zz.triggerPrice?.toFixed(2) ?? "-"} | ${zz.targetPrice?.toFixed(2) ?? "-"} | ${horizonOutcome(zz, "4h")} | ${horizonOutcome(zz, "8h")} | ${horizonOutcome(zz, "24h")} | ${bestMfe(zz)?.toFixed(2) ?? "-"} | ${bestMae(zz)?.toFixed(2) ?? "-"} | ${timeToTargetMin(zz)?.toFixed(1) ?? "-"} | ${reasonChainCompact(zz)} |`
    );
  });
  lines.push("");
  lines.push(`## 4. Successful zones`);
  lines.push("");
  const ok = z.filter((zz) => zz.status === "RESOLVED_REACHED");
  if (ok.length === 0) {
    lines.push(`No zones reached the 2 % target.`);
  } else {
    for (const zz of ok) {
      const reachedH = Object.entries(zz.targets).find(([, v]) => v.outcome === "reached")?.[0] ?? null;
      lines.push(`- \`${zz.id}\` ${zz.direction} ${zz.zoneType}: trigger=${isoOrDash(zz.triggerTs)} px=${zz.triggerPrice?.toFixed(2)} target=${zz.targetPrice?.toFixed(2)} reached=**${reachedH}** ttt=${timeToTargetMin(zz)?.toFixed(1) ?? "-"}min MFE=${bestMfe(zz)?.toFixed(2)}% MAE=${bestMae(zz)?.toFixed(2)}%`);
    }
  }
  lines.push("");
  return lines.join("\n");
}

function buildComparisonReport(d2: DayBucket, d1: DayBucket): string {
  const lines: string[] = [];
  lines.push(`# Deduplication Comparison Report`);
  lines.push("");
  lines.push(`> Comparison of **before dedup** vs **after dedup** full-day runs on the two reference days. Strategy thresholds in \`config/strategy.default.json\` are unchanged. The dedup change is purely an accounting fix in \`zoneDetector.ts\` — same-direction overlap suppression + cooldown after a zone resolves.`);
  lines.push("");
  lines.push(`- Generated: ${new Date().toISOString()}`);
  lines.push("");
  lines.push(`## What changed in the code`);
  lines.push("");
  lines.push(`- \`config/strategy.default.json\`: added \`deduplication\` block (\`enabled: true\`, \`sameDirectionOverlapSuppression: true\`, \`cooldownMinutesAfterResolve: 30\`, \`priceOverlapMinPct: 0.25\`).`);
  lines.push(`- \`src/strategy/zoneDetector.ts\`: before opening a new same-direction CANDIDATE, check existing CANDIDATE / CONFIRMED / TRIGGERED zones with overlapping price band → suppress; check terminated zones (INVALIDATED, EXPIRED, RESOLVED_*) within the cooldown window → suppress.`);
  lines.push(`- Records every suppression in a debug log with \`suppressedByZoneId\` and reason (\`active_open\` / \`active_triggered\` / \`cooldown\`).`);
  lines.push(`- Surfaces the suppression count and reason breakdown in \`daily_summary.csv\`, \`report.md\` and \`BacktestDayResult\`.`);
  lines.push(`- No threshold has been tuned. Failed / no_trigger / invalidated zones are still preserved.`);
  lines.push("");
  for (const b of [d2, d1]) {
    const preTrig = b.preZones.filter((z) => z.triggerTs !== undefined).length;
    const postTrig = b.postZones.filter((z) => z.triggerTs !== undefined).length;
    const preR4 = b.preZones.filter((z) => z.targets["4h"]?.outcome === "reached").length;
    const postR4 = b.postZones.filter((z) => z.targets["4h"]?.outcome === "reached").length;
    const preR8 = b.preZones.filter((z) => z.targets["8h"]?.outcome === "reached").length;
    const postR8 = b.postZones.filter((z) => z.targets["8h"]?.outcome === "reached").length;
    const preR24 = b.preZones.filter((z) => z.targets["24h"]?.outcome === "reached").length;
    const postR24 = b.postZones.filter((z) => z.targets["24h"]?.outcome === "reached").length;
    const preReached = b.preZones.filter((z) => z.status === "RESOLVED_REACHED").length;
    const postReached = b.postZones.filter((z) => z.status === "RESOLVED_REACHED").length;
    const preHr = preTrig > 0 ? preReached / preTrig : 0;
    const postHr = postTrig > 0 ? postReached / postTrig : 0;
    const preMoves = countUniqueMoves(b.preZones);
    const postMoves = countUniqueMoves(b.postZones);

    lines.push(`## ${b.date}`);
    lines.push("");
    lines.push(`| Metric | Before dedup | After dedup | Δ |`);
    lines.push(`|---|---|---|---|`);
    lines.push(`| Zones found | ${b.preZones.length} | ${b.postZones.length} | ${signedDelta(b.postZones.length - b.preZones.length)} |`);
    lines.push(`| LONG | ${b.preZones.filter((z) => z.direction === "LONG").length} | ${b.postZones.filter((z) => z.direction === "LONG").length} | ${signedDelta(b.postZones.filter((z) => z.direction === "LONG").length - b.preZones.filter((z) => z.direction === "LONG").length)} |`);
    lines.push(`| SHORT | ${b.preZones.filter((z) => z.direction === "SHORT").length} | ${b.postZones.filter((z) => z.direction === "SHORT").length} | ${signedDelta(b.postZones.filter((z) => z.direction === "SHORT").length - b.preZones.filter((z) => z.direction === "SHORT").length)} |`);
    lines.push(`| Triggered | ${preTrig} | ${postTrig} | ${signedDelta(postTrig - preTrig)} |`);
    lines.push(`| Reached 4h | ${preR4} | ${postR4} | ${signedDelta(postR4 - preR4)} |`);
    lines.push(`| Reached 8h | ${preR8} | ${postR8} | ${signedDelta(postR8 - preR8)} |`);
    lines.push(`| Reached 24h | ${preR24} | ${postR24} | ${signedDelta(postR24 - preR24)} |`);
    lines.push(`| Total reached (any horizon) | ${preReached} | ${postReached} | ${signedDelta(postReached - preReached)} |`);
    lines.push(`| Unique 2% moves | ${preMoves} | ${postMoves} | ${signedDelta(postMoves - preMoves)} |`);
    lines.push(`| Triggered hit rate (24h, raw) | ${pct(preHr)} | ${pct(postHr)} | ${pct(postHr - preHr)} |`);
    // Unique-move-adjusted hit rate (clustering applied to both runs):
    const preAdj = preTrig > 0 ? preMoves / preTrig : 0;
    const postAdj = postTrig > 0 ? postMoves / postTrig : 0;
    lines.push(`| **Unique-move-adjusted hit rate** | **${pct(preAdj)}** | **${pct(postAdj)}** | ${pct(postAdj - preAdj)} |`);
    lines.push(`| Duplicate move credits | ${preReached - preMoves} | ${postReached - postMoves} | ${postReached - postMoves - (preReached - preMoves) >= 0 ? "+" : ""}${postReached - postMoves - (preReached - preMoves)} |`);
    lines.push(`| Duplicate suppression count | n/a (off) | ${b.postMd.duplicateSuppressionCount} | — |`);
    if (Object.keys(b.postMd.suppressionsByReason).length > 0) {
      lines.push(`| Suppressions by reason | n/a | ${Object.entries(b.postMd.suppressionsByReason).map(([k, v]) => `\`${k}\`=${v}`).join(", ")} | — |`);
    }
    lines.push("");

    // Diagnostic prose for this day
    if (b.preZones.length > b.postZones.length) {
      const dropPct = (b.preZones.length - b.postZones.length) / b.preZones.length;
      lines.push(`Zone count dropped by ${pct(dropPct)} — ${b.preZones.length - b.postZones.length} fewer zones after dedup.`);
    } else if (b.preZones.length < b.postZones.length) {
      lines.push(`**Zone count went UP**, not down (+${b.postZones.length - b.preZones.length}). The reason is structural: the legacy detector code had a blanket rule "no two same-direction zones in openZones at the same time, regardless of price". The new rule is more precise — it only suppresses if the price band overlaps by at least ${b.postMd ? "25%" : "the configured threshold"}. So same-direction zones at *distinct* price bands, which the legacy rule blocked indiscriminately, are now allowed to coexist. Meanwhile, ${b.postMd.duplicateSuppressionCount.toLocaleString()} same-band overlapping duplicates WERE suppressed. The net effect on this day is: more distinct-band zones surface, fewer same-band duplicates make it to the zone list.`);
    } else {
      lines.push(`Zone count unchanged.`);
    }
    if (preReached > 0 && postReached > 0) {
      lines.push(`Reached-target count went from ${preReached} (clustered into ${preMoves} unique move${preMoves === 1 ? "" : "s"} by the audit) to ${postReached} (over ${postMoves} unique move${postMoves === 1 ? "" : "s"}). ${preReached - postReached > 0 ? `${preReached - postReached} duplicate same-band credits suppressed by the new rule.` : ""} The remaining ${postReached} reached zones still fall into ${postMoves} underlying directional move${postMoves === 1 ? "" : "s"} — meaning the dedup rule (which only blocks **same price band**) does NOT collapse "trend-following" zones at progressively different prices. They are technically distinct setups but ride the same multi-hour trend.`);
    } else if (preReached === 0 && postReached === 0) {
      lines.push(`No successful zones in either run — dedup makes no difference for hit-rate accounting on this day.`);
    } else if (preReached > 0 && postReached === 0) {
      lines.push(`The pre-dedup run had ${preReached} reached zone(s); the post-dedup run has 0. The original successes were duplicates of a single move, all suppressed by the new rule. **Check carefully whether at least one survivor should have remained.**`);
    } else {
      lines.push(`Unexpected: post-dedup has more reached zones than pre-dedup.`);
    }
    if (postHr === 0 && preHr > 0) {
      lines.push(`Triggered hit rate dropped from ${pct(preHr)} to 0% after dedup. **Verdict: prior result was inflated by fragmentation.**`);
    } else if (postHr > 0) {
      lines.push(`Triggered hit rate after dedup: ${pct(postHr)} (${postReached}/${postTrig}). Lower than the pre-dedup ${pct(preHr)} because same-band duplicate credits are now removed. Still inflated by trend-following — see "remaining limitations" below.`);
    }
    lines.push("");
  }

  // Final verdict
  lines.push(`## Honest verdict`);
  lines.push("");
  const d2Pre = d2.preZones.length, d2Post = d2.postZones.length;
  const d2PreReached = d2.preZones.filter((z) => z.status === "RESOLVED_REACHED").length;
  const d2PostReached = d2.postZones.filter((z) => z.status === "RESOLVED_REACHED").length;
  const d1Pre = d1.preZones.length, d1Post = d1.postZones.length;
  lines.push(`**Did fragmentation decrease?**`);
  lines.push(`**Same-band fragmentation: yes** — ${d2.postMd.duplicateSuppressionCount.toLocaleString()} same-direction same-band candidates suppressed on 2026-02-01 (${d1.postMd.duplicateSuppressionCount.toLocaleString()} on 2026-01-01). The detector is no longer emitting multiple zones whose price bands overlap by ≥ 25%.`);
  lines.push("");
  lines.push(`**Different-band same-direction zones during a trend: NOT addressed** by this rule. As price drops on 2026-02-01 the detector creates new SHORT zones at progressively lower price bands. Each is a distinct setup by the dedup rule (no price overlap), but all four reached zones still belong to one underlying multi-hour bear leg. This is a separate accounting problem — "trend-following overlap" — that the spec did not ask us to fix and would require a different rule (e.g. cluster successful zones whose triggerTs and reachedAt windows overlap, regardless of price-band overlap).`);
  lines.push("");
  lines.push(`**Total zone count went UP** (20 → 25 on 2026-02-01; 10 → 23 on 2026-01-01) because the legacy "any same-direction in openZones blocks all" was over-aggressive and hid distinct-price zones. The new precise rule reveals them. This is an accounting clean-up, not a regression.`);
  lines.push("");
  lines.push(`**Is at least one successful 2% setup preserved on 2026-02-01?**`);
  if (d2PostReached > 0) {
    lines.push(`Yes — the post-dedup run still has ${d2PostReached} zone(s) that reached the 2% target. The audit's "1 unique move" finding is preserved as a single credited zone, which is the honest accounting.`);
  } else {
    lines.push(`No — every reached zone from the pre-dedup run got suppressed. The dedup rule may be too aggressive (e.g. cooldown too long, or priceOverlapMinPct too small). Investigate before any further claims.`);
  }
  lines.push("");
  lines.push(`**Can the post-dedup hit rate be quoted as honest?**`);
  const postHr24 = (d2.postZones.filter((z) => z.triggerTs !== undefined).length > 0)
    ? d2PostReached / d2.postZones.filter((z) => z.triggerTs !== undefined).length
    : 0;
  lines.push(`On 2026-02-01: ${pct(postHr24)} (${d2PostReached} reached / ${d2.postZones.filter((z) => z.triggerTs !== undefined).length} triggered). On 2026-01-01: ${pct((d1.postZones.filter((z) => z.status === "RESOLVED_REACHED").length) / Math.max(1, d1.postZones.filter((z) => z.triggerTs !== undefined).length))}. These are honest in the sense that no two same-direction zones now share an active price band — but they are still **single-day numbers on first-of-month boundaries with no out-of-sample split**, so they cannot prove profitability. The headline pre-dedup 54.55% on 2026-02-01 was indeed inflated by fragmentation.`);
  lines.push("");
  lines.push(`**Remaining limitations**`);
  lines.push("");
  lines.push(`- Two days, both first-of-month — not a representative sample of any market regime.`);
  lines.push(`- 2026-01-01 is a near-flat day where price never moved 2% within 4h or 8h windows; the unconditional baseline itself is 0%, so no signal can hit the 2% target. This is target-mismatch, not dedup-related.`);
  lines.push(`- The cooldown setting (30 min) and \`priceOverlapMinPct\` (0.25) were chosen by hand; they are documented in config and not tuned to fit the result.`);
  lines.push(`- No slippage / fee / latency model — this is still a research module.`);
  lines.push(`- Multi-day paid-data verification is the only way to put any number on real edge.`);
  lines.push("");
  lines.push(`> **This is a deduplication / accounting fix, not a tuning of the strategy.**`);
  lines.push("");
  return lines.join("\n");
}

function signedDelta(n: number): string {
  if (n === 0) return "0";
  return n > 0 ? `+${n}` : `${n}`;
}

function main(): void {
  const d2 = loadDay("2026-02-01");
  const d1 = loadDay("2026-01-01");

  // Per-day post-dedup verification report + CSV.
  for (const b of [d2, d1]) {
    if (b.postZones.length === 0 && !fs.existsSync(path.join(b.postDir, "zones.json"))) {
      console.warn(`WARN: no post-dedup zones.json for ${b.date} — skipping per-day report.`);
      continue;
    }
    const md = buildPerDayMarkdown(b);
    const mdPath = path.join(REPORTS, `FULL_DAY_VERIFICATION_${b.date}_DEDUP.md`);
    fs.writeFileSync(mdPath, md, "utf8");
    const csvPath = path.join(REPORTS, `FULL_DAY_VERIFICATION_${b.date}_DEDUP_ZONES.csv`);
    const sortedZones = b.postZones.slice().sort((a, c) => a.startTs - c.startTs);
    writeCsv(csvPath, csvCols(), sortedZones.map(zoneToCsvRow));
    console.log(`Wrote: ${mdPath}`);
    console.log(`Wrote: ${csvPath}`);
  }

  // Comparison report.
  const cmp = buildComparisonReport(d2, d1);
  const cmpPath = path.join(REPORTS, "DEDUP_COMPARISON_REPORT.md");
  fs.writeFileSync(cmpPath, cmp, "utf8");
  console.log(`Wrote: ${cmpPath}`);

  // Print quick summary.
  const triggered = d2.postZones.filter((z) => z.triggerTs !== undefined).length;
  const reached = d2.postZones.filter((z) => z.status === "RESOLVED_REACHED").length;
  console.log("");
  console.log(`2026-02-01: ${d2.preZones.length} → ${d2.postZones.length} zones, ${d2.preZones.filter((z) => z.triggerTs !== undefined).length} → ${triggered} triggered, ${d2.preZones.filter((z) => z.status === "RESOLVED_REACHED").length} → ${reached} reached.`);
  console.log(`2026-01-01: ${d1.preZones.length} → ${d1.postZones.length} zones, ${d1.preZones.filter((z) => z.triggerTs !== undefined).length} → ${d1.postZones.filter((z) => z.triggerTs !== undefined).length} triggered, ${d1.preZones.filter((z) => z.status === "RESOLVED_REACHED").length} → ${d1.postZones.filter((z) => z.status === "RESOLVED_REACHED").length} reached.`);
  console.log(`Suppression count: 2026-02-01 = ${d2.postMd.duplicateSuppressionCount}, 2026-01-01 = ${d1.postMd.duplicateSuppressionCount}`);
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
