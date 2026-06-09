// Resolve Tardis CSV gzip files for a given symbol/date inside a folder
// or archive. The expected layout (matches the bundled downloader script):
//
//   <input>/
//     tardis_<exchange>_<SYMBOL>_<YYYY-MM-DD>/
//       <SYMBOL>_incremental_book_L2_<DATE>.csv.gz
//       <SYMBOL>_trades_<DATE>.csv.gz
//       <SYMBOL>_derivative_ticker_<DATE>.csv.gz
//       <SYMBOL>_liquidations_<DATE>.csv.gz
//       <SYMBOL>_book_ticker_<DATE>.csv.gz
//
// We're tolerant: any *.csv.gz under <input> whose filename contains the
// data-type keyword and the symbol (case-insensitive) is accepted.

import * as fs from "node:fs";
import * as path from "node:path";
import type { DataType } from "./schema.js";

export interface ResolvedFile {
  path: string;
  dataType: DataType;
  symbol: string;
  date: string;
}

const DATA_TYPE_TOKENS: Array<{ type: DataType; tokens: string[] }> = [
  { type: "incremental_book_L2", tokens: ["incremental_book_l2", "incremental_book_L2"] },
  { type: "trades", tokens: ["trades"] },
  { type: "book_ticker", tokens: ["book_ticker"] },
  { type: "derivative_ticker", tokens: ["derivative_ticker"] },
  { type: "liquidations", tokens: ["liquidations"] },
  { type: "book_snapshot_25", tokens: ["book_snapshot_25"] },
  { type: "book_snapshot_5", tokens: ["book_snapshot_5"] },
  { type: "quotes", tokens: ["quotes"] },
];

function classify(filename: string): DataType | null {
  const lower = filename.toLowerCase();
  for (const { type, tokens } of DATA_TYPE_TOKENS) {
    for (const t of tokens) {
      if (lower.includes(t.toLowerCase())) return type;
    }
  }
  return null;
}

function walk(dir: string, out: string[]): void {
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) walk(full, out);
    else if (e.isFile()) out.push(full);
  }
}

export function resolveInputFiles(
  input: string,
  symbol: string,
  date: string
): { files: ResolvedFile[]; missing: DataType[] } {
  const stat = fs.statSync(input);
  const all: string[] = [];
  if (stat.isDirectory()) {
    walk(input, all);
  } else {
    all.push(input);
  }
  const symLower = symbol.toLowerCase();
  const matched: ResolvedFile[] = [];
  for (const p of all) {
    if (!p.toLowerCase().endsWith(".csv.gz") && !p.toLowerCase().endsWith(".csv")) continue;
    const base = path.basename(p);
    const dataType = classify(base);
    if (!dataType) continue;
    // Symbol / date may live in the filename OR in any path component
    // (e.g. data/tardis/binance-futures/BTCUSDT/2026-01-01/incremental_book_L2.csv.gz).
    const fullLower = p.toLowerCase().replace(/\\/g, "/");
    if (!fullLower.includes(symLower)) continue;
    if (date && !fullLower.includes(date)) continue;
    matched.push({ path: p, dataType, symbol, date });
  }
  // De-duplicate by dataType, keeping the largest file for each.
  const byType = new Map<DataType, ResolvedFile>();
  for (const f of matched) {
    const prev = byType.get(f.dataType);
    if (!prev) byType.set(f.dataType, f);
    else {
      const a = fs.statSync(prev.path).size;
      const b = fs.statSync(f.path).size;
      if (b > a) byType.set(f.dataType, f);
    }
  }
  const required: DataType[] = ["incremental_book_L2", "trades"];
  const missing = required.filter((t) => !byType.has(t));
  return { files: Array.from(byType.values()), missing };
}
