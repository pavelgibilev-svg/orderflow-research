// Benchmark CLI:
//   npm run bench -- ./data/incremental_book_L2.csv.gz
//   tsx src/benchmark.ts ./data/incremental_book_L2.csv.gz
//
// Measures rows/sec and memory. Stores NOTHING per row (no array growth).
// Exits 1 if throughput < 300_000 rows/sec.

import { parseL2GzipFile } from "./l2-parser.js";
import type { L2ParserCallback } from "./types.js";

const THRESHOLD = 300_000;

function fmtInt(n: number): string {
  return n.toLocaleString("en-US");
}
function fmtMB(bytes: number): string {
  return `${Math.round(bytes / (1024 * 1024))} MB`;
}

async function main(): Promise<void> {
  const filePath = process.argv[2];
  if (!filePath) {
    console.error("usage: tsx src/benchmark.ts <path/to/incremental_book_L2.csv.gz>");
    process.exit(2);
    return;
  }

  let checksum = 0; // consumes the primitives so V8 can't dead-code the parsing
  let peakRss = 0;
  const SAMPLE_MASK = (1 << 22) - 1; // sample memory roughly every ~4.19M rows
  let seen = 0;

  // Minimal callback: touches every primitive cheaply, allocates nothing.
  const onEvent: L2ParserCallback = (timestampNs, sequence, _symbol, side, price, size) => {
    seen++;
    checksum += price + size + side + (timestampNs % 1000) + (sequence & 0xff);
    if ((seen & SAMPLE_MASK) === 0) {
      const rss = process.memoryUsage.rss();
      if (rss > peakRss) peakRss = rss;
    }
  };

  const start = process.hrtime.bigint();
  const { rows } = await parseL2GzipFile(filePath, {
    skipHeader: true,
    parseSymbol: false, // benchmark mode: skip the only per-row string alloc
    onEvent,
  });
  const end = process.hrtime.bigint();

  const seconds = Number(end - start) / 1e9;
  const speed = seconds > 0 ? rows / seconds : 0;

  const mem = process.memoryUsage();
  if (mem.rss > peakRss) peakRss = mem.rss;

  console.log(`File: ${filePath}`);
  console.log(`Rows: ${fmtInt(rows)}`);
  console.log(`Time: ${seconds.toFixed(2)}s`);
  console.log(`Speed: ${fmtInt(Math.round(speed))} rows/sec`);
  console.log("Memory:");
  console.log(`  rss(peak): ${fmtMB(peakRss)}`);
  console.log(`  heapUsed:  ${fmtMB(mem.heapUsed)}`);
  console.log(`  heapTotal: ${fmtMB(mem.heapTotal)}`);
  console.log(`  external:  ${fmtMB(mem.external)}`);
  console.log(`  (checksum guard: ${checksum.toFixed(0)})`);
  console.log("");

  if (speed >= THRESHOLD) {
    console.log(`PASS: speed >= ${fmtInt(THRESHOLD)} rows/sec`);
    process.exit(0);
  } else {
    console.log(`FAIL: speed ${fmtInt(Math.round(speed))} < ${fmtInt(THRESHOLD)} rows/sec`);
    process.exit(1);
  }
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
