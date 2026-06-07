// Batched writer: enqueue rows by table, flush in batches of N or every M ms.
// On ClickHouse failure, append to spool and retry on next flush. The writer
// also has a `recoverSpool()` method that re-inserts spooled rows.

import type { ClickHouseClient } from "./clickhouseClient.js";
import { SpoolWriter } from "./spoolWriter.js";

export interface BatchWriterOptions {
  ch: ClickHouseClient;
  spool: SpoolWriter;
  /** Max rows per table buffer before forcing a flush. */
  maxBatchSize?: number;
  /** Max ms between flushes. */
  flushIntervalMs?: number;
  /** Optional logger. */
  log?: (level: "info" | "warn" | "error", msg: string, extra?: unknown) => void;
}

export interface BatchWriterStats {
  pending: { [table: string]: number };
  inserted: number;
  spooled: number;
  recovered: number;
  flushFailures: number;
  lastFlushMs: number;
}

export class BatchWriter {
  private readonly ch: ClickHouseClient;
  private readonly spool: SpoolWriter;
  private readonly maxBatchSize: number;
  private readonly flushIntervalMs: number;
  private readonly log: (level: "info" | "warn" | "error", msg: string, extra?: unknown) => void;
  private readonly buffers = new Map<string, Array<Record<string, unknown>>>();
  private timer: NodeJS.Timeout | null = null;
  private inserted = 0;
  private spooled = 0;
  private recovered = 0;
  private flushFailures = 0;
  private lastFlushMs = 0;
  private stopping = false;

  constructor(opts: BatchWriterOptions) {
    this.ch = opts.ch;
    this.spool = opts.spool;
    this.maxBatchSize = opts.maxBatchSize ?? 5000;
    this.flushIntervalMs = opts.flushIntervalMs ?? 1000;
    this.log = opts.log ?? (() => undefined);
  }

  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => {
      this.flushAll().catch((e) => this.log("error", "flushAll failed", e));
    }, this.flushIntervalMs);
    if (this.timer.unref) this.timer.unref();
  }

  async stop(): Promise<void> {
    this.stopping = true;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    await this.flushAll();
  }

  /** Queue a single row for `table`. Auto-flushes when the buffer hits maxBatchSize. */
  enqueue(table: string, row: Record<string, unknown>): void {
    let buf = this.buffers.get(table);
    if (!buf) {
      buf = [];
      this.buffers.set(table, buf);
    }
    buf.push(row);
    if (buf.length >= this.maxBatchSize) {
      // Detach and flush the buffer asynchronously.
      const drained = buf;
      this.buffers.set(table, []);
      this.flushOne(table, drained).catch((e) => this.log("error", `flush of ${table} failed`, e));
    }
  }

  /** Bulk enqueue (preserves the insertion order). */
  enqueueMany(table: string, rows: ReadonlyArray<Record<string, unknown>>): void {
    if (rows.length === 0) return;
    let buf = this.buffers.get(table);
    if (!buf) {
      buf = [];
      this.buffers.set(table, buf);
    }
    for (const r of rows) buf.push(r);
    if (buf.length >= this.maxBatchSize) {
      const drained = buf;
      this.buffers.set(table, []);
      this.flushOne(table, drained).catch((e) => this.log("error", `flush of ${table} failed`, e));
    }
  }

  /** Flush every per-table buffer once. */
  async flushAll(): Promise<void> {
    const tables = Array.from(this.buffers.entries()).filter(([, b]) => b.length > 0);
    for (const [table, buf] of tables) {
      this.buffers.set(table, []);
      await this.flushOne(table, buf);
    }
    this.lastFlushMs = Date.now();
  }

  /** Try to insert one batch; on failure spool to disk. */
  async flushOne(table: string, rows: Array<Record<string, unknown>>): Promise<void> {
    if (rows.length === 0) return;
    try {
      await this.ch.insertJSONEachRow(table, rows);
      this.inserted += rows.length;
    } catch (e) {
      this.flushFailures++;
      try {
        this.spool.appendRows(table, rows);
        this.spooled += rows.length;
        this.log("warn", `ClickHouse insert failed; spooled ${rows.length} rows for ${table}`, e);
      } catch (spErr) {
        this.log("error", `Spool write FAILED for ${table} — rows lost`, spErr);
      }
    }
  }

  /** Walk spool files for the given tables and re-insert. Removes spool files
   *  on success. Designed to be called periodically (e.g. once a minute). */
  async recoverSpool(tables: ReadonlyArray<string>): Promise<void> {
    for (const table of tables) {
      for (const item of this.spool.readSpooledFiles(table)) {
        if (this.stopping) return;
        if (item.rows.length === 0) {
          this.spool.removeFile(item.file);
          continue;
        }
        try {
          await this.ch.insertJSONEachRow(table, item.rows);
          this.recovered += item.rows.length;
          this.spool.removeFile(item.file);
          this.log("info", `Recovered ${item.rows.length} rows from spool for ${table}`);
        } catch (e) {
          this.log("warn", `Spool recovery still failing for ${table}; will retry`, e);
          break; // back off — likely CH still down
        }
      }
    }
  }

  stats(): BatchWriterStats {
    const pending: { [k: string]: number } = {};
    for (const [k, v] of this.buffers) pending[k] = v.length;
    return {
      pending,
      inserted: this.inserted,
      spooled: this.spooled,
      recovered: this.recovered,
      flushFailures: this.flushFailures,
      lastFlushMs: this.lastFlushMs,
    };
  }
}
