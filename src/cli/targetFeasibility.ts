// Target-feasibility / regime diagnostic.
//
// For each day we stream trades.csv.gz, downsample to 1-minute close prices,
// and compute the maximum upward and downward price move within any 4h / 8h /
// 24h rolling window (in % of the window's starting price). The 2% target is
// "feasible on horizon X" if max_up_X% >= 2 OR max_down_X% >= 2 — i.e. there
// exists at least one starting point in the day from which the price moved
// 2% within X hours.
//
// Outputs:
//   reports/TARGET_FEASIBILITY_2PCT_JAN_APR_2026.md
//   reports/TARGET_FEASIBILITY_2PCT_JAN_APR_2026.csv
//
// Pure analysis — strategy thresholds, detector and target checker are NOT
// touched. This is a sanity check on whether 2% is the right target for
// these days at all.

import * as fs from "node:fs";
import * as path from "node:path";
import { writeCsv, type CsvColumn } from "../reports/csvWriter.js";
import { streamTardisFile } from "../data/tardisCsvLoader.js";
import type { TradeEvent } from "../data/schema.js";
import { dayBoundsUtc } from "../data/time.js";

const PROJECT_ROOT = process.cwd();
const REPORTS = path.join(PROJECT_ROOT, "reports");
const DATA_ROOT = path.join(PROJECT_ROOT, "data", "tardis", "binance-futures", "BTCUSDT");
const DATES = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"];

const OUT_MD = path.join(REPORTS, "TARGET_FEASIBILITY_2PCT_JAN_APR_2026.md");
const OUT_CSV = path.join(REPORTS, "TARGET_FEASIBILITY_2PCT_JAN_APR_2026.csv");

const TARGET_PCT = 2.0;
const MINUTES_PER_DAY = 1440;

interface DayFeasibility {
  date: string;
  trades: number;
  firstPrice: number | null;
  lastPrice: number | null;
  high: number | null;
  low: number | null;
  returnPct: number | null;
  rangePct: number | null;
  // Max moves over rolling windows, expressed as % of window start price.
  max4hUpPct: number;
  max4hDownPct: number;
  max8hUpPct: number;
  max8hDownPct: number;
  max24hUpPct: number;
  max24hDownPct: number;
  // 2% feasibility flags (≥ 2% reachable from at least one starting minute).
  feasible4h: boolean;
  feasible8h: boolean;
  feasibleIntraday: boolean;
  regime: "bullish" | "bearish" | "choppy" | "flat" | "unknown";
  recommendedTargetPct: number;
}

/** Bucket trades into 1-minute closing prices for the day [dayStart, dayStart+24h). */
async function buildMinuteBars(date: string): Promise<{ bars: Array<number | null>; firstPrice: number | null; lastPrice: number | null; high: number | null; low: number | null; trades: number }> {
  const file = path.join(DATA_ROOT, date, "trades.csv.gz");
  if (!fs.existsSync(file)) {
    return { bars: [], firstPrice: null, lastPrice: null, high: null, low: null, trades: 0 };
  }
  const { startMs } = dayBoundsUtc(date);
  const bars: Array<number | null> = new Array(MINUTES_PER_DAY).fill(null);
  let firstPx: number | null = null;
  let lastPx: number | null = null;
  let hi = -Infinity;
  let lo = +Infinity;
  let n = 0;
  for await (const ev of streamTardisFile(file, { dataType: "trades" })) {
    const t = ev as TradeEvent;
    n++;
    if (firstPx === null) firstPx = t.price;
    lastPx = t.price;
    if (t.price > hi) hi = t.price;
    if (t.price < lo) lo = t.price;
    const minuteIdx = Math.floor((t.ts - startMs) / 60_000);
    if (minuteIdx >= 0 && minuteIdx < MINUTES_PER_DAY) {
      bars[minuteIdx] = t.price; // overwrite — last trade in the minute is the close
    }
  }
  // Forward-fill empty minutes with the last seen price so windowed scans don't
  // skip gaps. The first bars before the first trade stay null.
  let lastSeen: number | null = null;
  for (let i = 0; i < bars.length; i++) {
    if (bars[i] !== null) lastSeen = bars[i];
    else if (lastSeen !== null) bars[i] = lastSeen;
  }
  return {
    bars,
    firstPrice: firstPx,
    lastPrice: lastPx,
    high: Number.isFinite(hi) ? hi : null,
    low: Number.isFinite(lo) ? lo : null,
    trades: n,
  };
}

