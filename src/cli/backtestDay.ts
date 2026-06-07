// `npm run backtest:day -- --input ./data/sample --exchange binance-futures \
//     --symbol BTCUSDT --date 2020-02-01 --target-pct 2 --horizons 4h,8h,24h`
//
// Full pipeline: file resolve -> streaming replay -> features -> zone
// detection -> target checking -> reports.
//
// We feed the replay engine with all matched files merged on `ts`. On each
// L2 event we update the order book + feature engine. On each trade we both
// record it for trade aggregation AND push it onto a flat array used by the
// TargetChecker after replay. Other event sources (derivative_ticker,
// liquidations) are forwarded to the FeatureEngine where appropriate.

import * as fs from "node:fs";
import * as path from "node:path";
import { parseArgs, getString, getNumber, getOptString } from "./args.js";
import { loadConfig } from "./loadConfig.js";
import { resolveInputFiles } from "../data/fileResolver.js";
import { replayFiles } from "../replay/marketReplayEngine.js";
import { OrderBook } from "../replay/orderBook.js";
import { FeatureEngine } from "../features/featureEngine.js";
import { evaluateBookQuality, newQualityState } from "../replay/dataQuality.js";
import { ZoneDetector } from "../strategy/zoneDetector.js";
import { TargetChecker, type TradePoint } from "../strategy/targetChecker.js";
import { computeBaseline } from "../strategy/probabilityBaseline.js";
import { writeAllReports } from "../reports/reportWriter.js";
import { dayBoundsUtc } from "../data/time.js";
import type {
  BookL2Event,
  TradeEvent,
  LiquidationEvent,
  AnyEvent,
} from "../data/schema.js";
import { applyMoveClustering, type UniqueMoveCluster } from "../strategy/uniqueMoveClustering.js";

interface RunOpts {
  input: string;
  exchange: string;
  symbol: string;
  date: string;
  targetPct: number;
  horizons: string[];
  configPath?: string;
  outDir?: string;
  /**
   * Optional cap on the heavy L2 replay portion (in hours from day start).
   * After this limit we stop applying L2 events to the order book and stop
   * generating new feature ticks, but we DO continue draining trade events
   * so the TargetChecker has the full 24h of trade prices to evaluate
   * triggered zones against the 4h/8h/24h horizons. This is purely a
   * compute-budget knob; it does not change strategy thresholds.
   */
  maxL2Hours?: number;
}

export interface BacktestDayResult {
  symbol: string;
  date: string;
  exchange: string;
  outDir: string;
  rowsProcessed: { l2: number; trades: number; other: number };
  zonesTotal: number;
  zonesCandidates: number;
  zonesConfirmed: number;
  zonesTriggered: number;
  zonesReachedByHorizon: { [horizon: string]: number };
  zonesFailedOrNoTriggerOrInvalidated: number;
  baselines: Array<{ horizon: string; upRate: number; downRate: number; samples: number }>;
  triggeredHitRate: number;
  qualityFlagsTickCount: number;
  warnings: string[];
  durationMs: number;
  /** Deduplication accounting fields. */
  deduplicationEnabled: boolean;
  cooldownMinutesAfterResolve: number;
  duplicateSuppressionCount: number;
  suppressedDuplicateZones: Array<{
    ts: number;
    direction: "LONG" | "SHORT";
    proposedLow: number;
    proposedHigh: number;
    suppressedByZoneId: string;
    reason: string;
    overlapPct: number;
  }>;
  /** Unique-move clustering accounting fields. */
  moveClusteringEnabled: boolean;
  reachedZonesRaw: number;
  uniqueReachedMoves: number;
  duplicateMoveCredits: number;
  rawTriggeredHitRate: number;
  uniqueMoveAdjustedHitRate: number;
  uniqueMoveClusters: UniqueMoveCluster[];
}

