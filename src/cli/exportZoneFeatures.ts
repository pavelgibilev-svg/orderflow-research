// exportZoneFeatures — Tier-2 deliverable (Part D).
//
// Runs the EXISTING FeatureEngine + ZoneDetector + TargetChecker over a date
// range and writes ONE CSV row per zone that finished its lifecycle (ALL final
// statuses: RESOLVED_REACHED / RESOLVED_FAILED / EXPIRED / INVALIDATED /
// NO_TRIGGER). It is a pure OBSERVER: it snapshots their outputs, it does not
// change strategy logic.
//
// Architecture (confirmed in Step 0):
//   - ONE streaming pass of MarketReplayEngine. The observable CORE
//     (`ZoneFeatureCollector`) is loader-agnostic: it is fed FeatureRows + a
//     trades array, so it is fully testable on fixtures without a data loader.
//   - Hook 1 (ZSM observer, additive/non-behavioral): on CANDIDATE->CONFIRMED
//     it deep-copies the FeatureEngine outputs of THAT tick onto the zone
//     (immutable snapshot -> no look-ahead). On EXPIRED/INVALIDATED/NO_TRIGGER
//     it records the terminal observation.
//   - Hook 2 (post-TargetChecker): RESOLVED_REACHED/FAILED are set directly by
//     TargetChecker (targetChecker.ts:130/139), bypassing the state machine, so
//     those zones are collected AFTER `resolveZone` runs.
//   - Rows are materialised ONCE from the authoritative `detector.zones()` list
//     (each zone appears exactly once) -> the "exactly one row per zone" guard
//     is structural; reconciliation (rows == zones seen) is printed.
//
// Right-censoring: if trigger_ts + horizon exceeds the LAST OBSERVED TRADE ts
// (same price series TargetChecker scans), the horizon outcome is UNOBSERVED
// (NULL), not false.
//
// Determinism: deterministic zone_id (sequential by candidate_ts_ms, tie-break
// direction/zone_low/zone_high), fixed float precision, single NULL token ("") ->
// byte-identical CSV on re-run.

import * as fs from "node:fs";
import * as path from "node:path";

import { parseArgs, getString, getOptString } from "./args.js";
import { loadConfig } from "./loadConfig.js";
import { resolveInputFiles } from "../data/fileResolver.js";
import { replayFiles } from "../replay/marketReplayEngine.js";
import { OrderBook } from "../replay/orderBook.js";
import { FeatureEngine } from "../features/featureEngine.js";
import { evaluateBookQuality, newQualityState } from "../replay/dataQuality.js";
import { ZoneDetector } from "../strategy/zoneDetector.js";
import { TargetChecker, type TradePoint } from "../strategy/targetChecker.js";
import { computeBaseline } from "../strategy/probabilityBaseline.js";
import { setTransitionObserver } from "../strategy/zoneStateMachine.js";
import { parseHorizon, dayBoundsUtc } from "../data/time.js";
import type { FeatureRow, Zone, ZoneStatus, ZoneReason, StrategyConfig } from "../strategy/types.js";
import type { BookL2Event, TradeEvent, LiquidationEvent } from "../data/schema.js";

const DAY_MS = 86_400_000;

// ---------------------------------------------------------------------------
// Immutable feature snapshot taken at CANDIDATE->CONFIRMED (deep copy of scalars).
// ---------------------------------------------------------------------------

export interface FeatureSnapshot {
  // imbalance keys are JS-number stringifications of depthPctBuckets:
  // labels _0.10/_0.50/_1.0/_2.0 map to keys "0.1"/"0.5"/"1"/"2".
  imb_0_05: number; imb_0_10: number; imb_0_25: number; imb_0_50: number; imb_1_0: number; imb_2_0: number;
  buyAbsorptionScore: number; sellAbsorptionScore: number;
  bidRefillScore: number; askRefillScore: number;
  bidThinningScore: number; askThinningScore: number;
  voidUp2PctScore: number; voidDown2PctScore: number;
  rangeCompression: boolean;
  range1mPct: number; realizedVolPct: number;
  buyPressure_300s: number; sellPressure_300s: number; delta_300s: number;
}