/** Max upward / downward price move within any rolling N-minute window. */
function maxMovesInWindow(bars: Array<number | null>, windowMinutes: number): { maxUpPct: number; maxDownPct: number } {
  const n = bars.length;
  let maxUp = 0;
  let maxDown = 0;
  // Sliding-window max and min via deques (monotonic).
  const maxDq: number[] = []; // indices, values bars[idx] strictly decreasing
  const minDq: number[] = []; // indices, values bars[idx] strictly increasing
  for (let i = 0; i < n; i++) {
    const v = bars[i];
    if (v === null) continue;
    // Insert i into both deques.
    while (maxDq.length > 0 && (bars[maxDq[maxDq.length - 1]] ?? -Infinity) <= v) maxDq.pop();
    maxDq.push(i);
    while (minDq.length > 0 && (bars[minDq[minDq.length - 1]] ?? +Infinity) >= v) minDq.pop();
    minDq.push(i);
    // Drop elements that fall out of [i - windowMinutes + 1 .. i] (we want forward window from i; we'll re-do below).
  }
  // Simpler approach: for each starting point i, scan window [i, i+windowMinutes].
  // 1440×min(240,480,1440) = at most 1440×1440 = 2.07M comparisons per window — cheap.
  for (let i = 0; i < n; i++) {
    const start = bars[i];
    if (start === null || start <= 0) continue;
    let localMax = start;
    let localMin = start;
    const end = Math.min(n, i + windowMinutes);
    for (let j = i; j < end; j++) {
      const v = bars[j];
      if (v === null) continue;
      if (v > localMax) localMax = v;
      if (v < localMin) localMin = v;
    }
    const upPct = ((localMax - start) / start) * 100;
    const downPct = ((start - localMin) / start) * 100;
    if (upPct > maxUp) maxUp = upPct;
    if (downPct > maxDown) maxDown = downPct;
  }
  return { maxUpPct: maxUp, maxDownPct: maxDown };
}

function classifyRegime(returnPct: number, rangePct: number): "bullish" | "bearish" | "choppy" | "flat" | "unknown" {
  if (rangePct < 1) return "flat";
  if (returnPct >= 1.5) return "bullish";
  if (returnPct <= -1.5) return "bearish";
  if (rangePct < 2) return "choppy";
  return "choppy";
}

function recommendTarget(rangePct: number, max4hUp: number, max4hDown: number, max8hUp: number, max8hDown: number): number {
  const max4h = Math.max(max4hUp, max4hDown);
  const max8h = Math.max(max8hUp, max8hDown);
  // Pick the largest standard target ≤ 0.6 * range (so 2x the average half-range
  // gives reasonable hit-rate variance) AND ≤ max 8h move (the strategy's
  // longest "active" horizon for a single setup).
  const cap = Math.min(rangePct * 0.6, max8h);
  const ladder = [2.0, 1.5, 1.0, 0.5];
  for (const t of ladder) if (t <= cap) return t;
  return 0.5;
}

async function analyseDay(date: string): Promise<DayFeasibility> {
  process.stdout.write(`Scanning ${date}... `);
  const t0 = Date.now();
  const built = await buildMinuteBars(date);
  if (built.trades === 0) {
    return {
      date,
      trades: 0,
      firstPrice: null,
      lastPrice: null,
      high: null,
      low: null,
      returnPct: null,
      rangePct: null,
      max4hUpPct: 0,
      max4hDownPct: 0,
      max8hUpPct: 0,
      max8hDownPct: 0,
      max24hUpPct: 0,
      max24hDownPct: 0,
      feasible4h: false,
      feasible8h: false,
      feasibleIntraday: false,
      regime: "unknown",
      recommendedTargetPct: 0.5,
    };
  }
  const { firstPrice, lastPrice, high, low, trades, bars } = built;
  const returnPct = firstPrice !== null && lastPrice !== null && firstPrice > 0 ? ((lastPrice - firstPrice) / firstPrice) * 100 : null;
  const rangePct = high !== null && low !== null && low > 0 ? ((high - low) / low) * 100 : null;
  const m4 = maxMovesInWindow(bars, 240);
  const m8 = maxMovesInWindow(bars, 480);
  const m24 = maxMovesInWindow(bars, MINUTES_PER_DAY);
  const feasible4h = m4.maxUpPct >= TARGET_PCT || m4.maxDownPct >= TARGET_PCT;
  const feasible8h = m8.maxUpPct >= TARGET_PCT || m8.maxDownPct >= TARGET_PCT;
  const feasibleIntraday = m24.maxUpPct >= TARGET_PCT || m24.maxDownPct >= TARGET_PCT;
  const regime = classifyRegime(returnPct ?? 0, rangePct ?? 0);
  const rec = recommendTarget(rangePct ?? 0, m4.maxUpPct, m4.maxDownPct, m8.maxUpPct, m8.maxDownPct);
  process.stdout.write(`done in ${((Date.now() - t0) / 1000).toFixed(1)}s\n`);
  return {
    date,
    trades,
    firstPrice,
    lastPrice,
    high,
    low,
    returnPct,
    rangePct,
    max4hUpPct: m4.maxUpPct,
    max4hDownPct: m4.maxDownPct,
    max8hUpPct: m8.maxUpPct,
    max8hDownPct: m8.maxDownPct,
    max24hUpPct: m24.maxUpPct,
    max24hDownPct: m24.maxDownPct,
    feasible4h,
    feasible8h,
    feasibleIntraday,
    regime,
    recommendedTargetPct: rec,
  };
}

