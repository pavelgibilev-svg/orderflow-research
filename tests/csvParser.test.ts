import { describe, expect, it } from "vitest";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import * as zlib from "node:zlib";
import { streamTardisFile } from "../src/data/tardisCsvLoader.js";
import {
  makeIncrementalBookL2Parser,
  makeTradesParser,
  dataTypeFromHeaders,
} from "../src/data/schema.js";

function gzWriteTmp(content: string, name: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ofr-"));
  const p = path.join(dir, name);
  const buf = zlib.gzipSync(Buffer.from(content, "utf8"));
  fs.writeFileSync(p, buf);
  return p;
}

describe("Tardis CSV parsers", () => {
  it("dataTypeFromHeaders identifies incremental_book_L2", () => {
    expect(
      dataTypeFromHeaders(["exchange", "symbol", "timestamp", "local_timestamp", "is_snapshot", "side", "price", "amount"])
    ).toBe("incremental_book_L2");
  });

  it("incremental_book_L2 parser converts microseconds and amount=0 deletes", () => {
    const headers = ["exchange", "symbol", "timestamp", "local_timestamp", "is_snapshot", "side", "price", "amount"];
    const parse = makeIncrementalBookL2Parser(headers);
    const row = parse(["binance-futures", "BTCUSDT", "1580515200000000", "1580515200000010", "true", "bid", "9300.0", "0.5"]);
    expect(row.ts).toBe(1580515200000); // ms
    expect(row.isSnapshot).toBe(true);
    expect(row.side).toBe("bid");
    expect(row.price).toBe(9300);
    expect(row.amount).toBe(0.5);

    const del = parse(["binance-futures", "BTCUSDT", "1580515201000000", "0", "false", "ask", "9301", "0"]);
    expect(del.amount).toBe(0);
    expect(del.side).toBe("ask");
  });

  it("trades parser yields buy/sell sides", () => {
    const headers = ["exchange", "symbol", "timestamp", "local_timestamp", "id", "side", "price", "amount"];
    const parse = makeTradesParser(headers);
    const buy = parse(["binance-futures", "BTCUSDT", "1580515200000000", "0", "1", "buy", "9300", "0.1"]);
    const sell = parse(["binance-futures", "BTCUSDT", "1580515201000000", "0", "2", "sell", "9301", "0.2"]);
    expect(buy.side).toBe("buy");
    expect(sell.side).toBe("sell");
    expect(buy.amount).toBe(0.1);
  });

  it("streaming gzip CSV yields all rows in order", async () => {
    // Tardis stores µs since epoch. 1_000_000 µs = 1_000 ms.
    const csv =
      "exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount\n" +
      "binance-futures,BTCUSDT,1000000,1000010,true,bid,100,1\n" +
      "binance-futures,BTCUSDT,2000000,2000010,false,ask,101,2\n" +
      "binance-futures,BTCUSDT,3000000,3000010,false,ask,101,0\n";
    const p = gzWriteTmp(csv, "incremental_book_L2.csv.gz");
    const rows: any[] = [];
    for await (const ev of streamTardisFile(p)) rows.push(ev);
    expect(rows).toHaveLength(3);
    expect(rows[0].ts).toBe(1000);
    expect(rows[1].ts).toBe(2000);
    expect(rows[2].amount).toBe(0);
  });
});
