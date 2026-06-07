// `npm run backtest:db` — run the existing strategy pipeline (FeatureEngine
// + ZoneDetector + TargetChecker) against events read from ClickHouse via
// the ClickHouseDataSource adapter. Mirrors `backtest:day` but the input is
// our live-recorded data instead of Tardis CSV.

import * as fs from "node:fs";
import * as path from "node:path";
import { parseArgs, getString, getNumber, getOptString } from "./args.js";
import { loadConfig } from "./loadConfig.js";
import { OrderBook } from "../replay/orderBook.js";
import { FeatureEngine } from "../features/featureEngine.js";
import { evaluateBookQuality, newQualityState } from "../replay/dataQuality.js";
import { ZoneDetector } from "../strategy/zoneDetector.js";
import { TargetChecker, type TradePoint } from "../strategy/targetChecker.js";
import { computeBaseline } from "../strategy/probabilityBaseline.js";
import { writeAllReports } from "../reports/reportWriter.js";
import { applyMoveClustering } from "../strategy/uniqueMoveClustering.js";
import type { BookL2Event, TradeEvent, LiquidationEvent } from "../data/schema.js";
import { clickhouseFromEnv } from "../live-recorder/clickhouseClient.js";
import { ClickHouseDataSource } from "../data/clickhouseDataSource.js";
import { parseHorizon } from "../data/time.js";

interface RunOpts {
  symbol: string;
  exchange: string;
  fromMs: number;
  toMs: number;
  targetPct: number;
  horizons: string[];
  configPath?: string;
  outDir?: string;
}

