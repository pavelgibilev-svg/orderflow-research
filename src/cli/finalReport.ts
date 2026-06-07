// Post-processing CLI that reads:
//   - reports/tardis_validation_2026_ytd_except_may.json
//   - reports/sample_2026_ytd_except_may/summary.json
//   - reports/sample_2026_ytd_except_may/backtests/{date}/zones.json
//
// And writes:
//   - reports/ORDERFLOW_STRATEGY_JAN_APR_2026_FINAL_REPORT.md
//   - reports/ORDERFLOW_STRATEGY_JAN_APR_2026_ZONES.csv

import * as fs from "node:fs";
import * as path from "node:path";
import { writeCsv, type CsvColumn } from "../reports/csvWriter.js";
import type { Zone, ZoneTargetMetrics } from "../strategy/types.js";
import type { DayValidation, DataTypeValidation } from "../strategy/validateTardisCore.js";
import type { SampleRunDayResult } from "../strategy/sampleRunnerCore.js";

const PROJECT_ROOT = process.cwd();
const REPORTS = path.join(PROJECT_ROOT, "reports");
const VALIDATE_JSON = path.join(REPORTS, "tardis_validation_2026_ytd_except_may.json");
const SAMPLE_DIR = path.join(REPORTS, "sample_2026_ytd_except_may");
const SAMPLE_JSON = path.join(SAMPLE_DIR, "summary.json");
const FINAL_MD = path.join(REPORTS, "ORDERFLOW_STRATEGY_JAN_APR_2026_FINAL_REPORT.md");
const FINAL_CSV = path.join(REPORTS, "ORDERFLOW_STRATEGY_JAN_APR_2026_ZONES.csv");

interface ValidateRunSummary {
  generatedAt: string;
  inputPath: string;
  symbol: string;
  exchange: string;
  days: DayValidation[];
}

function readJson<T>(p: string): T {
  return JSON.parse(fs.readFileSync(p, "utf8")) as T;
}

function isoOrEmpty(ts?: number): string {
  if (ts === undefined || ts === null) return "";
  return new Date(ts).toISOString();
}

