// `npm run live:acceptance -- --duration-min 10`
//
// Acceptance check for the live recorder. The orchestration is:
//   1. Ping ClickHouse and verify all recorder tables exist (else suggest db:migrate).
//   2. Start RecorderService for SYMBOLS (default BTCUSDT) for `--duration-min` minutes.
//   3. Every 30 s, print per-table inserted-row deltas, queue size, spool size.
//   4. After the timer elapses, stop the recorder, run the sanity SQL queries.
//   5. Run `backtest:db` for the same window so the DB → strategy adapter
//      gets exercised. Zero zones is normal on a 10-min window.
//   6. Write reports/LIVE_RECORDER_ACCEPTANCE_<timestamp>.{md,json}.
//
// The orchestration is split into a pure `runAcceptance()` function that
// takes injected ClickHouse / recorder-factory / backtest-runner deps, so
// tests can verify failure paths (e.g. CH down → recorder never starts).

import * as fs from "node:fs";
import * as path from "node:path";
import { parseArgs, getOptString } from "./args.js";
import {
  buildAcceptanceMarkdown,
  computeVerdict,
  type AcceptanceBacktestSummary,
  type AcceptanceHealth,
  type AcceptanceLatestSnapshot,
  type AcceptanceReportInput,
  type AcceptanceSnapshotQuality,
  type AcceptanceTableCount,
} from "../live-recorder/acceptance/acceptanceReport.js";
import {
  ACCEPTANCE_TABLES,
  buildCountSql,
  buildHealthAggregateSql,
  buildLatestSnapshotSql,
  buildMinMaxTimeSql,
  buildSnapshotQualitySql,
  type AcceptanceWindow,
} from "../live-recorder/acceptance/acceptanceQueries.js";
import { parseDurationMinutesArg } from "../live-recorder/acceptance/duration.js";
import { buildBacktestInvocation, describeBacktestInvocation } from "../live-recorder/acceptance/backtestDbInvocation.js";
import { ALL_TABLES } from "../live-recorder/schema.js";
import { clickhouseFromEnv, type ClickHouseClient } from "../live-recorder/clickhouseClient.js";
import { RecorderService } from "../live-recorder/recorderService.js";
import { runBacktestDb } from "./backtestDb.js";

// ---------- Injectable dependencies ----------

export interface AcceptanceCommonDeps {
  /** ClickHouse client. Injected for tests. */
  ch: ClickHouseClient;
  /** Function that builds and starts the recorder. Injected so we can avoid
   *  hitting Binance in unit tests. */
  startRecorder?: (opts: { symbols: string[]; spoolDir: string }) => Promise<{
    stop: () => Promise<void>;
  }>;
  /** Wraps `runBacktestDb`. Injected for unit tests. */
  runBacktest?: typeof runBacktestDb;
  /** Wall-clock — replaced in tests. */
  now?: () => number;
  /** Sleep — replaced in tests. */
  sleep?: (ms: number) => Promise<void>;
  /** Logger — replaced in tests to silence stdout. */
  log?: (level: "info" | "warn" | "error", msg: string, extra?: unknown) => void;
  /** Output directory for reports + spool. */
  reportsDir?: string;
  spoolDir?: string;
}

export interface AcceptanceRunOpts extends AcceptanceCommonDeps {
  durationMs: number;
  symbols: string[];
  exchange?: string;
  primarySymbol?: string;
  /** When true, skip backtest:db at the end. Useful in CI smoke tests. */
  skipBacktest?: boolean;
}

export interface AcceptanceRunResult {
  written: { md: string; json: string };
  verdict: ReturnType<typeof computeVerdict>;
  /** Convenience: the report input we produced (also serialised to JSON). */
  input: AcceptanceReportInput;
}

const STATUS_INTERVAL_MS = 30_000;