async function run(opts: RunOpts): Promise<void> {
  const cfg = loadConfig(opts.configPath);
  cfg.symbol = opts.symbol;
  cfg.exchange = opts.exchange;
  cfg.targetPct = opts.targetPct;
  cfg.targetChecker.horizons = opts.horizons;

  const ch = clickhouseFromEnv();
  const ok = await ch.ping();
  if (!ok) throw new Error(`ClickHouse not reachable at ${process.env.CLICKHOUSE_URL ?? "http://localhost:8123"}`);

  const source = new ClickHouseDataSource({ ch });

  console.log(
    `[backtest:db] symbol=${opts.symbol} exchange=${opts.exchange} from=${new Date(opts.fromMs).toISOString()} to=${new Date(opts.toMs).toISOString()} target=${opts.targetPct}% horizons=${opts.horizons.join(",")}`
  );
  const dateLabel = new Date(opts.fromMs).toISOString().slice(0, 10);
  const outDir = opts.outDir ?? path.join("reports", `db_${opts.symbol}_${dateLabel}`);

  const book = new OrderBook();
  const features = new FeatureEngine(cfg, book);
  const detector = new ZoneDetector(cfg, opts.symbol, dateLabel);
  const tradePoints: TradePoint[] = [];
  const quality = newQualityState();
  const warnings: string[] = [];

  let nextFeatureTs = 0;
  const featureIntervalMs = cfg.featureIntervalSec * 1000;
  let lastEventTs = 0;
  let firstSeenTs = 0;
  let l2Rows = 0;
  let tradeRows = 0;
  let otherRows = 0;
  const startedAt = Date.now();

  for await (const ev of source.events({
    symbol: opts.symbol,
    exchange: opts.exchange,
    fromMs: opts.fromMs,
    toMs: opts.toMs,
  })) {
    if (firstSeenTs === 0) firstSeenTs = ev.ts;
    lastEventTs = ev.ts;
    quality.lastEventTs = ev.ts;

    if (nextFeatureTs === 0) nextFeatureTs = Math.ceil(ev.ts / featureIntervalMs) * featureIntervalMs;
    while (ev.ts >= nextFeatureTs) {
      const flags = evaluateBookQuality(book, nextFeatureTs, cfg, quality);
      if (nextFeatureTs >= firstSeenTs + cfg.replay.warmupSeconds * 1000) {
        const row = features.buildFeatureRow(nextFeatureTs, flags);
        detector.ingest(row);
      }
      nextFeatureTs += featureIntervalMs;
    }

    switch (ev.source) {
      case "incremental_book_L2": {
        const e = ev as BookL2Event;
        book.apply({ ts: e.ts, isSnapshot: e.isSnapshot, side: e.side, price: e.price, amount: e.amount });
        features.onL2(e);
        l2Rows++;
        break;
      }
      case "trades": {
        const e = ev as TradeEvent;
        features.onTrade(e);
        tradePoints.push({ ts: e.ts, price: e.price });
        tradeRows++;
        break;
      }
      case "liquidations":
        features.onLiquidation(ev as LiquidationEvent);
        otherRows++;
        break;
      default:
        otherRows++;
    }
    if ((l2Rows + tradeRows + otherRows) % cfg.replay.logEveryRows === 0) {
      console.log(`  replay: l2=${l2Rows} trades=${tradeRows} other=${otherRows} elapsed=${((Date.now() - startedAt) / 1000).toFixed(1)}s`);
    }
  }

  const dayEnd = Math.min(opts.toMs, lastEventTs);
  while (nextFeatureTs > 0 && nextFeatureTs <= dayEnd) {
    const flags = evaluateBookQuality(book, nextFeatureTs, cfg, quality);
    const row = features.buildFeatureRow(nextFeatureTs, flags);
    detector.ingest(row);
    nextFeatureTs += featureIntervalMs;
  }

  detector.finalize(lastEventTs);
  const zones = detector.zones();
  const checker = new TargetChecker(cfg, tradePoints);
  for (const z of zones) checker.resolveZone(z);

  const triggeredCount = zones.filter((z) => z.triggerTs !== undefined).length;
  const moveResult = applyMoveClustering(zones, cfg.moveClustering, triggeredCount);

  const baselines = opts.horizons.map((h) => computeBaseline(tradePoints, h, opts.targetPct));

  if (tradePoints.length === 0) warnings.push("No trades in range — target checking is meaningless.");
  if (l2Rows === 0) warnings.push("No depth events in range — order book stayed empty.");

  const written = writeAllReports({
    outDir,
    zones,
    config: cfg,
    reportInputs: {
      symbol: opts.symbol,
      date: dateLabel,
      exchange: opts.exchange,
      zones,
      baselines,
      qualityNotes: [],
      durationMs: Date.now() - startedAt,
      rowsProcessed: { l2: l2Rows, trades: tradeRows, other: otherRows },
      warnings,
      moveClustering: {
        enabled: !!cfg.moveClustering?.enabled,
        moveClusterGapMinutes: cfg.moveClustering?.moveClusterGapMinutes ?? 0,
        reachedZonesRaw: moveResult.reachedZonesRaw,
        uniqueReachedMoves: moveResult.uniqueReachedMoves,
        duplicateMoveCredits: moveResult.duplicateMoveCredits,
        rawTriggeredHitRate: moveResult.rawTriggeredHitRate,
        uniqueMoveAdjustedHitRate: moveResult.uniqueMoveAdjustedHitRate,
        clusters: moveResult.clusters,
      },
    },
  });

  console.log(
    `\n[backtest:db] zones=${zones.length} triggered=${triggeredCount} reached_raw=${moveResult.reachedZonesRaw} unique_moves=${moveResult.uniqueReachedMoves} hit_rate_adj=${(moveResult.uniqueMoveAdjustedHitRate * 100).toFixed(2)}%`
  );
  console.log("Wrote:");
  for (const w of written) console.log(`  - ${w}`);
}

function parseIso(s: string): number {
  const ms = Date.parse(s);
  if (!Number.isFinite(ms)) throw new Error(`Bad ISO timestamp: ${s}`);
  return ms;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (args.flags["help"]) {
    console.log("Usage: backtest:db -- --symbol <SYM> --from <ISO> --to <ISO> [--exchange ...] [--target-pct N] [--horizons 4h,8h,24h]");
    return;
  }
  const symbol = getString(args, "symbol");
  const exchange = getString(args, "exchange", "binance-futures");
  const fromMs = parseIso(getString(args, "from"));
  const toMs = parseIso(getString(args, "to"));
  const targetPct = getNumber(args, "target-pct", 2);
  const horizons = getString(args, "horizons", "4h,8h,24h").split(",").map((s) => s.trim()).filter(Boolean);
  // sanity-check horizons parse
  for (const h of horizons) parseHorizon(h);
  const outDir = getOptString(args, "out");
  const configPath = getOptString(args, "config");
  await run({ symbol, exchange, fromMs, toMs, targetPct, horizons, configPath, outDir });
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

export { run as runBacktestDb };
