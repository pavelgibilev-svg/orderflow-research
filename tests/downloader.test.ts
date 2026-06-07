import { describe, expect, it } from "vitest";
import {
  buildSample2026DownloadPlan,
  SAMPLE_2026_DATES,
  SAMPLE_2026_DATA_TYPES,
  SAMPLE_2026_REQUIRED,
} from "../src/data/tardisUrls.js";

describe("Tardis sample-2026 download URL plan", () => {
  it("emits exactly Jan-Apr 2026 dates and never May or future months", () => {
    const plan = buildSample2026DownloadPlan({ exchange: "binance-futures", symbol: "BTCUSDT" });
    const dates = new Set(plan.map((p) => p.date));
    expect([...dates].sort()).toEqual(["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]);
    for (const p of plan) {
      expect(p.url).toContain("2026/");
      expect(p.url).not.toContain("/2026/05/");
      expect(p.url).not.toContain("/2026/06/");
      expect(p.url).not.toContain("/2026/07/");
      expect(p.url).not.toContain("/2026/08/");
      expect(p.url).not.toContain("/2026/09/");
      expect(p.url).not.toContain("/2026/10/");
      expect(p.url).not.toContain("/2026/11/");
      expect(p.url).not.toContain("/2026/12/");
      expect(p.url).not.toContain("/2027/");
      expect(p.url).not.toContain("/2025/");
    }
  });

  it("rejects any attempt to include May 2026 or future months explicitly", () => {
    expect(() =>
      buildSample2026DownloadPlan({
        exchange: "binance-futures",
        symbol: "BTCUSDT",
        dates: ["2026-05-01"],
      })
    ).toThrow(/not allowed/i);
    expect(() =>
      buildSample2026DownloadPlan({
        exchange: "binance-futures",
        symbol: "BTCUSDT",
        dates: ["2026-06-01"],
      })
    ).toThrow(/not allowed/i);
    expect(() =>
      buildSample2026DownloadPlan({
        exchange: "binance-futures",
        symbol: "BTCUSDT",
        dates: ["2026-12-01"],
      })
    ).toThrow(/not allowed/i);
    expect(() =>
      buildSample2026DownloadPlan({
        exchange: "binance-futures",
        symbol: "BTCUSDT",
        dates: ["2027-01-01"],
      })
    ).toThrow(/not allowed/i);
  });

  it("produces 5 URLs per date covering all 5 data types and uses canonical layout", () => {
    const plan = buildSample2026DownloadPlan({ exchange: "binance-futures", symbol: "BTCUSDT" });
    expect(plan.length).toBe(SAMPLE_2026_DATES.length * SAMPLE_2026_DATA_TYPES.length);
    for (const e of plan) {
      expect(e.url.startsWith("https://datasets.tardis.dev/v1/binance-futures/")).toBe(true);
      expect(e.url.endsWith("/BTCUSDT.csv.gz")).toBe(true);
      expect(e.outRelPath).toMatch(/^data\/tardis\/binance-futures\/BTCUSDT\/2026-0[1-4]-01\/[a-zA-Z0-9_]+\.csv\.gz$/);
    }
    // SAMPLE_2026_REQUIRED is a deterministic part of the spec.
    expect([...SAMPLE_2026_REQUIRED]).toEqual(["incremental_book_L2", "trades"]);
  });
});

// Cross-check the bundled scripts to ensure they don't accidentally include May or later months.
import * as fs from "node:fs";
import * as path from "node:path";

describe("bundled Jan-Apr-2026 downloader scripts", () => {
  const scripts = [
    "scripts/download-tardis-2026-ytd-except-may.sh",
    "scripts/download-tardis-2026-ytd-except-may.ps1",
    "scripts/download-tardis-2026-ytd-except-may.py",
  ];
  for (const rel of scripts) {
    it(`${rel} contains only 2026-01..2026-04 dates`, () => {
      const text = fs.readFileSync(path.resolve(rel), "utf8");
      expect(text).toContain("2026-01-01");
      expect(text).toContain("2026-02-01");
      expect(text).toContain("2026-03-01");
      expect(text).toContain("2026-04-01");
      expect(text).not.toContain("2026-05-01");
      expect(text).not.toContain("2026-06-01");
      expect(text).not.toContain("2026-07-01");
      expect(text).not.toContain("2026-12-01");
      expect(text).not.toContain("2027-01-01");
    });
  }
});
