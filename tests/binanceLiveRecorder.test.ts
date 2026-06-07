// Live-recorder unit tests covering the deterministic, network-free pieces:
//
// A. Binance depth update parser.
// B. Snapshot bootstrap logic (drop u<L, first event must satisfy U<=L+1<=u).
// C. pu/u sequence-continuity check.
// D. amount=0 removes a level (via the existing OrderBook).
// E. Sequence gap triggers resync flag.
// F. BatchWriter: batches rows and flushes; spools on CH failure.
// G. ClickHouse SQL generation (DDL + insert).
// H. ClickHouseDataSource maps rows to replay events.
// I. Recorder health metrics update on each tick.
// J. No trading endpoints exist in the live-recorder module.

import { describe, expect, it, beforeAll, afterAll } from "vitest";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import {
  parseAggTrade,
  parseBookTicker,
  parseDepthMessage,
  parseForceOrder,
  parseMarkPrice,
  type BinanceDiffDepthMessage,
  type BinanceAggTradeMessage,
  type BinanceBookTickerMessage,
  type BinanceMarkPriceMessage,
  type BinanceForceOrderMessage,
} from "../src/live-recorder/binanceTypes.js";
import { LocalOrderBookLive } from "../src/live-recorder/localOrderBookLive.js";
import { parseSnapshotPayload } from "../src/live-recorder/binanceRestClient.js";
import { BatchWriter } from "../src/live-recorder/batchWriter.js";
import { SpoolWriter } from "../src/live-recorder/spoolWriter.js";
import { allMigrationSql, ALL_TABLES } from "../src/live-recorder/schema.js";
import { ClickHouseDataSource, parseDt64, formatDt64 } from "../src/data/clickhouseDataSource.js";
import { HealthMonitor } from "../src/live-recorder/healthMonitor.js";

// ---------- A. Binance depth parser ----------

describe("A. Binance message parsers", () => {
  it("parses depthUpdate to a typed DepthEvent", () => {
    const msg: BinanceDiffDepthMessage = {
      e: "depthUpdate",
      E: 1700000000000,
      T: 1700000000000,
      s: "BTCUSDT",
      U: 100,
      u: 105,
      pu: 99,
      b: [["50000.10", "1.5"], ["50000.00", "0"]],
      a: [["50001.00", "2.0"]],
    };
    const ev = parseDepthMessage(msg, 1700000000050, JSON.stringify(msg));
    expect(ev.symbol).toBe("BTCUSDT");
    expect(ev.firstUpdateId).toBe(100);
    expect(ev.finalUpdateId).toBe(105);
    expect(ev.prevFinalUpdateId).toBe(99);
    expect(ev.bids).toEqual([[50000.1, 1.5], [50000.0, 0]]);
    expect(ev.asks).toEqual([[50001.0, 2.0]]);
    expect(ev.receivedAtMs).toBe(1700000000050);
  });

  it("parses aggTrade and maps `m` to taker side correctly", () => {
    const m1: BinanceAggTradeMessage = { e: "aggTrade", E: 1, s: "BTCUSDT", a: 7, p: "100", q: "1", f: 1, l: 1, T: 1, m: false };
    const t1 = parseAggTrade(m1, 2, JSON.stringify(m1));
    expect(t1.side).toBe("buy"); // m=false -> taker buy
    const m2: BinanceAggTradeMessage = { ...m1, m: true };
    const t2 = parseAggTrade(m2, 2, JSON.stringify(m2));
    expect(t2.side).toBe("sell"); // m=true -> taker sell
  });

  it("parses bookTicker / markPrice / forceOrder", () => {
    const bt: BinanceBookTickerMessage = { u: 1, s: "BTCUSDT", b: "100.0", B: "1", a: "100.5", A: "1", E: 1700 };
    expect(parseBookTicker(bt, 1701, JSON.stringify(bt)).bidPrice).toBe(100);
    const mp: BinanceMarkPriceMessage = { e: "markPriceUpdate", E: 1, s: "BTCUSDT", p: "100", i: "100", P: "100", r: "0", T: 100 };
    expect(parseMarkPrice(mp, 2, JSON.stringify(mp)).markPrice).toBe(100);
    const fo: BinanceForceOrderMessage = {
      e: "forceOrder",
      E: 1,
      o: { s: "BTCUSDT", S: "SELL", o: "LIMIT", f: "IOC", q: "1", p: "100", ap: "99", X: "FILLED", l: "1", z: "1", T: 1 },
    };
    const lq = parseForceOrder(fo, 2, JSON.stringify(fo));
    expect(lq.side).toBe("sell");
    expect(lq.originalQty).toBe(1);
  });
});

