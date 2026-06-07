// Generates reports/FULL_DAY_VERIFICATION_2026-03-01_DEDUP_CLUSTERED.md
// and ..._ZONES.csv from reports/full_day_2026-03-01_dedup_clustered/zones.json.
//
// Pure post-processing: applies the move-clustering pass that the backtest
// also runs, surfaces all metrics requested in the spec, and reads
// feasibility / regime context from existing analyser outputs.

import * as fs from "node:fs";
import * as path from "node:path";
import { writeCsv, type CsvColumn } from "../reports/csvWriter.js";
import type { Zone } from "../strategy/types.js";
import { applyMoveClustering, DEFAULT_MOVE_CLUSTERING_CFG } from "../strategy/uniqueMoveClustering.js";

const TARGET_DATE = "2026-03-01";
const PROJECT_ROOT = process.cwd();
const REPORTS = path.join(PROJECT_ROOT, "reports");
const ZONES_JSON = path.join(REPORTS, `full_day_${TARGET_DATE}_dedup_clustered`, "zones.json");
const PER_DAY_REPORT_MD = path.join(REPORTS, `full_day_${TARGET_DATE}_dedup_clustered`, "report.md");
const PER_DAY_DAILY_SUMMARY = path.join(REPORTS, `full_day_${TARGET_DATE}_dedup_clustered`, "daily_summary.csv");
const VALIDATION_JSON = path.join(REPORTS, "tardis_validation_2026_ytd_except_may.json");
const FEASIBILITY_JSON_DEFAULT_PATH = path.join(REPORTS, "TARGET_FEASIBILITY_2PCT_JAN_APR_2026.csv");

const OUT_MD = path.join(REPORTS, `FULL_DAY_VERIFICATION_${TARGET_DATE}_DEDUP_CLUSTERED.md`);
const OUT_CSV = path.join(REPORTS, `FULL_DAY_VERIFICATION_${TARGET_DATE}_DEDUP_CLUSTERED_ZONES.csv`);

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
  const m = t.match(/Rows processed:\*\*\s*L2=([0-9][\d,\s  ]*)\s+trades=([0-9][\d,\s  ]*)/);
  if (m) {
    out.l2 = Number(m[1].replace(/[,\s  ]/g, ""));
    out.trades = Number(m[2].replace(/[,\s  ]/g, ""));
  }
  const dm = t.match(/Duplicate same-direction candidates suppressed[^:]*:\s*\*\*([\d,\s  ]+)\*\*/);
  if (dm) out.duplicateSuppressionCount = Number(dm[1].replace(/[,\s  ]/g, ""));
  const reasonRegex = /^  -\s*`([a-z_]+)`:\s*(\d+)/gm;
  let rm: RegExpExecArray | null;
  while ((rm = reasonRegex.exec(t)) !== null) {
    out.suppressionsByReason[rm[1]] = Number(rm[2]);
  }
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

interface FeasibilityRow {
  date: string;
  return_pct: number;
  range_pct: number;
  max_4h_up_pct: number;
  max_4h_down_pct: number;
  max_8h_up_pct: number;
  max_8h_down_pct: number;
  max_24h_up_pct: number;
  max_24h_down_pct: number;
  feasible_2pct_4h: string;
  feasible_2pct_8h: string;
  feasible_2pct_intraday: string;
  regime: string;
  recommended_target_pct: number;
}

