// JSONL spool writer — fallback when ClickHouse is temporarily unavailable.
//
// The recorder must NEVER drop market data silently. If a batch insert fails,
// the rows are appended to a spool file at
//   <RAW_SPOOL_DIR>/<table>-<YYYYMMDD>.jsonl
// One file per table per UTC day so files don't grow unbounded. A periodic
// recovery task reads these files and re-attempts the insert.

import * as fs from "node:fs";
import * as path from "node:path";

export interface SpoolStats {
  files: number;
  totalBytes: number;
  totalLines: number;
  oldestMtime: number | null;
}

export class SpoolWriter {
  constructor(private readonly dir: string) {
    fs.mkdirSync(dir, { recursive: true });
  }

  spoolPath(table: string, ts = Date.now()): string {
    const d = new Date(ts);
    const yyyy = d.getUTCFullYear();
    const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(d.getUTCDate()).padStart(2, "0");
    return path.join(this.dir, `${table}-${yyyy}${mm}${dd}.jsonl`);
  }

  /** Append rows as JSONL. Returns the file path written to. */
  appendRows(table: string, rows: ReadonlyArray<Record<string, unknown>>): string {
    if (rows.length === 0) return "";
    const p = this.spoolPath(table);
    const lines = rows.map((r) => JSON.stringify(r)).join("\n") + "\n";
    fs.appendFileSync(p, lines, "utf8");
    return p;
  }

  /** Iterate every row in every spool file for a table. The caller is
   *  responsible for re-inserting the rows and removing the file on success. */
  *readSpooledFiles(table: string): IterableIterator<{ file: string; rows: Array<Record<string, unknown>> }> {
    if (!fs.existsSync(this.dir)) return;
    const all = fs.readdirSync(this.dir);
    for (const name of all) {
      if (!name.startsWith(`${table}-`) || !name.endsWith(".jsonl")) continue;
      const p = path.join(this.dir, name);
      const text = fs.readFileSync(p, "utf8");
      const rows: Array<Record<string, unknown>> = [];
      for (const line of text.split("\n")) {
        if (!line.trim()) continue;
        try {
          rows.push(JSON.parse(line));
        } catch {
          /* drop malformed line */
        }
      }
      yield { file: p, rows };
    }
  }

  /** Delete a spool file once its rows have been successfully reinserted. */
  removeFile(file: string): void {
    try {
      fs.unlinkSync(file);
    } catch {
      /* ignore */
    }
  }

  /** Diagnostics for the health monitor / live:health CLI. */
  stats(table?: string): SpoolStats {
    const out: SpoolStats = { files: 0, totalBytes: 0, totalLines: 0, oldestMtime: null };
    if (!fs.existsSync(this.dir)) return out;
    for (const name of fs.readdirSync(this.dir)) {
      if (!name.endsWith(".jsonl")) continue;
      if (table && !name.startsWith(`${table}-`)) continue;
      const p = path.join(this.dir, name);
      const stat = fs.statSync(p);
      out.files++;
      out.totalBytes += stat.size;
      // Count newlines as a quick line proxy.
      const buf = fs.readFileSync(p);
      let lines = 0;
      for (const b of buf) if (b === 0x0a) lines++;
      out.totalLines += lines;
      const m = stat.mtimeMs;
      if (out.oldestMtime === null || m < out.oldestMtime) out.oldestMtime = m;
    }
    return out;
  }
}
