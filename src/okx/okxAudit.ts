// Audit helpers for an OKX-swap "file-recording" folder produced by
// scripts/okx/convert_and_replay.py. Pure TS, no Python dep.
//
// Used by tests + by the OKX_HISTORICAL_L2_AUDIT report generator.

import * as fs from "node:fs";
import * as path from "node:path";
import { OKX_FILE_RECORDING_OUTPUTS } from "./okxConverterToFileRecording.js";

export interface FileRecordingPresence {
  file: string;
  path: string;
  exists: boolean;
  size_bytes: number;
}

export function listFileRecordingPresence(dir: string): FileRecordingPresence[] {
  return OKX_FILE_RECORDING_OUTPUTS.map((file) => {
    const p = path.join(dir, file);
    const exists = fs.existsSync(p);
    return { file, path: p, exists, size_bytes: exists ? fs.statSync(p).size : 0 };
  });
}

/** Streaming line-count of a JSONL file. Does not parse rows. */
export function countLines(filePath: string): number {
  if (!fs.existsSync(filePath)) return 0;
  const buf = fs.readFileSync(filePath);
  let n = 0;
  for (let i = 0; i < buf.length; i++) {
    if (buf[i] === 0x0a /* \n */) n += 1;
  }
  // Some writers omit the trailing newline; count the partial last line.
  if (buf.length > 0 && buf[buf.length - 1] !== 0x0a) n += 1;
  return n;
}

export interface OkxFileRecordingAuditSummary {
  dir: string;
  files: FileRecordingPresence[];
  required_present: boolean;
  required_missing: string[];
  line_counts: Record<string, number>;
  metadata_json_parsed: unknown;
}

const REQUIRED: ReadonlyArray<string> = [
  "raw_depth_events.jsonl",
  "trades.jsonl",
  "orderbook_snapshots_1s.jsonl",
  "health.jsonl",
  "metadata.json",
];

/** Audit a converted OKX day folder. Returns counts + presence,
 *  intentionally NOT a verdict — the verdict is composed by the report
 *  writer with full context (incl. external L2 audit numbers). */
export function auditOkxDayFolder(dir: string): OkxFileRecordingAuditSummary {
  const files = listFileRecordingPresence(dir);
  const required_missing = REQUIRED.filter(
    (req) => !files.find((f) => f.file === req && f.exists),
  );
  const line_counts: Record<string, number> = {};
  for (const f of files) {
    if (f.exists && f.file.endsWith(".jsonl")) {
      line_counts[f.file] = countLines(f.path);
    }
  }
  let meta: unknown = null;
  const mp = path.join(dir, "metadata.json");
  if (fs.existsSync(mp)) {
    try {
      meta = JSON.parse(fs.readFileSync(mp, "utf-8"));
    } catch (e) {
      meta = { _parse_error: String(e) };
    }
  }
  return {
    dir,
    files,
    required_present: required_missing.length === 0,
    required_missing,
    line_counts,
    metadata_json_parsed: meta,
  };
}