/** Pure entry point — every external dependency is injectable. */
export async function runAcceptance(opts: AcceptanceRunOpts): Promise<AcceptanceRunResult> {
  const log = opts.log ?? defaultLogger;
  const now = opts.now ?? (() => Date.now());
  const sleep = opts.sleep ?? ((ms) => new Promise<void>((r) => setTimeout(r, ms)));
  const reportsDir = opts.reportsDir ?? "reports";
  const spoolDir = opts.spoolDir ?? "./data/live-spool";
  const exchange = opts.exchange ?? "binance-futures";
  const primarySymbol = opts.primarySymbol ?? opts.symbols[0] ?? "BTCUSDT";
  const notes: string[] = [];

  // ---------- 1. ClickHouse health check ----------

  const pingOk = await opts.ch.ping().catch(() => false);
  if (!pingOk) {
    const msg = `ClickHouse not reachable. Start it (\`docker compose up -d clickhouse\`) and re-run.`;
    log("error", msg);
    throw new AcceptanceAbort(msg);
  }
  const db = (opts.ch as unknown as { qualifyTable(t: string): string }).qualifyTable("x").split(".")[0] ?? "default";
  // Verify recorder tables exist.
  const sysRows = await opts.ch.query<{ name: string }>(
    `SELECT name FROM system.tables WHERE database = '${db.replace(/'/g, "''")}' ORDER BY name`
  );
  const present = new Set(sysRows.map((r) => r.name));
  const missing = ALL_TABLES.filter((t) => !present.has(t));
  if (missing.length > 0) {
    const msg = `Missing tables: ${missing.join(", ")}. Run \`npm run db:migrate\` first.`;
    log("error", msg);
    throw new AcceptanceAbort(msg);
  }

  // ---------- 2. Start recorder ----------

  const startMs = now();
  const startTimeIso = new Date(startMs).toISOString();
  log("info", `[acceptance] start=${startTimeIso} symbols=${opts.symbols.join(",")} duration=${(opts.durationMs / 60_000).toFixed(1)}min`);

  const startRecorder = opts.startRecorder ?? defaultStartRecorder(opts.ch, exchange);
  const handle = await startRecorder({ symbols: opts.symbols, spoolDir });

  // ---------- 3. Per-30s status print loop ----------

  const window: AcceptanceWindow = {
    exchange,
    symbol: primarySymbol,
    fromMs: startMs,
    // Updated as the run progresses.
    toMs: startMs + opts.durationMs,
  };
  const printStatus = async (label: string): Promise<void> => {
    const w: AcceptanceWindow = { ...window, toMs: now() };
    try {
      const counts = await fetchTableCounts(opts.ch, w);
      const summary = counts.map((c) => `${c.table}=${c.rowCount}`).join(" ");
      log("info", `[${label}] ${summary}`);
    } catch (e) {
      log("warn", `[${label}] count query failed`, e);
    }
  };

  let elapsedMs = 0;
  while (elapsedMs < opts.durationMs) {
    const wait = Math.min(STATUS_INTERVAL_MS, opts.durationMs - elapsedMs);
    await sleep(wait);
    elapsedMs += wait;
    if (elapsedMs < opts.durationMs) {
      await printStatus(`progress @ ${(elapsedMs / 1000).toFixed(0)}s`);
    }
  }

  // ---------- 4. Stop recorder, gather final stats ----------

  log("info", "[acceptance] stopping recorder");
  try {
    await handle.stop();
  } catch (e) {
    log("warn", "recorder stop threw", e);
  }
  const endMs = now();
  const endTimeIso = new Date(endMs).toISOString();
  // Refresh window with the actual end time and re-run all queries.
  window.toMs = endMs;
  const tableCounts = await fetchTableCountsWithTimes(opts.ch, window);
  const snapshotQuality = await fetchSnapshotQuality(opts.ch, window);
  const latestSnapshot = await fetchLatestSnapshot(opts.ch, window);
  const health = await fetchHealth(opts.ch, window);
  const spoolFilesCreated = await checkSpoolFiles(spoolDir);
  const insertErrorsObserved = (health?.degradedSamples ?? 0) > 0 || (health?.maxSpoolQueueSize ?? 0) > 0;

  // ---------- 5. backtest:db sanity replay ----------

  const reportTimestamp = startTimeIso.replace(/[:.]/g, "-").replace("T", "_").replace("Z", "Z");
  const backtestOutDir = path.join(reportsDir, `live_acceptance_db_${reportTimestamp}`);
  let backtest: AcceptanceBacktestSummary;
  if (opts.skipBacktest) {
    backtest = {
      ran: false,
      zonesFound: 0,
      zonesTriggered: 0,
      zonesReachedRaw: 0,
      uniqueReachedMoves: 0,
      reportPath: null,
      skippedReason: "--skip-backtest flag set",
    };
  } else {
    const inv = buildBacktestInvocation({
      symbol: primarySymbol,
      exchange,
      fromMs: startMs,
      toMs: endMs,
      targetPct: 2,
      horizons: ["4h", "8h", "24h"],
      outDir: backtestOutDir,
    });
    log("info", `[acceptance] running ${describeBacktestInvocation(inv)}`);
    try {
      const runner = opts.runBacktest ?? runBacktestDb;
      // runBacktestDb writes its own reports — we just consume the output dir.
      await runner({
        symbol: inv.symbol,
        exchange: inv.exchange,
        fromMs: inv.fromMs,
        toMs: inv.toMs,
        targetPct: inv.targetPct,
        horizons: inv.horizons,
        outDir: inv.outDir,
      });
      // Try to extract zones / triggered from the produced zones.json.
      const zonesJson = path.join(inv.outDir, "zones.json");
      let zonesFound = 0;
      let zonesTriggered = 0;
      let zonesReachedRaw = 0;
      let uniqueReachedMoves = 0;
      if (fs.existsSync(zonesJson)) {
        const arr = JSON.parse(fs.readFileSync(zonesJson, "utf8")) as Array<{
          status: string;
          triggerTs?: number;
          uniqueMoveId?: number;
        }>;
        zonesFound = arr.length;
        zonesTriggered = arr.filter((z) => z.triggerTs !== undefined).length;
        zonesReachedRaw = arr.filter((z) => z.status === "RESOLVED_REACHED").length;
        uniqueReachedMoves = new Set(arr.filter((z) => z.uniqueMoveId !== undefined).map((z) => z.uniqueMoveId)).size;
      }
      backtest = {
        ran: true,
        zonesFound,
        zonesTriggered,
        zonesReachedRaw,
        uniqueReachedMoves,
        reportPath: backtestOutDir,
      };
    } catch (e) {
      backtest = {
        ran: false,
        zonesFound: 0,
        zonesTriggered: 0,
        zonesReachedRaw: 0,
        uniqueReachedMoves: 0,
        reportPath: null,
        skippedReason: `backtest:db threw: ${(e as Error).message}`,
      };
      notes.push(`backtest:db error: ${(e as Error).message}`);
    }
  }

  // ---------- 6. Write reports ----------

  const input: AcceptanceReportInput = {
    startTimeIso,
    endTimeIso,
    durationMs: endMs - startMs,
    exchange,
    symbols: [...opts.symbols],
    primarySymbol,
    ch: { url: process.env.CLICKHOUSE_URL ?? "http://localhost:8123", database: db },
    tableCounts,
    snapshotQuality,
    latestSnapshot,
    health,
    spoolFilesCreated,
    insertErrorsObserved,
    notes,
    backtest,
  };
  const verdict = computeVerdict(input);
  fs.mkdirSync(reportsDir, { recursive: true });
  const mdPath = path.join(reportsDir, `LIVE_RECORDER_ACCEPTANCE_${reportTimestamp}.md`);
  const jsonPath = path.join(reportsDir, `LIVE_RECORDER_ACCEPTANCE_${reportTimestamp}.json`);
  fs.writeFileSync(mdPath, buildAcceptanceMarkdown(input, verdict), "utf8");
  fs.writeFileSync(jsonPath, JSON.stringify({ input, verdict }, null, 2), "utf8");

  log("info", `[acceptance] verdict=${verdict.overall}`);
  log("info", `[acceptance] wrote: ${mdPath}`);
  log("info", `[acceptance] wrote: ${jsonPath}`);

  return { written: { md: mdPath, json: jsonPath }, verdict, input };
}

