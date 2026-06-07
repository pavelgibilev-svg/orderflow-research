// `npm run backtest:sample-2026`
//
// Runs validate -> snapshot export -> backtest:day for each of
// 2026-01-01, 2026-02-01, 2026-03-01, 2026-04-01 in order. One bad day
// does not abort the rest. Aggregates a per-day metrics table.

import * as fs from "node:fs";
import * as path from "node:path";
import { parseArgs, getString, getNumber } from "./args.js";
import { runSample2026 } from "../strategy/sampleRunnerCore.js";
import { writeJson } from "../reports/jsonWriter.js";
import { writeCsv, type CsvColumn } from "../reports/csvWriter.js";
import { buildSampleRunMarkdown } from "../reports/sampleRunReport.js";
import type { SampleRunDayResult } from "../strategy/sampleRunnerCore.js";
import { SAMPLE_2026_DATES } from "../data/tardisUrls.js";

interface CliOpts {
  input: string;
  symbol: string;
  exchange: string;
  targetPct: number;
  horizons: string[];
  outDir: string;
  configPath?: string;
}

function buildCsvCols(): CsvColumn<SampleRunDayResult>[] {
  return [
    { name: "date", get: (d) => d.date },
    { name: "valid", get: (d) => (d.isValid ? "yes" : "no") },
    { name: "l2_rows", get: (d) => d.backtest?.rowsProcessed.l2 ?? "" },
    { name: "trades_rows", get: (d) => d.backtest?.rowsProcessed.trades ?? "" },
    {
      name: "optional_present",
      get: (d) =>
        d.validation.dataTypes
          .filter((dt) => !dt.required && dt.status === "ok")
          .map((dt) => dt.dataType)
          .join("|"),
    },
    {
      name: "optional_missing",
      get: (d) =>
        d.validation.dataTypes
          .filter((dt) => !dt.required && dt.status !== "ok")
          .map((dt) => dt.dataType)
          .join("|"),
    },
    { name: "quality_flag_tick_count", get: (d) => d.backtest?.qualityFlagsTickCount ?? "" },
    { name: "snapshots_exported", get: (d) => d.snapshotsExported },
    { name: "zones_total", get: (d) => d.backtest?.zonesTotal ?? "" },
    { name: "zones_candidates", get: (d) => d.backtest?.zonesCandidates ?? "" },
    { name: "zones_confirmed", get: (d) => d.backtest?.zonesConfirmed ?? "" },
    { name: "zones_triggered", get: (d) => d.backtest?.zonesTriggered ?? "" },
    { name: "reached_4h", get: (d) => d.backtest?.zonesReachedByHorizon["4h"] ?? "" },
    { name: "reached_8h", get: (d) => d.backtest?.zonesReachedByHorizon["8h"] ?? "" },
    { name: "reached_24h", get: (d) => d.backtest?.zonesReachedByHorizon["24h"] ?? "" },
    { name: "failed_no_trigger_invalidated", get: (d) => d.backtest?.zonesFailedOrNoTriggerOrInvalidated ?? "" },
    {
      name: "baseline_24h_up_pct",
      get: (d) => {
        const b = d.backtest?.baselines.find((x) => x.horizon === "24h");
        return b ? (b.upRate * 100).toFixed(2) : "";
      },
    },
    {
      name: "baseline_24h_down_pct",
      get: (d) => {
        const b = d.backtest?.baselines.find((x) => x.horizon === "24h");
        return b ? (b.downRate * 100).toFixed(2) : "";
      },
    },
    {
      name: "triggered_hit_rate_pct",
      get: (d) => (d.backtest ? (d.backtest.triggeredHitRate * 100).toFixed(2) : ""),
    },
    { name: "notes", get: (d) => d.notes || "" },
    { name: "errored", get: (d) => d.errored || "" },
  ];
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const opts: CliOpts = {
    input: getString(args, "input", "./data/tardis/binance-futures/BTCUSDT"),
    symbol: getString(args, "symbol", "BTCUSDT"),
    exchange: getString(args, "exchange", "binance-futures"),
    targetPct: getNumber(args, "target-pct", 2),
    horizons: getString(args, "horizons", "4h,8h,24h").split(",").map((s) => s.trim()),
    outDir: getString(args, "out", path.join("reports", "sample_2026_ytd_except_may")),
    configPath: typeof args.flags["config"] === "string" ? (args.flags["config"] as string) : undefined,
  };

  console.log(`[sample-2026] symbol=${opts.symbol} exchange=${opts.exchange} target=${opts.targetPct}% horizons=${opts.horizons.join(",")} input=${opts.input}`);
  fs.mkdirSync(opts.outDir, { recursive: true });

  const skipSnapshots = !!args.flags["skip-snapshots"];
  if (skipSnapshots) console.log("[sample-2026] --skip-snapshots: diagnostic snapshot export will be skipped.");
  const maxL2HoursStr = typeof args.flags["max-l2-hours"] === "string" ? (args.flags["max-l2-hours"] as string) : undefined;
  const maxL2Hours = maxL2HoursStr !== undefined ? Number(maxL2HoursStr) : undefined;
  if (maxL2Hours !== undefined) {
    console.log(`[sample-2026] --max-l2-hours=${maxL2Hours}: heavy L2 replay limited to first ${maxL2Hours}h of each day; full-day trades retained for target checking.`);
  }
  const days = await runSample2026({
    input: opts.input,
    symbol: opts.symbol,
    exchange: opts.exchange,
    targetPct: opts.targetPct,
    horizons: opts.horizons,
    outDir: opts.outDir,
    configPath: opts.configPath,
    dates: SAMPLE_2026_DATES,
    skipSnapshots,
    maxL2Hours,
  });

  const summaryCsvPath = path.join(opts.outDir, "summary.csv");
  writeCsv(summaryCsvPath, buildCsvCols(), days);
  const summaryJsonPath = path.join(opts.outDir, "summary.json");
  writeJson(summaryJsonPath, days);
  const reportMdPath = path.join(opts.outDir, "report.md");
  fs.writeFileSync(
    reportMdPath,
    buildSampleRunMarkdown({
      generatedAt: new Date().toISOString(),
      symbol: opts.symbol,
      exchange: opts.exchange,
      targetPct: opts.targetPct,
      horizons: opts.horizons,
      inputPath: opts.input,
      days,
    }),
    "utf8"
  );

  console.log("\nPer-day verdicts:");
  for (const d of days) {
    const verdict = d.isValid ? "VALID  " : "INVALID";
    const hits = d.backtest
      ? `triggered=${d.backtest.zonesTriggered} reached4h=${d.backtest.zonesReachedByHorizon["4h"] ?? 0} reached24h=${d.backtest.zonesReachedByHorizon["24h"] ?? 0}`
      : "(no backtest)";
    console.log(`  ${d.date}  ${verdict}  ${hits}${d.errored ? "  ERR=" + d.errored : ""}`);
  }
  console.log(`\nWrote:\n  - ${summaryCsvPath}\n  - ${summaryJsonPath}\n  - ${reportMdPath}`);
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