function pct(n: number | null, digits = 2): string {
  if (n === null) return "-";
  return (n >= 0 ? "+" : "") + n.toFixed(digits) + "%";
}
function fmt(n: number | null, digits = 2): string {
  if (n === null) return "-";
  return n.toFixed(digits);
}
function yn(b: boolean): string {
  return b ? "yes" : "**no**";
}

function buildMarkdown(rows: DayFeasibility[]): string {
  const lines: string[] = [];
  lines.push(`# Target-Feasibility Diagnostic — 2 % target on Jan-Apr 2026`);
  lines.push("");
  lines.push(`> Pure analysis. Does NOT change \`config/strategy.default.json\`, the detector, or the target checker. Answers a single question: on these four days, is a 2 % target reachable in the first place?`);
  lines.push("");
  lines.push(`- Generated: ${new Date().toISOString()}`);
  lines.push(`- Source: \`data/tardis/binance-futures/BTCUSDT/<date>/trades.csv.gz\``);
  lines.push(`- Method: minute-by-minute close prices, sliding-window max upward and max downward % move within 4h / 8h / 24h windows.`);
  lines.push("");

  // Main per-day table
  lines.push(`## 1. Day-level metrics`);
  lines.push("");
  lines.push(`| Date | Return % | Range % | First | Last | High | Low | Trades | Regime |`);
  lines.push(`|---|---|---|---|---|---|---|---|---|`);
  for (const r of rows) {
    lines.push(
      `| ${r.date} | ${pct(r.returnPct)} | ${fmt(r.rangePct)}% | ${fmt(r.firstPrice)} | ${fmt(r.lastPrice)} | ${fmt(r.high)} | ${fmt(r.low)} | ${r.trades.toLocaleString()} | ${r.regime} |`
    );
  }
  lines.push("");

  // Max moves per window
  lines.push(`## 2. Max windowed moves`);
  lines.push("");
  lines.push(`Maximum upward and downward price movement (in % of the window's starting price) reachable from any starting minute of the day.`);
  lines.push("");
  lines.push(`| Date | Max 4h up | Max 4h down | Max 8h up | Max 8h down | Max 24h up | Max 24h down |`);
  lines.push(`|---|---|---|---|---|---|---|`);
  for (const r of rows) {
    lines.push(
      `| ${r.date} | ${fmt(r.max4hUpPct)}% | ${fmt(r.max4hDownPct)}% | ${fmt(r.max8hUpPct)}% | ${fmt(r.max8hDownPct)}% | ${fmt(r.max24hUpPct)}% | ${fmt(r.max24hDownPct)}% |`
    );
  }
  lines.push("");

  // Feasibility table
  lines.push(`## 3. 2 % target feasibility`);
  lines.push("");
  lines.push(`A 2 % target is "feasible" on horizon X if there exists at least one starting minute in the day from which the price moves 2 % up OR 2 % down within X hours. **If feasibility is "no", no signal — however good — can hit the 2 % target on that horizon.**`);
  lines.push("");
  lines.push(`| Date | 2 % feasible 4h | 2 % feasible 8h | 2 % feasible intraday (24h) | Recommended target % | Regime |`);
  lines.push(`|---|---|---|---|---|---|`);
  for (const r of rows) {
    lines.push(
      `| ${r.date} | ${yn(r.feasible4h)} | ${yn(r.feasible8h)} | ${yn(r.feasibleIntraday)} | ${r.recommendedTargetPct.toFixed(1)} | ${r.regime} |`
    );
  }
  lines.push("");

  // Days suitable
  const feasIntra = rows.filter((r) => r.feasibleIntraday);
  const feas8h = rows.filter((r) => r.feasible8h);
  const feas4h = rows.filter((r) => r.feasible4h);
  const not2pct = rows.filter((r) => !r.feasibleIntraday);

  lines.push(`## 4. Which days can be used to evaluate a 2 % strategy?`);
  lines.push("");
  lines.push(`- **Days where 2 % is reachable on intraday (24h) horizon:** ${feasIntra.length} of ${rows.length} → ${feasIntra.map((r) => r.date).join(", ") || "none"}.`);
  lines.push(`- **Days where 2 % is reachable on 8h horizon:** ${feas8h.length} of ${rows.length} → ${feas8h.map((r) => r.date).join(", ") || "none"}.`);
  lines.push(`- **Days where 2 % is reachable on 4h horizon:** ${feas4h.length} of ${rows.length} → ${feas4h.map((r) => r.date).join(", ") || "none"}.`);
  lines.push(`- **Days where 2 % is unreachable on any horizon (the target is structurally wrong for the day):** ${not2pct.length} of ${rows.length} → ${not2pct.map((r) => r.date).join(", ") || "none"}.`);
  lines.push("");

  // Days NOT suitable for 2%
  lines.push(`## 5. Days where 2 % is the wrong target`);
  lines.push("");
  if (not2pct.length === 0) {
    lines.push(`None — every day has at least one window where 2 % is reachable.`);
  } else {
    for (const r of not2pct) {
      lines.push(`### ${r.date} (${r.regime})`);
      lines.push("");
      lines.push(`- Day return: ${pct(r.returnPct)}, range ${fmt(r.rangePct)} %.`);
      lines.push(`- Max 24h move from any single minute: ${fmt(r.max24hUpPct)} % up / ${fmt(r.max24hDownPct)} % down — both **below 2 %**.`);
      lines.push(`- A 2 % target is structurally unreachable on this day. The strategy's 0 % hit rate on ${r.date} is **not evidence that the strategy is bad**; it's evidence that 2 % is the wrong target for this regime.`);
      lines.push(`- A more honest target for this day would be ≈ ${r.recommendedTargetPct.toFixed(1)} %.`);
      lines.push("");
    }
  }
  lines.push("");

  // Specifically address 2026-01-01
  const r1 = rows.find((r) => r.date === "2026-01-01");
  lines.push(`## 6. Can 2026-01-01 be used to evaluate a 2 % strategy?`);
  lines.push("");
  if (r1 !== undefined) {
    if (r1.feasibleIntraday) {
      lines.push(`Yes — 2 % was reachable on at least one intraday window (max 24h up = ${fmt(r1.max24hUpPct)} %, down = ${fmt(r1.max24hDownPct)} %).`);
    } else {
      lines.push(`**No.** Max 24h move from any minute is ${fmt(r1.max24hUpPct)} % up / ${fmt(r1.max24hDownPct)} % down — both below 2 %. Every triggered zone on this day has a 100 % failure rate **by definition of the day's price walk**, regardless of how good or bad the detector is. Any "0 % hit rate on 2026-01-01" should be reported with this caveat.`);
    }
  }
  lines.push("");

  // Recommended target ladder
  lines.push(`## 7. Recommended target by day`);
  lines.push("");
  lines.push(`The recommended target is chosen as the largest standard target (2.0 %, 1.5 %, 1.0 %, 0.5 %) that is BOTH (a) ≤ 0.6 × intraday range, and (b) ≤ max 8h move. This is a heuristic, not a tuned parameter — it just keeps the target inside what the day's price action actually delivered.`);
  lines.push("");
  lines.push(`| Date | Range % | Max 8h up | Max 8h down | Recommended target % |`);
  lines.push(`|---|---|---|---|---|`);
  for (const r of rows) {
    lines.push(`| ${r.date} | ${fmt(r.rangePct)}% | ${fmt(r.max8hUpPct)}% | ${fmt(r.max8hDownPct)}% | ${r.recommendedTargetPct.toFixed(1)} |`);
  }
  lines.push("");
  lines.push(`Days where 2 % is unreachable would yield more meaningful signal-vs-baseline numbers if evaluated against the recommended target instead. **This requires changing the \`targetPct\` parameter in a future run; it does not change the strategy, the detector, or the existing thresholds.**`);
  lines.push("");

  // Honest verdict
  lines.push(`## 8. Honest verdict`);
  lines.push("");
  if (feasIntra.length === rows.length) {
    lines.push(`Every one of the ${rows.length} days is theoretically usable to evaluate a 2 % strategy.`);
  } else {
    lines.push(`Only **${feasIntra.length} of ${rows.length}** days are suitable for evaluating a 2 % strategy on the intraday horizon. The remaining ${not2pct.length} day(s) (${not2pct.map((r) => r.date).join(", ")}) physically cannot deliver a 2 % move from any starting point — the strategy's hit rate on those days is **mechanically bounded at 0 %** regardless of detector quality.`);
  }
  lines.push("");
  lines.push(`Of the suitable days, only **${feas4h.length}** have 2 % reachable on the 4h horizon — meaning the 4h hit rate is the most discriminating; the 24h hit rate has the most permissive feasibility.`);
  lines.push("");
  lines.push(`When reporting hit rates on a single day, the honest framing is:`);
  lines.push(`- include "2 % feasible on this horizon: yes/no" for that day;`);
  lines.push(`- treat 0 % hit rate on infeasible days as a NULL result, not a strategy failure;`);
  lines.push(`- compute "wins per feasible day" alongside "wins per day" when aggregating multiple days.`);
  lines.push("");
  lines.push(`> The strategy thresholds in \`config/strategy.default.json\` are unchanged. The detector and target checker are unchanged. This is purely a feasibility audit of the chosen 2 % target on the available 4 days.`);
  lines.push("");

  return lines.join("\n");
}