export class AcceptanceAbort extends Error {
  constructor(msg: string) {
    super(msg);
    this.name = "AcceptanceAbort";
  }
}

// ---------- query helpers ----------

async function fetchTableCounts(ch: ClickHouseClient, w: AcceptanceWindow): Promise<AcceptanceTableCount[]> {
  const out: AcceptanceTableCount[] = [];
  for (const t of ACCEPTANCE_TABLES) {
    const rows = await ch.query<{ c: number | string }>(buildCountSql(t, w));
    out.push({ table: t, rowCount: Number(rows[0]?.c ?? 0), firstTs: null, lastTs: null });
  }
  return out;
}
async function fetchTableCountsWithTimes(ch: ClickHouseClient, w: AcceptanceWindow): Promise<AcceptanceTableCount[]> {
  const out: AcceptanceTableCount[] = [];
  for (const t of ACCEPTANCE_TABLES) {
    const cnt = await ch.query<{ c: number | string }>(buildCountSql(t, w));
    const tt = await ch.query<{ first_ts: string; last_ts: string }>(buildMinMaxTimeSql(t, w));
    out.push({
      table: t,
      rowCount: Number(cnt[0]?.c ?? 0),
      firstTs: tt[0]?.first_ts ?? null,
      lastTs: tt[0]?.last_ts ?? null,
    });
  }
  return out;
}

