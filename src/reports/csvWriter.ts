// Tiny CSV writer with explicit column order. We escape only quotes and
// commas. Output uses LF line endings.

import * as fs from "node:fs";

export interface CsvColumn<T> {
  name: string;
  get: (row: T) => string | number | boolean | null | undefined;
}

function escapeField(v: string | number | boolean | null | undefined): string {
  if (v === undefined || v === null) return "";
  const s = String(v);
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

export function writeCsv<T>(filePath: string, columns: CsvColumn<T>[], rows: Iterable<T>): void {
  const out = fs.createWriteStream(filePath, { encoding: "utf8" });
  out.write(columns.map((c) => c.name).join(",") + "\n");
  for (const r of rows) {
    out.write(columns.map((c) => escapeField(c.get(r))).join(",") + "\n");
  }
  out.end();
}