// ---------- B. Snapshot bootstrap logic ----------

describe("B. Snapshot bootstrap drops stale events and gates on U<=L+1<=u", () => {
  it("drops events with finalUpdateId < snapshot lastUpdateId", async () => {
    const snapshotBody = JSON.stringify({
      lastUpdateId: 1000,
      E: 0,
      T: 0,
      bids: [["100", "1"]],
      asks: [["101", "1"]],
    });
    const book = new LocalOrderBookLive({
      fetchSnapshot: async () => parseSnapshotPayload("BTCUSDT", snapshotBody, 0),
    });
    await book.bootstrap();
    expect(book.getStats().lastSnapshotUpdateId).toBe(1000);
    // Stale event before snapshot:
    const stale = parseDepthMessage(
      { e: "depthUpdate", E: 1, T: 1, s: "BTCUSDT", U: 800, u: 850, pu: 799, b: [], a: [] },
      0,
      ""
    );
    expect(book.applyDepthEvent(stale).kind).toBe("dropped_stale");
    // First event must straddle L+1.
    const ok = parseDepthMessage(
      { e: "depthUpdate", E: 2, T: 2, s: "BTCUSDT", U: 1000, u: 1010, pu: 999, b: [["100", "2"]], a: [] },
      0,
      ""
    );
    const r = book.applyDepthEvent(ok);
    expect(r.kind).toBe("applied");
    if (r.kind === "applied") expect(r.isFirstAfterSnapshot).toBe(true);
  });
});

// ---------- C. pu/u continuity + E. sequence gap ----------

describe("C/E. Sequence continuity and gap detection", () => {
  it("accepts contiguous pu == previous u; flags a gap and triggers resync when broken", async () => {
    const snap = JSON.stringify({ lastUpdateId: 100, bids: [], asks: [], E: 0 });
    let snapshotCount = 0;
    const book = new LocalOrderBookLive({
      fetchSnapshot: async () => {
        snapshotCount++;
        return parseSnapshotPayload("BTCUSDT", snap, 0);
      },
    });
    await book.bootstrap();
    expect(snapshotCount).toBe(1);
    const e1 = parseDepthMessage(
      { e: "depthUpdate", E: 1, T: 1, s: "BTCUSDT", U: 100, u: 110, pu: 99, b: [], a: [] },
      0,
      ""
    );
    expect(book.applyDepthEvent(e1).kind).toBe("applied");
    const e2 = parseDepthMessage(
      { e: "depthUpdate", E: 2, T: 2, s: "BTCUSDT", U: 111, u: 120, pu: 110, b: [], a: [] },
      0,
      ""
    );
    expect(book.applyDepthEvent(e2).kind).toBe("applied");
    // Now break continuity:
    const eBad = parseDepthMessage(
      { e: "depthUpdate", E: 3, T: 3, s: "BTCUSDT", U: 130, u: 140, pu: 129, b: [], a: [] },
      0,
      ""
    );
    const out = book.applyDepthEvent(eBad);
    expect(out.kind).toBe("sequence_gap");
    expect(book.getStats().sequenceGapCount).toBe(1);
    // Resync re-snapshots.
    await book.resync("sequence_gap");
    expect(snapshotCount).toBe(2);
  });
});

// ---------- D. amount=0 deletes the level (via OrderBook) ----------

describe("D. amount=0 removes a price level", () => {
  it("a depth update with qty=0 removes the level on the local book", async () => {
    const snap = JSON.stringify({
      lastUpdateId: 1,
      bids: [["100", "5"], ["99", "5"]],
      asks: [["101", "5"]],
      E: 0,
    });
    const book = new LocalOrderBookLive({
      fetchSnapshot: async () => parseSnapshotPayload("BTCUSDT", snap, 0),
    });
    await book.bootstrap();
    expect(book.book.bestBid()).toBe(100);
    const wipe = parseDepthMessage(
      { e: "depthUpdate", E: 1, T: 1, s: "BTCUSDT", U: 1, u: 2, pu: 0, b: [["100", "0"]], a: [] },
      0,
      ""
    );
    expect(book.applyDepthEvent(wipe).kind).toBe("applied");
    expect(book.book.bestBid()).toBe(99);
  });
});

// ---------- F. BatchWriter: batches and spools ----------

