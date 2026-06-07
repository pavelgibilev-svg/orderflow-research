import { describe, expect, it } from "vitest";
import {
  runSample2026,
  type SampleRunDayResult,
  type SampleRunDayOpts,
} from "../src/strategy/sampleRunnerCore.js";

function fakeDayResult(date: string, valid: boolean, errored: string | null): SampleRunDayResult {
  return {
    date,
    isValid: valid,
    validation: {
      date,
      symbol: "BTCUSDT",
      exchange: "binance-futures",
      inputPath: "test",
      isValid: valid,
      invalidReasons: valid ? [] : ["incremental_book_L2: missing_required"],
      dataTypes: [],
      warnings: [],
    },
    backtest: null,
    snapshotsExported: 0,
    errored,
    notes: errored ? "errored" : "ok",
  };
}

describe("sample-2026 runner", () => {
  it("does NOT abort the whole run when one day's runner throws", async () => {
    const calls: string[] = [];
    const days = await runSample2026({
      input: "test",
      symbol: "BTCUSDT",
      exchange: "binance-futures",
      targetPct: 2,
      horizons: ["4h"],
      outDir: "/nonexistent-test-out",
      runDay: async (opts: SampleRunDayOpts) => {
        calls.push(opts.date);
        if (opts.date === "2026-02-01") throw new Error("boom");
        return fakeDayResult(opts.date, true, null);
      },
    });
    // All 4 dates were attempted, in order.
    expect(calls).toEqual(["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]);
    expect(days).toHaveLength(4);
    // The crashing day surfaces as errored, but doesn't poison the others.
    const bad = days.find((d) => d.date === "2026-02-01")!;
    expect(bad.isValid).toBe(false);
    expect(bad.errored).toMatch(/boom/);
    const ok = days.find((d) => d.date === "2026-03-01")!;
    expect(ok.isValid).toBe(true);
  });

  it("preserves invalid (but non-throwing) days as isValid=false in summary", async () => {
    const days = await runSample2026({
      input: "test",
      symbol: "BTCUSDT",
      exchange: "binance-futures",
      targetPct: 2,
      horizons: ["4h"],
      runDay: async (opts) => {
        if (opts.date === "2026-04-01") return fakeDayResult(opts.date, false, null);
        return fakeDayResult(opts.date, true, null);
      },
    });
    expect(days.filter((d) => d.isValid)).toHaveLength(3);
    expect(days.filter((d) => !d.isValid)).toHaveLength(1);
    const bad = days.find((d) => !d.isValid)!;
    expect(bad.validation.invalidReasons[0]).toMatch(/incremental_book_L2/);
  });
});
