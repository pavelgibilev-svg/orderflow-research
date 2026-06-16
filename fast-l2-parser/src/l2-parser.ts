// Streaming parser for `incremental_book_L2.csv.gz`.
//
// Pipeline: fs.createReadStream -> zlib.createGunzip -> custom Writable sink.
// Inside the sink we do MANUAL line + field scanning at the Buffer level:
//   * newline (0x0A) is found with Buffer.indexOf (native memchr — the fastest
//     possible byte search; this is NOT readline and NOT split);
//   * fields are split by scanning for commas (0x2C) in a single pass and
//     dispatched by FIXED column index — no per-line array, no per-line object;
//   * numbers are parsed byte-by-byte (see fast-number.ts);
//   * `symbol` is the only field decoded to a JS string, and only when asked.
//
// Lines that straddle a chunk boundary are stitched via a small reusable
// `pending` buffer; the bulk of every chunk is parsed IN PLACE with zero copy.

import { createReadStream } from "node:fs";
import { createGunzip } from "node:zlib";
import { pipeline } from "node:stream/promises";
import { Writable } from "node:stream";
import type { L2ParserCallback, Side } from "./types.js";
import {
  parseUnsignedIntFromBuffer,
  parseDecimalFromBuffer,
  parseSideFromBuffer,
} from "./fast-number.js";

// ============================================================================
// STATIC COLUMN SCHEMA  (header: timestamp_ns,sequence,symbol,side,price,size)
// Column order is HARD-CODED by index — no header lookup in the hot path.
// ----------------------------------------------------------------------------
// To adapt to the real Tardis OKX file, whose header is:
//   exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount
// change ONLY these constants:
//   COL_TIMESTAMP_NS = 2   (this column is in MICROSECONDS — still fits a number)
//   COL_SEQUENCE     = -1  (no sequence column — see note in parseLine)
//   COL_SYMBOL       = 1
//   COL_SIDE         = 5
//   COL_PRICE        = 6
//   COL_SIZE         = 7
//   EXPECTED_COLUMNS = 8
// Nothing else changes — the parseLine switch dispatches purely by index.
// ============================================================================
const COL_TIMESTAMP_NS = 0;
const COL_SEQUENCE = 1;
const COL_SYMBOL = 2;
const COL_SIDE = 3;
const COL_PRICE = 4;
const COL_SIZE = 5;
const EXPECTED_COLUMNS = 6;

const NL = 0x0a; // '\n'
const CR = 0x0d; // '\r'
const COMMA = 0x2c; // ','
const EMPTY_SYMBOL = "";

export interface L2ParserOptions {
  /** Skip the first (header) line. Default true. */
  skipHeader?: boolean;
  /** Decode the `symbol` field to a JS string. Set false in benchmarks to skip
   *  the only per-row string allocation. Default true. */
  parseSymbol?: boolean;
  /** Guard against a pathological line with no newline (bytes). Default 1 MiB. */
  maxLineLength?: number;
  /** highWaterMark for the file read + gunzip + sink (bytes). Default 1 MiB. */
  highWaterMark?: number;
  /** Flat primitive callback invoked once per data row. */
  onEvent: L2ParserCallback;
}

class LineParser {
  rows = 0;

  private pending: Buffer;
  private pendingLen = 0;
  private headerHandled = false;

  private readonly onEvent: L2ParserCallback;
  private readonly skipHeader: boolean;
  private readonly parseSymbol: boolean;
  private readonly maxLineLength: number;

  constructor(opts: L2ParserOptions) {
    this.onEvent = opts.onEvent;
    this.skipHeader = opts.skipHeader ?? true;
    this.parseSymbol = opts.parseSymbol ?? true;
    this.maxLineLength = opts.maxLineLength ?? 1 << 20;
    // Reusable scratch buffer for boundary-straddling lines only.
    this.pending = Buffer.allocUnsafe(64 * 1024);
  }

  /** Feed one decompressed chunk. Lines fully inside the chunk are parsed in place. */
  push(chunk: Buffer): void {
    const len = chunk.length;
    let lineStart = 0;

    // (1) Complete a line that started in a previous chunk.
    if (this.pendingLen > 0) {
      const nl = chunk.indexOf(NL, 0);
      if (nl === -1) {
        // Whole chunk is still the same unterminated line — carry it over.
        this.appendPending(chunk, 0, len);
        return;
      }
      this.appendPending(chunk, 0, nl);
      this.consumePending();
      lineStart = nl + 1;
    }

    // (2) Main loop: scan newlines natively, parse each complete line in place.
    while (lineStart < len) {
      const nl = chunk.indexOf(NL, lineStart);
      if (nl === -1) break;
      let end = nl;
      if (end > lineStart && chunk[end - 1] === CR) end--; // strip CRLF's '\r'
      this.handleLine(chunk, lineStart, end);
      lineStart = nl + 1;
    }

    // (3) Carry the unterminated tail to the next chunk.
    if (lineStart < len) this.appendPending(chunk, lineStart, len);
  }

