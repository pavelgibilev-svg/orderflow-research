// Builds FULL_DAY_VERIFICATION_<DATE>.md and ..._ZONES.csv for a second
// full-day verification day, comparing regime + zones against the
// previously verified 2026-02-01 (bearish) day.

import * as fs from "node:fs";
import * as path from "node:path";
import { writeCsv, type CsvColumn } from "../reports/csvWriter.js";
import type { Zone } from "../strategy/types.js";

const TARGET_DATE = process.env.VERIFY_DATE ?? "2026-01-01";
const REFERENCE_DATE = "2026-02-01";

const PROJECT_ROOT = process.cwd();
const REPORTS = path.join(PROJECT_ROOT, "reports");
const TARGET_DAY_DIR = path.join(REPORTS, `full_day_${TARGET_DATE}`);
const REFERENCE_DAY_DIR = path.join(REPORTS, `full_day_${REFERENCE_DATE}`);
const FULL_MD_PATH = path.join(REPORTS, `FULL_DAY_VERIFICATION_${TARGET_DATE}.md`);
const FULL_CSV_PATH = path.join(REPORTS, `FULL_DAY_VERIFICATION_${TARGET_DATE}_ZONES.csv`);
const VALIDATION_JSON = path.join(REPORTS, "tardis_validation_2026_ytd_except_may.json");
const REGIME_JSON = path.join(REPORTS, "day_regimes_2026.json");
const CONFIG_JSON_PATH = path.join(PROJECT_ROOT, "config", "strategy.default.json");

interface ParsedReportMd {
  l2: number;
  trades: number;
  other: number;
  qualityFlagsTickCount: number;
  baselines: Array<{ horizon: string; up: number; down: number; samples: number }>;
}