/** Deep copy of the FeatureEngine outputs at this tick (primitives only -> a true
 *  immutable snapshot; later mutations of the engine cannot change it). */
function snapshotFeatures(row: FeatureRow, refWindowKey: string): FeatureSnapshot {
  const imb = row.imbalance;
  const w = row.trades.windows[refWindowKey];
  const num = (v: number | undefined): number => (typeof v === "number" ? v : NaN);
  return Object.freeze({
    imb_0_05: num(imb["0.05"]), imb_0_10: num(imb["0.1"]), imb_0_25: num(imb["0.25"]),
    imb_0_50: num(imb["0.5"]), imb_1_0: num(imb["1"]), imb_2_0: num(imb["2"]),
    buyAbsorptionScore: row.absorption.buyAbsorptionScore,
    sellAbsorptionScore: row.absorption.sellAbsorptionScore,
    bidRefillScore: row.liquidityEvents.bidRefillScore,
    askRefillScore: row.liquidityEvents.askRefillScore,
    bidThinningScore: row.liquidityEvents.bidThinningScore,
    askThinningScore: row.liquidityEvents.askThinningScore,
    voidUp2PctScore: row.liquidityVoid.voidUp2PctScore,
    voidDown2PctScore: row.liquidityVoid.voidDown2PctScore,
    rangeCompression: row.rangeCompression,
    range1mPct: row.volatility.range1mPct,
    realizedVolPct: row.volatility.realizedVolPct,
    buyPressure_300s: row.pressure.buyPressure,
    sellPressure_300s: row.pressure.sellPressure,
    delta_300s: w ? w.delta : NaN,
  });
}

// ---------------------------------------------------------------------------
// Per-horizon outcome (with right-censoring applied).
// ---------------------------------------------------------------------------

interface HorizonOutcome {
  reached: boolean | null; // null = unobserved (right-censored) OR not triggered
  timeToTargetMin: number | null;
  mfePct: number | null;
  maePct: number | null;
  maxDrawdownBeforeTargetPct: number | null;
}

const NULL_OUTCOME: HorizonOutcome = {
  reached: null, timeToTargetMin: null, mfePct: null, maePct: null, maxDrawdownBeforeTargetPct: null,
};

export interface ExportRow {
  zone_id: number;
  direction: "LONG" | "SHORT";
  candidate_ts_ms: number;
  confirmed_ts_ms: number | null;
  trigger_ts_ms: number | null;
  resolution_ts_ms: number | null;
  final_status: ZoneStatus;
  zone_low: number;
  zone_high: number;
  trigger_price: number | null;
  target_price: number | null;
  snap: FeatureSnapshot | null;
  outcomes: Record<string, HorizonOutcome>; // keyed by horizon
  baseline_24h_reach_prob: number | null;
}

export interface CollectStats {
  rows: number;
  byStatus: Record<string, number>;
  zonesSeen: number;
  reconciledOk: boolean;
  censoredHorizonCells: number;
}

// ---------------------------------------------------------------------------
// Loader-agnostic collector core.
// ---------------------------------------------------------------------------

export class ZoneFeatureCollector {
  readonly detector: ZoneDetector;
  private readonly cfg: StrategyConfig;
  private readonly horizons: string[];
  private readonly refWindowKey: string;
  private currentRow: FeatureRow | null = null;
  private readonly snapshots = new Map<Zone, FeatureSnapshot>();
  private readonly terminalSeen = new Map<Zone, "hook" | "postResolve" | "fallback">();
  private active = false;

  constructor(cfg: StrategyConfig, symbol: string, rangeLabel: string) {
    this.cfg = cfg;
    this.horizons = cfg.targetChecker.horizons.slice();
    this.refWindowKey = cfg.tradeWindowsSec[cfg.tradeWindowsSec.length - 1].toString(); // "300"
    this.detector = new ZoneDetector(cfg, symbol, rangeLabel);
  }

