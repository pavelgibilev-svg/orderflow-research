// OkxHistoricalDataSource — minimal wrapper around the existing
// Tardis-canonical CSV.gz loader that exposes an iterator-style API for
// OKX-swap data on a per-symbol/per-date folder.
//
// It does NOT implement the full MarketDataSource interface used by the
// ClickHouse backtest path. The reason: our existing src/cli/backtestDay.ts
// already reads OKX-swap CSV files directly via resolveInputFiles +
// replayFiles (the column schema is identical). This adapter is a typed
// facade for tests + cross-venue research scripts; the backtest CLI path
// can stay as-is.

import * as fs from "node:fs";
import * as path from "node:path";
import { OKX_SWAP_EXCHANGE_SLUG, type OkxDataType } from "./okxTardisSchema.js";

export interface OkxDayLocator {
  /** Absolute or relative root that contains the per-symbol/per-date folder. */
  root: string;
  /** "BTC-USDT-SWAP" */
  symbol: string;
  /** "YYYY-MM-DD" */
  date: string;
}

export interface OkxFileEntry {
  dataType: OkxDataType;
  path: string;
  sizeBytes: number;
}

/** Returns the canonical on-disk folder for a downloaded OKX day. */
export function okxDayDir(loc: OkxDayLocator): string {
  return path.join(loc.root, loc.symbol, loc.date);
}

/** Scan the day folder and list every supported OKX data file present. */
export function listOkxDayFiles(loc: OkxDayLocator): OkxFileEntry[] {
  const dir = okxDayDir(loc);
  if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) return [];
  const dataTypes: OkxDataType[] = [
    "incremental_book_L2",
    "trades",
    "book_ticker",
    "derivative_ticker",
    "liquidations",
  ];
  const out: OkxFileEntry[] = [];
  for (const t of dataTypes) {
    const candidates = [
      path.join(dir, `${t}.csv.gz`),
      path.join(dir, `${loc.symbol}_${t}_${loc.date}.csv.gz`),
    ];
    for (const p of candidates) {
      if (fs.existsSync(p) && fs.statSync(p).isFile()) {
        out.push({ dataType: t, path: p, sizeBytes: fs.statSync(p).size });
        break;
      }
    }
  }
  return out;
}

/** Quick presence summary for an OKX day. */
export function okxDayStatus(loc: OkxDayLocator): {
  exchange: string;
  symbol: string;
  date: string;
  dir: string;
  exists: boolean;
  files_present: OkxDataType[];
  files_missing: OkxDataType[];
  total_bytes: number;
} {
  const dir = okxDayDir(loc);
  const exists = fs.existsSync(dir);
  const files = exists ? listOkxDayFiles(loc) : [];
  const present = new Set(files.map((f) => f.dataType));
  const all: OkxDataType[] = [
    "incremental_book_L2",
    "trades",
    "book_ticker",
    "derivative_ticker",
    "liquidations",
  ];
  return {
    exchange: OKX_SWAP_EXCHANGE_SLUG,
    symbol: loc.symbol,
    date: loc.date,
    dir,
    exists,
    files_present: all.filter((t) => present.has(t)),
    files_missing: all.filter((t) => !present.has(t)),
    total_bytes: files.reduce((s, f) => s + f.sizeBytes, 0),
  };
}
