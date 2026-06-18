import { describe, it, expect } from "vitest";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import { loadConfig } from "../src/cli/loadConfig.js";
import { ZoneDetector } from "../src/strategy/zoneDetector.js";
import { setTransitionObserver } from "../src/strategy/zoneStateMachine.js";
import type { TradePoint } from "../src/strategy/targetChecker.js";
import type { FeatureRow, TradeAggWindow } from "../src/strategy/types.js";
import {
  ZoneFeatureCollector,
  columnsForConfig,
  writeOutputs,
  buildSchemaMarkdown,
  type ExportRow,
} from "../src/cli/exportZoneFeatures.js";

const T0 = 1_700_000_000_000; // round ms
const MIN = 60_000;
const HOUR = 3_600_000;

function win(buy = 50, sell = 50): TradeAggWindow {
  return { windowSec: 300, buyVolume: buy, sellVolume: sell, delta: buy - sell, trades: 10, vwap: 100, highPrice: 100, lowPrice: 100 };
}

interface RowOpts {
  mid?: number; buyPressure?: number; sellPressure?: number; buyAbs?: number; sellAbs?: number;
  bidRefill?: number; askThin?: number; void?: number; downMove?: number; rangeCompression?: boolean;
  w300?: TradeAggWindow;
}

/** A complete FeatureRow. Defaults pass the LONG candidate gate but FAIL the SHORT gate
 *  (sellAbs=0.3), so a single LONG zone forms. */
function makeRow(ts: number, o: RowOpts = {}): FeatureRow {
  const mid = o.mid ?? 100;
  return {
    ts,
    book: { ts, bestBid: mid - 0.01, bestAsk: mid + 0.01, mid, spread: 0.02, spreadPct: 0.0002, totalBid: 1000, totalAsk: 1000, depthBuckets: {}, bidLevels: 50, askLevels: 50, qualityFlags: [] },
    trades: { ts, windows: { "5": win(), "15": win(), "60": win(), "300": o.w300 ?? win() } },
    imbalance: { "0.05": 0.2, "0.1": 0.21, "0.25": 0.22, "0.5": 0.23, "1": 0.24, "2": 0.25 },
    pressure: { buyPressure: o.buyPressure ?? 0.6, sellPressure: o.sellPressure ?? 0.6, aggressiveFlowRatio: 0.6 },
    absorption: { buyAbsorptionScore: o.buyAbs ?? 0.7, sellAbsorptionScore: o.sellAbs ?? 0.3, priceProgressDownPct: o.downMove ?? 0.05, priceProgressUpPct: 0.05 },
    liquidityVoid: { voidUp2PctScore: o.void ?? 0.6, voidDown2PctScore: 0.6, askVolUpTo2Pct: 1, bidVolDownTo2Pct: 1 },
    liquidityEvents: { bidAddRate: 0, bidRemoveRate: 0, askAddRate: 0, askRemoveRate: 0, bidRefillScore: o.bidRefill ?? 0.6, askRefillScore: 0.6, bidThinningScore: 0.6, askThinningScore: o.askThin ?? 0.6 },
    volatility: { realizedVolPct: 0.1, range1mPct: 0.05 },
    rangeCompression: o.rangeCompression ?? true,
    qualityFlags: [],
  } as FeatureRow;
}

/** Rows that confirm a LONG zone at T0+180k. `confirmBuyAbs` sets the confirm-tick value. */
function confirmRows(confirmBuyAbs = 0.7): FeatureRow[] {
  return [
    makeRow(T0 + 0 * MIN, { w300: win(50, 50) }),       // candidate (baselineFlow=100)
    makeRow(T0 + 1 * MIN),
    makeRow(T0 + 2 * MIN),
    makeRow(T0 + 3 * MIN, { buyAbs: confirmBuyAbs }),    // CONFIRM here
  ];
}

/** Trigger row at T0+4min: break up + flow burst; rangeCompression=false so no new candidate. */
function triggerRow(mid = 100.5, buyAbs = 0.9): FeatureRow {
  return makeRow(T0 + 4 * MIN, { mid, rangeCompression: false, buyAbs, w300: win(200, 0) });
}

function tradesRange(startTs: number, endTs: number, stepMs: number, priceAt: (ts: number) => number): TradePoint[] {
  const out: TradePoint[] = [];
  for (let ts = startTs; ts <= endTs; ts += stepMs) out.push({ ts, price: priceAt(ts) });
  return out;
}

function runScenario(rows: FeatureRow[], trades: TradePoint[]) {
  const cfg = loadConfig();
  const c = new ZoneFeatureCollector(cfg, "BTCUSDT", "fixture");
  for (const r of rows) c.ingestRow(r);
  const { rows: out, stats } = c.finalize(rows[rows.length - 1].ts, trades);
  return { out, stats, cfg };
}

// --------------------------------------------------------------------------- confirm + reach

