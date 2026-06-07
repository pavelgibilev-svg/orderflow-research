// Builds reports/VALID_2PCT_DAYS_COMPARISON_JAN_APR_2026.md.
//
// Compares only days where the 2% target was reachable (per the feasibility
// analyser): 2026-02-01, 2026-03-01, 2026-04-01. 2026-01-01 is excluded
// because max-24h move is below 2% on that day, so any hit-rate evaluation
// is mechanically zero — see TARGET_FEASIBILITY_2PCT_JAN_APR_2026.md.
//
// Strategy thresholds, detector logic and target checker are unchanged.

import * as fs from "node:fs";
import * as path from "node:path";
import type { Zone } from "../strategy/types.js";
import { applyMoveClustering, DEFAULT_MOVE_CLUSTERING_CFG } from "../strategy/uniqueMoveClustering.js";

const PROJECT_ROOT = process.cwd();
const REPORTS = path.join(PROJECT_ROOT, "reports");
const OUT_MD = path.join(REPORTS, "VALID_2PCT_DAYS_COMPARISON_JAN_APR_2026.md");

interface DaySource {
  date: string;
  variant: "DEDUP" | "DEDUP_CLUSTERED";
  zonesPath: string;
  reportMdPath: string;
  feasibilityCategory: "fully feasible (both directions)" | "partial feasible (one direction only)" | "not feasible";
}

const DAYS: DaySource[] = [
  // 2026-02-01: bearish full-day with dedup applied (no clustered-named output exists; clustering applied at read time).
  {
    date: "2026-02-01",
    variant: "DEDUP",
    zonesPath: path.join(REPORTS, "full_day_2026-02-01_dedup", "zones.json"),
    reportMdPath: path.join(REPORTS, "full_day_2026-02-01_dedup", "report.md"),
    feasibilityCategory: "fully feasible (both directions)",
  },
  // 2026-03-01: today's run.
  {
    date: "2026-03-01",
    variant: "DEDUP_CLUSTERED",
    zonesPath: path.join(REPORTS, "full_day_2026-03-01_dedup_clustered", "zones.json"),
    reportMdPath: path.join(REPORTS, "full_day_2026-03-01_dedup_clustered", "report.md"),
    feasibilityCategory: "fully feasible (both directions)",
  },
  // 2026-04-01: also today's run; partial feasible (max 4h down = 1.62% < 2%).
  {
    date: "2026-04-01",
    variant: "DEDUP_CLUSTERED",
    zonesPath: path.join(REPORTS, "full_day_2026-04-01_dedup_clustered", "zones.json"),
    reportMdPath: path.join(REPORTS, "full_day_2026-04-01_dedup_clustered", "report.md"),
    feasibilityCategory: "partial feasible (one direction only)",
  },
];

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
}
function loadFeasibility(): Map<string, FeasibilityRow> {
  const out = new Map<string, FeasibilityRow>();
  const p = path.join(REPORTS, "TARGET_FEASIBILITY_2PCT_JAN_APR_2026.csv");
  if (!fs.existsSync(p)) return out;
  const lines = fs.readFileSync(p, "utf8").split(/\r?\n/);
  if (lines.length < 2) return out;
  const headers = lines[0].split(",");
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",");
    if (cols.length < 5) continue;
    const obj: Record<string, string> = {};
    headers.forEach((h, j) => (obj[h] = cols[j] ?? ""));
    const row: FeasibilityRow = {
      date: obj["date"] ?? "",
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
    };
    if (row.date) out.set(row.date, row);
  }
  return out;
}

interface Bucket {
  date: string;
  variant: string;
  feasibilityCategory: string;
  zones: Zone[];
  triggered: number;
  reachedRaw: number;
  uniqueMoves: number;
  duplicateMoveCredits: number;
  rawHitRate: number;
  adjustedHitRate: number;
  longZones: number;
  shortZones: number;
  reachedLong: number;
  reachedShort: number;
  uniqueMovesLong: number;
  uniqueMovesShort: number;
  reached4h: number;
  reached8h: number;
  reached24h: number;
  feas: FeasibilityRow | null;
  rowsProcessedL2: number;
  rowsProcessedTrades: number;
  available: boolean;
}