async function run(opts: RunOpts): Promise<BacktestDayResult> {
  const cfg = loadConfig(opts.configPath);
  cfg.symbol = opts.symbol;
  cfg.exchange = opts.exchange;
  cfg.targetPct = opts.targetPct;
  cfg.targetChecker.horizons = opts.horizons;

  console.log(`[backtest] symbol=${opts.symbol} date=${opts.date} target=${opts.targetPct}% horizons=${opts.horizons.join(",")}`);

  const { files: allFiles, missing } = resolveInputFiles(opts.input, opts.symbol, opts.date);
  if (allFiles.length === 0) {
    throw new Error(`No files matched for input=${opts.input} symbol=${opts.symbol} date=${opts.date}`);
  }
  if (missing.length > 0) {
    console.warn(`WARN: missing required data types: ${missing.join(",")}`);
  }
  // The strategy only consumes incremental_book_L2, trades and (optionally)
  // liquidations. derivative_ticker / book_ticker are parsed-and-dropped, so
  // we exclude them from the replay merge to save ~30% of total I/O. The
  // validation report still records whether they were present on disk.
  const STRATEGY_TYPES = new Set([
    "incremental_book_L2",
    "trades",
    "liquidations",
  ] as const);
  const files = allFiles.filter((f) => STRATEGY_TYPES.has(f.dataType as typeof STRATEGY_TYPES extends Set<infer T> ? T : never));
  for (const f of files) {
    console.log(`  - ${f.dataType.padEnd(22)} ${f.path}`);
  }
  if (files.length < allFiles.length) {
    const skipped = allFiles
      .filter((f) => !files.includes(f))
      .map((f) => f.dataType)
      .join(",");
    console.log(`  (skipping non-strategy types from replay: ${skipped})`);
  }

  const dayBounds = dayBoundsUtc(opts.date);
  const l2CutoffMs =
    opts.maxL2Hours !== undefined
      ? dayBounds.startMs + Math.max(0, opts.maxL2Hours) * 3_600_000
      : Number.POSITIVE_INFINITY;
  if (Number.isFinite(l2CutoffMs)) {
    console.log(
      `  [budget] L2 replay capped at ${opts.maxL2Hours}h from day start (cutoff=${new Date(
        l2CutoffMs
      ).toISOString()}). Trades continue full 24h for target checking.`
    );
  }

  const book = new OrderBook();
  const features = new FeatureEngine(cfg, book);
  const detector = new ZoneDetector(cfg, opts.symbol, opts.date);
  const tradePoints: TradePoint[] = [];
  const quality = newQualityState();
  const warnings: string[] = [];

  let nextFeatureTs = 0;
  const featureIntervalMs = cfg.featureIntervalSec * 1000;
  let lastEventTs = 0;
  let l2Rows = 0,
    tradeRows = 0,
    otherRows = 0;
  let l2RowsAfterCutoff = 0;
  const startedAt = Date.now();
  let firstSeenTs = 0;

  // Per-data-type ts ceiling: stop reading the L2 (and liquidations) files
  // once they cross the cutoff. The trades file is read fully so the
  // TargetChecker has the full 24h of price history.
  const endTsByDataType: Record<string, number> = {};
  if (Number.isFinite(l2CutoffMs)) {
    endTsByDataType["incremental_book_L2"] = l2CutoffMs;
    endTsByDataType["liquidations"] = l2CutoffMs;
    // trades intentionally NOT capped.
  }

  for await (const { ev } of replayFiles(files, { endTsByDataType })) {
    if (firstSeenTs === 0) firstSeenTs = ev.ts;
    lastEventTs = ev.ts;
    quality.lastEventTs = ev.ts;

    // Drive feature ticks based on event time, but only up to the L2 cutoff.
    // After the cutoff we stop generating new feature rows: the strategy
    // produces zones using order-book state up to the cutoff, then the
    // TargetChecker scans the rest of the day's trades.
    if (ev.ts <= l2CutoffMs) {
      if (nextFeatureTs === 0) {
        nextFeatureTs = Math.ceil(ev.ts / featureIntervalMs) * featureIntervalMs;
      }
      while (ev.ts >= nextFeatureTs && nextFeatureTs <= l2CutoffMs) {
        const flags = evaluateBookQuality(book, nextFeatureTs, cfg, quality);
        if (nextFeatureTs >= firstSeenTs + cfg.replay.warmupSeconds * 1000) {
          const row = features.buildFeatureRow(nextFeatureTs, flags);
          detector.ingest(row);
        }
        nextFeatureTs += featureIntervalMs;
      }
    }

    switch (ev.source) {
      case "incremental_book_L2": {
        const e = ev as BookL2Event;
        if (e.ts <= l2CutoffMs) {
          book.apply({
            ts: e.ts,
            isSnapshot: e.isSnapshot,
            side: e.side,
            price: e.price,
            amount: e.amount,
          });
          features.onL2(e);
          l2Rows++;
        } else {
          l2RowsAfterCutoff++;
        }
        break;
      }
      case "trades": {
        const e = ev as TradeEvent;
        // Always push trade prices for TargetChecker, regardless of cutoff.
        tradePoints.push({ ts: e.ts, price: e.price });
        if (e.ts <= l2CutoffMs) features.onTrade(e);
        tradeRows++;
        break;
      }
      case "liquidations": {
        if (ev.ts <= l2CutoffMs) features.onLiquidation(ev as LiquidationEvent);
        otherRows++;
        break;
      }
      default:
        otherRows++;
    }

    if ((l2Rows + tradeRows + otherRows) % cfg.replay.logEveryRows === 0) {
      const elapsed = (Date.now() - startedAt) / 1000;
      console.log(`  replay: l2=${l2Rows} trades=${tradeRows} other=${otherRows} elapsed=${elapsed.toFixed(1)}s`);
    }
  }

  // Final feature ticks after last event (until end of day).
  const dayEnd = Math.min(dayBounds.endMs, lastEventTs);
  while (nextFeatureTs > 0 && nextFeatureTs <= dayEnd) {
    const flags = evaluateBookQuality(book, nextFeatureTs, cfg, quality);
    const row = features.buildFeatureRow(nextFeatureTs, flags);
    detector.ingest(row);
    nextFeatureTs += featureIntervalMs;
  }

  detector.finalize(lastEventTs);
  const zones = detector.zones();

  // Resolve targets using the trades captured during replay.
  const checker = new TargetChecker(cfg, tradePoints);
  for (const z of zones) checker.resolveZone(z);

  // Unique-move clustering — pure post-processing accounting fix.
  // Zones get tagged with uniqueMoveId / moveClusterSize / isPrimaryMoveZone
  // / duplicateMoveCredit. Headline hit-rate becomes
  // uniqueReachedMoves / triggered (the honest number) alongside the raw one.
  const triggeredCount = zones.filter((z) => z.triggerTs !== undefined).length;
  const moveClusteringResult = applyMoveClustering(zones, cfg.moveClustering, triggeredCount);

  // Baselines per horizon.
  const baselines = opts.horizons.map((h) => computeBaseline(tradePoints, h, opts.targetPct));

  if (tradePoints.length === 0) warnings.push("No trades parsed — target checking is meaningless.");
  if (l2Rows === 0) warnings.push("No L2 events parsed — order book reconstruction was empty.");
  if (quality.invalidIntervals > 0) warnings.push(`Encountered ${quality.invalidIntervals} feature ticks with quality flags.`);
  if (Number.isFinite(l2CutoffMs)) {
    warnings.push(
      `L2 replay was capped at ${opts.maxL2Hours}h (compute-budget knob, not a strategy threshold). ${l2RowsAfterCutoff} L2 events were dropped after the cutoff. Trades continued full day.`
    );
  }

  const outDir = opts.outDir ?? path.join("reports", `${opts.symbol}_${opts.date}`);
  const detectorSuppressions = detector.suppressions();
  const suppressionsByReason: { [reason: string]: number } = {};
  for (const s of detectorSuppressions) {
    suppressionsByReason[s.reason] = (suppressionsByReason[s.reason] ?? 0) + 1;
  }
  const written = writeAllReports({
    outDir,
    zones,
    config: cfg,
    reportInputs: {
      symbol: opts.symbol,
      date: opts.date,
      exchange: opts.exchange,
      zones,
      baselines,
      qualityNotes: missing.length ? [`Missing data types: ${missing.join(", ")}`] : [],
      durationMs: Date.now() - startedAt,
      rowsProcessed: { l2: l2Rows, trades: tradeRows, other: otherRows },
      warnings,
      dedup: {
        enabled: !!cfg.deduplication?.enabled,
        cooldownMinutesAfterResolve: cfg.deduplication?.cooldownMinutesAfterResolve ?? 0,
        duplicateSuppressionCount: detectorSuppressions.length,
        suppressionsByReason,
      },
      moveClustering: {
        enabled: !!cfg.moveClustering?.enabled,
        moveClusterGapMinutes: cfg.moveClustering?.moveClusterGapMinutes ?? 0,
        reachedZonesRaw: moveClusteringResult.reachedZonesRaw,
        uniqueReachedMoves: moveClusteringResult.uniqueReachedMoves,
        duplicateMoveCredits: moveClusteringResult.duplicateMoveCredits,
        rawTriggeredHitRate: moveClusteringResult.rawTriggeredHitRate,
        uniqueMoveAdjustedHitRate: moveClusteringResult.uniqueMoveAdjustedHitRate,
        clusters: moveClusteringResult.clusters,
      },
    },
  });

  console.log(`\n[backtest] zones=${zones.length} triggered=${zones.filter((z) => z.triggerTs !== undefined).length} reached=${zones.filter((z) => z.status === "RESOLVED_REACHED").length}`);
  console.log("Wrote:");
  for (const w of written) console.log(`  - ${w}`);

  // Build summary metrics for orchestrators (sample:2026, etc).
  const triggeredZones = zones.filter((z) => z.triggerTs !== undefined);
  const reachedByHorizon: { [horizon: string]: number } = {};
  for (const h of opts.horizons) {
    reachedByHorizon[h] = zones.filter((z) => z.targets[h]?.outcome === "reached").length;
  }
  const failedOrNoTriggerOrInvalidated = zones.filter(
    (z) =>
      z.status === "RESOLVED_FAILED" ||
      z.status === "NO_TRIGGER" ||
      z.status === "INVALIDATED" ||
      z.status === "EXPIRED"
  ).length;
  const triggeredHitRate =
    triggeredZones.length > 0 ? zones.filter((z) => z.status === "RESOLVED_REACHED").length / triggeredZones.length : 0;

  const suppressions = detector.suppressions();
  return {
    symbol: opts.symbol,
    date: opts.date,
    exchange: opts.exchange,
    outDir,
    rowsProcessed: { l2: l2Rows, trades: tradeRows, other: otherRows },
    zonesTotal: zones.length,
    zonesCandidates: zones.length, // every zone started life as a candidate
    zonesConfirmed: zones.filter((z) => z.confirmedTs !== undefined).length,
    zonesTriggered: triggeredZones.length,
    zonesReachedByHorizon: reachedByHorizon,
    zonesFailedOrNoTriggerOrInvalidated: failedOrNoTriggerOrInvalidated,
    baselines: baselines.map((b) => ({
      horizon: b.horizon,
      upRate: b.upRate,
      downRate: b.downRate,
      samples: b.totalSamples,
    })),
    triggeredHitRate,
    qualityFlagsTickCount: quality.invalidIntervals,
    warnings,
    durationMs: Date.now() - startedAt,
    deduplicationEnabled: !!cfg.deduplication?.enabled,
    cooldownMinutesAfterResolve: cfg.deduplication?.cooldownMinutesAfterResolve ?? 0,
    duplicateSuppressionCount: suppressions.length,
    suppressedDuplicateZones: suppressions.map((s) => ({
      ts: s.ts,
      direction: s.direction,
      proposedLow: s.proposedLow,
      proposedHigh: s.proposedHigh,
      suppressedByZoneId: s.suppressedByZoneId,
      reason: s.reason,
      overlapPct: s.overlapPct,
    })),
    moveClusteringEnabled: !!cfg.moveClustering?.enabled,
    reachedZonesRaw: moveClusteringResult.reachedZonesRaw,
    uniqueReachedMoves: moveClusteringResult.uniqueReachedMoves,
    duplicateMoveCredits: moveClusteringResult.duplicateMoveCredits,
    rawTriggeredHitRate: moveClusteringResult.rawTriggeredHitRate,
    uniqueMoveAdjustedHitRate: moveClusteringResult.uniqueMoveAdjustedHitRate,
    uniqueMoveClusters: moveClusteringResult.clusters,
  };
}

