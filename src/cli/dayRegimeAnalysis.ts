// `npx tsx src/cli/dayRegimeAnalysis.ts`
//
// Streams the trades.csv.gz of every downloaded day and computes:
//   - first trade price (day open)
//   - last trade price (day close)
//   - high / low
//   - day return %
//   - intraday range %
//   - regime classification (bullish / bearish / choppy)
//
// Used to pick the most contrasting day vs 2026-02-01 for the second
// full-day verification run.

import * as fs from "node:fs";
import * as path from "node:path";
import { streamTardisFile } from "../data/tardisCsvLoader.js";
import type { TradeEvent } from "../data/schema.js";

interface DayStats {
  date: string;
  firstPrice: number | null;
  lastPrice: number | null;
  high: number | null;
  low: number | null;
  trades: number;
  returnPct: number | null;
  rangePct: number | null;
  regime: "bullish" | "bearish" | "choppy" | "unknown";
}

const DATA_ROOT = "data/tardis/binance-futures/BTCUSDT";

async function statsForDay(date: string): Promise<DayStats> {
  const file = path.join(DATA_ROOT, date, "trades.csv.gz");
  const stats: DayStats = {
    date,
    firstPrice: null,
    lastPrice: null,
    high: null,
    low: null,
    trades: 0,
    returnPct: null,
    rangePct: null,
    regime: "unknown",
  };
  if (!fs.existsSync(file)) return stats;
  let n = 0;
  let hi = -Infinity;
  let lo = +Infinity;
  let firstPx: number | null = null;
  let lastPx: number | null = null;
  for await (const ev of streamTardisFile(file, { dataType: "trades" })) {
    const t = ev as TradeEvent;
    if (firstPx === null) firstPx = t.price;
    lastPx = t.price;
    if (t.price > hi) hi = t.price;
    if (t.price < lo) lo = t.price;
    n++;
  }
  stats.firstPrice = firstPx;
  stats.lastPrice = lastPx;
  stats.high = Number.isFinite(hi) ? hi : null;
  stats.low = Number.isFinite(lo) ? lo : null;
  stats.trades = n;
  if (firstPx !== null && lastPx !== null && firstPx > 0) {
    stats.returnPct = ((lastPx - firstPx) / firstPx) * 100;
  }
  if (stats.high !== null && stats.low !== null && stats.low > 0) {
    stats.rangePct = ((stats.high - stats.low) / stats.low) * 100;
  }
  // Regime: |return| >= 1.5% -> trending; else choppy/flat.
  // Sign decides bullish/bearish.
  if (stats.returnPct !== null) {
    if (stats.returnPct >= 1.5) stats.regime = "bullish";
    else if (stats.returnPct <= -1.5) stats.regime = "bearish";
    else stats.regime = "choppy";
  }
  return stats;
}

async function main(): Promise<void> {
  const dates = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"];
  const all: DayStats[] = [];
  for (const d of dates) {
    process.stdout.write(`Scanning ${d}... `);
    const t0 = Date.now();
    const s = await statsForDay(d);
    all.push(s);
    process.stdout.write(`done in ${((Date.now() - t0) / 1000).toFixed(1)}s\n`);
  }
  console.log("");
  console.log("| Date | First | Last | High | Low | Return % | Range % | Trades | Regime |");
  console.log("|---|---|---|---|---|---|---|---|---|");
  for (const s of all) {
    const fmt = (n: number | null) => (n === null ? "-" : n.toFixed(2));
    const fmtPct = (n: number | null) => (n === null ? "-" : (n >= 0 ? "+" : "") + n.toFixed(2) + "%");
    console.log(
      `| ${s.date} | ${fmt(s.firstPrice)} | ${fmt(s.lastPrice)} | ${fmt(s.high)} | ${fmt(s.low)} | ${fmtPct(s.returnPct)} | ${fmt(s.rangePct)}% | ${s.trades.toLocaleString()} | ${s.regime} |`
    );
  }

  // Save to JSON for later consumption by the verification report writer.
  fs.mkdirSync("reports", { recursive: true });
  fs.writeFileSync("reports/day_regimes_2026.json", JSON.stringify(all, null, 2), "utf8");
  console.log("\nSaved: reports/day_regimes_2026.json");
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