function csvCols(): CsvColumn<DayFeasibility>[] {
  return [
    { name: "date", get: (r) => r.date },
    { name: "trades", get: (r) => r.trades },
    { name: "first_price", get: (r) => (r.firstPrice !== null ? r.firstPrice.toFixed(2) : "") },
    { name: "last_price", get: (r) => (r.lastPrice !== null ? r.lastPrice.toFixed(2) : "") },
    { name: "high", get: (r) => (r.high !== null ? r.high.toFixed(2) : "") },
    { name: "low", get: (r) => (r.low !== null ? r.low.toFixed(2) : "") },
    { name: "return_pct", get: (r) => (r.returnPct !== null ? r.returnPct.toFixed(3) : "") },
    { name: "range_pct", get: (r) => (r.rangePct !== null ? r.rangePct.toFixed(3) : "") },
    { name: "max_4h_up_pct", get: (r) => r.max4hUpPct.toFixed(3) },
    { name: "max_4h_down_pct", get: (r) => r.max4hDownPct.toFixed(3) },
    { name: "max_8h_up_pct", get: (r) => r.max8hUpPct.toFixed(3) },
    { name: "max_8h_down_pct", get: (r) => r.max8hDownPct.toFixed(3) },
    { name: "max_24h_up_pct", get: (r) => r.max24hUpPct.toFixed(3) },
    { name: "max_24h_down_pct", get: (r) => r.max24hDownPct.toFixed(3) },
    { name: "feasible_2pct_4h", get: (r) => (r.feasible4h ? "yes" : "no") },
    { name: "feasible_2pct_8h", get: (r) => (r.feasible8h ? "yes" : "no") },
    { name: "feasible_2pct_intraday", get: (r) => (r.feasibleIntraday ? "yes" : "no") },
    { name: "regime", get: (r) => r.regime },
    { name: "recommended_target_pct", get: (r) => r.recommendedTargetPct.toFixed(2) },
  ];
}