function readZones(p: string): Zone[] {
  if (!fs.existsSync(p)) return [];
  return JSON.parse(fs.readFileSync(p, "utf8")) as Zone[];
}

function readReportMdRows(p: string): { l2: number; trades: number } {
  if (!fs.existsSync(p)) return { l2: 0, trades: 0 };
  const t = fs.readFileSync(p, "utf8");
  const m = t.match(/Rows processed:\*\*\s*L2=([0-9][\d,\s  ]*)\s+trades=([0-9][\d,\s  ]*)/);
  if (!m) return { l2: 0, trades: 0 };
  return {
    l2: Number(m[1].replace(/[,\s  ]/g, "")),
    trades: Number(m[2].replace(/[,\s  ]/g, "")),
  };
}

function loadBucket(d: DaySource, feasibility: Map<string, FeasibilityRow>): Bucket {
  const zones = readZones(d.zonesPath);
  const reportMd = readReportMdRows(d.reportMdPath);
  const triggered = zones.filter((z) => z.triggerTs !== undefined).length;
  const result = applyMoveClustering(zones, DEFAULT_MOVE_CLUSTERING_CFG, triggered);
  const longMoves = result.clusters.filter((c) => c.direction === "LONG").length;
  const shortMoves = result.clusters.filter((c) => c.direction === "SHORT").length;
  const reachedLong = zones.filter((z) => z.direction === "LONG" && z.status === "RESOLVED_REACHED").length;
  const reachedShort = zones.filter((z) => z.direction === "SHORT" && z.status === "RESOLVED_REACHED").length;
  const reached4h = zones.filter((z) => z.targets["4h"]?.outcome === "reached").length;
  const reached8h = zones.filter((z) => z.targets["8h"]?.outcome === "reached").length;
  const reached24h = zones.filter((z) => z.targets["24h"]?.outcome === "reached").length;
  return {
    date: d.date,
    variant: d.variant,
    feasibilityCategory: d.feasibilityCategory,
    zones,
    triggered,
    reachedRaw: result.reachedZonesRaw,
    uniqueMoves: result.uniqueReachedMoves,
    duplicateMoveCredits: result.duplicateMoveCredits,
    rawHitRate: result.rawTriggeredHitRate,
    adjustedHitRate: result.uniqueMoveAdjustedHitRate,
    longZones: zones.filter((z) => z.direction === "LONG").length,
    shortZones: zones.filter((z) => z.direction === "SHORT").length,
    reachedLong,
    reachedShort,
    uniqueMovesLong: longMoves,
    uniqueMovesShort: shortMoves,
    reached4h,
    reached8h,
    reached24h,
    feas: feasibility.get(d.date) ?? null,
    rowsProcessedL2: reportMd.l2,
    rowsProcessedTrades: reportMd.trades,
    available: zones.length > 0 || fs.existsSync(d.zonesPath),
  };
}

function pct(n: number): string {
  return `${(n * 100).toFixed(2)}%`;
}
function fmt(n: number): string {
  return n.toFixed(2);
}