describe("F. BatchWriter batches rows and spools on ClickHouse failure", () => {
  let tmpDir: string;
  beforeAll(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ofr-bw-"));
  });
  afterAll(() => {
    try {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  });

  it("flushes when the buffer reaches maxBatchSize and inserts the rows", async () => {
    const inserts: Array<{ table: string; rows: ReadonlyArray<Record<string, unknown>> }> = [];
    const fakeCh = {
      qualifyTable: (t: string) => `db.${t}`,
      insertJSONEachRow: async (table: string, rows: ReadonlyArray<Record<string, unknown>>) => {
        inserts.push({ table, rows });
      },
    } as unknown as ConstructorParameters<typeof BatchWriter>[0]["ch"];
    const w = new BatchWriter({
      ch: fakeCh as never,
      spool: new SpoolWriter(tmpDir),
      maxBatchSize: 3,
      flushIntervalMs: 10_000,
    });
    w.enqueue("trades", { a: 1 });
    w.enqueue("trades", { a: 2 });
    w.enqueue("trades", { a: 3 });
    // The third enqueue triggers an async flushOne. Wait a tick for the
    // microtask to settle.
    await new Promise((r) => setTimeout(r, 10));
    expect(inserts.length).toBeGreaterThanOrEqual(1);
    expect(inserts[0]!.rows.length).toBe(3);
    await w.stop();
    expect(w.stats().inserted).toBe(3);
  });

  it("spools rows when the insert throws, then recovers them on next attempt", async () => {
    let failNext = true;
    const inserts: Array<ReadonlyArray<Record<string, unknown>>> = [];
    const fakeCh = {
      qualifyTable: (t: string) => `db.${t}`,
      insertJSONEachRow: async (_table: string, rows: ReadonlyArray<Record<string, unknown>>) => {
        if (failNext) {
          failNext = false;
          throw new Error("simulated CH down");
        }
        inserts.push(rows);
      },
    } as unknown as ConstructorParameters<typeof BatchWriter>[0]["ch"];
    const spool = new SpoolWriter(tmpDir);
    const w = new BatchWriter({
      ch: fakeCh as never,
      spool,
      maxBatchSize: 1,
      flushIntervalMs: 10_000,
    });
    w.enqueue("trades", { a: 99 });
    await new Promise((r) => setTimeout(r, 20));
    // First attempt failed → row is on disk, not in inserts.
    expect(inserts.length).toBe(0);
    expect(w.stats().spooled).toBe(1);
    // Now run recovery → the row should be inserted.
    await w.recoverSpool(["trades"]);
    expect(inserts.length).toBe(1);
    expect(w.stats().recovered).toBe(1);
    await w.stop();
  });
});

// ---------- G. SQL generation ----------

describe("G. ClickHouse DDL SQL generation", () => {
  it("includes every required table and uses MergeTree with daily partitioning", () => {
    const sql = allMigrationSql("orderflow");
    const joined = sql.join("\n;\n");
    for (const t of ALL_TABLES) {
      expect(joined.toLowerCase()).toContain(t);
    }
    expect(joined).toContain("CREATE DATABASE IF NOT EXISTS orderflow");
    expect(joined).toContain("ENGINE = MergeTree");
    expect(joined).toContain("PARTITION BY toYYYYMMDD(event_time)");
    expect(joined).toContain("ENGINE = ReplacingMergeTree");
  });
});

// ---------- H. ClickHouseDataSource maps rows to replay events ----------

describe("H. ClickHouseDataSource maps SELECT rows back to replay events", () => {
  it("maps a raw_depth_events row into bid/ask BookL2Events with correct ts", async () => {
    const fakeRows = [
      {
        exchange: "binance-futures",
        symbol: "BTCUSDT",
        event_time: "2026-05-09 12:34:56.789",
        first_update_id: 1,
        final_update_id: 2,
        bids_prices: [100, 99],
        bids_qty: [1, 0.5],
        asks_prices: [101],
        asks_qty: [2],
      },
    ];
    const tradeRows = [
      { exchange: "binance-futures", symbol: "BTCUSDT", event_time: "2026-05-09 12:34:57.000", agg_trade_id: 7, price: 100.5, qty: 0.1, side: "buy" },
    ];
    const fakeCh = {
      qualifyTable: (t: string) => `orderflow.${t}`,
      query: async (sql: string) => {
        if (sql.includes("raw_depth_events")) return fakeRows as never;
        if (sql.includes("trades") && !sql.includes("liquidations")) return tradeRows as never;
        return [];
      },
    } as never;
    const ds = new ClickHouseDataSource({ ch: fakeCh, pageSize: 1000 });
    const events: Array<{ source: string; ts: number; price?: number; side?: string; amount?: number }> = [];
    for await (const ev of ds.events({ symbol: "BTCUSDT", exchange: "binance-futures", fromMs: 0, toMs: Number.MAX_SAFE_INTEGER })) {
      events.push(ev as never);
    }
    // 3 depth (2 bid + 1 ask) + 1 trade = 4
    expect(events.length).toBe(4);
    const depth = events.filter((e) => e.source === "incremental_book_L2");
    expect(depth.length).toBe(3);
    expect(depth.every((d) => d.ts === Date.parse("2026-05-09T12:34:56.789Z"))).toBe(true);
    expect(depth.find((d) => d.price === 99 && d.side === "bid")?.amount).toBe(0.5);
    const trades = events.filter((e) => e.source === "trades");
    expect(trades.length).toBe(1);
  });

  it("parseDt64 / formatDt64 round-trip", () => {
    const ms = Date.UTC(2026, 4, 9, 12, 34, 56, 789);
    const s = formatDt64(ms);
    expect(s).toBe("2026-05-09 12:34:56.789");
    expect(parseDt64(s)).toBe(ms);
  });
});