function reachedScenario() {
  const triggerTs = T0 + 4 * MIN;
  const rows = [...confirmRows(0.77), triggerRow(100.5, 0.99)];
  // ref = triggerPrice = 100.5; target +2% = 102.51. Reach at +1h. Full 24h observed.
  const trades = tradesRange(T0, triggerTs + 25 * HOUR, 5 * MIN, (ts) =>
    ts >= triggerTs + 1 * HOUR && ts <= triggerTs + 1 * HOUR + 6 * MIN ? 103 : 100.5
  );
  return { rows, trades, triggerTs };
}

describe("ZoneFeatureCollector — lifecycle to CSV", () => {
  it("confirms, triggers, and emits a RESOLVED_REACHED row with snapshot + outcomes", () => {
    const { rows, trades } = reachedScenario();
    const { out, stats } = runScenario(rows, trades);
    expect(out.length).toBe(1);
    const r = out[0];
    expect(r.final_status).toBe("RESOLVED_REACHED");
    expect(r.direction).toBe("LONG");
    expect(r.confirmed_ts_ms).toBe(T0 + 3 * MIN);
    expect(r.trigger_ts_ms).toBe(T0 + 4 * MIN);
    expect(r.snap).not.toBeNull();
    expect(r.outcomes["4h"].reached).toBe(true);
    expect(stats.reconciledOk).toBe(true);
    expect(stats.byStatus["RESOLVED_REACHED"]).toBe(1);
  });

  it("capture-at-confirm: post-confirm feature changes do NOT alter the snapshot (no look-ahead)", () => {
    const { rows, trades } = reachedScenario();
    // confirm-tick buyAbs = 0.77; trigger-tick buyAbs = 0.99. Snapshot must be 0.77.
    const { out } = runScenario(rows, trades);
    expect(out[0].snap!.buyAbsorptionScore).toBeCloseTo(0.77, 10);
    expect(out[0].snap!.buyAbsorptionScore).not.toBeCloseTo(0.99, 5);
  });

  it("EXPIRED before confirm -> NULL features + NULL confirmed/trigger ts, row still emitted", () => {
    const rows = [makeRow(T0), makeRow(T0 + 61 * MIN, { rangeCompression: false, bidRefill: 0.1 })];
    const { out } = runScenario(rows, []);
    expect(out.length).toBe(1);
    expect(out[0].final_status).toBe("EXPIRED");
    expect(out[0].snap).toBeNull(); // no confirm snapshot
    expect(out[0].confirmed_ts_ms).toBeNull();
    expect(out[0].trigger_ts_ms).toBeNull();
  });

  it("INVALIDATED (post-confirm in this detector) emits a row WITH snapshot, no trigger", () => {
    // After confirm, an adverse drop invalidates (LONG: mid < zoneLow*0.995).
    const rows = [...confirmRows(0.7), makeRow(T0 + 4 * MIN, { mid: 99, rangeCompression: false })];
    const { out } = runScenario(rows, []);
    expect(out.length).toBe(1);
    expect(out[0].final_status).toBe("INVALIDATED");
    expect(out[0].snap).not.toBeNull();
    expect(out[0].trigger_ts_ms).toBeNull();
    for (const h of ["4h", "8h", "24h"]) expect(out[0].outcomes[h].reached).toBeNull();
  });

  it("NO_TRIGGER (confirmed, never triggers, finalize) emits a row with snapshot", () => {
    // Confirm, then benign rows that neither trigger (no break/flow) nor invalidate.
    const rows = [...confirmRows(0.7), makeRow(T0 + 4 * MIN, { rangeCompression: false }), makeRow(T0 + 5 * MIN, { rangeCompression: false })];
    const { out } = runScenario(rows, []);
    expect(out.length).toBe(1);
    expect(out[0].final_status).toBe("NO_TRIGGER");
    expect(out[0].snap).not.toBeNull();
    expect(out[0].trigger_ts_ms).toBeNull();
  });
});

describe("right-censoring", () => {
  it("horizon beyond last observed trade -> reached = NULL (unobserved), not false", () => {
    const triggerTs = T0 + 4 * MIN;
    const rows = [...confirmRows(0.7), triggerRow(100.5, 0.9)];
    // Target NOT reached; trades end at trigger+5h -> 4h observed (false), 8h/24h censored (NULL).
    const trades = tradesRange(T0, triggerTs + 5 * HOUR, 5 * MIN, () => 100.5);
    const { out } = runScenario(rows, trades);
    expect(out[0].final_status).toBe("RESOLVED_FAILED");
    expect(out[0].outcomes["4h"].reached).toBe(false); // fully observed failure
    expect(out[0].outcomes["8h"].reached).toBeNull(); // right-censored
    expect(out[0].outcomes["24h"].reached).toBeNull();
    expect(out[0].outcomes["24h"].mfePct).toBeNull();
  });
});