function buildMarkdown(buckets: Bucket[]): string {
  const lines: string[] = [];
  lines.push(`# Valid 2 % Days Comparison — Jan-Apr 2026`);
  lines.push("");
  lines.push(`> Honest cross-day evaluation of the strategy on **only the days where the 2 % target is structurally reachable** per the target-feasibility analyser. 2026-01-01 is excluded by design because its 24h max move is < 2 % in both directions, so any hit-rate from that day is mechanically zero and not informative about strategy quality. Strategy thresholds are unchanged. Detector and target checker are unchanged.`);
  lines.push("");
  lines.push(`- Generated: ${new Date().toISOString()}`);
  lines.push(`- Days included: ${buckets.map((b) => b.date).join(", ")}`);
  lines.push("");

  // Headline table
  lines.push(`## 1. Headline metrics — only feasible days`);
  lines.push("");
  lines.push(`| Date | Feasibility | Regime | Range | Triggered | Reached raw | **Unique moves** | Adj hit rate | Raw hit rate | LONG / SHORT moves | Days notes |`);
  lines.push(`|---|---|---|---|---|---|---|---|---|---|---|`);
  for (const b of buckets) {
    const r = b.feas?.range_pct ?? null;
    lines.push(
      `| ${b.date} | ${b.feasibilityCategory} | ${b.feas?.regime ?? "?"} | ${r === null ? "-" : fmt(r) + "%"} | ${b.triggered} | ${b.reachedRaw} | **${b.uniqueMoves}** | **${pct(b.adjustedHitRate)}** | ${pct(b.rawHitRate)} | ${b.uniqueMovesLong} / ${b.uniqueMovesShort} | ${b.zones.length === 0 ? "**(no zones available — backtest may not have completed)**" : ""} |`
    );
  }
  // Aggregate
  const agg = aggregate(buckets);
  lines.push(
    `| **TOTAL (feasible days only)** | — | — | — | **${agg.triggered}** | **${agg.reachedRaw}** | **${agg.uniqueMoves}** | **${agg.triggered > 0 ? pct(agg.uniqueMoves / agg.triggered) : "-"}** | ${agg.triggered > 0 ? pct(agg.reachedRaw / agg.triggered) : "-"} | **${agg.uniqueMovesLong} / ${agg.uniqueMovesShort}** | — |`
  );
  lines.push("");

  // Per-day detail
  lines.push(`## 2. Per-day detail`);
  lines.push("");
  for (const b of buckets) {
    lines.push(`### ${b.date} (${b.feasibilityCategory})`);
    lines.push("");
    if (b.zones.length === 0) {
      lines.push(`**Backtest output not found** at \`${path.relative(PROJECT_ROOT, DAYS.find((d) => d.date === b.date)!.zonesPath)}\`. Skipping this day.`);
      lines.push("");
      continue;
    }
    if (b.feas) {
      lines.push(`Day price action:`);
      lines.push(`- Return: ${fmt(b.feas.return_pct)}%, Range: ${fmt(b.feas.range_pct)}%, Regime: ${b.feas.regime}`);
      lines.push(`- Max 4h up/down: ${fmt(b.feas.max_4h_up_pct)}% / ${fmt(b.feas.max_4h_down_pct)}%`);
      lines.push(`- Max 8h up/down: ${fmt(b.feas.max_8h_up_pct)}% / ${fmt(b.feas.max_8h_down_pct)}%`);
      lines.push(`- Max 24h up/down: ${fmt(b.feas.max_24h_up_pct)}% / ${fmt(b.feas.max_24h_down_pct)}%`);
      lines.push(`- 2% feasible: 4h=${b.feas.feasible_2pct_4h}, 8h=${b.feas.feasible_2pct_8h}, 24h=${b.feas.feasible_2pct_intraday}`);
      lines.push("");
    }
    lines.push(`Strategy result:`);
    lines.push(`- L2 events processed: ${b.rowsProcessedL2.toLocaleString()}, trades scanned: ${b.rowsProcessedTrades.toLocaleString()}`);
    lines.push(`- Zones found: ${b.zones.length} (LONG=${b.longZones}, SHORT=${b.shortZones})`);
    lines.push(`- Triggered: ${b.triggered}`);
    lines.push(`- Reached zones (raw): ${b.reachedRaw} (LONG=${b.reachedLong}, SHORT=${b.reachedShort})`);
    lines.push(`- Reached by horizon: 4h=${b.reached4h}, 8h=${b.reached8h}, 24h=${b.reached24h}`);
    lines.push(`- Unique reached moves: **${b.uniqueMoves}** (LONG=${b.uniqueMovesLong}, SHORT=${b.uniqueMovesShort})`);
    lines.push(`- Duplicate move credits collapsed: ${b.duplicateMoveCredits}`);
    lines.push(`- Raw triggered hit rate: ${pct(b.rawHitRate)}`);
    lines.push(`- **Unique-move-adjusted hit rate: ${pct(b.adjustedHitRate)}**`);
    lines.push("");
    if (b.uniqueMoves > 0) {
      if (b.uniqueMovesLong > 0 && b.uniqueMovesShort > 0) {
        lines.push(`**Conclusion:** the strategy caught both LONG and SHORT moves on this day. Best single-day evidence of regime-independence.`);
      } else if (b.uniqueMovesShort > 0) {
        lines.push(`**Conclusion:** SHORT-only success on this day. Consistent with bearish-bias hypothesis but does NOT confirm it (this day's regime is ${b.feas?.regime ?? "?"}, return ${b.feas ? fmt(b.feas.return_pct) + "%" : "?"}).`);
      } else {
        lines.push(`**Conclusion:** LONG-only success on this day.`);
      }
    } else {
      lines.push(`**Conclusion:** no 2% target reached, despite the day being structurally feasible. Negative signal for the strategy on this regime.`);
    }
    lines.push("");
  }

  // Honest verdict
  lines.push(`## 3. Honest verdict across feasible days`);
  lines.push("");
  const completedDays = buckets.filter((b) => b.zones.length > 0);
  lines.push(`Days successfully evaluated: ${completedDays.length} of ${buckets.length}.`);
  lines.push("");
  if (completedDays.length === 0) {
    lines.push(`No data — re-run the backtests first.`);
    return lines.join("\n");
  }

  // Key questions
  const aggMoves = agg.uniqueMoves;
  const longMoves = agg.uniqueMovesLong;
  const shortMoves = agg.uniqueMovesShort;
  const days = completedDays.map((b) => b.date).join(", ");

  lines.push(`### Q1. Is the 2026-02-01 result confirmed on a second feasible day?`);
  lines.push("");
  const day2 = completedDays.find((b) => b.date === "2026-02-01");
  const day3 = completedDays.find((b) => b.date === "2026-03-01");
  if (day2 && day3) {
    if (day3.uniqueMoves > 0) {
      lines.push(
        `**Partially yes.** 2026-03-01 produced ${day3.uniqueMoves} unique reached move${day3.uniqueMoves === 1 ? "" : "s"} (LONG=${day3.uniqueMovesLong}, SHORT=${day3.uniqueMovesShort}). The strategy is not zero on a second feasible day — it ${day3.uniqueMoves >= day2.uniqueMoves ? "matches or exceeds" : "is below"} the 2026-02-01 result of ${day2.uniqueMoves} unique move${day2.uniqueMoves === 1 ? "" : "s"}.`
      );
    } else {
      lines.push(
        `**Not confirmed.** 2026-03-01 is structurally feasible in both directions yet the strategy caught **0** unique 2 % moves. 2026-02-01 had ${day2.uniqueMoves} unique move${day2.uniqueMoves === 1 ? "" : "s"}. On a 2-day comparison this is a clear negative signal that needs more days to interpret.`
      );
    }
  } else {
    lines.push(`(2026-02-01 or 2026-03-01 missing — verdict can't be computed)`);
  }
  lines.push("");

  lines.push(`### Q2. Is success regime-dependent (only bearish days)?`);
  lines.push("");
  const longDays = completedDays.filter((b) => b.uniqueMovesLong > 0).map((b) => b.date);
  const shortDays = completedDays.filter((b) => b.uniqueMovesShort > 0).map((b) => b.date);
  if (longDays.length > 0 && shortDays.length > 0) {
    lines.push(
      `**No clear bearish-only bias.** Across feasible days the strategy produced LONG successes on (${longDays.join(", ") || "none"}) and SHORT successes on (${shortDays.join(", ") || "none"}). The bearish-only hypothesis from 2026-02-01 alone is **not supported** once we look at all feasible days together.`
    );
  } else if (shortDays.length > 0 && longDays.length === 0) {
    lines.push(
      `**Likely yes.** Across all feasible days the strategy ONLY succeeded on the SHORT side (${shortDays.join(", ")}). LONG never reached its 2 % target — even on days where LONG was structurally feasible. This is consistent with regime-dependent / bearish-bias behaviour, though 2-3 days is too few to be conclusive.`
    );
  } else if (longDays.length > 0 && shortDays.length === 0) {
    lines.push(
      `Surprising: across all feasible days the strategy ONLY succeeded on the LONG side (${longDays.join(", ")}). This contradicts the 2026-02-01 SHORT-only finding. Need more days.`
    );
  } else {
    lines.push(`No successful direction on any feasible day in this sample — strategy is currently producing zero verified edge across the included days.`);
  }
  lines.push("");

  lines.push(`### Q3. How many unique 2 % moves were caught in total?`);
  lines.push("");
  lines.push(
    `**${aggMoves}** unique 2 % moves across ${completedDays.length} feasible day${completedDays.length === 1 ? "" : "s"} (${longMoves} LONG + ${shortMoves} SHORT). Aggregate triggered hit rate (raw): ${agg.triggered > 0 ? pct(agg.reachedRaw / agg.triggered) : "n/a"}. Aggregate unique-move-adjusted: ${agg.triggered > 0 ? pct(aggMoves / agg.triggered) : "n/a"}.`
  );
  lines.push("");

  lines.push(`### Q4. Can we already speak about an edge?`);
  lines.push("");
  lines.push(
    `**No.** Even with ${aggMoves} unique moves over ${completedDays.length} feasible day${completedDays.length === 1 ? "" : "s"}, this is far below any sample size that supports a profitability claim:`
  );
  lines.push(`- All ${completedDays.length} days are first-of-month boundaries — atypical liquidity / funding-reset behaviour.`);
  lines.push(`- No out-of-sample split.`);
  lines.push(`- No fees / slippage / latency model.`);
  lines.push(`- The hit rate is not horizon-matched against an unconditional baseline at 24h (the per-day baseline only has enough samples at 4h / 8h).`);
  lines.push(`- 2-3 days does not bound directional bias well — a single regime tilt can swamp the result.`);
  lines.push("");

  lines.push(`### Q5. What to test next?`);
  lines.push("");
  lines.push(`1. **Paid Tardis subscription, ≥ 1 calendar month** at full-day resolution; this is the only way to escape first-of-month sample bias.`);
  lines.push(`2. Per-direction-per-day hit rate against a horizon-matched baseline (P(±2 % within 24h) computed on the same days the detector ran on).`);
  lines.push(`3. A symmetric per-day target ladder (0.5 / 1.0 / 1.5 / 2.0 %) — see TARGET_FEASIBILITY_2PCT_JAN_APR_2026.md. This separates "the strategy works" from "the day moved enough".`);
  lines.push(`4. Once the live recorder has a few weeks of data, replay through \`backtest:db\` and compare with the Tardis-CSV runs to detect any source-specific bias.`);
  lines.push(`5. Do **not** retune \`config/strategy.default.json\` based on this 2-3 day sample.`);
  lines.push("");

  lines.push(`> **This is a feasibility-aware, post-dedup, post-clustering verification.** Strategy thresholds are unchanged. Detector logic is unchanged. Failed / no_trigger / invalidated zones are preserved in every per-day report.`);
  lines.push("");

  return lines.join("\n");
}