async function main(): Promise<void> {
  const rows: DayFeasibility[] = [];
  for (const d of DATES) {
    rows.push(await analyseDay(d));
  }
  fs.mkdirSync(REPORTS, { recursive: true });
  fs.writeFileSync(OUT_MD, buildMarkdown(rows), "utf8");
  writeCsv(OUT_CSV, csvCols(), rows);
  console.log("");
  console.log(`Wrote: ${path.resolve(OUT_MD)}`);
  console.log(`Wrote: ${path.resolve(OUT_CSV)}`);
  console.log("");
  console.log("| Date | Return | Range | Max4hUp | Max4hDn | Max8hUp | Max8hDn | 2%feas? | Regime |");
  console.log("|---|---|---|---|---|---|---|---|---|");
  for (const r of rows) {
    console.log(
      `| ${r.date} | ${pct(r.returnPct)} | ${fmt(r.rangePct)}% | ${fmt(r.max4hUpPct)}% | ${fmt(r.max4hDownPct)}% | ${fmt(r.max8hUpPct)}% | ${fmt(r.max8hDownPct)}% | 4h:${r.feasible4h ? "Y" : "N"} 8h:${r.feasible8h ? "Y" : "N"} 24h:${r.feasibleIntraday ? "Y" : "N"} | ${r.regime} |`
    );
  }
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