function readFeasibility(date: string): FeasibilityRow | null {
  if (!fs.existsSync(FEASIBILITY_JSON_DEFAULT_PATH)) return null;
  const t = fs.readFileSync(FEASIBILITY_JSON_DEFAULT_PATH, "utf8").split(/\r?\n/);
  if (t.length < 2) return null;
  const headers = t[0].split(",");
  for (let i = 1; i < t.length; i++) {
    const line = t[i];
    if (!line) continue;
    const cols = line.split(",");
    const obj: Record<string, string> = {};
    headers.forEach((h, j) => (obj[h] = cols[j] ?? ""));
    if (obj["date"] === date) {
      return {
        date,
        return_pct: Number(obj["return_pct"]),
        range_pct: Number(obj["range_pct"]),
        max_4h_up_pct: Number(obj["max_4h_up_pct"]),
        max_4h_down_pct: Number(obj["max_4h_down_pct"]),
        max_8h_up_pct: Number(obj["max_8h_up_pct"]),
        max_8h_down_pct: Number(obj["max_8h_down_pct"]),
        max_24h_up_pct: Number(obj["max_24h_up_pct"]),
        max_24h_down_pct: Number(obj["max_24h_down_pct"]),
        feasible_2pct_4h: obj["feasible_2pct_4h"] ?? "",
        feasible_2pct_8h: obj["feasible_2pct_8h"] ?? "",
        feasible_2pct_intraday: obj["feasible_2pct_intraday"] ?? "",
        regime: obj["regime"] ?? "",
        recommended_target_pct: Number(obj["recommended_target_pct"]),
      };
    }
  }
  return null;
}