async function fetchSnapshotQuality(ch: ClickHouseClient, w: AcceptanceWindow): Promise<AcceptanceSnapshotQuality | null> {
  const rows = await ch.query<{
    snapshots: number | string;
    crossed: number | string;
    empty: number | string;
    flagged_crossed: number | string;
    flagged_empty: number | string;
    flagged_wide_spread: number | string;
    spread_min: number | string;
    spread_max: number | string;
    spread_avg: number | string;
  }>(buildSnapshotQualitySql(w));
  const r = rows[0];
  if (!r || Number(r.snapshots) === 0) return null;
  return {
    snapshots: Number(r.snapshots),
    crossed: Number(r.crossed),
    empty: Number(r.empty),
    flaggedCrossed: Number(r.flagged_crossed),
    flaggedEmpty: Number(r.flagged_empty),
    flaggedWideSpread: Number(r.flagged_wide_spread),
    spreadMin: Number(r.spread_min),
    spreadMax: Number(r.spread_max),
    spreadAvg: Number(r.spread_avg),
  };
}

async function fetchLatestSnapshot(ch: ClickHouseClient, w: AcceptanceWindow): Promise<AcceptanceLatestSnapshot | null> {
  const rows = await ch.query<{
    ts: string;
    best_bid: number | string;
    best_ask: number | string;
    mid: number | string;
    spread: number | string;
    sequence_final_update_id: number | string;
    quality_flags_csv: string;
  }>(buildLatestSnapshotSql(w));
  const r = rows[0];
  if (!r) return null;
  return {
    ts: r.ts,
    bestBid: Number(r.best_bid),
    bestAsk: Number(r.best_ask),
    mid: Number(r.mid),
    spread: Number(r.spread),
    sequenceFinalUpdateId: Number(r.sequence_final_update_id),
    qualityFlagsCsv: r.quality_flags_csv ?? "",
  };
}

async function fetchHealth(ch: ClickHouseClient, w: AcceptanceWindow): Promise<AcceptanceHealth | null> {
  const rows = await ch.query<{
    sequence_gap_count: number | string;
    reconnect_count: number | string;
    max_db_queue_size: number | string;
    max_spool_queue_size: number | string;
    ok_samples: number | string;
    degraded_samples: number | string;
    down_samples: number | string;
    samples: number | string;
  }>(buildHealthAggregateSql(w));
  const r = rows[0];
  if (!r || Number(r.samples) === 0) return null;
  return {
    sequenceGapCount: Number(r.sequence_gap_count),
    reconnectCount: Number(r.reconnect_count),
    maxDbQueueSize: Number(r.max_db_queue_size),
    maxSpoolQueueSize: Number(r.max_spool_queue_size),
    okSamples: Number(r.ok_samples),
    degradedSamples: Number(r.degraded_samples),
    downSamples: Number(r.down_samples),
    samples: Number(r.samples),
  };
}

async function checkSpoolFiles(dir: string): Promise<boolean> {
  try {
    if (!fs.existsSync(dir)) return false;
    const items = fs.readdirSync(dir);
    return items.some((n) => n.endsWith(".jsonl"));
  } catch {
    return false;
  }
}

// ---------- default recorder factory ----------

function defaultStartRecorder(ch: ClickHouseClient, exchange: string) {
  return async (opts: { symbols: string[]; spoolDir: string }) => {
    const svc = new RecorderService({
      ch,
      exchange,
      symbols: opts.symbols,
      depthSpeed: "100ms",
      snapshotIntervalMs: 1000,
      spoolDir: opts.spoolDir,
    });
    await svc.start();
    return { stop: () => svc.stop() };
  };
}

function defaultLogger(level: "info" | "warn" | "error", msg: string, extra?: unknown): void {
  const ts = new Date().toISOString();
  const prefix = level.toUpperCase();
  if (extra instanceof Error) console.log(`[${ts}] ${prefix} ${msg} :: ${extra.message}`);
  else if (extra !== undefined) console.log(`[${ts}] ${prefix} ${msg} :: ${JSON.stringify(extra)}`);
  else console.log(`[${ts}] ${prefix} ${msg}`);
}

// ---------- CLI entry ----------

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const durationStr = getOptString(args, "duration-min");
  const durationMs = parseDurationMinutesArg(durationStr);
  const symbols = (getOptString(args, "symbols") ?? process.env.SYMBOLS ?? "BTCUSDT")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const skipBacktest = !!args.flags["skip-backtest"];

  const ch = clickhouseFromEnv();
  try {
    await runAcceptance({
      ch,
      durationMs,
      symbols,
      skipBacktest,
    });
  } catch (e) {
    if (e instanceof AcceptanceAbort) {
      console.error(`[acceptance] aborted: ${e.message}`);
      process.exit(2);
    }
    throw e;
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
