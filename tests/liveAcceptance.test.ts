// Acceptance-orchestrator tests (offline). Cover:
//
// 1. live:acceptance does NOT start the recorder when ClickHouse is unreachable.
// 2. Duration parser accepts the documented formats and rejects garbage.
// 3. Acceptance report writer produces the expected sections + verdict.
// 4. SQL query builder substitutes the (exchange, symbol, time-range) tuple.
// 5. backtest:db invocation arg builder validates inputs and produces the expected struct.

import { describe, expect, it, beforeAll, afterAll } from "vitest";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import { parseDurationMinutesArg, DurationParseError } from "../src/live-recorder/acceptance/duration.js";
import {
  buildAcceptanceMarkdown,
  computeVerdict,
  type AcceptanceReportInput,
} from "../src/live-recorder/acceptance/acceptanceReport.js";
import {
  buildCountSql,
  buildHealthAggregateSql,
  buildLatestSnapshotSql,
  buildMinMaxTimeSql,
  buildSnapshotQualitySql,
} from "../src/live-recorder/acceptance/acceptanceQueries.js";
import {
  buildBacktestInvocation,
  describeBacktestInvocation,
} from "../src/live-recorder/acceptance/backtestDbInvocation.js";
import { runAcceptance, AcceptanceAbort } from "../src/cli/liveAcceptance.js";
import type { ClickHouseClient } from "../src/live-recorder/clickhouseClient.js";

// ---------- 1. CH-down → recorder never starts ----------

describe("liveAcceptance: aborts when ClickHouse is unreachable", () => {
  let tmp: string;
  beforeAll(() => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), "ofr-acc-"));
  });
  afterAll(() => {
    try {
      fs.rmSync(tmp, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  });

  it("never calls startRecorder if ch.ping() returns false", async () => {
    let recorderStarted = false;
    const fakeCh = {
      ping: async () => false,
      qualifyTable: (t: string) => `orderflow.${t}`,
      query: async () => [],
    } as unknown as ClickHouseClient;
    const startRecorder = async () => {
      recorderStarted = true;
      return { stop: async () => undefined };
    };
    await expect(
      runAcceptance({
        ch: fakeCh,
        durationMs: 60_000,
        symbols: ["BTCUSDT"],
        startRecorder,
        runBacktest: async () => undefined,
        sleep: async () => undefined,
        log: () => undefined,
        reportsDir: tmp,
        spoolDir: tmp,
      })
    ).rejects.toBeInstanceOf(AcceptanceAbort);
    expect(recorderStarted).toBe(false);
  });

  it("aborts (and recorder never starts) when required tables are missing", async () => {
    let recorderStarted = false;
    const fakeCh = {
      ping: async () => true,
      qualifyTable: (t: string) => `orderflow.${t}`,
      query: async (sql: string) => {
        // system.tables list — return only two tables, leaving most missing.
        if (/system\.tables/i.test(sql)) return [{ name: "trades" }, { name: "raw_depth_events" }] as never;
        return [] as never;
      },
    } as unknown as ClickHouseClient;
    await expect(
      runAcceptance({
        ch: fakeCh,
        durationMs: 60_000,
        symbols: ["BTCUSDT"],
        startRecorder: async () => {
          recorderStarted = true;
          return { stop: async () => undefined };
        },
        runBacktest: async () => undefined,
        sleep: async () => undefined,
        log: () => undefined,
        reportsDir: tmp,
        spoolDir: tmp,
      })
    ).rejects.toBeInstanceOf(AcceptanceAbort);
    expect(recorderStarted).toBe(false);
  });
});

// ---------- 2. Duration parser ----------

describe("parseDurationMinutesArg", () => {
  it("treats bare numbers as minutes", () => {
    expect(parseDurationMinutesArg("10")).toBe(600_000);
    expect(parseDurationMinutesArg(5)).toBe(300_000);
  });
  it("accepts unit suffixes", () => {
    expect(parseDurationMinutesArg("10min")).toBe(600_000);
    expect(parseDurationMinutesArg("1h")).toBe(3_600_000);
    expect(parseDurationMinutesArg("30s")).toBe(30_000);
    expect(parseDurationMinutesArg("0.5h")).toBe(1_800_000);
  });
  it("uses the fallback when undefined / empty", () => {
    expect(parseDurationMinutesArg(undefined)).toBe(600_000);
    expect(parseDurationMinutesArg("")).toBe(600_000);
    expect(parseDurationMinutesArg(undefined, 5)).toBe(300_000);
  });
  it("throws DurationParseError on garbage input", () => {
    expect(() => parseDurationMinutesArg("abc")).toThrow(DurationParseError);
    expect(() => parseDurationMinutesArg("0")).toThrow(DurationParseError);
    expect(() => parseDurationMinutesArg("-1m")).toThrow(DurationParseError);
  });
});