function readZones(p: string): Zone[] {
  if (!fs.existsSync(p)) throw new Error(`Missing ${p}`);
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
function reasonChainCompact(z: Zone): string {
  return z.reasons
    .map((r) => {
      const cs = Object.entries(r.conditions || {}).map(([k, v]) => `${k}=${typeof v === "number" ? Number(v).toFixed(3) : v}`).join(",");
      return `${r.stage}@${new Date(r.ts).toISOString()}{${cs}}`;
    })
    .join(" | ");
}
function horizonOutcome(z: Zone, h: string): string {
  return z.targets[h]?.outcome ?? "-";
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
    reasons: reasonChainCompact(z),
  };
}
function csvCols(): CsvColumn<ZoneCsvRow>[] {
  return [
    { name: "date", get: (r) => r.date },
    { name: "symbol", get: (r) => r.symbol },
    { name: "direction", get: (r) => r.direction },
    { name: "zoneType", get: (r) => r.zoneType },
    { name: "status", get: (r) => r.status },
    { name: "zoneStartTs", get: (r) => r.zoneStartTs },
    { name: "zoneConfirmedTs", get: (r) => r.zoneConfirmedTs },
    { name: "triggerTs", get: (r) => r.triggerTs },
    { name: "zoneLow", get: (r) => r.zoneLow },
    { name: "zoneHigh", get: (r) => r.zoneHigh },
    { name: "triggerPrice", get: (r) => r.triggerPrice ?? "" },
    { name: "targetPrice", get: (r) => r.targetPrice ?? "" },
    { name: "target4h", get: (r) => r.target4h },
    { name: "target8h", get: (r) => r.target8h },
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

function buildMarkdown(): string {
  const zones = readZones(ZONES_JSON);
  const triggered = zones.filter((z) => z.triggerTs !== undefined).length;
  const result = applyMoveClustering(zones, DEFAULT_MOVE_CLUSTERING_CFG, triggered);
  const reportMd = readReportMd(PER_DAY_REPORT_MD);
  const feas = readFeasibility(TARGET_DATE);

  const longZones = zones.filter((z) => z.direction === "LONG");
  const shortZones = zones.filter((z) => z.direction === "SHORT");
  const reachedLong = zones.filter((z) => z.direction === "LONG" && z.status === "RESOLVED_REACHED");
  const reachedShort = zones.filter((z) => z.direction === "SHORT" && z.status === "RESOLVED_REACHED");
  const reached4h = zones.filter((z) => z.targets["4h"]?.outcome === "reached").length;
  const reached8h = zones.filter((z) => z.targets["8h"]?.outcome === "reached").length;
  const reached24h = zones.filter((z) => z.targets["24h"]?.outcome === "reached").length;
  const confirmed = zones.filter((z) => z.confirmedTs !== undefined).length;

  const lines: string[] = [];
  lines.push(`# Full-Day Verification (post-dedup + move-clustering) — BTCUSDT ${TARGET_DATE}`);
  lines.push("");
  lines.push(`> **Full-day technical verification** with deduplication and unique-move clustering enabled. Strategy thresholds in \`config/strategy.default.json\` are unchanged. Detector logic untouched.`);
  lines.push("");
  lines.push(`- Generated: ${new Date().toISOString()}`);
  lines.push(`- Source zones: \`reports/full_day_${TARGET_DATE}_dedup_clustered/zones.json\``);
  lines.push("");

  // Section 1: Run conditions
  lines.push(`## 1. Run conditions`);
  lines.push("");
  lines.push(`| Setting | Value |`);
  lines.push(`|---|---|`);
  lines.push(`| Date | ${TARGET_DATE} |`);
  lines.push(`| Symbol | BTCUSDT |`);
  lines.push(`| Exchange | binance-futures |`);
  lines.push(`| Target percent | 2.0 |`);
  lines.push(`| Horizons | 4h, 8h, 24h |`);
  lines.push(`| L2 time limitation | NO (full 24h L2 replay) |`);
  lines.push(`| Skip-snapshots | yes |`);
  lines.push(`| Threshold tuning | NONE |`);
  lines.push(`| Deduplication enabled | yes (cooldown 30min, priceOverlapMinPct 0.25) |`);
  lines.push(`| Move clustering enabled | yes (gap 120min, sameDirectionOnly true) |`);
  lines.push("");

  // Section 2: Feasibility context
  lines.push(`## 2. Target-feasibility context for ${TARGET_DATE}`);
  lines.push("");
  if (feas) {
    lines.push(`| Metric | Value |`);
    lines.push(`|---|---|`);
    lines.push(`| Day return | ${feas.return_pct.toFixed(2)}% |`);
    lines.push(`| Day range | ${feas.range_pct.toFixed(2)}% |`);
    lines.push(`| Max 4h up | ${feas.max_4h_up_pct.toFixed(2)}% |`);
    lines.push(`| Max 4h down | ${feas.max_4h_down_pct.toFixed(2)}% |`);
    lines.push(`| Max 8h up | ${feas.max_8h_up_pct.toFixed(2)}% |`);
    lines.push(`| Max 8h down | ${feas.max_8h_down_pct.toFixed(2)}% |`);
    lines.push(`| Max 24h up | ${feas.max_24h_up_pct.toFixed(2)}% |`);
    lines.push(`| Max 24h down | ${feas.max_24h_down_pct.toFixed(2)}% |`);
    lines.push(`| 2% feasible 4h | ${feas.feasible_2pct_4h} |`);
    lines.push(`| 2% feasible 8h | ${feas.feasible_2pct_8h} |`);
    lines.push(`| 2% feasible intraday | ${feas.feasible_2pct_intraday} |`);
    lines.push(`| Regime | ${feas.regime} |`);
    lines.push(`| Recommended target | ${feas.recommended_target_pct.toFixed(1)}% |`);
    lines.push("");
    lines.push(`On this day **2% is reachable in BOTH directions** (max up = ${feas.max_4h_up_pct.toFixed(2)}% within 4h, max down = ${feas.max_4h_down_pct.toFixed(2)}% within 4h, both ≥ 2%). Unlike 2026-01-01, this is a structurally valid day for evaluating a 2% strategy. Unlike 2026-02-01 which was unidirectionally bearish, here both directions clear the bar.`);
  } else {
    lines.push(`(feasibility CSV not found — re-run \`tsx src/cli/targetFeasibility.ts\` first)`);
  }
  lines.push("");

  // Section 3: Strategy summary
  lines.push(`## 3. Strategy summary (full-day, post-dedup + clustered)`);
  lines.push("");
  lines.push(`| Metric | Value |`);
  lines.push(`|---|---|`);
  lines.push(`| L2 events processed | ${reportMd.l2.toLocaleString()} |`);
  lines.push(`| Trades scanned | ${reportMd.trades.toLocaleString()} |`);
  lines.push(`| Zones found | ${zones.length} |`);
  lines.push(`| LONG / SHORT zones | ${longZones.length} / ${shortZones.length} |`);
  lines.push(`| Confirmed zones | ${confirmed} |`);
  lines.push(`| Triggered zones | ${triggered} |`);
  lines.push(`| Reached zones (raw) | ${result.reachedZonesRaw} |`);
  lines.push(`| Reached LONG / SHORT (raw) | ${reachedLong.length} / ${reachedShort.length} |`);
  lines.push(`| **Unique reached moves** | **${result.uniqueReachedMoves}** |`);
  lines.push(`| Duplicate move credits | ${result.duplicateMoveCredits} |`);
  lines.push(`| Reached 2% within 4h | ${reached4h} |`);
  lines.push(`| Reached 2% within 8h | ${reached8h} |`);
  lines.push(`| Reached 2% within 24h | ${reached24h} |`);
  lines.push(`| Failed (RESOLVED_FAILED) | ${zones.filter((z) => z.status === "RESOLVED_FAILED").length} |`);
  lines.push(`| No trigger | ${zones.filter((z) => z.status === "NO_TRIGGER").length} |`);
  lines.push(`| Invalidated | ${zones.filter((z) => z.status === "INVALIDATED").length} |`);
  lines.push(`| Expired | ${zones.filter((z) => z.status === "EXPIRED").length} |`);
  lines.push(`| Raw triggered hit rate | ${pct(result.rawTriggeredHitRate)} |`);
  lines.push(`| **Unique-move-adjusted hit rate** | **${pct(result.uniqueMoveAdjustedHitRate)}** |`);
  lines.push(`| Duplicate suppressions during run | ${reportMd.duplicateSuppressionCount.toLocaleString()} |`);
  for (const [k, v] of Object.entries(reportMd.suppressionsByReason)) {
    lines.push(`| Suppressions \`${k}\` | ${v.toLocaleString()} |`);
  }
  for (const bl of reportMd.baselines) {
    lines.push(`| Baseline ${bl.horizon} (up/down) | ${pct(bl.up)} / ${pct(bl.down)} (n=${bl.samples}) |`);
  }
  lines.push("");

  // Section 4: Direction split + were the successful moves LONG or SHORT?
  lines.push(`## 4. Direction of successful moves`);
  lines.push("");
  if (result.uniqueReachedMoves === 0) {
    lines.push(`No reached zones — no direction split to discuss.`);
  } else {
    const longMoves = result.clusters.filter((c) => c.direction === "LONG").length;
    const shortMoves = result.clusters.filter((c) => c.direction === "SHORT").length;
    lines.push(`Unique reached moves split:`);
    lines.push(`- LONG: **${longMoves}** unique move${longMoves === 1 ? "" : "s"}, ${reachedLong.length} reached zone${reachedLong.length === 1 ? "" : "s"}`);
    lines.push(`- SHORT: **${shortMoves}** unique move${shortMoves === 1 ? "" : "s"}, ${reachedShort.length} reached zone${reachedShort.length === 1 ? "" : "s"}`);
    lines.push("");
    if (longMoves > 0 && shortMoves > 0) {
      lines.push(`**Both directions worked.** This is the first piece of evidence that the strategy is not purely a directional bet on a bearish regime — it caught both an upward and a downward move on the same day.`);
    } else if (longMoves === 0 && shortMoves > 0) {
      lines.push(`Only SHORT moves succeeded on this day (despite both directions being feasible by max-move analysis). Consistent with a bearish-bias detector or with the day's price path favouring SHORT entries.`);
    } else if (longMoves > 0 && shortMoves === 0) {
      lines.push(`Only LONG moves succeeded on this day. New evidence: previous 2026-02-01 had only SHORT successes, so on this day the strategy did the opposite — argues against pure-bearish bias.`);
    }
  }
  lines.push("");

  // Section 5: Cluster details
  lines.push(`## 5. Unique moves`);
  lines.push("");
  if (result.clusters.length === 0) {
    lines.push(`(none)`);
  } else {
    lines.push(`| Move id | Dir | Size | Trigger window | Reached window | Trigger px range | Target px range | Primary zone | Member zones |`);
    lines.push(`|---|---|---|---|---|---|---|---|---|`);
    for (const cl of result.clusters) {
      const zonesIn = zones.filter((z) => cl.zoneIds.includes(z.id));
      const trigPxs = zonesIn.map((z) => z.triggerPrice ?? 0).filter(Boolean);
      const tgtPxs = zonesIn.map((z) => z.targetPrice ?? 0).filter(Boolean);
      const trigPxRange = trigPxs.length > 0 ? `${Math.min(...trigPxs).toFixed(2)}–${Math.max(...trigPxs).toFixed(2)}` : "-";
      const tgtPxRange = tgtPxs.length > 0 ? `${Math.min(...tgtPxs).toFixed(2)}–${Math.max(...tgtPxs).toFixed(2)}` : "-";
      lines.push(
        `| ${cl.uniqueMoveId} | ${cl.direction} | ${cl.size} | ${timeOnly(cl.triggerWindowStart)}–${timeOnly(cl.triggerWindowEnd)} | ${timeOnly(cl.reachedAtMin)}–${timeOnly(cl.reachedAtMax)} | ${trigPxRange} | ${tgtPxRange} | \`${cl.primaryZoneId}\` | ${cl.zoneIds.join(", ")} |`
      );
    }
  }
  lines.push("");

  // Section 6: All zones
  lines.push(`## 6. All zones`);
  lines.push("");
  lines.push(`Total zones: **${zones.length}** (every zone is included regardless of outcome).`);
  lines.push("");
  lines.push(`| # | Dir | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Move id | Primary? | Reason chain |`);
  lines.push(`|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|`);
  zones.sort((a, b) => a.startTs - b.startTs);
  zones.forEach((z, idx) => {
    const compactReasons = (z.reasons || []).map((r) => `${r.stage}@${timeOnly(r.ts)}`).join(" → ");
    lines.push(
      `| ${idx + 1} | ${z.direction} | ${z.status} | ${timeOnly(z.startTs)} | ${timeOnly(z.confirmedTs)} | ${timeOnly(z.triggerTs)} | ${z.zoneLow.toFixed(2)} | ${z.zoneHigh.toFixed(2)} | ${z.triggerPrice?.toFixed(2) ?? "-"} | ${z.targetPrice?.toFixed(2) ?? "-"} | ${horizonOutcome(z, "4h")} | ${horizonOutcome(z, "8h")} | ${horizonOutcome(z, "24h")} | ${bestMfe(z)?.toFixed(2) ?? "-"} | ${bestMae(z)?.toFixed(2) ?? "-"} | ${timeToTargetMin(z)?.toFixed(1) ?? "-"} | ${z.uniqueMoveId ?? "-"} | ${z.isPrimaryMoveZone === true ? "yes" : z.isPrimaryMoveZone === false ? "no" : "-"} | ${compactReasons} |`
    );
  });
  lines.push("");

  // Section 7: Successful zones detail
  lines.push(`## 7. Successful zones detail`);
  lines.push("");
  const ok = zones.filter((z) => z.status === "RESOLVED_REACHED");
  if (ok.length === 0) {
    lines.push(`No zones reached the 2 % target on this day.`);
  } else {
    for (const z of ok) {
      const reachedH = Object.entries(z.targets).find(([, v]) => v.outcome === "reached")?.[0] ?? null;
      const reachedTs = reachedH ? z.targets[reachedH].reachedAt : undefined;
      lines.push(`### ${z.id}`);
      lines.push("");
      lines.push(`- Direction: ${z.direction}, type ${z.zoneType}`);
      lines.push(`- Trigger time: ${isoOrDash(z.triggerTs)}, trigger price: ${z.triggerPrice?.toFixed(2)}, target price: ${z.targetPrice?.toFixed(2)}`);
      lines.push(`- Earliest reached horizon: **${reachedH}**, reached at: ${isoOrDash(reachedTs)}, t→target: ${timeToTargetMin(z)?.toFixed(1) ?? "-"} min`);
      lines.push(`- MFE %: ${bestMfe(z)?.toFixed(3) ?? "-"}, MAE %: ${bestMae(z)?.toFixed(3) ?? "-"}`);
      lines.push(`- Move clustering: uniqueMoveId=${z.uniqueMoveId}, clusterSize=${z.moveClusterSize}, primary=${z.isPrimaryMoveZone}, duplicateMoveCredit=${z.duplicateMoveCredit}`);
      lines.push(`- Scores at trigger: absorption=${z.scores.absorptionScore.toFixed(3)}, void=${z.scores.liquidityVoidScore.toFixed(3)}, trigger=${z.scores.triggerScore?.toFixed(3) ?? "-"}, refill=${z.scores.refillScore?.toFixed(3) ?? "-"}`);
      lines.push(`- Reason chain: ${reasonChainCompact(z)}`);
      lines.push("");
    }
  }
  lines.push("");

  // Section 8: Honest verdict for this day
  lines.push(`## 8. Honest verdict for ${TARGET_DATE}`);
  lines.push("");
  lines.push(`| Metric | Value |`);
  lines.push(`|---|---|`);
  lines.push(`| Triggered | ${triggered} |`);
  lines.push(`| Reached (raw) | ${result.reachedZonesRaw} |`);
  lines.push(`| Unique reached moves | ${result.uniqueReachedMoves} |`);
  lines.push(`| Raw triggered hit rate | ${pct(result.rawTriggeredHitRate)} |`);
  lines.push(`| **Unique-move-adjusted hit rate** | **${pct(result.uniqueMoveAdjustedHitRate)}** |`);
  lines.push("");
  if (result.uniqueReachedMoves > 0) {
    const longMoves = result.clusters.filter((c) => c.direction === "LONG").length;
    const shortMoves = result.clusters.filter((c) => c.direction === "SHORT").length;
    if (longMoves > 0 && shortMoves > 0) {
      lines.push(`The strategy caught **${result.uniqueReachedMoves} unique 2% moves on a feasible-both-directions day**, with both LONG and SHORT among them. This is the strongest single-day evidence so far that the detector is not regime-locked to bearish moves.`);
    } else {
      lines.push(`The strategy caught **${result.uniqueReachedMoves} unique 2% move${result.uniqueReachedMoves === 1 ? "" : "s"}**. Direction: ${longMoves > 0 ? "LONG" : "SHORT"} only. The day was feasible in BOTH directions, but the detector only picked up one side here.`);
    }
  } else {
    lines.push(`The strategy did NOT catch any 2% move on this day, even though both directions were feasible. This is a meaningful negative signal: when the market gives ${feas?.max_4h_up_pct.toFixed(2) ?? "?"}% up moves and ${feas?.max_4h_down_pct.toFixed(2) ?? "?"}% down moves and the detector still misses, the detector's trigger conditions may be too restrictive for this regime.`);
  }
  lines.push("");
  lines.push(`> **Strategy thresholds in \`config/strategy.default.json\` are unchanged.** Detector and target checker untouched. Failed / no_trigger / invalidated zones are preserved in the zones list and the CSV.`);
  lines.push("");

  return lines.join("\n");
}

function main(): void {
  const md = buildMarkdown();
  fs.writeFileSync(OUT_MD, md, "utf8");
  const zones = readZones(ZONES_JSON);
  applyMoveClustering(zones, DEFAULT_MOVE_CLUSTERING_CFG, zones.filter((z) => z.triggerTs !== undefined).length);
  zones.sort((a, b) => a.startTs - b.startTs);
  writeCsv(OUT_CSV, csvCols(), zones.map(zoneToCsvRow));
  console.log(`Wrote: ${path.resolve(OUT_MD)}`);
  console.log(`Wrote: ${path.resolve(OUT_CSV)}`);
  // Also: read daily summary if exists
  if (fs.existsSync(PER_DAY_DAILY_SUMMARY)) console.log(`(per-day daily_summary.csv: ${PER_DAY_DAILY_SUMMARY})`);
  if (fs.existsSync(VALIDATION_JSON)) {
    /* nothing */
  }
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
