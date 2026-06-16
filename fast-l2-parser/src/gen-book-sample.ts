// Bonus: generate a VALID (never-crossed) L2 stream in the 6-column spec schema
// so `npm run bench:book` runs end-to-end without the real OKX file.
//
//   tsx src/gen-book-sample.ts ./data/book.csv.gz 5000000
//
// Bids live strictly in [MID-DEPTH, MID-1], asks in [MID+1, MID+DEPTH], so the
// book is always valid regardless of inserts/deletes. Multiple updates share a
// timestamp (to exercise batch logic); sequence is monotonic +1.

import { createWriteStream } from "node:fs";
import { createGzip } from "node:zlib";
import { pipeline } from "node:stream/promises";
import { Readable } from "node:stream";

const out = process.argv[2] ?? "./data/book.csv.gz";
const rows = Number(process.argv[3] ?? 5_000_000);

const MID = 43000;
const DEPTH = 50;
const BATCH = 4; // updates per timestamp

function* gen(): Generator<string> {
  yield "timestamp_ns,sequence,symbol,side,price,size\n";
  let ts = 1_700_000_000_000_000_000n; // exact ns; bumped once per batch (cheap)
  // mulberry32 — fast pure-number PRNG (no BigInt in the hot loop).
  let s = 0x9e3779b9 >>> 0;
  const next = (): number => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return (t ^ (t >>> 14)) >>> 0;
  };
  for (let i = 0; i < rows; i++) {
    if (i % BATCH === 0) ts += 1000n;
    const r = next();
    const isBid = (r & 1) === 0;
    const offset = 1 + (r % DEPTH); // 1..DEPTH
    const price = isBid ? MID - offset : MID + offset;
    // ~12% deletes (size 0), else a positive size.
    const size = r % 8 === 0 ? 0 : (r % 1000) / 100 + 0.01;
    yield `${ts},${i + 1},BTCUSDT,${isBid ? "bid" : "ask"},${price.toFixed(1)},${size.toFixed(3)}\n`;
  }
}

await pipeline(Readable.from(gen()), createGzip({ level: 6 }), createWriteStream(out));
console.log(`wrote ${rows.toLocaleString("en-US")} rows -> ${out}`);