// ---------- I. HealthMonitor emits a metrics row each tick ----------

describe("I. HealthMonitor emits one health row per tick", () => {
  it("calls emit() with the expected fields on a manual tick", () => {
    const emitted: Array<Record<string, unknown>> = [];
    const now = Date.now();
    const hm = new HealthMonitor({
      exchange: "binance-futures",
      symbol: "BTCUSDT",
      collect: () => ({
        wsConnected: true,
        sequenceOk: true,
        lastDepthEventTimeMs: now,
        lastTradeEventTimeMs: now,
        depthEventCountInWindow: 600,
        tradeEventCountInWindow: 60,
        reconnectCount: 0,
        sequenceGapCount: 0,
        dbQueueSize: 12,
        spoolQueueSize: 0,
      }),
      emit: (row) => emitted.push(row),
      windowMs: 60_000,
    });
    hm.tick();
    expect(emitted.length).toBe(1);
    const row = emitted[0]!;
    expect(row.exchange).toBe("binance-futures");
    expect(row.symbol).toBe("BTCUSDT");
    expect(row.status).toBe("OK");
    expect(row.depth_events_per_sec).toBe(10); // 600 / 60s
    expect(row.trades_per_sec).toBe(1);
    expect(row.ws_connected).toBe(1);
    expect(row.sequence_ok).toBe(1);
  });

  it("downgrades status to DEGRADED on stale depth and DOWN on disconnect", () => {
    const emitted: Array<Record<string, unknown>> = [];
    const cases = [
      { wsConnected: false, expect: "DOWN" },
      { wsConnected: true, lastDepth: Date.now() - 60_000, expect: "DEGRADED" },
    ];
    for (const c of cases) {
      const hm = new HealthMonitor({
        exchange: "x",
        symbol: "Y",
        collect: () => ({
          wsConnected: c.wsConnected,
          sequenceOk: true,
          lastDepthEventTimeMs: c.lastDepth ?? Date.now(),
          lastTradeEventTimeMs: Date.now(),
          depthEventCountInWindow: 0,
          tradeEventCountInWindow: 0,
          reconnectCount: 0,
          sequenceGapCount: 0,
          dbQueueSize: 0,
          spoolQueueSize: 0,
        }),
        emit: (row) => emitted.push(row),
      });
      hm.tick();
      expect(emitted.at(-1)!.status).toBe(c.expect);
    }
  });
});

// ---------- J. No trading endpoints anywhere in the live-recorder module ----------

describe("J. live-recorder source contains NO trading endpoints", () => {
  const banned = [
    /api[-_]?key/i,
    /\/fapi\/v1\/order\b/i,
    /\/fapi\/v1\/allOrders\b/i,
    /\bplaceOrder\b/i,
    /\bcancelOrder\b/i,
    /\bsignedRequest\b/i,
    /HMAC-SHA256/i,
    /X-MBX-APIKEY/i,
  ];
  const dir = path.resolve(__dirname, "..", "src", "live-recorder");
  it("no banned tokens appear in src/live-recorder/*", () => {
    function* walk(d: string): IterableIterator<string> {
      for (const e of fs.readdirSync(d, { withFileTypes: true })) {
        const p = path.join(d, e.name);
        if (e.isDirectory()) yield* walk(p);
        else if (e.isFile() && p.endsWith(".ts")) yield p;
      }
    }
    const offenders: string[] = [];
    for (const f of walk(dir)) {
      const t = fs.readFileSync(f, "utf8");
      for (const re of banned) {
        if (re.test(t)) offenders.push(`${f} matches ${re}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