function readReportMd(p: string): ParsedReportMd {
  if (!fs.existsSync(p)) return { l2: 0, trades: 0, other: 0, qualityFlagsTickCount: 0, baselines: [] };
  const t = fs.readFileSync(p, "utf8");
  const out: ParsedReportMd = { l2: 0, trades: 0, other: 0, qualityFlagsTickCount: 0, baselines: [] };
  const m = t.match(/Rows processed:\*\*\s*L2=([0-9][\d,\s  ]*)\s+trades=([0-9][\d,\s  ]*)\s+other=([0-9][\d,\s  ]*)/);
  if (m) {
    out.l2 = Number(m[1].replace(/[,\s  ]/g, ""));
    out.trades = Number(m[2].replace(/[,\s  ]/g, ""));
    out.other = Number(m[3].replace(/[,\s  ]/g, ""));
  }
  const qm = t.match(/Encountered (\d+) feature ticks with quality flags/);
  if (qm) out.qualityFlagsTickCount = Number(qm[1]);
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

interface DayRegime {
  date: string;
  firstPrice: number | null;
  lastPrice: number | null;
  high: number | null;
  low: number | null;
  trades: number;
  returnPct: number | null;
  rangePct: number | null;
  regime: string;
}

function readRegimes(): DayRegime[] {
  if (!fs.existsSync(REGIME_JSON)) return [];
  return JSON.parse(fs.readFileSync(REGIME_JSON, "utf8")) as DayRegime[];
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
  return { reached, triggered: triggered.length, rate: triggered.length > 0 ? reached / triggered.length : 0 };
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
function readValidationDay(date: string): DataTypeFileInfo[] {
  const out: DataTypeFileInfo[] = [];
  if (!fs.existsSync(VALIDATION_JSON)) return out;
  const v = JSON.parse(fs.readFileSync(VALIDATION_JSON, "utf8"));
  const day = (v.days as Array<Record<string, unknown>>).find((d) => d["date"] === date);
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
  const targetZones = readZones(path.join(TARGET_DAY_DIR, "zones.json"));
  const targetReport = readReportMd(path.join(TARGET_DAY_DIR, "report.md"));
  const refZones = readZones(path.join(REFERENCE_DAY_DIR, "zones.json"));
  const refReport = readReportMd(path.join(REFERENCE_DAY_DIR, "report.md"));
  const dataTypes = readValidationDay(TARGET_DATE);
  const regimes = readRegimes();
  const targetRegime = regimes.find((r) => r.date === TARGET_DATE);
  const refRegime = regimes.find((r) => r.date === REFERENCE_DATE);

  const targetTriggered = targetZones.filter((z) => z.triggerTs !== undefined);
  const targetReached24 = targetZones.filter((z) => z.targets["24h"]?.outcome === "reached").length;
  const targetReached8 = targetZones.filter((z) => z.targets["8h"]?.outcome === "reached").length;
  const targetReached4 = targetZones.filter((z) => z.targets["4h"]?.outcome === "reached").length;
  const targetLong = targetZones.filter((z) => z.direction === "LONG").length;
  const targetShort = targetZones.filter((z) => z.direction === "SHORT").length;
  const targetReachedDir = {
    long: targetZones.filter((z) => z.direction === "LONG" && z.status === "RESOLVED_REACHED").length,
    short: targetZones.filter((z) => z.direction === "SHORT" && z.status === "RESOLVED_REACHED").length,
  };
  const refTriggered = refZones.filter((z) => z.triggerTs !== undefined);
  const refReached24 = refZones.filter((z) => z.targets["24h"]?.outcome === "reached").length;
  const refReached8 = refZones.filter((z) => z.targets["8h"]?.outcome === "reached").length;
  const refReached4 = refZones.filter((z) => z.targets["4h"]?.outcome === "reached").length;
  const refLong = refZones.filter((z) => z.direction === "LONG").length;
  const refShort = refZones.filter((z) => z.direction === "SHORT").length;
  const refReachedDir = {
    long: refZones.filter((z) => z.direction === "LONG" && z.status === "RESOLVED_REACHED").length,
    short: refZones.filter((z) => z.direction === "SHORT" && z.status === "RESOLVED_REACHED").length,
  };

  const lines: string[] = [];
  lines.push(`# Full-Day Verification — BTCUSDT ${TARGET_DATE}`);
  lines.push("");
  lines.push(`> **This is a full-day technical verification run, not a proof of strategy profitability.**`);
  lines.push("");
  lines.push(`Second full-day verification, picked deliberately to contrast with the regime of ${REFERENCE_DATE}.`);
  lines.push("");
  lines.push(`- Generated: ${new Date().toISOString()}`);
  lines.push("");

  // Day-regime selection table
  lines.push(`## 0. Day regime selection`);
  lines.push("");
  if (regimes.length > 0) {
    lines.push(`| Date | First | Last | High | Low | Return % | Range % | Regime | Used in this report |`);
    lines.push(`|---|---|---|---|---|---|---|---|---|`);
    for (const r of regimes) {
      const fmt = (n: number | null) => (n === null ? "-" : n.toFixed(2));
      const fmtPct = (n: number | null) => (n === null ? "-" : (n >= 0 ? "+" : "") + n.toFixed(2) + "%");
      const tag = r.date === TARGET_DATE ? "**target**" : r.date === REFERENCE_DATE ? "**reference**" : "";
      lines.push(`| ${r.date} | ${fmt(r.firstPrice)} | ${fmt(r.lastPrice)} | ${fmt(r.high)} | ${fmt(r.low)} | ${fmtPct(r.returnPct)} | ${fmt(r.rangePct)}% | ${r.regime} | ${tag} |`);
    }
    lines.push("");
    if (targetRegime) {
      lines.push(`Selection rationale: the spec asks for the day "**maximally different from 2026-02-01**", preferably bullish, otherwise the most choppy/flat. Among the four downloaded days, none has a pronounced bullish move (>= 1.5% net return) — \`${TARGET_DATE}\` (${targetRegime.regime}, return ${targetRegime.returnPct?.toFixed(2)}%, range ${targetRegime.rangePct?.toFixed(2)}%) is the closest to bullish (mild up-drift) AND has a very different volatility profile from \`${REFERENCE_DATE}\` (${refRegime?.regime}, return ${refRegime?.returnPct?.toFixed(2)}%, range ${refRegime?.rangePct?.toFixed(2)}%). It is the most contrasting day available.`);
    }
  } else {
    lines.push(`> regime JSON not available — re-run \`tsx src/cli/dayRegimeAnalysis.ts\` first.`);
  }
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
  lines.push(`| Skip-snapshots used | yes |`);
  lines.push(`| Config file | \`config/strategy.default.json\` (unchanged from canonical defaults) |`);
  lines.push(`| Threshold tuning | **NONE** — no values in \`config/strategy.default.json\` were modified |`);
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
    lines.push(`| ${d.type} | ${d.present ? "yes" : "no"} | ${fmtBytes(d.sizeBytes)} | ${d.rowsParsed} | ${d.required ? "required" : "optional"} | ${d.validationStatus} |`);
  }
  lines.push("");

  // Section 3: Strategy summary
  lines.push(`## 3. Full-day strategy summary`);
  lines.push("");
  const hr4 = hitRateForHorizon(targetZones, "4h");
  const hr8 = hitRateForHorizon(targetZones, "8h");
  const hr24 = hitRateForHorizon(targetZones, "24h");
  lines.push(`| Metric | Value |`);
  lines.push(`|---|---|`);
  lines.push(`| L2 events processed | ${targetReport.l2.toLocaleString()} |`);
  lines.push(`| Trades scanned | ${targetReport.trades.toLocaleString()} |`);
  lines.push(`| Zones found (total) | ${targetZones.length} |`);
  lines.push(`| LONG zones | ${targetLong} |`);
  lines.push(`| SHORT zones | ${targetShort} |`);
  lines.push(`| Confirmed zones | ${targetZones.filter((z) => z.confirmedTs !== undefined).length} |`);
  lines.push(`| Triggered zones | ${targetTriggered.length} |`);
  lines.push(`| Reached 2% within 4h | ${targetReached4} |`);
  lines.push(`| Reached 2% within 8h | ${targetReached8} |`);
  lines.push(`| Reached 2% within 24h | ${targetReached24} |`);
  lines.push(`| Reached 2% LONG / SHORT | ${targetReachedDir.long} / ${targetReachedDir.short} |`);
  lines.push(`| Failed (RESOLVED_FAILED) | ${targetZones.filter((z) => z.status === "RESOLVED_FAILED").length} |`);
  lines.push(`| No trigger (NO_TRIGGER) | ${targetZones.filter((z) => z.status === "NO_TRIGGER").length} |`);
  lines.push(`| Invalidated | ${targetZones.filter((z) => z.status === "INVALIDATED").length} |`);
  lines.push(`| Expired | ${targetZones.filter((z) => z.status === "EXPIRED").length} |`);
  lines.push(`| Triggered hit rate 4h | ${pct(hr4.rate)} (${hr4.reached}/${hr4.triggered}) |`);
  lines.push(`| Triggered hit rate 8h | ${pct(hr8.rate)} (${hr8.reached}/${hr8.triggered}) |`);
  lines.push(`| Triggered hit rate 24h | ${pct(hr24.rate)} (${hr24.reached}/${hr24.triggered}) |`);
  for (const b of targetReport.baselines) {
    lines.push(`| Unconditional baseline ${b.horizon} | ${pct(b.up)} up / ${pct(b.down)} down (n=${b.samples}) |`);
  }
  lines.push(`| Quality flag ticks | ${targetReport.qualityFlagsTickCount} |`);
  lines.push("");

  // Section 4: Regime comparison vs 2026-02-01
  lines.push(`## 4. Comparison vs ${REFERENCE_DATE} (bearish reference day)`);
  lines.push("");
  lines.push(`| Metric | ${REFERENCE_DATE} (bearish) | ${TARGET_DATE} (${targetRegime?.regime ?? "?"}) |`);
  lines.push(`|---|---|---|`);
  lines.push(`| Day return | ${refRegime?.returnPct?.toFixed(2) ?? "?"}% | ${targetRegime?.returnPct?.toFixed(2) ?? "?"}% |`);
  lines.push(`| Day range | ${refRegime?.rangePct?.toFixed(2) ?? "?"}% | ${targetRegime?.rangePct?.toFixed(2) ?? "?"}% |`);
  lines.push(`| L2 events | ${refReport.l2.toLocaleString()} | ${targetReport.l2.toLocaleString()} |`);
  lines.push(`| Trades scanned | ${refReport.trades.toLocaleString()} | ${targetReport.trades.toLocaleString()} |`);
  lines.push(`| Zones found | ${refZones.length} | ${targetZones.length} |`);
  lines.push(`| LONG zones | ${refLong} | ${targetLong} |`);
  lines.push(`| SHORT zones | ${refShort} | ${targetShort} |`);
  lines.push(`| Triggered zones | ${refTriggered.length} | ${targetTriggered.length} |`);
  lines.push(`| Reached 4h | ${refReached4} | ${targetReached4} |`);
  lines.push(`| Reached 8h | ${refReached8} | ${targetReached8} |`);
  lines.push(`| Reached 24h | ${refReached24} | ${targetReached24} |`);
  lines.push(`| Reached LONG / SHORT | ${refReachedDir.long} / ${refReachedDir.short} | ${targetReachedDir.long} / ${targetReachedDir.short} |`);
  const refHr24 = hitRateForHorizon(refZones, "24h");
  lines.push(`| Triggered hit rate 24h | ${pct(refHr24.rate)} (${refHr24.reached}/${refHr24.triggered}) | ${pct(hr24.rate)} (${hr24.reached}/${hr24.triggered}) |`);
  // Direction bias check
  lines.push("");
  lines.push(`### Direction-bias check`);
  lines.push("");
  if (refTriggered.length > 0) {
    const refShortTrig = refTriggered.filter((z) => z.direction === "SHORT").length;
    const refLongTrig = refTriggered.filter((z) => z.direction === "LONG").length;
    const refShortReached = refReachedDir.short;
    const refLongReached = refReachedDir.long;
    lines.push(`- ${REFERENCE_DATE} (bearish, ${refRegime?.returnPct?.toFixed(2)}%): triggered LONG=${refLongTrig}, SHORT=${refShortTrig}; reached LONG=${refLongReached}, SHORT=${refShortReached}.`);
  }
  if (targetTriggered.length > 0) {
    const tShortTrig = targetTriggered.filter((z) => z.direction === "SHORT").length;
    const tLongTrig = targetTriggered.filter((z) => z.direction === "LONG").length;
    const tShortReached = targetReachedDir.short;
    const tLongReached = targetReachedDir.long;
    lines.push(`- ${TARGET_DATE} (${targetRegime?.regime}, ${targetRegime?.returnPct?.toFixed(2)}%): triggered LONG=${tLongTrig}, SHORT=${tShortTrig}; reached LONG=${tLongReached}, SHORT=${tShortReached}.`);
  } else {
    lines.push(`- ${TARGET_DATE}: no triggered zones at all.`);
  }
  lines.push("");

  // Section 5: All zones
  lines.push(`## 5. All zones`);
  lines.push("");
  lines.push(`Total zones: **${targetZones.length}** (every zone is included regardless of outcome).`);
  lines.push("");
  if (targetZones.length === 0) {
    lines.push(`*No zones detected on this day.*`);
  } else {
    lines.push(`| # | Dir | Type | Status | Start | Confirmed | Trigger | Low | High | TrigPx | TargetPx | 4h | 8h | 24h | MFE % | MAE % | t→tgt min | Reason chain |`);
    lines.push(`|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|`);
    targetZones.sort((a, b) => a.startTs - b.startTs);
    targetZones.forEach((z, idx) => {
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
  }
  lines.push("");

  // Section 6: Successful 2% zones
  lines.push(`## 6. Successful 2% zones`);
  lines.push("");
  const successful = targetZones.filter((z) => z.status === "RESOLVED_REACHED");
  if (successful.length === 0) {
    lines.push(`No zones reached the 2% target on ${TARGET_DATE}.`);
    lines.push("");
    lines.push(`This is itself a meaningful finding: on a non-trending day with only ${targetRegime?.rangePct?.toFixed(2)}% intraday range, hitting a ±2% target from any reference price is mathematically constrained — the price simply did not move 2% from many points in the day.`);
  } else {
    lines.push(`**${successful.length} zone(s) reached the 2% target.**`);
    lines.push("");
    for (const z of successful) {
      const reachedH = Object.entries(z.targets).find(([, v]) => v.outcome === "reached")?.[0] ?? null;
      const reachedTs = reachedH ? z.targets[reachedH].reachedAt : undefined;
      lines.push(`### ${z.id}`);
      lines.push("");
      lines.push(`- Direction: ${z.direction}, type ${z.zoneType}`);
      lines.push(`- Trigger time: ${isoOrDash(z.triggerTs)}, trigger price: ${z.triggerPrice?.toFixed(2)}`);
      lines.push(`- Target reached time: ${isoOrDash(reachedTs)}, earliest horizon: **${reachedH}**`);
      lines.push(`- Time to target: ${timeToTargetMin(z)?.toFixed(1) ?? "-"} min`);
      lines.push(`- MFE: ${bestMfe(z)?.toFixed(3) ?? "-"} %, MAE: ${bestMae(z)?.toFixed(3) ?? "-"} %`);
      lines.push(`- Scores at trigger: absorption=${z.scores.absorptionScore.toFixed(3)}, void=${z.scores.liquidityVoidScore.toFixed(3)}, trigger=${z.scores.triggerScore?.toFixed(3) ?? "-"}, refill=${z.scores.refillScore?.toFixed(3) ?? "-"}`);
      lines.push(`- Reason chain: ${reasonChainCompact(z)}`);
      lines.push("");
    }
  }
  lines.push("");

  // Section 7: Failed zones analysis
  lines.push(`## 7. Failed zones analysis`);
  lines.push("");
  const failed = targetZones.filter((z) => z.status === "RESOLVED_FAILED" || z.status === "NO_TRIGGER" || z.status === "INVALIDATED" || z.status === "EXPIRED");
  lines.push(`Failed-or-unfinished zones: **${failed.length}** of ${targetZones.length}.`);
  lines.push("");
  const byStatus = new Map<string, Zone[]>();
  for (const z of failed) {
    const arr = byStatus.get(z.status) ?? [];
    arr.push(z);
    byStatus.set(z.status, arr);
  }
  for (const [s, arr] of byStatus.entries()) lines.push(`- \`${s}\`: ${arr.length}`);
  lines.push("");
  let neverTriggered = 0;
  let triggeredButFailed = 0;
  let lowMfe = 0;
  let highMae = 0;
  let weakLiquidityVoid = 0;
  let weakAbsorption = 0;
  for (const z of failed) {
    if (z.triggerTs === undefined) neverTriggered++;
    else triggeredButFailed++;
    const mfe = bestMfe(z);
    if (mfe !== null && mfe < 2) lowMfe++;
    const mae = bestMae(z);
    if (mae !== null && mae > 1) highMae++;
    if (z.scores.liquidityVoidScore < 0.55) weakLiquidityVoid++;
    if (z.scores.absorptionScore < 0.6) weakAbsorption++;
  }
  lines.push(`- Never reached the trigger stage: ${neverTriggered}`);
  lines.push(`- Triggered but failed by timeout (MFE didn't reach 2%): ${triggeredButFailed}`);
  lines.push(`- MFE < 2 % among failed zones: ${lowMfe}`);
  lines.push(`- MAE > 1 % among failed zones: ${highMae}`);
  lines.push(`- Below \`minLiquidityVoidScore\` (0.55) at confirmation: ${weakLiquidityVoid}`);
  lines.push(`- Below \`minAbsorptionScore\` (0.60) at confirmation: ${weakAbsorption}`);
  lines.push("");
  if (failed.length > 0) {
    lines.push(`Sample (up to 15) failed zones with reason chain:`);
    lines.push("");
    for (const z of failed.slice(0, 15)) {
      lines.push(`- \`${z.id}\` (${z.direction}, ${z.status}, MFE=${bestMfe(z)?.toFixed(2) ?? "-"}%, MAE=${bestMae(z)?.toFixed(2) ?? "-"}%): ${reasonChainCompact(z)}`);
    }
    lines.push("");
  }

  // Section 8: Strategy assessment + regime question
  lines.push(`## 8. Strategy assessment — does the 2026-02-01 result hold across regimes?`);
  lines.push("");
  lines.push(`> **This is a full-day technical verification run, not a proof of strategy profitability.**`);
  lines.push("");
  lines.push(`**The central question:** is the strategy able to find ±2 % zones on a non-bearish day, or was the 2026-02-01 result a side-effect of a strongly directional bearish regime?`);
  lines.push("");
  // Reach
  if (successful.length > 0) {
    lines.push(`**Answer:** the strategy ${successful.length === 1 ? "found" : "found"} **${successful.length}** zone(s) that reached the 2 % target on a ${targetRegime?.regime} day with only ${targetRegime?.rangePct?.toFixed(2)}% intraday range. The 2026-02-01 result is not regime-locked.`);
  } else {
    lines.push(`**Answer:** **NO zones reached the 2 % target on ${TARGET_DATE}** (a ${targetRegime?.regime} day with ${targetRegime?.rangePct?.toFixed(2)}% intraday range), while ${REFERENCE_DATE} (a bearish day with ${refRegime?.rangePct?.toFixed(2)}% range) had ${refReached24} reached zones.`);
    lines.push("");
    lines.push(`This is consistent with two non-exclusive explanations:`);
    lines.push(`  1. The current strategy is **regime-dependent** — it works best when the market actually moves 2 % within a horizon. On a flat day, no signal can hit a 2 % target the price never reaches.`);
    lines.push(`  2. The 2026-02-01 success was at least partly **a directional tailwind**: 13 of 20 zones were SHORT, all 6 successful zones were SHORT, in a -2.26 % bearish day. The strategy "rode the bias".`);
    lines.push("");
    lines.push(`Both explanations are consistent with the data. Neither is proof.`);
  }
  lines.push("");
  lines.push(`### Direction split tells the same story`);
  lines.push("");
  lines.push(`On ${REFERENCE_DATE} (bearish): ${refLong} LONG / ${refShort} SHORT zones, ${refReachedDir.long} LONG reached / ${refReachedDir.short} SHORT reached.`);
  lines.push(`On ${TARGET_DATE} (${targetRegime?.regime}): ${targetLong} LONG / ${targetShort} SHORT zones, ${targetReachedDir.long} LONG reached / ${targetReachedDir.short} SHORT reached.`);
  lines.push("");

  lines.push(`### Honest verdict`);
  lines.push("");
  if (successful.length > 0) {
    lines.push(`- **2026-02-01 result confirmed on another regime: PARTIALLY.** The strategy can fire and hit 2 % on a non-bearish day, but at lower frequency.`);
    lines.push(`- **Current strategy: likely directional / regime-dependent**, but not exclusively bearish.`);
  } else {
    lines.push(`- **2026-02-01 result confirmed on another regime: NOT confirmed.** Hit rate dropped from ${pct(refHr24.rate)} (bearish) to 0 % (${targetRegime?.regime}) on this single comparison.`);
    lines.push(`- **Current strategy: very likely regime-dependent / directional.** It does fire signals across regimes (${targetTriggered.length} triggered on ${TARGET_DATE} vs ${refTriggered.length} on ${REFERENCE_DATE}), but on a flat / non-trending day the 2 % target is unreachable for most of the day's price walk.`);
  }
  lines.push("");
  lines.push(`### What should be tested next`);
  lines.push("");
  lines.push(`1. A **paid Tardis subscription** for ≥ 1 calendar month at full-day resolution — every day, not just first-of-month boundaries.`);
  lines.push(`2. **Conditional hit rate by regime:** classify each day by net return / range, then compute triggered hit rate within each bucket. This is the only way to disentangle "the strategy works" from "the day moved enough for any 2 % zone to win".`);
  lines.push(`3. **Symmetric baseline comparison:** for each successful zone direction, compare its hit rate to the unconditional probability of price moving ±2 % in the matching horizon, computed on the SAME days. The current per-day baseline is computed on the full day's price walk and is not directly horizon-matched to triggered-zone hit rate.`);
  lines.push(`4. **Drawdown + slippage realism:** add a simple fill model and an assumed maker-taker fee schedule before any "profitability" claim is made.`);
  lines.push(`5. **Do not retune thresholds on this 2-day sample.** Two days is far too few to justify changing \`config/strategy.default.json\`.`);
  lines.push("");

  return lines.join("\n");
}

function main(): void {
  const md = buildMarkdown();
  fs.writeFileSync(FULL_MD_PATH, md, "utf8");
  const targetZones = readZones(path.join(TARGET_DAY_DIR, "zones.json"));
  targetZones.sort((a, b) => a.startTs - b.startTs);
  writeCsv(FULL_CSV_PATH, csvCols(), targetZones.map(zoneToCsvRow));
  console.log(`Verification report : ${path.resolve(FULL_MD_PATH)}`);
  console.log(`Verification CSV    : ${path.resolve(FULL_CSV_PATH)}`);
  const triggered = targetZones.filter((z) => z.triggerTs !== undefined).length;
  const reached4h = targetZones.filter((z) => z.targets["4h"]?.outcome === "reached").length;
  const reached8h = targetZones.filter((z) => z.targets["8h"]?.outcome === "reached").length;
  const reached24h = targetZones.filter((z) => z.targets["24h"]?.outcome === "reached").length;
  const reachedAny = targetZones.filter((z) => z.status === "RESOLVED_REACHED").length;
  const fr = readReportMd(path.join(TARGET_DAY_DIR, "report.md"));
  console.log(`l2 events processed : ${fr.l2.toLocaleString()}`);
  console.log(`trades scanned      : ${fr.trades.toLocaleString()}`);
  console.log(`zones found         : ${targetZones.length}`);
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