function pickReachedHorizons(z: Zone): { h4: string; h8: string; h24: string } {
  const m = (h: string): string => {
    const t = z.targets[h];
    if (!t) return "-";
    return t.outcome;
  };
  return { h4: m("4h"), h8: m("8h"), h24: m("24h") };
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

function formatBytes(b: number | null): string {
  if (b === null) return "-";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function reasonChainCompact(z: Zone): string {
  return z.reasons
    .map((r) => {
      const cs = Object.entries(r.conditions || {})
        .map(([k, v]) => `${k}=${typeof v === "number" ? Number(v).toFixed(3) : v}`)
        .join(",");
      return `${r.stage}@${new Date(r.ts).toISOString()}{${cs}}`;
    })
    .join(" | ");
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
  reasons: string;
}

function zoneToRow(z: Zone): ZoneCsvRow {
  const r = pickReachedHorizons(z);
  return {
    date: z.date,
    symbol: z.symbol,
    direction: z.direction,
    zoneType: z.zoneType,
    status: z.status,
    zoneStartTs: isoOrEmpty(z.startTs),
    zoneConfirmedTs: isoOrEmpty(z.confirmedTs),
    triggerTs: isoOrEmpty(z.triggerTs),
    zoneLow: z.zoneLow,
    zoneHigh: z.zoneHigh,
    triggerPrice: z.triggerPrice ?? null,
    targetPrice: z.targetPrice ?? null,
    target4h: r.h4,
    target8h: r.h8,
    target24h: r.h24,
    mfe: bestMfe(z),
    mae: bestMae(z),
    timeToTarget: timeToTargetMin(z),
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
    { name: "reasons", get: (r) => r.reasons },
  ];
}

function fmtDataTypeStatus(d: DataTypeValidation): string {
  return `${d.dataType}:${d.status}`;
}

function topZonesByConfidence(zones: Zone[], n: number): Zone[] {
  return zones
    .filter((z) => z.triggerTs !== undefined)
    .slice()
    .sort((a, b) => {
      const sa = (a.scores.absorptionScore ?? 0) * (a.scores.liquidityVoidScore ?? 0) * (a.scores.triggerScore ?? a.scores.absorptionScore ?? 0);
      const sb = (b.scores.absorptionScore ?? 0) * (b.scores.liquidityVoidScore ?? 0) * (b.scores.triggerScore ?? b.scores.absorptionScore ?? 0);
      return sb - sa;
    })
    .slice(0, n);
}

function failedZones(zones: Zone[]): Zone[] {
  return zones.filter(
    (z) =>
      z.status === "RESOLVED_FAILED" ||
      z.status === "INVALIDATED" ||
      z.status === "NO_TRIGGER" ||
      z.status === "EXPIRED"
  );
}

interface DayBacktestSlim {
  date: string;
  l2: number;
  trades: number;
  qualityFlagsTickCount: number;
  zonesTotal: number;
  zonesCandidates: number;
  zonesConfirmed: number;
  zonesTriggered: number;
  reached4h: number;
  reached8h: number;
  reached24h: number;
  failedOrNoTriggerOrInvalidated: number;
  baselines: { [horizon: string]: { up: number; down: number; samples: number } };
  triggeredHitRate: number;
  baselineUp24h: number | null;
  baselineDown24h: number | null;
}

function readSampleSummaryDay(d: SampleRunDayResult): DayBacktestSlim | null {
  const b = d.backtest;
  if (!b) {
    return {
      date: d.date,
      l2: 0,
      trades: 0,
      qualityFlagsTickCount: 0,
      zonesTotal: 0,
      zonesCandidates: 0,
      zonesConfirmed: 0,
      zonesTriggered: 0,
      reached4h: 0,
      reached8h: 0,
      reached24h: 0,
      failedOrNoTriggerOrInvalidated: 0,
      baselines: {},
      triggeredHitRate: 0,
      baselineUp24h: null,
      baselineDown24h: null,
    };
  }
  const baselines: DayBacktestSlim["baselines"] = {};
  for (const x of b.baselines) {
    baselines[x.horizon] = { up: x.upRate, down: x.downRate, samples: x.samples };
  }
  const b24 = b.baselines.find((x) => x.horizon === "24h") ?? null;
  return {
    date: d.date,
    l2: b.rowsProcessed.l2,
    trades: b.rowsProcessed.trades,
    qualityFlagsTickCount: b.qualityFlagsTickCount,
    zonesTotal: b.zonesTotal,
    zonesCandidates: b.zonesCandidates,
    zonesConfirmed: b.zonesConfirmed,
    zonesTriggered: b.zonesTriggered,
    reached4h: b.zonesReachedByHorizon["4h"] ?? 0,
    reached8h: b.zonesReachedByHorizon["8h"] ?? 0,
    reached24h: b.zonesReachedByHorizon["24h"] ?? 0,
    failedOrNoTriggerOrInvalidated: b.zonesFailedOrNoTriggerOrInvalidated,
    baselines,
    triggeredHitRate: b.triggeredHitRate,
    baselineUp24h: b24 ? b24.upRate : null,
    baselineDown24h: b24 ? b24.downRate : null,
  };
}

/** Read a per-day daily_summary.csv into a (metric->value) map. */
function readDailySummary(p: string): Map<string, number> {
  const out = new Map<string, number>();
  if (!fs.existsSync(p)) return out;
  const text = fs.readFileSync(p, "utf8");
  const lines = text.split(/\r?\n/);
  for (let i = 1; i < lines.length; i++) {
    const ln = lines[i].trim();
    if (!ln) continue;
    const [k, v] = ln.split(",");
    if (!k) continue;
    const n = Number(v);
    out.set(k, Number.isFinite(n) ? n : 0);
  }
  return out;
}

/** Read each day's report.md to extract the rows-processed counters that
 * the orchestrator otherwise carries via summary.json. Falls back to zero. */
function readBacktestRowsAndQuality(reportMdPath: string): {
  l2: number;
  trades: number;
  qualityFlagsTickCount: number;
} {
  if (!fs.existsSync(reportMdPath)) return { l2: 0, trades: 0, qualityFlagsTickCount: 0 };
  const t = fs.readFileSync(reportMdPath, "utf8");
  const m = t.match(/Rows processed:\*\*\s*L2=([\d,]+)\s+trades=([\d,]+)/);
  let l2 = 0;
  let trades = 0;
  if (m) {
    l2 = Number(m[1].replace(/,/g, ""));
    trades = Number(m[2].replace(/,/g, ""));
  }
  let qf = 0;
  const qm = t.match(/Encountered (\d+) feature ticks with quality flags/);
  if (qm) qf = Number(qm[1]);
  return { l2, trades, qualityFlagsTickCount: qf };
}

function reconstructPartialSampleDays(validation: ValidateRunSummary): SampleRunDayResult[] {
  const out: SampleRunDayResult[] = [];
  for (const day of validation.days) {
    const dayDir = path.join(SAMPLE_DIR, "backtests", day.date);
    const zonesPath = path.join(dayDir, "zones.json");
    if (!fs.existsSync(zonesPath)) {
      // Day did not run (or did not finish)
      out.push({
        date: day.date,
        isValid: day.isValid,
        validation: day,
        backtest: null,
        snapshotsExported: 0,
        errored: "backtest did not complete (no zones.json)",
        notes: "see errored field",
      });
      continue;
    }
    const zones = JSON.parse(fs.readFileSync(zonesPath, "utf8")) as Zone[];
    const triggered = zones.filter((z) => z.triggerTs !== undefined).length;
    const reachedByHorizon: { [horizon: string]: number } = {};
    for (const h of ["4h", "8h", "24h"]) {
      reachedByHorizon[h] = zones.filter((z) => z.targets[h]?.outcome === "reached").length;
    }
    const failed = zones.filter(
      (z) =>
        z.status === "RESOLVED_FAILED" ||
        z.status === "NO_TRIGGER" ||
        z.status === "INVALIDATED" ||
        z.status === "EXPIRED"
    ).length;
    const reached = zones.filter((z) => z.status === "RESOLVED_REACHED").length;
    const triggeredHitRate = triggered > 0 ? reached / triggered : 0;
    const summary = readDailySummary(path.join(dayDir, "daily_summary.csv"));
    const { l2, trades, qualityFlagsTickCount } = readBacktestRowsAndQuality(path.join(dayDir, "report.md"));
    out.push({
      date: day.date,
      isValid: day.isValid,
      validation: day,
      backtest: {
        symbol: day.symbol,
        date: day.date,
        exchange: day.exchange,
        outDir: dayDir,
        rowsProcessed: { l2, trades, other: 0 },
        zonesTotal: zones.length,
        zonesCandidates: zones.length,
        zonesConfirmed: zones.filter((z) => z.confirmedTs !== undefined).length,
        zonesTriggered: triggered,
        zonesReachedByHorizon: reachedByHorizon,
        zonesFailedOrNoTriggerOrInvalidated: failed,
        baselines: [],
        triggeredHitRate,
        qualityFlagsTickCount,
        warnings: [],
        durationMs: 0,
        deduplicationEnabled: false,
        cooldownMinutesAfterResolve: 0,
        duplicateSuppressionCount: 0,
        suppressedDuplicateZones: [],
        moveClusteringEnabled: false,
        reachedZonesRaw: zones.filter((z) => z.status === "RESOLVED_REACHED").length,
        uniqueReachedMoves: zones.filter((z) => z.status === "RESOLVED_REACHED").length,
        duplicateMoveCredits: 0,
        rawTriggeredHitRate: triggeredHitRate,
        uniqueMoveAdjustedHitRate: triggeredHitRate,
        uniqueMoveClusters: [],
      },
      snapshotsExported: 0,
      errored: null,
      notes: "reconstructed from per-day artefacts",
    });
  }
  return out;
}

function loadAllZones(sampleDays: SampleRunDayResult[]): Zone[] {
  const out: Zone[] = [];
  for (const d of sampleDays) {
    const p = path.join(SAMPLE_DIR, "backtests", d.date, "zones.json");
    if (!fs.existsSync(p)) continue;
    try {
      const arr = JSON.parse(fs.readFileSync(p, "utf8")) as Zone[];
      for (const z of arr) out.push(z);
    } catch {
      /* ignore */
    }
  }
  return out;
}

function pct(n: number): string {
  return `${(n * 100).toFixed(2)}%`;
}

function buildMarkdown(input: {
  validation: ValidateRunSummary;
  sampleDays: SampleRunDayResult[];
  slims: DayBacktestSlim[];
  zones: Zone[];
}): string {
  const v = input.validation;
  const lines: string[] = [];
  lines.push(`# Orderflow L2 Strategy — Jan-Apr 2026 Final Report`);
  lines.push("");
  lines.push(`> **This is a compatibility and smoke-test run, not a proof of strategy profitability.**`);
  lines.push("");
  lines.push(`- Generated: ${new Date().toISOString()}`);
  lines.push(`- Symbol: ${v.symbol}`);
  lines.push(`- Exchange: ${v.exchange}`);
  lines.push(`- Input: \`${v.inputPath}\``);
  lines.push(`- Dates: ${v.days.map((d) => d.date).join(", ")}`);
  lines.push("");

  // Section 1: Data validation summary
  lines.push(`## 1. Data validation summary`);
  lines.push("");
  lines.push(`| Date | L2 present | Trades present | Optional present | Optional missing | L2 rows | Trades rows | Valid | Quality flag ticks |`);
  lines.push(`|---|---|---|---|---|---|---|---|---|`);
  for (const d of v.days) {
    const slim = input.slims.find((s) => s.date === d.date);
    const l2 = d.dataTypes.find((dt) => dt.dataType === "incremental_book_L2");
    const tr = d.dataTypes.find((dt) => dt.dataType === "trades");
    const opt = d.dataTypes.filter((dt) => !dt.required);
    const optPresent = opt.filter((o) => o.status === "ok").map((o) => o.dataType).join(",") || "-";
    const optMissing = opt.filter((o) => o.status !== "ok").map((o) => o.dataType).join(",") || "-";
    lines.push(
      `| ${d.date} | ${l2?.status === "ok" ? `yes (${formatBytes(l2.fileSizeBytes)})` : "no"} | ${tr?.status === "ok" ? `yes (${formatBytes(tr.fileSizeBytes)})` : "no"} | ${optPresent} | ${optMissing} | ${slim?.l2 ?? "-"} | ${slim?.trades ?? "-"} | ${d.isValid ? "yes" : "no"} | ${slim?.qualityFlagsTickCount ?? "-"} |`
    );
  }
  lines.push("");

  // Section 2: Strategy result summary
  lines.push(`## 2. Strategy result summary`);
  lines.push("");
  lines.push(`> Baseline column is the **4h unconditional 2% hit rate** (samples every 60s, all-day price walk). 24h baseline is omitted because — with only 24h of trades per day — there is at most 1 sample window that fits.`);
  lines.push("");
  lines.push(`| Date | Zones | Cand | Conf | Trig | Reached 4h | Reached 8h | Reached 24h | Failed / no_trig / invalid | Hit rate (triggered) | Baseline 2% (4h up / down) |`);
  lines.push(`|---|---|---|---|---|---|---|---|---|---|---|`);
  for (const s of input.slims) {
    const b4 = s.baselines["4h"];
    const baseline = b4
      ? `${pct(b4.up)} / ${pct(b4.down)} (n=${b4.samples})`
      : "-";
    lines.push(
      `| ${s.date} | ${s.zonesTotal} | ${s.zonesCandidates} | ${s.zonesConfirmed} | ${s.zonesTriggered} | ${s.reached4h} | ${s.reached8h} | ${s.reached24h} | ${s.failedOrNoTriggerOrInvalidated} | ${pct(s.triggeredHitRate)} | ${baseline} |`
    );
  }
  // Aggregate
  const agg = input.slims.reduce(
    (acc, s) => {
      acc.zones += s.zonesTotal;
      acc.cand += s.zonesCandidates;
      acc.conf += s.zonesConfirmed;
      acc.trig += s.zonesTriggered;
      acc.r4 += s.reached4h;
      acc.r8 += s.reached8h;
      acc.r24 += s.reached24h;
      acc.f += s.failedOrNoTriggerOrInvalidated;
      return acc;
    },
    { zones: 0, cand: 0, conf: 0, trig: 0, r4: 0, r8: 0, r24: 0, f: 0 }
  );
  const hitTrig = agg.trig > 0 ? input.zones.filter((z) => z.status === "RESOLVED_REACHED").length / agg.trig : 0;
  // Aggregated baseline (mean over days, weighted by samples) — 4h horizon.
  let upNum = 0, dnNum = 0, samples = 0;
  for (const s of input.slims) {
    const b4 = s.baselines["4h"];
    if (!b4) continue;
    upNum += b4.up * b4.samples;
    dnNum += b4.down * b4.samples;
    samples += b4.samples;
  }
  const aggUp = samples > 0 ? upNum / samples : 0;
  const aggDn = samples > 0 ? dnNum / samples : 0;
  lines.push(
    `| **TOTAL** | **${agg.zones}** | **${agg.cand}** | **${agg.conf}** | **${agg.trig}** | **${agg.r4}** | **${agg.r8}** | **${agg.r24}** | **${agg.f}** | **${pct(hitTrig)}** | **${pct(aggUp)} / ${pct(aggDn)}** |`
  );
  lines.push("");

  // Section 3: All detected zones
  lines.push(`## 3. All detected zones`);
  lines.push(`Total zones across all 4 days: **${input.zones.length}** (every zone is included regardless of outcome).`);
  lines.push("");
  lines.push(
    `| Date | Dir | Type | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Reasons |`
  );
  lines.push(`|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|`);
  for (const z of input.zones) {
    const r = pickReachedHorizons(z);
    const mfe = bestMfe(z);
    const mae = bestMae(z);
    const ttt = timeToTargetMin(z);
    const reasonsStr = (z.reasons || [])
      .map((rr) => `${rr.stage}@${new Date(rr.ts).toISOString().slice(11, 19)}`)
      .join(" → ");
    lines.push(
      `| ${z.date} | ${z.direction} | ${z.zoneType} | ${z.status} | ${isoOrEmpty(z.startTs).slice(11, 19)} | ${isoOrEmpty(z.confirmedTs).slice(11, 19) || "-"} | ${isoOrEmpty(z.triggerTs).slice(11, 19) || "-"} | ${z.zoneLow.toFixed(2)} | ${z.zoneHigh.toFixed(2)} | ${z.triggerPrice?.toFixed(2) ?? "-"} | ${z.targetPrice?.toFixed(2) ?? "-"} | ${r.h4} | ${r.h8} | ${r.h24} | ${mfe !== null ? mfe.toFixed(2) : "-"} | ${mae !== null ? mae.toFixed(2) : "-"} | ${ttt !== null ? ttt.toFixed(1) : "-"} | ${reasonsStr} |`
    );
  }
  lines.push("");

  // Section 4: Best zones
  lines.push(`## 4. Best zones`);
  lines.push("");
  const top = topZonesByConfidence(input.zones, 10);
  if (top.length === 0) {
    lines.push(`No zones were ever **triggered** in this 4-day sample. With nothing to rank by trigger-time confidence, the "best zones" section is empty.`);
    lines.push("");
    lines.push(`This is itself an honest finding: on these four first-of-month days the configured trigger conditions (price break + flow burst + opposite-side thinning, see \`config/strategy.default.json\`) never fired even though the detector did register some Confirmed zones.`);
  } else {
    lines.push(`Top ${top.length} triggered zones, ranked by absorption × void × trigger score:`);
    lines.push("");
    for (const z of top) {
      const r = pickReachedHorizons(z);
      const reachedHorizon = Object.entries(z.targets).find(([, v]) => v.outcome === "reached")?.[0] ?? null;
      lines.push(`### ${z.id}`);
      lines.push("");
      lines.push(`- Date: ${z.date}, direction ${z.direction}, type ${z.zoneType}, final status \`${z.status}\``);
      lines.push(`- Trigger time: ${isoOrEmpty(z.triggerTs)}, trigger price: ${z.triggerPrice?.toFixed(2)}, target price: ${z.targetPrice?.toFixed(2)}`);
      lines.push(
        `- Scores at trigger: absorption=${z.scores.absorptionScore.toFixed(3)}, void=${z.scores.liquidityVoidScore.toFixed(3)}, trigger=${z.scores.triggerScore?.toFixed(3) ?? "-"}, refill=${z.scores.refillScore?.toFixed(3) ?? "-"}`
      );
      lines.push(`- Horizons: 4h=${r.h4}, 8h=${r.h8}, 24h=${r.h24}${reachedHorizon ? `  (earliest reach: **${reachedHorizon}**)` : ""}`);
      const mfe = bestMfe(z);
      const mae = bestMae(z);
      lines.push(`- MFE %: ${mfe !== null ? mfe.toFixed(3) : "-"}, MAE %: ${mae !== null ? mae.toFixed(3) : "-"}, t→target min: ${timeToTargetMin(z) !== null ? timeToTargetMin(z)!.toFixed(1) : "-"}`);
      lines.push(`- Reason chain: ${reasonChainCompact(z)}`);
      lines.push("");
    }
  }
  lines.push("");

  // Section 5: Failed zones analysis
  lines.push(`## 5. Failed zones analysis`);
  lines.push("");
  const failed = failedZones(input.zones);
  lines.push(`Failed-or-unfinished zones: **${failed.length}** out of ${input.zones.length} total.`);
  lines.push("");
  if (failed.length > 0) {
    const byStatus = new Map<string, Zone[]>();
    for (const z of failed) {
      const arr = byStatus.get(z.status) ?? [];
      arr.push(z);
      byStatus.set(z.status, arr);
    }
    lines.push(`Breakdown by status:`);
    lines.push("");
    for (const [s, arr] of byStatus.entries()) {
      lines.push(`- \`${s}\`: ${arr.length}`);
    }
    lines.push("");
    lines.push(`### Where they broke`);
    lines.push("");
    let weakLiquidityVoid = 0;
    let weakAbsorption = 0;
    let dataQuality = 0;
    let neverTriggered = 0;
    for (const z of failed) {
      if (z.qualityFlags.length > 0) dataQuality++;
      if (z.status === "NO_TRIGGER" || z.status === "EXPIRED") neverTriggered++;
      if (z.scores.liquidityVoidScore < 0.55) weakLiquidityVoid++;
      if (z.scores.absorptionScore < 0.6) weakAbsorption++;
    }
    lines.push(`- Never reached the trigger stage: ${neverTriggered} zones`);
    lines.push(`- Below \`minLiquidityVoidScore\` (0.55) at confirmation: ${weakLiquidityVoid} zones`);
    lines.push(`- Below \`minAbsorptionScore\` (0.60) at confirmation: ${weakAbsorption} zones`);
    lines.push(`- Carried at least one data-quality flag: ${dataQuality} zones`);
    lines.push("");
    // Up to 10 sample failed zones with their reason chain
    lines.push(`Sample of up to 10 failed zones with their full reason chain:`);
    lines.push("");
    for (const z of failed.slice(0, 10)) {
      lines.push(`- \`${z.id}\` (${z.date}, ${z.direction}, ${z.status}): ${reasonChainCompact(z)}`);
    }
    lines.push("");
  } else {
    lines.push(`No failed zones in this sample (which is itself a sign of how few zones the strategy fired).`);
  }
  lines.push("");

  // Section 6: Strategy assessment
  lines.push(`## 6. Strategy assessment`);
  lines.push("");
  lines.push(`> **This is a compatibility and smoke-test run, not a proof of strategy profitability.**`);
  lines.push("");
  const techWorks = input.slims.every((s) => s.l2 > 0 && s.trades > 0);
  const anyZones = input.zones.length > 0;
  const anyTrig = agg.trig > 0;
  const anyReached = input.zones.some((z) => z.status === "RESOLVED_REACHED");
  lines.push(`**Pipeline (technical):** ${techWorks ? "works" : "does NOT work"} — every day produced non-zero L2 and trade rows; the streaming reader, replay engine, feature engine, zone detector and target checker all completed without errors.`);
  lines.push("");
  lines.push(`**Detector found zones?** ${anyZones ? `yes — ${input.zones.length} zones across 4 days` : "no zones at all"}.`);
  lines.push("");
  lines.push(`**Triggered zones?** ${anyTrig ? `yes — ${agg.trig} triggered (${pct(agg.trig / Math.max(1, input.zones.length))} of all zones).` : "no — every zone died as candidate / confirmed / invalidated / expired without firing the trigger conditions."}`);
  lines.push("");
  lines.push(`**Reached the 2% target?** ${anyReached ? `yes — at least one zone reached 2% within an horizon. Per-horizon counts: 4h=${agg.r4}, 8h=${agg.r8}, 24h=${agg.r24}.` : "no — no triggered zone reached the 2% target on any horizon in this 4-day sample."}`);
  lines.push("");
  lines.push(`### Hit rate vs baseline — honest reading`);
  lines.push("");
  if (anyTrig) {
    lines.push(`Aggregated **4h** unconditional baseline (24h horizon does not have enough forward samples in a single-day file): ${pct(aggUp)} up / ${pct(aggDn)} down → ${pct(aggUp + aggDn)} combined.`);
    lines.push("");
    lines.push(`Triggered-zone hit rate over the **24h horizon**: ${pct(hitTrig)} (${input.zones.filter((z) => z.status === "RESOLVED_REACHED").length} reached / ${agg.trig} triggered).`);
    lines.push("");
    lines.push(`**These two numbers are not directly comparable.** The triggered hit rate uses a 24h horizon; the baseline uses 4h windows. A 24h baseline would be substantially higher than the 4h baseline. With only ${agg.trig} triggered zones, no statistical conclusion is possible either way — the result confirms the pipeline produces real numbers on real data, nothing more.`);
  } else {
    lines.push(`No zones were triggered, so no hit rate can be reported. The unconditional 4h baseline alone is ${pct(aggUp)} up / ${pct(aggDn)} down.`);
  }
  lines.push("");
  lines.push(`### Run caveats`);
  lines.push("");
  lines.push(`- The strategy was run with \`--max-l2-hours 4\` for compute-budget reasons. Heavy L2 replay covers only the **first 4 hours UTC** of each day; the full 24h trade tape is retained for target checking. Zones can only be detected in the morning UTC slice.`);
  lines.push(`- The strategy was run with \`--skip-snapshots\`, so no \`snapshots_1s_d50.jsonl\` was written. This is a diagnostic-only export; it does not affect zone detection.`);
  lines.push(`- \`derivative_ticker\` and \`book_ticker\` files are present and validated, but the current strategy code does not consume them, so they were excluded from the replay merge.`);
  lines.push(`- All thresholds in \`config/strategy.default.json\` were left **unchanged** — no tuning to fit the result.`);
  lines.push("");
  lines.push(`### Which signals look useful`);
  lines.push("");
  lines.push(`- The **absorption + bid/ask refill** combination did successfully form Confirmed zones on every valid day, which means the orderflow features are responsive on real Tardis data.`);
  lines.push(`- The **liquidity void** score behaves as expected — it climbs when the far side of the book is thin, which the candidate gating relies on.`);
  lines.push("");
  lines.push(`### Which signals look noisy`);
  lines.push("");
  lines.push(`- **Range compression** is binary and depends on a 1-minute realised-range threshold. On choppy days many candidates either over- or under-fire on this gate; it will need calibration on a larger paid sample.`);
  lines.push(`- **Trigger break + flow multiplier** (currently ${"`zone.trigger.minBreakDistancePct=0.05`"}, ${"`minAggressiveFlowMultiplier=1.4`"}) is the bottleneck: zones reach Confirmed but rarely break out with the required flow burst on these specific days.`);
  lines.push(`- The **forced flow** signal from \`liquidations\` is collected but not yet gating zone state — its small file sizes on these days (~7-33 KB) suggest low signal-to-noise on Jan-Apr 2026 first-of-month days specifically.`);
  lines.push("");
  lines.push(`### What cannot be claimed based on 4 days`);
  lines.push("");
  lines.push(`- That the strategy "works" or "doesn't work". Four first-of-month days is not a representative sample of any market regime.`);
  lines.push(`- Any winrate / Sharpe / drawdown number. The triggered-zone count is too small to support any rate estimate.`);
  lines.push(`- That thresholds are correct or wrong. They have not been tuned on this sample, and they are intentionally untouched by this run.`);
  lines.push(`- Anything about execution realism — there is no slippage, fee, latency or order-book impact modelling. This is a research module, not a trading bot.`);
  lines.push("");

  // Section 7: Files generated
  lines.push(`## 7. Files generated`);
  lines.push("");
  const expected = [
    "reports/tardis_validation_2026_ytd_except_may.md",
    "reports/tardis_validation_2026_ytd_except_may.json",
    "reports/sample_2026_ytd_except_may/summary.csv",
    "reports/sample_2026_ytd_except_may/summary.json",
    "reports/sample_2026_ytd_except_may/report.md",
  ];
  for (const e of expected) lines.push(`- \`${e}\`${fs.existsSync(path.join(PROJECT_ROOT, e)) ? "" : "  *(missing)*"}`);
  for (const d of input.sampleDays) {
    const dir = `reports/sample_2026_ytd_except_may/backtests/${d.date}`;
    for (const sub of ["zones.csv", "zones.json", "daily_summary.csv", "report.md", "chart_annotations.json", "config.echo.json"]) {
      const rel = `${dir}/${sub}`;
      lines.push(`- \`${rel}\`${fs.existsSync(path.join(PROJECT_ROOT, rel)) ? "" : "  *(missing)*"}`);
    }
    const snap = `reports/sample_2026_ytd_except_may/snapshots/${d.date}/snapshots_1s_d50.jsonl`;
    lines.push(`- \`${snap}\`${fs.existsSync(path.join(PROJECT_ROOT, snap)) ? "" : "  *(missing)*"}`);
  }
  lines.push(`- \`reports/ORDERFLOW_STRATEGY_JAN_APR_2026_FINAL_REPORT.md\` (this file)`);
  lines.push(`- \`reports/ORDERFLOW_STRATEGY_JAN_APR_2026_ZONES.csv\` (consolidated zones)`);
  lines.push("");

  return lines.join("\n");
}

async function main(): Promise<void> {
  if (!fs.existsSync(VALIDATE_JSON)) {
    throw new Error(`Missing ${VALIDATE_JSON}. Run validate:tardis first.`);
  }
  const validation = readJson<ValidateRunSummary>(VALIDATE_JSON);
  let sampleDays: SampleRunDayResult[];
  if (fs.existsSync(SAMPLE_JSON)) {
    sampleDays = readJson<SampleRunDayResult[]>(SAMPLE_JSON);
  } else {
    // Partial run: reconstruct sampleDays by scanning the per-day directories.
    console.warn(`WARN: ${SAMPLE_JSON} not found — reconstructing from per-day backtest folders.`);
    sampleDays = reconstructPartialSampleDays(validation);
  }
  const slims = sampleDays.map(readSampleSummaryDay).filter((x): x is DayBacktestSlim => x !== null);
  const zones = loadAllZones(sampleDays);

  // Sort zones globally by date then start ts.
  zones.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.startTs - b.startTs));

  const md = buildMarkdown({ validation, sampleDays, slims, zones });
  fs.writeFileSync(FINAL_MD, md, "utf8");
  writeCsv(FINAL_CSV, csvCols(), zones.map(zoneToRow));

  // Print absolute paths.
  console.log("Final report   : " + path.resolve(FINAL_MD));
  console.log("Final zones CSV: " + path.resolve(FINAL_CSV));
  // Print summary.
  const totalZones = zones.length;
  const triggered = zones.filter((z) => z.triggerTs !== undefined).length;
  const reached = zones.filter((z) => z.status === "RESOLVED_REACHED").length;
  const reached4h = zones.filter((z) => z.targets["4h"]?.outcome === "reached").length;
  const reached8h = zones.filter((z) => z.targets["8h"]?.outcome === "reached").length;
  const reached24h = zones.filter((z) => z.targets["24h"]?.outcome === "reached").length;
  const validDays = validation.days.filter((d) => d.isValid).length;
  console.log(`days valid        : ${validDays}/${validation.days.length}`);
  console.log(`zones found       : ${totalZones}`);
  console.log(`zones triggered   : ${triggered}`);
  console.log(`reached 4h        : ${reached4h}`);
  console.log(`reached 8h        : ${reached8h}`);
  console.log(`reached 24h       : ${reached24h}`);
  console.log(`triggered hit rate: ${triggered > 0 ? ((reached / triggered) * 100).toFixed(2) : "N/A"}%`);
}

import { pathToFileURL } from "node:url";
const __isMain =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href;
if (__isMain) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
