import { describe, expect, it, beforeAll, afterAll } from "vitest";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import * as zlib from "node:zlib";
import { validateDay } from "../src/strategy/validateTardisCore.js";

function gzWriteCsv(dir: string, name: string, content: string): string {
  fs.mkdirSync(dir, { recursive: true });
  const p = path.join(dir, name);
  fs.writeFileSync(p, zlib.gzipSync(Buffer.from(content, "utf8")));
  return p;
}

function dayDir(root: string, exchange: string, symbol: string, date: string): string {
  return path.join(root, exchange, symbol, date);
}

const SYMBOL = "BTCUSDT";
const EXCHANGE = "binance-futures";
const DATE = "2026-01-01";

let tmpRoot: string;
beforeAll(() => {
  tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), "ofr-validate-"));
});
afterAll(() => {
  try {
    fs.rmSync(tmpRoot, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
});

describe("validate:tardis core", () => {
  it("marks a day VALID when only required L2 + trades are present, optional missing", async () => {
    const dir = dayDir(tmpRoot, EXCHANGE, SYMBOL, DATE);
    const usDay = "1735689600000000"; // 2025-01-01... we only need parsable µs
    gzWriteCsv(
      dir,
      "incremental_book_L2.csv.gz",
      [
        "exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount",
        `${EXCHANGE},${SYMBOL},${usDay},${usDay},true,bid,100,1`,
        `${EXCHANGE},${SYMBOL},${usDay},${usDay},true,ask,101,1`,
        `${EXCHANGE},${SYMBOL},${usDay},${usDay},false,bid,99,2`,
      ].join("\n") + "\n"
    );
    gzWriteCsv(
      dir,
      "trades.csv.gz",
      [
        "exchange,symbol,timestamp,local_timestamp,id,side,price,amount",
        `${EXCHANGE},${SYMBOL},${usDay},${usDay},1,buy,100.5,0.1`,
        `${EXCHANGE},${SYMBOL},${usDay},${usDay},2,sell,100.4,0.2`,
      ].join("\n") + "\n"
    );

    const v = await validateDay({
      inputPath: tmpRoot,
      symbol: SYMBOL,
      exchange: EXCHANGE,
      date: DATE,
    });
    expect(v.isValid).toBe(true);
    const opt = v.dataTypes.filter((d) => !d.required);
    // None of the optional types were placed on disk:
    for (const o of opt) expect(o.status).toBe("missing_optional");
    // Required types parsed cleanly:
    const req = v.dataTypes.filter((d) => d.required);
    for (const r of req) expect(r.status).toBe("ok");
    // L2 reports both snapshot and update rows in the first sample:
    const l2 = v.dataTypes.find((d) => d.dataType === "incremental_book_L2")!;
    expect(l2.hasSnapshotRows).toBe(true);
    expect(l2.hasUpdateRows).toBe(true);
  });

  it("marks a day INVALID when incremental_book_L2 is missing", async () => {
    const dir = dayDir(tmpRoot, EXCHANGE, SYMBOL, "2026-02-01");
    const us = "1735689600000000";
    gzWriteCsv(
      dir,
      "trades.csv.gz",
      [
        "exchange,symbol,timestamp,local_timestamp,id,side,price,amount",
        `${EXCHANGE},${SYMBOL},${us},${us},1,buy,100.5,0.1`,
      ].join("\n") + "\n"
    );
    const v = await validateDay({
      inputPath: tmpRoot,
      symbol: SYMBOL,
      exchange: EXCHANGE,
      date: "2026-02-01",
    });
    expect(v.isValid).toBe(false);
    expect(v.invalidReasons.join(",")).toMatch(/incremental_book_L2/);
    const l2 = v.dataTypes.find((d) => d.dataType === "incremental_book_L2")!;
    expect(l2.status).toBe("missing_required");
  });

  it("marks a day INVALID when trades is missing", async () => {
    const dir = dayDir(tmpRoot, EXCHANGE, SYMBOL, "2026-03-01");
    const us = "1735689600000000";
    gzWriteCsv(
      dir,
      "incremental_book_L2.csv.gz",
      [
        "exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount",
        `${EXCHANGE},${SYMBOL},${us},${us},true,bid,100,1`,
      ].join("\n") + "\n"
    );
    const v = await validateDay({
      inputPath: tmpRoot,
      symbol: SYMBOL,
      exchange: EXCHANGE,
      date: "2026-03-01",
    });
    expect(v.isValid).toBe(false);
    expect(v.invalidReasons.join(",")).toMatch(/trades/);
  });

  it("treats derivative_ticker / liquidations as optional and does not invalidate the day", async () => {
    // Reuse the valid 2026-01-01 dataset; only check the optional flagging.
    const v = await validateDay({
      inputPath: tmpRoot,
      symbol: SYMBOL,
      exchange: EXCHANGE,
      date: DATE,
    });
    const opt = v.dataTypes.filter((d) => !d.required);
    expect(opt.length).toBeGreaterThanOrEqual(3);
    expect(v.isValid).toBe(true);
  });
});
