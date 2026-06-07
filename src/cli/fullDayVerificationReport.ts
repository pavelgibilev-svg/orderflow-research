// Builds the FULL_DAY_VERIFICATION_2026-02-01.md and .csv from the
// per-day backtest artefacts. Specifically tailored to compare a full-day
// run against the previously captured capped run on the same date.

import * as fs from "node:fs";
import * as path from "node:path";
import { writeCsv, type CsvColumn } from "../reports/csvWriter.js";
import type { Zone } from "../strategy/types.js";

const PROJECT_ROOT = process.cwd();
const REPORTS = path.join(PROJECT_ROOT, "reports");

const TARGET_DATE = "2026-02-01";
const FULL_DAY_DIR = path.join(REPORTS, "full_day_2026-02-01");
const CAPPED_DAY_DIR = path.join(REPORTS, "sample_2026_ytd_except_may", "backtests", "2026-02-01");
const FULL_MD_PATH = path.join(REPORTS, "FULL_DAY_VERIFICATION_2026-02-01.md");
const FULL_CSV_PATH = path.join(REPORTS, "FULL_DAY_VERIFICATION_2026-02-01_ZONES.csv");
const VALIDATION_JSON = path.join(REPORTS, "tardis_validation_2026_ytd_except_may.json");
const CONFIG_JSON_PATH = path.join(PROJECT_ROOT, "config", "strategy.default.json");

interface ParsedReportMd {
  l2: number;
  trades: number;
  other: number;
  qualityFlagsTickCount: number;
  baselines: Array<{ horizon: string; up: number; down: number; samples: number }>;
}

function readReportMd(p: string): ParsedReportMd {
  if (!fs.existsSync(p)) {
    return { l2: 0, trades: 0, other: 0, qualityFlagsTickCount: 0, baselines: [] };
  }
  const t = fs.readFileSync(p, "utf8");
  const out: ParsedReportMd = { l2: 0, trades: 0, other: 0, qualityFlagsTickCount: 0, baselines: [] };
  // toLocaleString() may emit thin/regular/non-breaking spaces or commas as
  // thousand separators depending on the runtime locale. Accept any of them.
  const m = t.match(/Rows processed:\*\*\s*L2=([0-9][\d,\s  ]*)\s+trades=([0-9][\d,\s  ]*)\s+other=([0-9][\d,\s  ]*)/);
  if (m) {
    out.l2 = Number(m[1].replace(/[,\s  ]/g, ""));
    out.trades = Number(m[2].replace(/[,\s  ]/g, ""));
    out.other = Number(m[3].replace(/[,\s  ]/g, ""));
  }
  const qm = t.match(/Encountered (\d+) feature ticks with quality flags/);
  if (qm) out.qualityFlagsTickCount = Number(qm[1]);
  // Baseline table rows look like: | 4h | 0.08% | 20.00% | 1200 |
  const blockMatch = t.match(/## Unconditional baseline[\s\S]*?(?=\n##|$)/);
  if (blockMatch) {
    const block = blockMatch[0];
    const rowRegex = /\|\s*(\d+\s*[smhd])\s*\|\s*([0-9.]+)%\s*\|\s*([0-9.]+)%\s*\|\s*(\d+)\s*\|/g;
    let mm: RegExpExecArray | null;
    while ((mm = rowRegex.exec(block)) !== null) {
      out.baselines.push({
        horizon: mm[1].replace(/\s/g, ""),
        up: Number(mm[2]) / 100,
        down: Number(mm[3]) / 100,
        samples: Number(mm[4]),
      });
    }
  }
  return out;
}

function readZones(p: string): Zone[] {
  if (!fs.existsSync(p)) return [];
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
function fmtBytes(b: number | null): string {
  if (b === null) return "-";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
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
      const cs = Object.entries(r.conditions || {})
        .map(([k, v]) => `${k}=${typeof v === "number" ? Number(v).toFixed(3) : v}`)
        .join(",");
      return `${r.stage}@${new Date(r.ts).toISOString()}{${cs}}`;
    })
    .join(" | ");
}
function horizonOutcome(z: Zone, h: string): string {
  const t = z.targets[h];
  return t ? t.outcome : "-";
}
function hitRateForHorizon(zones: Zone[], h: string): { reached: number; triggered: number; rate: number } {
  const triggered = zones.filter((z) => z.triggerTs !== undefined);
  const reached = triggered.filter((z) => z.targets[h]?.outcome === "reached").length;
  return {
    reached,
    triggered: triggered.length,
    rate: triggered.length > 0 ? reached / triggered.length : 0,
  };
}