// ---------- 3. Acceptance report writer + verdict ----------

describe("acceptanceReport / computeVerdict", () => {
  function makeInput(over: Partial<AcceptanceReportInput> = {}): AcceptanceReportInput {
    return {
      startTimeIso: "2026-05-09T00:00:00.000Z",
      endTimeIso: "2026-05-09T00:10:00.000Z",
      durationMs: 600_000,
      exchange: "binance-futures",
      symbols: ["BTCUSDT"],
      primarySymbol: "BTCUSDT",
      ch: { url: "http://localhost:8123", database: "orderflow" },
      tableCounts: [
        { table: "raw_depth_events", rowCount: 100_000, firstTs: "...", lastTs: "..." },
        { table: "trades", rowCount: 5_000, firstTs: "...", lastTs: "..." },
        { table: "orderbook_snapshots_1s", rowCount: 600, firstTs: "...", lastTs: "..." },
        { table: "book_ticker", rowCount: 200_000, firstTs: "...", lastTs: "..." },
        { table: "mark_price", rowCount: 10, firstTs: "...", lastTs: "..." },
        { table: "liquidations", rowCount: 0, firstTs: null, lastTs: null },
        { table: "recorder_health", rowCount: 60, firstTs: "...", lastTs: "..." },
      ],
      snapshotQuality: {
        snapshots: 600,
        crossed: 0,
        empty: 0,
        flaggedCrossed: 0,
        flaggedEmpty: 0,
        flaggedWideSpread: 0,
        spreadMin: 0.1,
        spreadMax: 0.5,
        spreadAvg: 0.2,
      },
      latestSnapshot: {
        ts: "2026-05-09 00:09:59.000",
        bestBid: 80000,
        bestAsk: 80000.5,
        mid: 80000.25,
        spread: 0.5,
        sequenceFinalUpdateId: 1234567,
        qualityFlagsCsv: "",
      },
      health: {
        sequenceGapCount: 0,
        reconnectCount: 0,
        maxDbQueueSize: 100,
        maxSpoolQueueSize: 0,
        okSamples: 60,
        degradedSamples: 0,
        downSamples: 0,
        samples: 60,
      },
      spoolFilesCreated: false,
      insertErrorsObserved: false,
      notes: [],
      backtest: {
        ran: true,
        zonesFound: 0,
        zonesTriggered: 0,
        zonesReachedRaw: 0,
        uniqueReachedMoves: 0,
        reportPath: "reports/live_acceptance_db_x",
      },
      ...over,
    };
  }

  it("produces PASS on a healthy run with all tables non-zero and no quality issues", () => {
    const v = computeVerdict(makeInput());
    expect(v.overall).toBe("PASS");
    const labels = v.parts.map((p) => p.label);
    for (const required of [
      "raw_depth_events written",
      "trades written",
      "orderbook_snapshots_1s written",
      "book_ticker written",
      "no spool files (CH was reachable throughout)",
      "no ClickHouse insert errors",
      "no sequence gaps",
      "backtest:db ran end-to-end",
    ]) {
      expect(labels).toContain(required);
    }
  });

  it("produces FAIL when raw_depth_events is empty (strategy-critical stream missing)", () => {
    const v = computeVerdict(
      makeInput({
        tableCounts: [
          { table: "raw_depth_events", rowCount: 0, firstTs: null, lastTs: null },
          { table: "trades", rowCount: 5000, firstTs: "...", lastTs: "..." },
          { table: "orderbook_snapshots_1s", rowCount: 600, firstTs: "...", lastTs: "..." },
          { table: "book_ticker", rowCount: 0, firstTs: null, lastTs: null },
          { table: "mark_price", rowCount: 0, firstTs: null, lastTs: null },
          { table: "liquidations", rowCount: 0, firstTs: null, lastTs: null },
          { table: "recorder_health", rowCount: 0, firstTs: null, lastTs: null },
        ],
      })
    );
    expect(v.overall).toBe("FAIL");
  });

  it("produces DEGRADED when spool files exist but core streams populated", () => {
    const v = computeVerdict(makeInput({ spoolFilesCreated: true }));
    expect(v.overall).toBe("DEGRADED");
  });

  it("buildAcceptanceMarkdown contains every required section", () => {
    const md = buildAcceptanceMarkdown(makeInput());
    for (const heading of [
      "# Live Recorder Acceptance Run",
      "## 1. Table row counts",
      "## 2. Snapshot quality",
      "## 3. Latest snapshot",
      "## 4. Recorder health summary",
      "## 5. Spool / insert-error checks",
      "## 6. backtest:db sanity replay",
      "## 7. Verdict",
    ]) {
      expect(md).toContain(heading);
    }
    expect(md).toContain("Verdict: **PASS**");
  });
});