function parseHorizonsList(s: string): string[] {
  return s
    .split(",")
    .map((x) => x.trim())
    .filter((x) => x.length > 0);
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (args.flags["help"]) {
    console.log("Usage: backtestDay --input <path> --exchange <ex> --symbol <SYM> --date YYYY-MM-DD --target-pct N --horizons 4h,8h,24h");
    return;
  }

  const input = getString(args, "input");
  const exchange = getString(args, "exchange", "binance-futures");
  const symbol = getString(args, "symbol");
  const targetPct = getNumber(args, "target-pct", 2);
  const horizons = parseHorizonsList(getString(args, "horizons", "4h,8h,24h"));
  const configPath = getOptString(args, "config");
  const outDir = getOptString(args, "out");
  const maxL2HoursStr = getOptString(args, "max-l2-hours");
  const maxL2Hours = maxL2HoursStr !== undefined ? Number(maxL2HoursStr) : undefined;

  // Either --date or --from / --to (range).
  if (typeof args.flags["range"] === "boolean" || args.flags["from"]) {
    const from = getString(args, "from");
    const to = getString(args, "to");
    const dates = enumerateDates(from, to);
    for (const d of dates) {
      await run({ input, exchange, symbol, date: d, targetPct, horizons, configPath, outDir, maxL2Hours });
    }
    return;
  }

  const date = getString(args, "date");
  await run({ input, exchange, symbol, date, targetPct, horizons, configPath, outDir, maxL2Hours });
}

function enumerateDates(from: string, to: string): string[] {
  const a = Date.parse(from + "T00:00:00Z");
  const b = Date.parse(to + "T00:00:00Z");
  const out: string[] = [];
  for (let t = a; t <= b; t += 86_400_000) {
    out.push(new Date(t).toISOString().slice(0, 10));
  }
  return out;
}

// Entry point guard: only run main() when this file is invoked directly,
// not when imported as a library by the orchestrator.
import { pathToFileURL } from "node:url";
const __isMain =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href;
if (__isMain) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}

export { run as runBacktestDay };
