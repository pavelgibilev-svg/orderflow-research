// Pure functions used by the downloader scripts and tested from JS.
// Keeping the URL/path logic as TS code lets us unit-test that:
//   - we never emit URLs for May 2026 or any future month;
//   - the directory layout matches data/tardis/{exchange}/{symbol}/{date}/{dataType}.csv.gz.

import * as path from "node:path";
import type { DataType } from "./schema.js";

export const SAMPLE_2026_DATES: ReadonlyArray<string> = [
  "2026-01-01",
  "2026-02-01",
  "2026-03-01",
  "2026-04-01",
];

export const SAMPLE_2026_DATA_TYPES: ReadonlyArray<DataType> = [
  "incremental_book_L2",
  "trades",
  "derivative_ticker",
  "book_ticker",
  "liquidations",
];

export const SAMPLE_2026_REQUIRED: ReadonlyArray<DataType> = ["incremental_book_L2", "trades"];

export const TARDIS_BASE_URL = "https://datasets.tardis.dev/v1";

export interface DownloadEntry {
  date: string;
  dataType: DataType;
  url: string;
  /** Relative output path (POSIX-style separators). */
  outRelPath: string;
}

/** Builds the deterministic download plan used by all three scripts. */
export function buildSample2026DownloadPlan(opts: {
  exchange: string;
  symbol: string;
  outRoot?: string;
  dates?: ReadonlyArray<string>;
  dataTypes?: ReadonlyArray<DataType>;
}): DownloadEntry[] {
  const exchange = opts.exchange;
  const symbol = opts.symbol;
  const outRoot = opts.outRoot ?? "data/tardis";
  const dates = opts.dates ?? SAMPLE_2026_DATES;
  const dataTypes = opts.dataTypes ?? SAMPLE_2026_DATA_TYPES;

  // Hard guard: never include 2026-05 or any 2026-06+ in this sample.
  for (const d of dates) {
    if (!/^2026-(01|02|03|04)-01$/.test(d)) {
      throw new Error(`Date ${d} is not allowed in the YTD-except-May sample. Allowed: 2026-01-01..2026-04-01.`);
    }
  }

  const out: DownloadEntry[] = [];
  for (const d of dates) {
    const [yyyy, mm, dd] = d.split("-");
    for (const t of dataTypes) {
      const url = `${TARDIS_BASE_URL}/${exchange}/${t}/${yyyy}/${mm}/${dd}/${symbol}.csv.gz`;
      const outRel = `${outRoot}/${exchange}/${symbol}/${d}/${t}.csv.gz`;
      out.push({ date: d, dataType: t, url, outRelPath: outRel });
    }
  }
  return out;
}

/** Resolve a per-day folder under the standard layout. */
export function dayFolder(opts: {
  outRoot: string;
  exchange: string;
  symbol: string;
  date: string;
}): string {
  return path.join(opts.outRoot, opts.exchange, opts.symbol, opts.date);
}
