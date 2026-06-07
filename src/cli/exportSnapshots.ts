// `npm run export:snapshots -- --input ./data/sample --symbol BTCUSDT --date 2020-02-01 --interval 1s --depth 50`
//
// Reconstructs the order book from incremental_book_L2 and exports periodic
// snapshots to JSONL (one JSON object per line). We don't load all snapshots
// into RAM — they're streamed straight to disk.

import * as fs from "node:fs";
import * as path from "node:path";
import { parseArgs, getString } from "./args.js";
import { resolveInputFiles } from "../data/fileResolver.js";
import { streamTardisFile } from "../data/tardisCsvLoader.js";
import { OrderBook } from "../replay/orderBook.js";
import { exportSnapshot } from "../replay/snapshotBuilder.js";
import { parseInterval } from "../data/time.js";
import type { BookL2Event } from "../data/schema.js";

export interface ExportSnapshotsOpts {
  input: string;
  symbol: string;
  date?: string;
  interval: string; // "1s", "100ms", ...
  depth: number;
  outDir?: string;
}

export interface ExportSnapshotsResult {
  outPath: string;
  count: number;
  durationMs: number;
}

export async function runExportSnapshots(opts: ExportSnapshotsOpts): Promise<ExportSnapshotsResult> {
  const intervalMs = parseInterval(opts.interval);
  const { files } = resolveInputFiles(opts.input, opts.symbol, opts.date ?? "");
  const l2 = files.find((f) => f.dataType === "incremental_book_L2");
  if (!l2) {
    throw new Error(`incremental_book_L2 file not found in ${opts.input} for ${opts.symbol} ${opts.date ?? ""}`);
  }

  const outDir = opts.outDir ?? path.join("reports", `${opts.symbol}_${opts.date ?? "any"}_snapshots`);
  fs.mkdirSync(outDir, { recursive: true });
  const outPath = path.join(outDir, `snapshots_${opts.interval}_d${opts.depth}.jsonl`);
  const out = fs.createWriteStream(outPath, { encoding: "utf8" });

  const book = new OrderBook();
  let nextSnapshotTs = 0;
  let count = 0;
  const start = Date.now();
  for await (const ev of streamTardisFile(l2.path, { dataType: "incremental_book_L2" })) {
    const e = ev as BookL2Event;
    if (nextSnapshotTs === 0) nextSnapshotTs = Math.ceil(e.ts / intervalMs) * intervalMs;
    while (e.ts >= nextSnapshotTs) {
      const snap = exportSnapshot(book, nextSnapshotTs, opts.depth);
      out.write(JSON.stringify(snap) + "\n");
      count++;
      nextSnapshotTs += intervalMs;
    }
    book.apply({
      ts: e.ts,
      isSnapshot: e.isSnapshot,
      side: e.side,
      price: e.price,
      amount: e.amount,
    });
  }
  // Final snapshot at the end.
  const snap = exportSnapshot(book, nextSnapshotTs, opts.depth);
  out.write(JSON.stringify(snap) + "\n");
  count++;
  out.end();
  await new Promise<void>((resolve) => out.on("close", () => resolve()));
  const durationMs = Date.now() - start;
  return { outPath, count, durationMs };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const input = getString(args, "input");
  const symbol = getString(args, "symbol");
  const date = getString(args, "date", "");
  const interval = getString(args, "interval", "1s");
  const depth = parseInt(getString(args, "depth", "50"), 10);
  const outDirArg = getString(args, "out", "");

  const r = await runExportSnapshots({
    input,
    symbol,
    date,
    interval,
    depth,
    outDir: outDirArg || undefined,
  });
  console.log(`Wrote ${r.count} snapshots to ${r.outPath} in ${(r.durationMs / 1000).toFixed(2)}s`);
}

import { pathToFileURL } from "node:url";
const __isMain =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href;
if (__isMain) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
