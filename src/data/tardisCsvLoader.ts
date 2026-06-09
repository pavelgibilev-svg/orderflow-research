// Streaming gzip CSV reader for Tardis dumps.
//
// Why streaming?
//   incremental_book_L2 for one BTCUSDT day is 200-2000 MB compressed.
//   We MUST never load the full file into memory.
//
// Implementation:
//   Node fs.createReadStream() -> zlib.createGunzip() -> async iterator over
//   bytes. We split on '\n', parse CSV manually (Tardis CSVs have no quoted
//   fields with commas — they only have plain numeric/string columns).
//   This avoids any heavy CSV parser dep.
//
// API:
//   for await (const event of streamTardisFile(path, dataTypeHint)) { ... }
//
// Each yielded event is a typed AnyEvent (see schema.ts).

import * as fs from "node:fs";
import * as zlib from "node:zlib";
import { Readable } from "node:stream";
import {
  type DataType,
  type AnyEvent,
  type BookL2Event,
  type TradeEvent,
  type BookTickerEvent,
  type DerivativeTickerEvent,
  type LiquidationEvent,
  makeIncrementalBookL2Parser,
  makeTradesParser,
  makeBookTickerParser,
  makeDerivativeTickerParser,
  makeLiquidationsParser,
} from "./schema.js";

export interface StreamOpts {
  // Override classification (filename heuristic might fail).
  dataType?: DataType;
  // Maximum number of rows to yield. Useful for inspect:data.
  limit?: number;
  // Reset stats counter for telemetry.
  onProgress?: (rows: number, bytes: number) => void;
  progressEveryRows?: number;
  // If set, the iterator stops as soon as it encounters a row whose `ts`
  // exceeds this value (in ms). Tardis CSVs are time-sorted, so this is
  // safe and lets callers cap I/O when only a portion of the day is needed.
  endTsMs?: number;
}

function* splitLines(chunk: string, leftover: string): IterableIterator<string> {
  // Yields complete lines and returns the new leftover via closure.
  // We use an iterator factory pattern in streamTardisFile instead.
  // (this is a placeholder; not used directly)
  yield leftover + chunk;
}

function parseCsvLine(line: string): string[] {
  // Tardis CSVs use plain ',' separators, no quoting. Fast path.
  return line.split(",");
}

export async function* streamTardisFile(
  filePath: string,
  opts: StreamOpts = {}
): AsyncIterableIterator<AnyEvent> {
  const lower = filePath.toLowerCase();
  const isGz = lower.endsWith(".gz");
  const fileStream = fs.createReadStream(filePath);
  const stream: Readable = isGz ? (fileStream.pipe(zlib.createGunzip()) as Readable) : (fileStream as Readable);

  let leftover = "";
  let headers: string[] | null = null;
  let parser: ((row: string[]) => AnyEvent) | null = null;
  let rows = 0;
  let bytes = 0;
  const progressEvery = opts.progressEveryRows ?? 1_000_000;

  // Build parser lazily once we have headers.
  function buildParser(hdr: string[]): (row: string[]) => AnyEvent {
    const dt = opts.dataType ?? inferType(hdr, filePath);
    if (!dt) throw new Error(`Cannot infer data type for ${filePath}`);
    switch (dt) {
      case "incremental_book_L2":
        return makeIncrementalBookL2Parser(hdr) as (row: string[]) => AnyEvent;
      case "trades":
        return makeTradesParser(hdr) as (row: string[]) => AnyEvent;
      case "book_ticker":
        return makeBookTickerParser(hdr) as (row: string[]) => AnyEvent;
      case "derivative_ticker":
        return makeDerivativeTickerParser(hdr) as (row: string[]) => AnyEvent;
      case "liquidations":
        return makeLiquidationsParser(hdr) as (row: string[]) => AnyEvent;
      default:
        throw new Error(`Unsupported data type: ${dt}`);
    }
  }

  for await (const chunkRaw of stream) {
    const chunk: Buffer = chunkRaw as Buffer;
    bytes += chunk.length;
    const text = leftover + chunk.toString("utf8");
    let start = 0;
    let nl: number;
    while ((nl = text.indexOf("\n", start)) !== -1) {
      let line = text.slice(start, nl);
      start = nl + 1;
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (line.length === 0) continue;
      if (!headers) {
        headers = parseCsvLine(line);
        parser = buildParser(headers);
        continue;
      }
      const row = parseCsvLine(line);
      try {
        const ev = parser!(row);
        rows++;
        if (rows % progressEvery === 0 && opts.onProgress) opts.onProgress(rows, bytes);
        if (opts.endTsMs !== undefined && ev.ts > opts.endTsMs) {
          stream.destroy?.();
          fileStream.destroy?.();
          return;
        }
        yield ev;
        if (opts.limit !== undefined && rows >= opts.limit) return;
      } catch (e) {
        // Skip malformed row — research module shouldn't die on a single bad line.
        continue;
      }
    }
    leftover = text.slice(start);
  }
  // Final flush of any trailing line without newline.
  if (leftover.trim().length > 0 && headers && parser) {
    try {
      const row = parseCsvLine(leftover);
      yield parser(row);
      rows++;
    } catch {
      /* ignore */
    }
  }
  if (opts.onProgress) opts.onProgress(rows, bytes);
}

function inferType(headers: string[], filePath: string): DataType | null {
  const lower = filePath.toLowerCase();
  if (lower.includes("incremental_book_l2")) return "incremental_book_L2";
  if (lower.includes("trades")) return "trades";
  if (lower.includes("book_ticker")) return "book_ticker";
  if (lower.includes("derivative_ticker")) return "derivative_ticker";
  if (lower.includes("liquidations")) return "liquidations";
  // header heuristic
  const set = new Set(headers);
  if (set.has("is_snapshot") && set.has("price") && set.has("amount")) return "incremental_book_L2";
  if (set.has("bid_price") && set.has("ask_price")) return "book_ticker";
  if (set.has("funding_rate") || set.has("mark_price")) return "derivative_ticker";
  if (set.has("price") && set.has("amount") && set.has("side")) return "trades";
  return null;
}

// Convenience: read just the header row of a gzip CSV without consuming the rest.
export async function readHeaderOnly(filePath: string): Promise<string[]> {
  const lower = filePath.toLowerCase();
  const isGz = lower.endsWith(".gz");
  const fileStream = fs.createReadStream(filePath, { highWaterMark: 8192 });
  const stream: Readable = isGz ? (fileStream.pipe(zlib.createGunzip()) as Readable) : (fileStream as Readable);
  let leftover = "";
  for await (const chunkRaw of stream) {
    const chunk: Buffer = chunkRaw as Buffer;
    leftover += chunk.toString("utf8");
    const nl = leftover.indexOf("\n");
    if (nl !== -1) {
      let line = leftover.slice(0, nl);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      stream.destroy?.();
      fileStream.destroy?.();
      return line.split(",");
    }
  }
  return leftover.split(",");
}

export type { AnyEvent, BookL2Event, TradeEvent, BookTickerEvent, DerivativeTickerEvent, LiquidationEvent };
