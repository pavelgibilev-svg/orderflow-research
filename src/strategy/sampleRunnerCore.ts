// Pure orchestrator core for `backtest:sample-2026`.
//
// Sequentially: validate -> snapshots -> backtest, per day. Catches errors
// per day so one bad day doesn't kill the run, and aggregates a metrics
// table that the markdown report renders.

import * as fs from "node:fs";
import * as path from "node:path";
import type { DayValidation } from "./validateTardisCore.js";
import { validateDay } from "./validateTardisCore.js";
import type { BacktestDayResult } from "../cli/backtestDay.js";
import { runBacktestDay } from "../cli/backtestDay.js";
import { runExportSnapshots } from "../cli/exportSnapshots.js";
import { SAMPLE_2026_DATES } from "../data/tardisUrls.js";

export interface SampleRunDayResult {
  date: string;
  isValid: boolean;
  validation: DayValidation;
  backtest: BacktestDayResult | null;
  snapshotsExported: number;
  errored: string | null;
  notes: string;
}

export interface SampleRunOpts {
  input: string;
  symbol: string;
  exchange: string;
  targetPct: number;
  horizons: string[];
  dates?: ReadonlyArray<string>;
  outDir?: string;
  configPath?: string;
  /** When true, skip the export:snapshots pass (purely diagnostic). */
  skipSnapshots?: boolean;
  /** Compute-budget cap on L2 replay per day (in hours). Trades continue full 24h. */
  maxL2Hours?: number;
  /** Optional injection seam for tests: replaces the per-day function. */
  runDay?: (
    opts: SampleRunDayOpts
  ) => Promise<SampleRunDayResult>;
}

export interface SampleRunDayOpts {
  date: string;
  input: string;
  symbol: string;
  exchange: string;
  targetPct: number;
  horizons: string[];
  outDir: string;
  configPath?: string;
  skipSnapshots?: boolean;
  maxL2Hours?: number;
}

export async function runSample2026(opts: SampleRunOpts): Promise<SampleRunDayResult[]> {
  const dates = opts.dates ?? SAMPLE_2026_DATES;
  const outDir = opts.outDir ?? path.join("reports", "sample_2026_ytd_except_may");
  fs.mkdirSync(outDir, { recursive: true });
  const results: SampleRunDayResult[] = [];
  const runner = opts.runDay ?? defaultRunDay;
  for (const date of dates) {
    try {
      const r = await runner({
        date,
        input: opts.input,
        symbol: opts.symbol,
        exchange: opts.exchange,
        targetPct: opts.targetPct,
        horizons: opts.horizons,
        outDir,
        configPath: opts.configPath,
        skipSnapshots: opts.skipSnapshots,
        maxL2Hours: opts.maxL2Hours,
      });
      results.push(r);
    } catch (e) {
      // Even the runner itself failed catastrophically — record and move on.
      results.push({
        date,
        isValid: false,
        validation: {
          date,
          symbol: opts.symbol,
          exchange: opts.exchange,
          inputPath: opts.input,
          isValid: false,
          invalidReasons: ["runner crashed"],
          dataTypes: [],
          warnings: [],
        },
        backtest: null,
        snapshotsExported: 0,
        errored: (e as Error).message,
        notes: "runner crashed; see errored field",
      });
    }
  }
  return results;
}

async function defaultRunDay(opts: SampleRunDayOpts): Promise<SampleRunDayResult> {
  const validation = await validateDay({
    inputPath: opts.input,
    symbol: opts.symbol,
    exchange: opts.exchange,
    date: opts.date,
  });
  if (!validation.isValid) {
    return {
      date: opts.date,
      isValid: false,
      validation,
      backtest: null,
      snapshotsExported: 0,
      errored: null,
      notes: `Day skipped: ${validation.invalidReasons.join("; ")}`,
    };
  }
  let snapshotsExported = 0;
  let backtest: BacktestDayResult | null = null;
  let errored: string | null = null;
  if (!opts.skipSnapshots) {
    try {
      const snapDir = path.join(opts.outDir, "snapshots", opts.date);
      const snap = await runExportSnapshots({
        input: opts.input,
        symbol: opts.symbol,
        date: opts.date,
        interval: "1s",
        depth: 50,
        outDir: snapDir,
      });
      snapshotsExported = snap.count;
    } catch (e) {
      errored = `snapshots: ${(e as Error).message}`;
    }
  }
  try {
    backtest = await runBacktestDay({
      input: opts.input,
      exchange: opts.exchange,
      symbol: opts.symbol,
      date: opts.date,
      targetPct: opts.targetPct,
      horizons: opts.horizons,
      configPath: opts.configPath,
      outDir: path.join(opts.outDir, "backtests", opts.date),
      maxL2Hours: opts.maxL2Hours,
    });
  } catch (e) {
    errored = errored ? errored + "; " : "";
    errored += `backtest: ${(e as Error).message}`;
  }
  return {
    date: opts.date,
    isValid: true,
    validation,
    backtest,
    snapshotsExported,
    errored,
    notes: errored ? "see errored field" : "ok",
  };
}