describe("read-only: ZSM hook is non-behavioral", () => {
  it("detector funnel identical with and without the observer attached", () => {
    const cfg = loadConfig();
    const rows = [...confirmRows(0.7), triggerRow()];
    const snapOf = (d: ZoneDetector) => d.zones().map((z) => `${z.direction}:${z.status}:${z.startTs}:${z.zoneLow.toFixed(6)}`).sort();

    const dA = new ZoneDetector(cfg, "BTCUSDT", "fix");
    for (const r of rows) dA.ingest(r);
    dA.finalize(rows[rows.length - 1].ts);
    const baseline = snapOf(dA);

    let calls = 0;
    setTransitionObserver(() => { calls++; });
    const dB = new ZoneDetector(cfg, "BTCUSDT", "fix");
    for (const r of rows) dB.ingest(r);
    dB.finalize(rows[rows.length - 1].ts);
    setTransitionObserver(null);

    expect(snapOf(dB)).toEqual(baseline); // identical funnel
    expect(calls).toBeGreaterThan(0); // observer actually fired
  });
});

describe("determinism + reconciliation + schema", () => {
  it("exactly one row per zone; rows == zones seen; deterministic unique ids", () => {
    const { rows, trades } = reachedScenario();
    const { out, stats } = runScenario(rows, trades);
    expect(stats.rows).toBe(out.length);
    expect(stats.reconciledOk).toBe(true);
    const ids = out.map((r) => r.zone_id);
    expect(new Set(ids).size).toBe(ids.length); // unique
    expect(ids).toEqual([...ids].sort((a, b) => a - b)); // sequential ascending
  });

  it("idempotent: identical scenario -> byte-identical CSV", () => {
    const cfg = loadConfig();
    const cols = columnsForConfig(cfg);
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "zf-"));
    const run = (p: string): string => {
      const { rows, trades } = reachedScenario();
      const { out } = runScenario(rows, trades);
      return writeOutputs(p, cols, out).csv;
    };
    const a = run(path.join(tmp, "a.csv"));
    const b = run(path.join(tmp, "b.csv"));
    expect(a).toBe(b);
    expect(fs.readFileSync(path.join(tmp, "a.csv"), "utf8")).toBe(fs.readFileSync(path.join(tmp, "b.csv"), "utf8"));
  });

  it("schema check: every contract column has a real source column", () => {
    const cfg = loadConfig();
    const names = new Set(columnsForConfig(cfg).map((c) => c.name));
    const required = [
      "zone_id", "direction", "candidate_ts_ms", "confirmed_ts_ms", "trigger_ts_ms", "resolution_ts_ms", "final_status",
      "zone_low", "zone_high", "trigger_price", "target_price",
      "orderflowImbalance_0.05", "orderflowImbalance_0.10", "orderflowImbalance_0.25", "orderflowImbalance_0.50", "orderflowImbalance_1.0", "orderflowImbalance_2.0",
      "buyAbsorptionScore", "sellAbsorptionScore", "bidRefillScore", "askRefillScore", "bidThinningScore", "askThinningScore",
      "voidUp2PctScore", "voidDown2PctScore", "rangeCompression", "range1mPct", "realizedVolPct",
      "buyPressure_300s", "sellPressure_300s", "delta_300s",
      "reached_4h", "time_to_target_4h_min", "MFE_4h", "MAE_4h", "maxDrawdownBeforeTarget_4h",
      "reached_24h", "MFE_24h", "baseline_24h_reach_prob",
    ];
    for (const r of required) expect(names.has(r), `missing column ${r}`).toBe(true);
  });

  it("data-dictionary written next to CSV, one entry per column, header matches", () => {
    const cfg = loadConfig();
    const cols = columnsForConfig(cfg);
    const { rows, trades } = reachedScenario();
    const { out } = runScenario(rows, trades);
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "zf-"));
    const csvPath = path.join(tmp, "zone_features.csv");
    const { schemaPath } = writeOutputs(csvPath, cols, out);
    expect(fs.existsSync(schemaPath)).toBe(true);
    const schema = fs.readFileSync(schemaPath, "utf8");
    for (const c of cols) expect(schema).toContain(`| ${c.name} |`); // one table row per column
    const header = fs.readFileSync(csvPath, "utf8").split("\n")[0];
    expect(header).toBe(cols.map((c) => c.name).join(","));
  });

  it("rangeCompression NULL (no snapshot) is distinct from false in the CSV", () => {
    const cols = columnsForConfig(loadConfig());
    const col = cols.find((c) => c.name === "rangeCompression")!;
    const withSnap = { snap: { rangeCompression: false } } as unknown as ExportRow;
    const noSnap = { snap: null } as unknown as ExportRow;
    expect(col.get(withSnap)).toBe("false"); // false -> "false"
    expect(col.get(noSnap)).toBe(""); // NULL -> empty (distinct)
  });
});

describe("data dictionary content", () => {
  it("schema markdown documents type/units/null for each column", () => {
    const md = buildSchemaMarkdown(columnsForConfig(loadConfig()));
    expect(md).toContain("data dictionary");
    expect(md).toContain("| column | type | units / source | NULL semantics |");
    expect(md).toContain("baseline_24h_reach_prob");
  });
});