interface AggResult {
  triggered: number;
  reachedRaw: number;
  uniqueMoves: number;
  uniqueMovesLong: number;
  uniqueMovesShort: number;
}
function aggregate(buckets: Bucket[]): AggResult {
  let triggered = 0,
    reachedRaw = 0,
    uniqueMoves = 0,
    uniqueMovesLong = 0,
    uniqueMovesShort = 0;
  for (const b of buckets) {
    if (b.zones.length === 0) continue;
    triggered += b.triggered;
    reachedRaw += b.reachedRaw;
    uniqueMoves += b.uniqueMoves;
    uniqueMovesLong += b.uniqueMovesLong;
    uniqueMovesShort += b.uniqueMovesShort;
  }
  return { triggered, reachedRaw, uniqueMoves, uniqueMovesLong, uniqueMovesShort };
}

function main(): void {
  const feasibility = loadFeasibility();
  const buckets = DAYS.map((d) => loadBucket(d, feasibility));
  const md = buildMarkdown(buckets);
  fs.writeFileSync(OUT_MD, md, "utf8");
  console.log(`Wrote: ${path.resolve(OUT_MD)}`);
  for (const b of buckets) {
    console.log(
      `  ${b.date}: zones=${b.zones.length} triggered=${b.triggered} reachedRaw=${b.reachedRaw} uniqueMoves=${b.uniqueMoves} (L=${b.uniqueMovesLong} S=${b.uniqueMovesShort}) adj=${(b.adjustedHitRate * 100).toFixed(2)}%`
    );
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
