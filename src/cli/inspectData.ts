// `npm run inspect:data -- --input ./data/sample --symbol BTCUSDT --date 2020-02-01`
//
// Prints a quick summary of which Tardis CSV files are visible, what columns
// they expose, and a few sample rows. NO replay or strategy work is done.

import * as fs from "node:fs";
import { parseArgs, getString } from "./args.js";
import { resolveInputFiles } from "../data/fileResolver.js";
import { readHeaderOnly, streamTardisFile } from "../data/tardisCsvLoader.js";

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const input = getString(args, "input");
  const symbol = getString(args, "symbol");
  const date = getString(args, "date", "");

  if (!fs.existsSync(input)) {
    console.error(`ERROR: --input path not found: ${input}`);
    process.exit(1);
  }

  console.log(`Inspecting input=${input} symbol=${symbol} date=${date || "(any)"}`);
  const { files, missing } = resolveInputFiles(input, symbol, date);
  if (files.length === 0) {
    console.error("ERROR: no Tardis CSV files matched your filters.");
    console.error("Hint: filenames must contain the data type, the symbol, and the date.");
    process.exit(2);
  }
  console.log(`Resolved ${files.length} file(s):`);
  for (const f of files) {
    const size = fs.statSync(f.path).size;
    console.log(`  - ${f.dataType.padEnd(22)} ${formatBytes(size).padStart(10)}  ${f.path}`);
  }
  if (missing.length > 0) {
    console.log(`Missing required types: ${missing.join(", ")}`);
  }

  for (const f of files) {
    const headers = await readHeaderOnly(f.path);
    console.log(`\n>>> ${f.dataType}`);
    console.log(`columns: ${headers.join(", ")}`);
    console.log(`first 3 rows:`);
    let n = 0;
    for await (const ev of streamTardisFile(f.path, { dataType: f.dataType, limit: 3 })) {
      console.log(`  ${JSON.stringify(ev)}`);
      n++;
      if (n >= 3) break;
    }
  }
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
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
