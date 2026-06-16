// Order-book builder benchmark:
//   npm run bench:book -- ./data/incremental_book_L2.csv.gz
//
// Wires the task-1 fast parser -> dispatcher -> OrderBookBuilder, measures
// updates/sec and final book state. Exits 1 if throughput < 300_000 updates/sec.
//
// NOTE: validateSequence is OFF here because the real Tardis OKX schema has no
// sequence column. The 6-column spec sample also carries no is_snapshot column,
// so every row is fed as an incremental update (isSnapshot=false). For real OKX
// data with snapshots, extend the parser to emit the is_snapshot column (index
// 4 in `exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount`)
// and pass it through to dispatcher.onUpdate(...).

import { parseL2GzipFile } from "./l2-parser.js";
import type { L2ParserCallback } from "./types.js";
import { OrderBookBuilder } from "./order-book.js";
import { OrderBookTimestampDispatcher } from "./order-book-dispatcher.js";

const THRESHOLD = 300_000;
const fmtInt = (n: number) => n.toLocaleString("en-US");
const fmtMB = (b: number) => `${Math.round(b / (1024 * 1024))} MB`;

async function main(): Promise<void> {
  const filePath = process.argv[2];
  if (!filePath) {
    console.error("usage: tsx src/order-book-benchmark.ts <path/to/incremental_book_L2.csv.gz>");
    process.exit(2);
    return;
  }

  const book = new OrderBookBuilder({ validateSequence: false });
  const dispatcher = new OrderBookTimestampDispatcher(book);

  // Flat callback -> dispatcher; no object allocated per update.
  const onEvent: L2ParserCallback = (timestampNs, sequence, _symbol, side, price, size) => {
    dispatcher.onUpdate(timestampNs, sequence, side, price, size, false);
  };

  const start = process.hrtime.bigint();
  const { rows } = await parseL2GzipFile(filePath, { skipHeader: true, parseSymbol: false, onEvent });
  dispatcher.finish();
  const end = process.hrtime.bigint();

  const seconds = Number(end - start) / 1e9;
  const speed = seconds > 0 ? rows / seconds : 0;
  const mem = process.memoryUsage();
  const spread = book.getSpread();

  console.log(`File: ${filePath}`);
  console.log(`Updates: ${fmtInt(rows)}`);
  console.log(`Time: ${seconds.toFixed(2)}s`);
  console.log(`Speed: ${fmtInt(Math.round(speed))} updates/sec`);
  console.log("Book:");
  console.log(`  bidDepth: ${fmtInt(book.getBidDepth())}`);
  console.log(`  askDepth: ${fmtInt(book.getAskDepth())}`);
  console.log(`  bestBid:  ${book.getBestBid() ?? "—"}`);
  console.log(`  bestAsk:  ${book.getBestAsk() ?? "—"}`);
  console.log(`  spread:   ${spread === undefined ? "—" : spread}`);
  console.log("Memory:");
  console.log(`  rss:       ${fmtMB(mem.rss)}`);
  console.log(`  heapUsed:  ${fmtMB(mem.heapUsed)}`);
  console.log(`  heapTotal: ${fmtMB(mem.heapTotal)}`);
  console.log(`  external:  ${fmtMB(mem.external)}`);
  console.log("");

  if (speed >= THRESHOLD) {
    console.log(`PASS: speed >= ${fmtInt(THRESHOLD)} updates/sec`);
    process.exit(0);
  } else {
    console.log(`FAIL: speed ${fmtInt(Math.round(speed))} < ${fmtInt(THRESHOLD)} updates/sec`);
    process.exit(1);
  }
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