  /** Called once at end-of-stream — handles a final line with no trailing '\n'. */
  flush(): void {
    if (this.pendingLen > 0) {
      let end = this.pendingLen;
      if (end > 0 && this.pending[end - 1] === CR) end--;
      this.handleLine(this.pending, 0, end);
      this.pendingLen = 0;
    }
  }

  private consumePending(): void {
    let end = this.pendingLen;
    if (end > 0 && this.pending[end - 1] === CR) end--;
    this.handleLine(this.pending, 0, end);
    this.pendingLen = 0;
  }

  private handleLine(buf: Buffer, start: number, end: number): void {
    if (end <= start) return; // empty line — skip
    if (this.skipHeader && !this.headerHandled) {
      this.headerHandled = true; // first non-empty line is the header
      return;
    }
    this.parseLine(buf, start, end);
  }

  /**
   * Single-pass field split + typed dispatch by fixed column index.
   * No array of fields is built; no event object is allocated. The terminator
   * for the last field is the line end (handled by the `i === end` branch).
   */
  private parseLine(buf: Buffer, start: number, end: number): void {
    let field = 0;
    let fStart = start;

    let timestampNs = 0;
    let sequence = 0;
    let side: Side = 0;
    let price = 0;
    let size = 0;
    let symStart = 0;
    let symEnd = 0;

    for (let i = start; i <= end; i++) {
      if (i === end || buf[i] === COMMA) {
        const fEnd = i;
        switch (field) {
          case COL_TIMESTAMP_NS:
            timestampNs = parseUnsignedIntFromBuffer(buf, fStart, fEnd);
            break;
          case COL_SEQUENCE:
            sequence = parseUnsignedIntFromBuffer(buf, fStart, fEnd);
            break;
          case COL_SYMBOL:
            symStart = fStart;
            symEnd = fEnd;
            break;
          case COL_SIDE:
            side = parseSideFromBuffer(buf, fStart, fEnd);
            break;
          case COL_PRICE:
            price = parseDecimalFromBuffer(buf, fStart, fEnd);
            break;
          case COL_SIZE:
            size = parseDecimalFromBuffer(buf, fStart, fEnd);
            break;
          default:
            break; // surplus columns: ignored here, caught by the count check
        }
        field++;
        fStart = i + 1;
      }
    }

    if (field !== EXPECTED_COLUMNS) {
      throw new Error(
        `row ${this.rows + 1}: expected ${EXPECTED_COLUMNS} columns, got ${field} — ` +
          `"${buf.toString("utf8", start, end)}"`
      );
    }

    // Only allocation that can happen per row — opt-out via parseSymbol:false.
    const symbol = this.parseSymbol ? buf.toString("utf8", symStart, symEnd) : EMPTY_SYMBOL;

    this.rows++;
    this.onEvent(timestampNs, sequence, symbol, side, price, size);
  }

  /** Append [start, end) of `src` to the reusable pending buffer, growing if needed. */
  private appendPending(src: Buffer, start: number, end: number): void {
    const len = end - start;
    if (len <= 0) return;
    const need = this.pendingLen + len;
    if (need > this.pending.length) {
      let cap = this.pending.length * 2;
      while (cap < need) cap *= 2;
      const grown = Buffer.allocUnsafe(cap);
      this.pending.copy(grown, 0, 0, this.pendingLen);
      this.pending = grown;
    }
    src.copy(this.pending, this.pendingLen, start, end);
    this.pendingLen = need;
    if (this.pendingLen > this.maxLineLength) {
      throw new Error(`line exceeds maxLineLength=${this.maxLineLength} bytes (no newline found)`);
    }
  }
}

/**
 * Stream a gzipped L2 CSV file and invoke `onEvent` for each data row.
 * Resolves with the number of data rows parsed (header excluded).
 *
 * Backpressure & lifecycle are handled by `stream/promises.pipeline`:
 * the file feeds gunzip, gunzip feeds the sink, and the sink's `write`
 * callback paces decompression. Errors from any stage reject the promise;
 * `pipeline` also destroys all streams on failure (no leaks).
 */
export async function parseL2GzipFile(
  filePath: string,
  options: L2ParserOptions
): Promise<{ rows: number }> {
  const parser = new LineParser(options);
  const hwm = options.highWaterMark ?? 1 << 20; // 1 MiB

  const fileStream = createReadStream(filePath, { highWaterMark: hwm });
  const gunzip = createGunzip({ chunkSize: hwm });

  const sink = new Writable({
    highWaterMark: hwm,
    // decodeStrings stays true (default) -> chunk is always a Buffer.
    write(chunk: Buffer, _enc: BufferEncoding, cb: (err?: Error | null) => void): void {
      try {
        parser.push(chunk);
        cb();
      } catch (err) {
        cb(err as Error);
      }
    },
    final(cb: (err?: Error | null) => void): void {
      try {
        parser.flush();
        cb();
      } catch (err) {
        cb(err as Error);
      }
    },
  });

  await pipeline(fileStream, gunzip, sink);
  return { rows: parser.rows };
}