  /** Activate the ZSM observer for this collector (one active collector at a time). */
  attach(): void {
    this.active = true;
    setTransitionObserver(this.onTransition);
  }
  detach(): void {
    this.active = false;
    setTransitionObserver(null);
  }

  /** Feed one FeatureRow: snapshots are captured synchronously inside ingest(). */
  ingestRow(row: FeatureRow): void {
    if (!this.active) this.attach();
    this.currentRow = row;
    this.detector.ingest(row);
  }

  private onTransition = (zone: Zone, to: ZoneStatus, _reason: ZoneReason): void => {
    if (to === "CONFIRMED") {
      if (this.currentRow) this.snapshots.set(zone, snapshotFeatures(this.currentRow, this.refWindowKey));
    } else if (to === "EXPIRED" || to === "INVALIDATED" || to === "NO_TRIGGER") {
      if (!this.terminalSeen.has(zone)) this.terminalSeen.set(zone, "hook");
    }
    // TRIGGERED is not terminal here; RESOLVED_* never reach this observer.
  };

  /**
   * Finalise: close open zones, run TargetChecker, then materialise one row per
   * zone (all statuses). `lastEventTs` ends the detector; `trades` drive
   * TargetChecker AND define the right-censoring edge (last observed trade ts).
   */
  finalize(lastEventTs: number, trades: TradePoint[]): { rows: ExportRow[]; stats: CollectStats } {
    try {
      if (!this.active) this.attach();
      this.detector.finalize(lastEventTs);

      const tc = new TargetChecker(this.cfg, trades);
      const zones = this.detector.zones();
      for (const z of zones) tc.resolveZone(z);

      // Hook 2: RESOLVED_* bypass the SM, so record them here.
      for (const z of zones) {
        if (!this.terminalSeen.has(z)) {
          if (z.status === "RESOLVED_REACHED" || z.status === "RESOLVED_FAILED") {
            this.terminalSeen.set(z, "postResolve");
          } else {
            this.terminalSeen.set(z, "fallback"); // defensive: should not happen post-finalize
          }
        }
      }

      const lastTradeTs = trades.length > 0 ? trades[trades.length - 1].ts : Number.NEGATIVE_INFINITY;
      const baselineByDay = this.computeBaselines(trades);

      let censoredCells = 0;
      const rows: ExportRow[] = [];
      for (const z of zones) {
        const snap = this.snapshots.get(z) ?? null;
        const outcomes: Record<string, HorizonOutcome> = {};
        for (const h of this.horizons) {
          const o = this.horizonOutcome(z, h, lastTradeTs);
          if (z.triggerTs !== undefined && o.reached === null) censoredCells++;
          outcomes[h] = o;
        }
        const day = Math.floor(z.startTs / DAY_MS);
        const base = baselineByDay.get(day);
        const baseline =
          base && base.totalSamples > 0 ? (z.direction === "LONG" ? base.upRate : base.downRate) : null;
        rows.push({
          zone_id: -1, // assigned after the deterministic sort below
          direction: z.direction,
          candidate_ts_ms: z.startTs,
          confirmed_ts_ms: z.confirmedTs ?? null,
          trigger_ts_ms: z.triggerTs ?? null,
          resolution_ts_ms: z.resolvedTs ?? null,
          final_status: z.status,
          zone_low: z.zoneLow,
          zone_high: z.zoneHigh,
          trigger_price: z.triggerPrice ?? null,
          target_price: z.targetPrice ?? null,
          snap,
          outcomes,
          baseline_24h_reach_prob: baseline,
        });
      }

      // Deterministic order + ids: candidate_ts_ms, then direction, zone_low, zone_high.
      rows.sort(
        (a, b) =>
          a.candidate_ts_ms - b.candidate_ts_ms ||
          (a.direction < b.direction ? -1 : a.direction > b.direction ? 1 : 0) ||
          a.zone_low - b.zone_low ||
          a.zone_high - b.zone_high
      );
      rows.forEach((r, i) => (r.zone_id = i));

      const byStatus: Record<string, number> = {};
      for (const r of rows) byStatus[r.final_status] = (byStatus[r.final_status] ?? 0) + 1;
      const stats: CollectStats = {
        rows: rows.length,
        byStatus,
        zonesSeen: this.terminalSeen.size,
        reconciledOk: rows.length === zones.length && this.terminalSeen.size === zones.length,
        censoredHorizonCells: censoredCells,
      };
      return { rows, stats };
    } finally {
      this.detach();
    }
  }