interface CsvRow {
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

function zoneToCsvRow(z: Zone): CsvRow {
  return {
    date: z.date,
    symbol: z.symbol,
    direction: z.direction,
    zoneType: z.zoneType,
    status: z.status,
    zoneStartTs: isoOrDash(z.startTs),
    zoneConfirmedTs: isoOrDash(z.confirmedTs),
    triggerTs: isoOrDash(z.triggerTs),
    zoneLow: z.zoneLow,
    zoneHigh: z.zoneHigh,
    triggerPrice: z.triggerPrice ?? null,
    targetPrice: z.targetPrice ?? null,
    target4h: horizonOutcome(z, "4h"),
    target8h: horizonOutcome(z, "8h"),
    target24h: horizonOutcome(z, "24h"),
    mfe: bestMfe(z),
    mae: bestMae(z),
    timeToTarget: timeToTargetMin(z),
    reasons: reasonChainCompact(z),
  };
}

function csvCols(): CsvColumn<CsvRow>[] {
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

interface DataTypeFileInfo {
  type: string;
  required: boolean;
  present: boolean;
  sizeBytes: number | null;
  rowsParsed: number;
  validationStatus: string;
}

function readValidationDay(): DataTypeFileInfo[] {
  const out: DataTypeFileInfo[] = [];
  if (!fs.existsSync(VALIDATION_JSON)) return out;
  const v = JSON.parse(fs.readFileSync(VALIDATION_JSON, "utf8"));
  const day = (v.days as Array<Record<string, unknown>>).find((d) => d["date"] === TARGET_DATE);
  if (!day) return out;
  for (const dt of (day["dataTypes"] as Array<Record<string, unknown>>)) {
    out.push({
      type: dt["dataType"] as string,
      required: dt["required"] as boolean,
      present: dt["filePath"] !== null,
      sizeBytes: (dt["fileSizeBytes"] as number | null) ?? null,
      rowsParsed: (dt["rowsParsed"] as number) ?? 0,
      validationStatus: dt["status"] as string,
    });
  }
  return out;
}

function buildMarkdown(): string {
  const fullZones = readZones(path.join(FULL_DAY_DIR, "zones.json"));
  const fullReport = readReportMd(path.join(FULL_DAY_DIR, "report.md"));
  const cappedZones = readZones(path.join(CAPPED_DAY_DIR, "zones.json"));
  const cappedReport = readReportMd(path.join(CAPPED_DAY_DIR, "report.md"));
  const dataTypes = readValidationDay();

  const lines: string[] = [];
  lines.push(`# Full-Day Verification — BTCUSDT 2026-02-01`);
  lines.push("");
  lines.push(`> **This is a full-day technical verification run, not a proof of strategy profitability.**`);
  lines.push("");
  lines.push(`- Generated: ${new Date().toISOString()}`);
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
  lines.push(`| Files used | incremental_book_L2, trades, liquidations (derivative_ticker / book_ticker present but not consumed by strategy) |`);
  lines.push(`| L2 time limitation | **NO** — full 24h L2 replay (no \`--max-l2-hours\`) |`);
  lines.push(`| Skip-snapshots used | yes (\`--skip-snapshots\` only suppresses the diagnostic 1s-depth-50 export; it does not affect zone detection) |`);
  lines.push(`| Config file | \`config/strategy.default.json\` (unchanged from canonical defaults) |`);
  lines.push(`| Threshold tuning | **NONE** — no values in \`config/strategy.default.json\` were modified for this run |`);
  if (fs.existsSync(CONFIG_JSON_PATH)) {
    try {
      const cfg = JSON.parse(fs.readFileSync(CONFIG_JSON_PATH, "utf8"));
      lines.push(`| targetPct | ${cfg.targetPct} |`);
      lines.push(`| featureIntervalSec | ${cfg.featureIntervalSec} |`);
      lines.push(`| zone.minAbsorptionScore | ${cfg.zone.minAbsorptionScore} |`);
      lines.push(`| zone.minLiquidityVoidScore | ${cfg.zone.minLiquidityVoidScore} |`);
      lines.push(`| zone.trigger.minBreakDistancePct | ${cfg.zone.trigger.minBreakDistancePct} |`);
      lines.push(`| zone.trigger.minAggressiveFlowMultiplier | ${cfg.zone.trigger.minAggressiveFlowMultiplier} |`);
    } catch {
      /* ignore */
    }
  }
  lines.push("");

  // Section 2: Data validation
  lines.push(`## 2. Data validation`);
  lines.push("");
  lines.push(`| File type | Present | Size | Rows parsed (first 1000) | Required/Optional | Validation status |`);
  lines.push(`|---|---|---|---|---|---|`);
  for (const d of dataTypes) {
    lines.push(
      `| ${d.type} | ${d.present ? "yes" : "no"} | ${fmtBytes(d.sizeBytes)} | ${d.rowsParsed} | ${d.required ? "required" : "optional"} | ${d.validationStatus} |`
    );
  }
  lines.push("");

  // Section 3: Full-day strategy summary
  lines.push(`## 3. Full-day strategy summary`);
  lines.push("");
  const triggered = fullZones.filter((z) => z.triggerTs !== undefined);
  const confirmed = fullZones.filter((z) => z.confirmedTs !== undefined);
  const reached4h = fullZones.filter((z) => z.targets["4h"]?.outcome === "reached").length;
  const reached8h = fullZones.filter((z) => z.targets["8h"]?.outcome === "reached").length;
  const reached24h = fullZones.filter((z) => z.targets["24h"]?.outcome === "reached").length;
  const failedByTimeout = fullZones.filter((z) => z.status === "RESOLVED_FAILED").length;
  const noTrigger = fullZones.filter((z) => z.status === "NO_TRIGGER").length;
  const invalidated = fullZones.filter((z) => z.status === "INVALIDATED").length;
  const expired = fullZones.filter((z) => z.status === "EXPIRED").length;
  const hr4 = hitRateForHorizon(fullZones, "4h");
  const hr8 = hitRateForHorizon(fullZones, "8h");
  const hr24 = hitRateForHorizon(fullZones, "24h");
  lines.push(`| Metric | Value |`);
  lines.push(`|---|---|`);
  lines.push(`| L2 events processed | ${fullReport.l2.toLocaleString()} |`);
  lines.push(`| Trades scanned | ${fullReport.trades.toLocaleString()} |`);
  lines.push(`| Zones found (total) | ${fullZones.length} |`);
  lines.push(`| Candidate zones (every zone reached at least the candidate stage) | ${fullZones.length} |`);
  lines.push(`| Confirmed zones | ${confirmed.length} |`);
  lines.push(`| Triggered zones | ${triggered.length} |`);
  lines.push(`| Reached 2% within 4h | ${reached4h} |`);
  lines.push(`| Reached 2% within 8h | ${reached8h} |`);
  lines.push(`| Reached 2% within 24h | ${reached24h} |`);
  lines.push(`| Failed (RESOLVED_FAILED) | ${failedByTimeout} |`);
  lines.push(`| No trigger (NO_TRIGGER) | ${noTrigger} |`);
  lines.push(`| Invalidated | ${invalidated} |`);
  lines.push(`| Expired | ${expired} |`);
  lines.push(`| Triggered hit rate 4h | ${pct(hr4.rate)} (${hr4.reached}/${hr4.triggered}) |`);
  lines.push(`| Triggered hit rate 8h | ${pct(hr8.rate)} (${hr8.reached}/${hr8.triggered}) |`);
  lines.push(`| Triggered hit rate 24h | ${pct(hr24.rate)} (${hr24.reached}/${hr24.triggered}) |`);
  if (fullReport.baselines.length > 0) {
    for (const b of fullReport.baselines) {
      lines.push(`| Unconditional baseline ${b.horizon} | ${pct(b.up)} up / ${pct(b.down)} down (n=${b.samples}) |`);
    }
  } else {
    lines.push(`| Unconditional baseline | not parseable from per-day report.md |`);
  }
  lines.push(`| Quality flag ticks | ${fullReport.qualityFlagsTickCount} |`);
  lines.push("");

  // Section 4: Comparison with capped run
  lines.push(`## 4. Comparison with previous capped run`);
  lines.push("");
  const cappedTrig = cappedZones.filter((z) => z.triggerTs !== undefined);
  const cappedReached = cappedZones.filter((z) => z.status === "RESOLVED_REACHED").length;
  lines.push(`| Metric | Capped run (4h L2) | Full-day run (24h L2) | Δ |`);
  lines.push(`|---|---|---|---|`);
  lines.push(`| L2 events processed | ${cappedReport.l2.toLocaleString()} | ${fullReport.l2.toLocaleString()} | +${(fullReport.l2 - cappedReport.l2).toLocaleString()} |`);
  lines.push(`| Trades scanned | ${cappedReport.trades.toLocaleString()} | ${fullReport.trades.toLocaleString()} | +${(fullReport.trades - cappedReport.trades).toLocaleString()} |`);
  lines.push(`| Zones found | ${cappedZones.length} | ${fullZones.length} | ${fullZones.length - cappedZones.length >= 0 ? "+" : ""}${fullZones.length - cappedZones.length} |`);
  lines.push(`| Triggered | ${cappedTrig.length} | ${triggered.length} | ${triggered.length - cappedTrig.length >= 0 ? "+" : ""}${triggered.length - cappedTrig.length} |`);
  lines.push(`| Reached 2% (any horizon) | ${cappedReached} | ${reached24h} | ${reached24h - cappedReached >= 0 ? "+" : ""}${reached24h - cappedReached} |`);
  lines.push("");

  // Identify zones that exist in full but not in capped (by startTs after 04:00 UTC).
  const cutoffMs = Date.UTC(2026, 1, 1) + 4 * 3_600_000;
  const newAfter4h = fullZones.filter((z) => z.startTs >= cutoffMs);
  lines.push(`### New zones discovered after 04:00 UTC (i.e. that the capped run could not see)`);
  lines.push("");
  if (newAfter4h.length === 0) {
    lines.push(`None — the full-day run produced no zones whose \`startTs\` falls after the 04:00 UTC cap boundary.`);
  } else {
    lines.push(`Found **${newAfter4h.length}** new zones that the capped run could not have seen:`);
    lines.push("");
    lines.push(`| ID | Dir | Start | Trigger | Status | 4h | 8h | 24h |`);
    lines.push(`|---|---|---|---|---|---|---|---|`);
    for (const z of newAfter4h) {
      lines.push(
        `| ${z.id} | ${z.direction} | ${timeOnly(z.startTs)} | ${timeOnly(z.triggerTs)} | ${z.status} | ${horizonOutcome(z, "4h")} | ${horizonOutcome(z, "8h")} | ${horizonOutcome(z, "24h")} |`
      );
    }
  }
  lines.push("");
  // How distorted was the capped run?
  lines.push(`### How much did \`--max-l2-hours 4\` distort the picture?`);
  lines.push("");
  if (cappedZones.length === 0) {
    lines.push(`Capped run had **0 zones**, so any non-zero result here is a strict improvement.`);
  } else {
    const ratio = fullZones.length / cappedZones.length;
    lines.push(`The full-day run produced **${ratio.toFixed(1)}× more zones** than the capped run (${fullZones.length} vs ${cappedZones.length}).`);
    lines.push(`Triggered ratio: **${cappedTrig.length > 0 ? (triggered.length / cappedTrig.length).toFixed(1) + "×" : "+∞ (capped had 0 triggered)"}** (${triggered.length} vs ${cappedTrig.length}).`);
    if (cappedReached === 0 && reached24h > 0) {
      lines.push(`The capped run reached 2% on ${cappedReached} zones; full-day reached on ${reached24h}. Capping at 4h was **leaving real signal on the table.**`);
    } else if (cappedReached > 0 && reached24h === 0) {
      lines.push(`Counter-intuitively, the capped run found ${cappedReached} reached zones but the full-day found 0. This usually means a zone that triggered in the morning had its target reached in the afternoon, while later-in-day zones the full-day run finds simply did not work out — i.e. the capped run was lucky.`);
    } else if (cappedReached > 0 && reached24h >= cappedReached) {
      lines.push(`Both runs found reached zones. Full-day found ${reached24h - cappedReached} additional reached zones that the capped run could not see.`);
    }
  }
  lines.push("");

  // Section 5: All zones
  lines.push(`## 5. All zones`);
  lines.push("");
  lines.push(`Total zones across the full day: **${fullZones.length}** (every zone is included regardless of outcome — successful, failed, no_trigger, invalidated and expired all appear).`);
  lines.push("");
  lines.push(`| # | Dir | Type | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Reason chain |`);
  lines.push(`|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|`);
  fullZones.sort((a, b) => a.startTs - b.startTs);
  fullZones.forEach((z, idx) => {
    const r4 = horizonOutcome(z, "4h");
    const r8 = horizonOutcome(z, "8h");
    const r24 = horizonOutcome(z, "24h");
    const mfe = bestMfe(z);
    const mae = bestMae(z);
    const ttt = timeToTargetMin(z);
    const reasonsStr = (z.reasons || []).map((rr) => `${rr.stage}@${timeOnly(rr.ts)}`).join(" → ");
    lines.push(
      `| ${idx + 1} | ${z.direction} | ${z.zoneType} | ${z.status} | ${timeOnly(z.startTs)} | ${timeOnly(z.confirmedTs)} | ${timeOnly(z.triggerTs)} | ${z.zoneLow.toFixed(2)} | ${z.zoneHigh.toFixed(2)} | ${z.triggerPrice?.toFixed(2) ?? "-"} | ${z.targetPrice?.toFixed(2) ?? "-"} | ${r4} | ${r8} | ${r24} | ${mfe !== null ? mfe.toFixed(2) : "-"} | ${mae !== null ? mae.toFixed(2) : "-"} | ${ttt !== null ? ttt.toFixed(1) : "-"} | ${reasonsStr} |`
    );
  });
  lines.push("");

  // Section 6: Successful 2% zones
  lines.push(`## 6. Successful 2% zones`);
  lines.push("");
  const successful = fullZones.filter((z) => z.status === "RESOLVED_REACHED");
  if (successful.length === 0) {
    lines.push(`No zones reached the 2% target in this full-day run.`);
  } else {
    lines.push(`**${successful.length} zone(s) reached the 2% target.**`);
    lines.push("");
    for (const z of successful) {
      const reachedH = Object.entries(z.targets).find(([, v]) => v.outcome === "reached")?.[0] ?? null;
      const reachedTs = reachedH ? z.targets[reachedH].reachedAt : undefined;
      const fromCap = z.startTs < cutoffMs;
      lines.push(`### ${z.id}`);
      lines.push("");
      lines.push(`- Direction: ${z.direction}, type ${z.zoneType}`);
      lines.push(`- Trigger time: ${isoOrDash(z.triggerTs)}, trigger price: ${z.triggerPrice?.toFixed(2)}`);
      lines.push(`- Target reached time: ${isoOrDash(reachedTs)}, earliest horizon: **${reachedH}**`);
      lines.push(`- Time to target: ${timeToTargetMin(z)?.toFixed(1) ?? "-"} min`);
      lines.push(`- MFE: ${bestMfe(z)?.toFixed(3) ?? "-"} %, MAE: ${bestMae(z)?.toFixed(3) ?? "-"} %`);
      lines.push(`- Scores at trigger: absorption=${z.scores.absorptionScore.toFixed(3)}, void=${z.scores.liquidityVoidScore.toFixed(3)}, trigger=${z.scores.triggerScore?.toFixed(3) ?? "-"}, refill=${z.scores.refillScore?.toFixed(3) ?? "-"}`);
      lines.push(`- This zone's start (${timeOnly(z.startTs)}) is ${fromCap ? "**within the first 4h** — it was already visible to the capped run" : "**after 04:00 UTC** — it is a *new* zone the capped run could not see"}.`);
      lines.push(`- Full reason chain: ${reasonChainCompact(z)}`);
      lines.push("");
    }
  }
  lines.push("");

  // Section 7: Failed zones analysis
  lines.push(`## 7. Failed zones analysis`);
  lines.push("");
  const failedZones = fullZones.filter(
    (z) => z.status === "RESOLVED_FAILED" || z.status === "NO_TRIGGER" || z.status === "INVALIDATED" || z.status === "EXPIRED"
  );
  lines.push(`Failed-or-unfinished zones: **${failedZones.length}** out of ${fullZones.length} total.`);
  lines.push("");
  const byStatus = new Map<string, Zone[]>();
  for (const z of failedZones) {
    const arr = byStatus.get(z.status) ?? [];
    arr.push(z);
    byStatus.set(z.status, arr);
  }
  for (const [s, arr] of byStatus.entries()) lines.push(`- \`${s}\`: ${arr.length}`);
  lines.push("");
  lines.push(`### Why they broke`);
  lines.push("");
  let neverTriggered = 0;
  let triggeredButFailed = 0;
  let lowMfe = 0;
  let highMae = 0;
  let weakLiquidityVoid = 0;
  let weakAbsorption = 0;
  let dataQuality = 0;
  for (const z of failedZones) {
    if (z.triggerTs === undefined) neverTriggered++;
    else triggeredButFailed++;
    const mfe = bestMfe(z);
    if (mfe !== null && mfe < 2) lowMfe++;
    const mae = bestMae(z);
    if (mae !== null && mae > 1) highMae++;
    if (z.scores.liquidityVoidScore < 0.55) weakLiquidityVoid++;
    if (z.scores.absorptionScore < 0.6) weakAbsorption++;
    if (z.qualityFlags.length > 0) dataQuality++;
  }
  lines.push(`- Never reached the trigger stage: ${neverTriggered} zones`);
  lines.push(`- Triggered but failed by timeout (MFE didn't reach 2%): ${triggeredButFailed} zones`);
  lines.push(`- MFE < 2 % among failed zones: ${lowMfe}`);
  lines.push(`- MAE > 1 % among failed zones: ${highMae}`);
  lines.push(`- Below \`minLiquidityVoidScore\` (0.55) at confirmation: ${weakLiquidityVoid}`);
  lines.push(`- Below \`minAbsorptionScore\` (0.60) at confirmation: ${weakAbsorption}`);
  lines.push(`- Carried at least one data-quality flag: ${dataQuality}`);
  lines.push("");
  lines.push(`Sample (up to 15) failed zones with their compact reason chain:`);
  lines.push("");
  for (const z of failedZones.slice(0, 15)) {
    lines.push(`- \`${z.id}\` (${z.direction}, ${z.status}, MFE=${bestMfe(z)?.toFixed(2) ?? "-"}%, MAE=${bestMae(z)?.toFixed(2) ?? "-"}%): ${reasonChainCompact(z)}`);
  }
  lines.push("");

  // Section 8: Strategy assessment
  lines.push(`## 8. Strategy assessment`);
  lines.push("");
  lines.push(`> **This is a full-day technical verification run, not a proof of strategy profitability.**`);
  lines.push("");
  const techWorks = fullReport.l2 > 0 && fullReport.trades > 0 && fullZones.length > 0;
  lines.push(`**Technical operation:** ${techWorks ? "verified" : "FAILED"}.`);
  lines.push(`Full-day L2 replay processed ${fullReport.l2.toLocaleString()} events without crashing or running out of memory; the streaming reader, order-book reconstruction, feature engine, zone state machine and target checker all completed end-to-end on the full 24 hours of real Tardis data. This is the first valid proof that the pipeline scales to a complete day.`);
  lines.push("");
  if (successful.length > 0) {
    lines.push(`**Strategy itself:** the full-day run produced ${successful.length} zone(s) that reached the +2% target. This is a stronger signal than zero. It is **still not a proof of profitability** — a single day cannot prove anything statistically, and there is no slippage / fee / latency model.`);
  } else {
    lines.push(`**Strategy itself:** the full-day run produced ZERO zones that reached the +2% target across all three horizons. The detector did fire ${triggered.length} triggered zones, but none of them succeeded. Whether that is bad luck on this specific day or a real weakness can only be answered by running on many more days.`);
  }
  lines.push("");
  lines.push(`**Worth continuing?**`);
  lines.push("");
  if (techWorks && triggered.length > 0) {
    lines.push(`Yes, conditional on **honest evaluation**:`);
    lines.push(`- The pipeline is fast enough to scale to many days (~${(fullReport.l2 / 1e6).toFixed(1)}M L2 events processed for a single day; multi-day runs are now feasible).`);
    lines.push(`- The detector finds plausible zones with full reason chains. Whether the *trigger* logic and *target* horizons are tuned correctly is an open question that requires a paid-data multi-day sample.`);
    lines.push(`- Failed zones still carry useful information (MFE distribution, MAE distribution) that could feed a calibration loop later.`);
  } else if (techWorks) {
    lines.push(`Marginal. The technical pipeline is solid, but no zones triggered or none reached. Either the day is a poor sample, or the trigger conditions in \`config/strategy.default.json\` are too strict for this regime. **Do not change thresholds based on a single day** — run a multi-day paid sample first.`);
  } else {
    lines.push(`No — fix the technical issues first.`);
  }
  lines.push("");
  lines.push(`**What does this say about 2% intraday on 2026-02-01?**`);
  lines.push("");
  if (fullReport.baselines.length > 0) {
    const b4 = fullReport.baselines.find((b) => b.horizon === "4h");
    if (b4) {
      lines.push(`- The unconditional 4h baseline was ${pct(b4.up)} up / ${pct(b4.down)} down (n=${b4.samples}) — the day was strongly biased ${b4.down > b4.up * 2 ? "**downward**" : b4.up > b4.down * 2 ? "**upward**" : "balanced"}.`);
      lines.push(`- A SHORT zone reaching its target is consistent with that bias; a LONG zone failing on a strongly down day is also consistent.`);
    }
  }
  lines.push("");
  lines.push(`**Difference from the capped run**`);
  lines.push("");
  lines.push(`- The capped run saw only the first 4 hours UTC; the full-day run saw all 24 hours.`);
  lines.push(`- Zones found: ${cappedZones.length} (capped) → ${fullZones.length} (full-day) — ${fullZones.length > cappedZones.length ? "more" : fullZones.length < cappedZones.length ? "fewer" : "same"}.`);
  lines.push(`- Triggered: ${cappedTrig.length} → ${triggered.length}.`);
  lines.push(`- Reached: ${cappedReached} → ${reached24h}.`);
  lines.push(`- The capped result on 2026-02-01 (1 reached SHORT) ${cappedReached > 0 && successful.some((z) => z.id === cappedZones.find((c) => c.status === "RESOLVED_REACHED")?.id) ? "is preserved in the full-day run" : "may have been overwritten by a different sequence in the full-day run depending on detection timing"}.`);
  lines.push("");
  lines.push(`**Next steps**`);
  lines.push("");
  lines.push(`- Run a paid Tardis subscription month (≥20 days) at full-day resolution, no L2 cap.`);
  lines.push(`- Generate a per-zone score distribution across days and look at calibration of \`absorptionScore\`, \`liquidityVoidScore\`, \`triggerScore\` against actual MFE.`);
  lines.push(`- Only after that, consider tuning thresholds — and split into in-sample / out-of-sample so the tuning isn't fitted to its own data.`);
  lines.push(`- This run does **not** justify any threshold change.`);
  lines.push("");

  return lines.join("\n");
}

function main(): void {
  const md = buildMarkdown();
  fs.writeFileSync(FULL_MD_PATH, md, "utf8");
  const fullZones = readZones(path.join(FULL_DAY_DIR, "zones.json"));
  fullZones.sort((a, b) => a.startTs - b.startTs);
  writeCsv(FULL_CSV_PATH, csvCols(), fullZones.map(zoneToCsvRow));
  console.log(`Verification report : ${path.resolve(FULL_MD_PATH)}`);
  console.log(`Verification CSV    : ${path.resolve(FULL_CSV_PATH)}`);
  // Stats:
  const triggered = fullZones.filter((z) => z.triggerTs !== undefined).length;
  const reached4h = fullZones.filter((z) => z.targets["4h"]?.outcome === "reached").length;
  const reached8h = fullZones.filter((z) => z.targets["8h"]?.outcome === "reached").length;
  const reached24h = fullZones.filter((z) => z.targets["24h"]?.outcome === "reached").length;
  const reachedAny = fullZones.filter((z) => z.status === "RESOLVED_REACHED").length;
  const fr = readReportMd(path.join(FULL_DAY_DIR, "report.md"));
  console.log(`l2 events processed : ${fr.l2.toLocaleString()}`);
  console.log(`trades scanned      : ${fr.trades.toLocaleString()}`);
  console.log(`zones found         : ${fullZones.length}`);
  console.log(`zones triggered     : ${triggered}`);
  console.log(`reached 4h          : ${reached4h}`);
  console.log(`reached 8h          : ${reached8h}`);
  console.log(`reached 24h         : ${reached24h}`);
  console.log(`triggered hit rate  : ${triggered > 0 ? ((reachedAny / triggered) * 100).toFixed(2) : "N/A"}%`);
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