// ---------- 4. SQL query builders ----------

describe("acceptance SQL builders", () => {
  const w = {
    exchange: "binance-futures",
    symbol: "BTCUSDT",
    fromMs: Date.UTC(2026, 4, 9, 0, 0, 0, 0),
    toMs: Date.UTC(2026, 4, 9, 0, 10, 0, 0),
  };

  it("buildCountSql substitutes the table, exchange, symbol and window", () => {
    const sql = buildCountSql("raw_depth_events", w);
    expect(sql).toContain("FROM raw_depth_events");
    expect(sql).toContain("exchange = 'binance-futures'");
    expect(sql).toContain("symbol = 'BTCUSDT'");
    expect(sql).toContain("toDateTime64('2026-05-09 00:00:00.000', 3, 'UTC')");
    expect(sql).toContain("toDateTime64('2026-05-09 00:10:00.000', 3, 'UTC')");
    expect(sql.toLowerCase()).toContain("count()");
  });

  it("uses ts column for snapshots and recorder_health", () => {
    expect(buildCountSql("orderbook_snapshots_1s", w).toLowerCase()).toContain("ts >=");
    expect(buildCountSql("recorder_health", w).toLowerCase()).toContain("ts >=");
  });

  it("buildMinMaxTimeSql / SnapshotQuality / LatestSnapshot / Health all contain symbol filter", () => {
    for (const sql of [
      buildMinMaxTimeSql("trades", w),
      buildSnapshotQualitySql(w),
      buildLatestSnapshotSql(w),
      buildHealthAggregateSql(w),
    ]) {
      expect(sql).toContain("symbol = 'BTCUSDT'");
      expect(sql).toContain("exchange = 'binance-futures'");
    }
  });

  it("rejects unknown tables", () => {
    expect(() => buildCountSql("nonexistent_table", w)).toThrow();
    expect(() => buildMinMaxTimeSql("nonexistent_table", w)).toThrow();
  });

  it("escapes single quotes in symbol/exchange", () => {
    const evil = { ...w, symbol: "BT'CUSDT" };
    const sql = buildCountSql("trades", evil);
    expect(sql).toContain("symbol = 'BT''CUSDT'");
    expect(sql).not.toMatch(/symbol = 'BT'CUSDT'/);
  });
});

// ---------- 5. backtest:db invocation arg builder ----------

describe("buildBacktestInvocation", () => {
  it("returns a typed invocation when required fields are present", () => {
    const fromMs = Date.UTC(2026, 4, 9, 0, 0, 0, 0);
    const toMs = Date.UTC(2026, 4, 9, 0, 10, 0, 0);
    const inv = buildBacktestInvocation({
      symbol: "BTCUSDT",
      exchange: "binance-futures",
      fromMs,
      toMs,
      targetPct: 2,
      horizons: ["4h", "8h", "24h"],
      outDir: "reports/x",
    });
    expect(inv.symbol).toBe("BTCUSDT");
    expect(inv.toMs).toBe(toMs);
    expect(inv.horizons).toEqual(["4h", "8h", "24h"]);
    expect(describeBacktestInvocation(inv)).toContain("--symbol BTCUSDT");
    expect(describeBacktestInvocation(inv)).toContain("--from 2026-05-09T00:00:00.000Z");
  });
  it("rejects to <= from", () => {
    expect(() =>
      buildBacktestInvocation({
        symbol: "BTCUSDT",
        exchange: "x",
        fromMs: 1,
        toMs: 1,
        targetPct: 2,
        horizons: ["4h"],
        outDir: ".",
      })
    ).toThrow(/to must be > from/);
  });
  it("rejects empty horizons", () => {
    expect(() =>
      buildBacktestInvocation({
        symbol: "BTCUSDT",
        exchange: "x",
        fromMs: 1,
        toMs: 2,
        targetPct: 2,
        horizons: [],
        outDir: ".",
      })
    ).toThrow(/horizons required/);
  });
  it("rejects missing symbol/exchange", () => {
    expect(() =>
      buildBacktestInvocation({
        symbol: "",
        exchange: "x",
        fromMs: 1,
        toMs: 2,
        targetPct: 2,
        horizons: ["4h"],
        outDir: ".",
      })
    ).toThrow(/symbol required/);
  });
});