  private horizonOutcome(zone: Zone, h: string, lastTradeTs: number): HorizonOutcome {
    if (zone.triggerTs === undefined) return NULL_OUTCOME; // never triggered -> no horizon outcome
    const m = zone.targets[h];
    if (m && m.outcome === "reached") {
      return {
        reached: true,
        timeToTargetMin: m.timeToTargetMin ?? null,
        mfePct: m.mfePct ?? null,
        maePct: m.maePct ?? null,
        maxDrawdownBeforeTargetPct: m.maxDrawdownBeforeTargetPct ?? null,
      };
    }
    const endTs = zone.triggerTs + parseHorizon(h);
    if (endTs > lastTradeTs) return NULL_OUTCOME; // right-censored: horizon not fully observed
    return {
      reached: false,
      timeToTargetMin: null,
      mfePct: m?.mfePct ?? null,
      maePct: m?.maePct ?? null,
      maxDrawdownBeforeTargetPct: m?.maxDrawdownBeforeTargetPct ?? null,
    };
  }

  /** Per-UTC-day 24h baseline. Zone-AGNOSTIC (probabilityBaseline ignores zones,
   *  see its docstring) -> NO outcome leakage; no leave-one-out needed. */
  private computeBaselines(trades: TradePoint[]) {
    const byDay = new Map<number, TradePoint[]>();
    for (const t of trades) {
      const d = Math.floor(t.ts / DAY_MS);
      let arr = byDay.get(d);
      if (!arr) byDay.set(d, (arr = []));
      arr.push(t);
    }
    const out = new Map<number, ReturnType<typeof computeBaseline>>();
    for (const [d, ts] of byDay) out.set(d, computeBaseline(ts, "24h", this.cfg.targetPct));
    return out;
  }
}

// ---------------------------------------------------------------------------
// CSV column contract + data dictionary (single source of truth).
// ---------------------------------------------------------------------------

type ColType = "int" | "ts_ms" | "price" | "score" | "pct" | "bool" | "enum";

interface ColumnDef {
  name: string;
  type: ColType;
  units: string;
  nullSemantics: string;
  get: (r: ExportRow) => string;
}

const NULL_TOKEN = "";
const FLOAT_DP = 6;

function fInt(v: number | null): string {
  return v === null || !Number.isFinite(v) ? NULL_TOKEN : String(v);
}
function fFloat(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return NULL_TOKEN;
  const n = Object.is(v, -0) ? 0 : v;
  return n.toFixed(FLOAT_DP);
}
function fBool(v: boolean | null): string {
  return v === null ? NULL_TOKEN : v ? "true" : "false";
}

