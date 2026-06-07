// `npm run validate:tardis -- --input ./data/tardis/binance-futures/BTCUSDT \
//      --symbol BTCUSDT --exchange binance-futures \
//      --dates 2026-01-01,2026-02-01,2026-03-01,2026-04-01`
//
// Validates that each requested day has Tardis CSV files that parse cleanly
// for the strategy backtest. Optional types are tolerated; only
// `incremental_book_L2` and `trades` are required.

import * as fs from "node:fs";
import * as path from "node:path";
import { parseArgs, getString } from "./args.js";
import { validateDay, type DayValidation } from "../strategy/validateTardisCore.js";
import { writeJson } from "../reports/jsonWriter.js";
import { buildValidateMarkdown } from "../reports/validateTardisReport.js";
import { SAMPLE_2026_DATES } from "../data/tardisUrls.js";

export interface ValidateRunOpts {
  input: string;
  symbol: string;
  exchange: string;
  dates: string[];
  outDir?: string;
  reportName?: string;
}

export interface ValidateRunResult {
  days: DayValidation[];
  reportMdPath: string;
  reportJsonPath: string;
}

export async function runValidate(opts: ValidateRunOpts): Promise<ValidateRunResult> {
  const days: DayValidation[] = [];
  for (const date of opts.dates) {
    const v = await validateDay({
      inputPath: opts.input,
      symbol: opts.symbol,
      exchange: opts.exchange,
      date,
    });
    days.push(v);
  }
  const reportName = opts.reportName ?? "tardis_validation_2026_ytd_except_may";
  const outDir = opts.outDir ?? "reports";
  fs.mkdirSync(outDir, { recursive: true });
  const md = buildValidateMarkdown({
    generatedAt: new Date().toISOString(),
    inputPath: opts.input,
    symbol: opts.symbol,
    exchange: opts.exchange,
    days,
  });
  const reportMdPath = path.join(outDir, `${reportName}.md`);
  const reportJsonPath = path.join(outDir, `${reportName}.json`);
  fs.writeFileSync(reportMdPath, md, "utf8");
  writeJson(reportJsonPath, {
    generatedAt: new Date().toISOString(),
    inputPath: opts.input,
    symbol: opts.symbol,
    exchange: opts.exchange,
    days,
  });
  return { days, reportMdPath, reportJsonPath };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const input = getString(args, "input");
  const symbol = getString(args, "symbol");
  const exchange = getString(args, "exchange", "binance-futures");
  const datesArg = getString(args, "dates", SAMPLE_2026_DATES.join(","));
  const dates = datesArg
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
  const outDir = (args.flags["out"] as string | undefined) ?? "reports";

  console.log(`[validate:tardis] input=${input} symbol=${symbol} exchange=${exchange} dates=${dates.join(",")}`);
  const r = await runValidate({ input, symbol, exchange, dates, outDir });
  for (const d of r.days) {
    const verdict = d.isValid ? "VALID" : "INVALID";
    console.log(`  ${d.date}: ${verdict}${d.invalidReasons.length ? "  reasons=" + d.invalidReasons.join("; ") : ""}`);
  }
  console.log(`Wrote:\n  - ${r.reportMdPath}\n  - ${r.reportJsonPath}`);
  // Exit non-zero only if EVERY day is invalid (otherwise we want to continue
  // into a partial sample backtest).
  if (r.days.length > 0 && r.days.every((d) => !d.isValid)) process.exit(2);
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
