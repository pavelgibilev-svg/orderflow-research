// Bonus helper — generate a synthetic spec-schema sample so `npm run bench`
// is runnable end-to-end without the real (8-column) Tardis file.
//
//   tsx src/gen-sample.ts ./data/incremental_book_L2.csv.gz 5000000
//
// Schema: timestamp_ns,sequence,symbol,side,price,size

import { createWriteStream } from "node:fs";
import { createGzip } from "node:zlib";
import { pipeline } from "node:stream/promises";
import { Readable } from "node:stream";

const out = process.argv[2] ?? "./data/incremental_book_L2.csv.gz";
const rows = Number(process.argv[3] ?? 5_000_000);

function* gen(): Generator<string> {
  yield "timestamp_ns,sequence,symbol,side,price,size\n";
  let ts = 1_700_000_000_000_000_000n; // nanoseconds
  let price = 43000;
  for (let i = 0; i < rows; i++) {
    ts += 1000n;
    price += (i % 7) - 3;
    const side = (i & 1) === 0 ? "bid" : "ask";
    const size = (i % 1000) / 1000 + 0.001;
    yield `${ts},${i + 1},BTCUSDT,${side},${price.toFixed(1)},${size.toFixed(3)}\n`;
  }
}

await pipeline(Readable.from(gen()), createGzip({ level: 6 }), createWriteStream(out));
console.log(`wrote ${rows.toLocaleString("en-US")} rows -> ${out}`);