function buildColumns(horizons: string[]): ColumnDef[] {
  const sf = (name: string, units: string, pick: (s: FeatureSnapshot) => number): ColumnDef => ({
    name,
    type: "score",
    units,
    nullSemantics: "empty = no snapshot (zone never CONFIRMED)",
    get: (r) => (r.snap ? fFloat(pick(r.snap)) : NULL_TOKEN),
  });
  const cols: ColumnDef[] = [
    { name: "zone_id", type: "int", units: "sequential", nullSemantics: "never null (exporter-generated, sorted by candidate_ts_ms/direction/zone_low/zone_high)", get: (r) => String(r.zone_id) },
    { name: "direction", type: "enum", units: "LONG|SHORT", nullSemantics: "never null", get: (r) => r.direction },
    { name: "candidate_ts_ms", type: "ts_ms", units: "ms (UTC)", nullSemantics: "never null", get: (r) => fInt(r.candidate_ts_ms) },
    { name: "confirmed_ts_ms", type: "ts_ms", units: "ms (UTC)", nullSemantics: "empty = never confirmed (EXPIRED/INVALIDATED before CONFIRMED)", get: (r) => fInt(r.confirmed_ts_ms) },
    { name: "trigger_ts_ms", type: "ts_ms", units: "ms (UTC)", nullSemantics: "empty = NO_TRIGGER", get: (r) => fInt(r.trigger_ts_ms) },
    { name: "resolution_ts_ms", type: "ts_ms", units: "ms (UTC)", nullSemantics: "empty if absent", get: (r) => fInt(r.resolution_ts_ms) },
    { name: "final_status", type: "enum", units: "RESOLVED_REACHED|RESOLVED_FAILED|EXPIRED|INVALIDATED|NO_TRIGGER", nullSemantics: "never null", get: (r) => r.final_status },
    { name: "zone_low", type: "price", units: "price", nullSemantics: "never null", get: (r) => fFloat(r.zone_low) },
    { name: "zone_high", type: "price", units: "price", nullSemantics: "never null", get: (r) => fFloat(r.zone_high) },
    { name: "trigger_price", type: "price", units: "price", nullSemantics: "empty = never triggered", get: (r) => fFloat(r.trigger_price) },
    { name: "target_price", type: "price", units: "price", nullSemantics: "empty = never triggered", get: (r) => fFloat(r.target_price) },
    sf("orderflowImbalance_0.05", "(bid-ask)/(bid+ask), src key '0.05'", (s) => s.imb_0_05),
    sf("orderflowImbalance_0.10", "(bid-ask)/(bid+ask), src key '0.1'", (s) => s.imb_0_10),
    sf("orderflowImbalance_0.25", "(bid-ask)/(bid+ask), src key '0.25'", (s) => s.imb_0_25),
    sf("orderflowImbalance_0.50", "(bid-ask)/(bid+ask), src key '0.5'", (s) => s.imb_0_50),
    sf("orderflowImbalance_1.0", "(bid-ask)/(bid+ask), src key '1'", (s) => s.imb_1_0),
    sf("orderflowImbalance_2.0", "(bid-ask)/(bid+ask), src key '2'", (s) => s.imb_2_0),
    sf("buyAbsorptionScore", "0..1", (s) => s.buyAbsorptionScore),
    sf("sellAbsorptionScore", "0..1", (s) => s.sellAbsorptionScore),
    sf("bidRefillScore", "0..1", (s) => s.bidRefillScore),
    sf("askRefillScore", "0..1", (s) => s.askRefillScore),
    sf("bidThinningScore", "0..1", (s) => s.bidThinningScore),
    sf("askThinningScore", "0..1", (s) => s.askThinningScore),
    sf("voidUp2PctScore", "0..1", (s) => s.voidUp2PctScore),
    sf("voidDown2PctScore", "0..1", (s) => s.voidDown2PctScore),
    {
      name: "rangeCompression", type: "bool", units: "true|false",
      nullSemantics: "empty = no snapshot (DISTINCT from false)",
      get: (r) => (r.snap ? fBool(r.snap.rangeCompression) : NULL_TOKEN),
    },
    sf("range1mPct", "percent", (s) => s.range1mPct),
    sf("realizedVolPct", "percent", (s) => s.realizedVolPct),
    sf("buyPressure_300s", "0..1 (300s window)", (s) => s.buyPressure_300s),
    sf("sellPressure_300s", "0..1 (300s window)", (s) => s.sellPressure_300s),
    sf("delta_300s", "buyVol-sellVol (300s window)", (s) => s.delta_300s),
  ];
  for (const h of horizons) {
    cols.push(
      { name: `reached_${h}`, type: "bool", units: "true|false", nullSemantics: "empty = not triggered OR right-censored (horizon beyond last observed trade)", get: (r) => fBool(r.outcomes[h]?.reached ?? null) },
      { name: `time_to_target_${h}_min`, type: "score", units: "minutes", nullSemantics: "empty = not reached / unobserved", get: (r) => fFloat(r.outcomes[h]?.timeToTargetMin ?? null) },
      { name: `MFE_${h}`, type: "pct", units: "percent (favourable, signed by direction)", nullSemantics: "empty = unobserved", get: (r) => fFloat(r.outcomes[h]?.mfePct ?? null) },
      { name: `MAE_${h}`, type: "pct", units: "percent (adverse)", nullSemantics: "empty = unobserved", get: (r) => fFloat(r.outcomes[h]?.maePct ?? null) },
      { name: `maxDrawdownBeforeTarget_${h}`, type: "pct", units: "percent", nullSemantics: "empty = unobserved", get: (r) => fFloat(r.outcomes[h]?.maxDrawdownBeforeTargetPct ?? null) }
    );
  }
  cols.push({
    name: "baseline_24h_reach_prob", type: "score", units: "probability 0..1 (per-direction: LONG=upRate, SHORT=downRate; per zone's UTC day; zone-agnostic, no leakage)",
    nullSemantics: "empty = no baseline samples for that day", get: (r) => fFloat(r.baseline_24h_reach_prob),
  });
  return cols;
}

