import * as fs from "node:fs";

export function writeJson(filePath: string, data: unknown): void {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf8");
}

/** Streaming-ish JSONL writer for big arrays. */
export function writeJsonl<T>(filePath: string, rows: Iterable<T>): void {
  const out = fs.createWriteStream(filePath, { encoding: "utf8" });
  for (const r of rows) {
    out.write(JSON.stringify(r) + "\n");
  }
  out.end();
}