/** Build the CSV text. Matches the repo CSV convention (comma-join, LF, quote
 *  escaping) from reports/csvWriter.ts; written synchronously for the byte-identical
 *  idempotency guarantee (a streaming writer cannot guarantee it for comparison). */
function renderCsv(cols: ColumnDef[], rows: ExportRow[]): string {
  const esc = (s: string): string =>
    s.includes(",") || s.includes('"') || s.includes("\n") ? '"' + s.replace(/"/g, '""') + '"' : s;
  const lines = [cols.map((c) => c.name).join(",")];
  for (const r of rows) lines.push(cols.map((c) => esc(c.get(r))).join(","));
  return lines.join("\n") + "\n";
}

export function buildSchemaMarkdown(cols: ColumnDef[]): string {
  const head =
    "# zone_features.csv — data dictionary\n\n" +
    "One row per zone that finished its lifecycle. NULL token = empty string. " +
    "Floats fixed at 6 dp. `bool` empty is DISTINCT from `false`.\n\n" +
    "| column | type | units / source | NULL semantics |\n|---|---|---|---|\n";
  const body = cols
    .map((c) => `| ${c.name} | ${c.type} | ${c.units} | ${c.nullSemantics} |`)
    .join("\n");
  return head + body + "\n";
}

/** Write CSV + sibling data-dictionary; return the exact bytes written (for tests). */
export function writeOutputs(csvPath: string, cols: ColumnDef[], rows: ExportRow[]): { csv: string; schemaPath: string } {
  const csv = renderCsv(cols, rows);
  fs.mkdirSync(path.dirname(csvPath), { recursive: true });
  fs.writeFileSync(csvPath, csv, "utf8");
  const schemaPath = csvPath.replace(/\.csv$/i, "") + ".schema.md";
  fs.writeFileSync(schemaPath, buildSchemaMarkdown(cols), "utf8");
  return { csv, schemaPath };
}

export function columnsForConfig(cfg: StrategyConfig): ColumnDef[] {
  return buildColumns(cfg.targetChecker.horizons);
}

// ---------------------------------------------------------------------------
// CLI (E2E over real files). PENDING data/loader unblock (Part C-1) -> not run yet.
// ---------------------------------------------------------------------------

interface ExportOpts {
  input: string;
  from: string;
  to: string;
  output: string;
  symbol: string;
  exchange: string;
  configPath?: string;
}

function enumerateDates(from: string, to: string): string[] {
  const start = dayBoundsUtc(from).startMs;
  const end = dayBoundsUtc(to).startMs;
  const out: string[] = [];
  for (let ms = start; ms <= end; ms += DAY_MS) out.push(new Date(ms).toISOString().slice(0, 10));
  return out;
}

async function runExport(opts: ExportOpts): Promise<CollectStats> {
  const cfg = loadConfig(opts.configPath);
  cfg.symbol = opts.symbol;
  cfg.exchange = opts.exchange;

  const dates = enumerateDates(opts.from, opts.to);
  const files = dates.flatMap((d) => resolveInputFiles(opts.input, opts.symbol, d).files)
    .filter((f) => f.dataType === "incremental_book_L2" || f.dataType === "trades" || f.dataType === "liquidations");
  if (files.length === 0) {
    throw new Error(`No input files matched for input=${opts.input} symbol=${opts.symbol} from=${opts.from} to=${opts.to}`);
  }

  const book = new OrderBook();
  const features = new FeatureEngine(cfg, book);
  const collector = new ZoneFeatureCollector(cfg, opts.symbol, `${opts.from}..${opts.to}`);
  collector.attach();
  const trades: TradePoint[] = [];
  const quality = newQualityState();

  const featureIntervalMs = cfg.featureIntervalSec * 1000;
  let nextFeatureTs = 0;
  let firstSeenTs = 0;
  let lastEventTs = 0;

  for await (const { ev } of replayFiles(files)) {
    if (firstSeenTs === 0) firstSeenTs = ev.ts;
    lastEventTs = ev.ts;
    quality.lastEventTs = ev.ts;

    if (nextFeatureTs === 0) nextFeatureTs = Math.ceil(ev.ts / featureIntervalMs) * featureIntervalMs;
    while (ev.ts >= nextFeatureTs) {
      const flags = evaluateBookQuality(book, nextFeatureTs, cfg, quality);
      if (nextFeatureTs >= firstSeenTs + cfg.replay.warmupSeconds * 1000) {
        collector.ingestRow(features.buildFeatureRow(nextFeatureTs, flags));
      }
      nextFeatureTs += featureIntervalMs;
    }

    switch (ev.source) {
      case "incremental_book_L2": {
        const e = ev as BookL2Event;
        book.apply({ ts: e.ts, isSnapshot: e.isSnapshot, side: e.side, price: e.price, amount: e.amount });
        features.onL2(e);
        break;
      }
      case "trades": {
        const e = ev as TradeEvent;
        trades.push({ ts: e.ts, price: e.price });
        features.onTrade(e);
        break;
      }
      case "liquidations":
        features.onLiquidation(ev as LiquidationEvent);
        break;
      default:
        break;
    }
  }

  const { rows, stats } = collector.finalize(lastEventTs, trades);
  const cols = columnsForConfig(cfg);
  const { schemaPath } = writeOutputs(opts.output, cols, rows);

  // Sanity print.
  const sizeBytes = fs.statSync(opts.output).size;
  console.log(`[export] ${opts.from}..${opts.to} symbol=${opts.symbol}`);
  console.log(`  rows=${stats.rows}  zones_seen=${stats.zonesSeen}  reconciled(rows==zones)=${stats.reconciledOk ? "OK" : "MISMATCH!"}`);
  console.log(`  by_status: ${Object.entries(stats.byStatus).map(([k, v]) => `${k}=${v}`).join("  ") || "(none)"}`);
  console.log(`  right_censored_horizon_cells=${stats.censoredHorizonCells}`);
  console.log(`  csv=${opts.output} (${sizeBytes} bytes)  schema=${schemaPath}`);
  if (!stats.reconciledOk) console.log("  WARN: row/zone reconciliation mismatch — investigate before using the CSV.");
  return stats;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const opts: ExportOpts = {
    input: getString(args, "input"),
    from: getString(args, "from"),
    to: getString(args, "to"),
    output: getString(args, "output", "reports/zone_features.csv"),
    symbol: getString(args, "symbol", "BTCUSDT"),
    exchange: getString(args, "exchange", "bybit"),
    configPath: getOptString(args, "config"),
  };
  await runExport(opts);
}

// Only run as a CLI when invoked directly.
const invokedDirectly = process.argv[1] && /exportZoneFeatures\.(ts|js)$/.test(process.argv[1]);
if (invokedDirectly) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
