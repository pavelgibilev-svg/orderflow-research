// Pure (no console) validation logic for `validate:tardis`.
// Designed to be unit-testable: it doesn't read configuration, doesn't
// write reports, and never throws on missing optional files.

import * as fs from "node:fs";
import { resolveInputFiles } from "../data/fileResolver.js";
import { readHeaderOnly, streamTardisFile } from "../data/tardisCsvLoader.js";
import {
  type DataType,
  dataTypeFromHeaders,
} from "../data/schema.js";
import { SAMPLE_2026_REQUIRED } from "../data/tardisUrls.js";

export type DataTypeStatus = "ok" | "missing_optional" | "missing_required" | "error";

export interface DataTypeValidation {
  dataType: DataType;
  required: boolean;
  filePath: string | null;
  fileSizeBytes: number | null;
  gzipOk: boolean;
  headers: string[] | null;
  inferredType: DataType | null;
  rowsParsed: number;
  parseErrors: number;
  hasSnapshotRows: boolean;
  hasUpdateRows: boolean;
  errors: string[];
  status: DataTypeStatus;
  notes: string[];
}

export interface DayValidation {
  date: string;
  symbol: string;
  exchange: string;
  inputPath: string;
  isValid: boolean;
  invalidReasons: string[];
  dataTypes: DataTypeValidation[];
  warnings: string[];
}

export interface ValidateOpts {
  inputPath: string;
  symbol: string;
  exchange: string;
  date: string;
  required?: ReadonlyArray<DataType>;
  optional?: ReadonlyArray<DataType>;
  sampleRows?: number;
}

const DEFAULT_OPTIONAL: ReadonlyArray<DataType> = [
  "derivative_ticker",
  "book_ticker",
  "liquidations",
];

export async function validateDay(opts: ValidateOpts): Promise<DayValidation> {
  const required = opts.required ?? SAMPLE_2026_REQUIRED;
  const optional = opts.optional ?? DEFAULT_OPTIONAL;
  const sampleRows = opts.sampleRows ?? 1000;

  const dt = (t: DataType): boolean => required.includes(t);
  const all = [...required, ...optional];

  const warnings: string[] = [];
  let resolved: ReturnType<typeof resolveInputFiles>["files"] = [];
  try {
    if (!fs.existsSync(opts.inputPath)) {
      // Treat as no files — every required type will be missing_required.
      warnings.push(`input path does not exist: ${opts.inputPath}`);
    } else {
      const r = resolveInputFiles(opts.inputPath, opts.symbol, opts.date);
      resolved = r.files;
    }
  } catch (e) {
    warnings.push(`resolve error: ${(e as Error).message}`);
  }

  const dataTypes: DataTypeValidation[] = [];
  for (const t of all) {
    const isReq = dt(t);
    const found = resolved.find((f) => f.dataType === t);
    const rec: DataTypeValidation = {
      dataType: t,
      required: isReq,
      filePath: found ? found.path : null,
      fileSizeBytes: null,
      gzipOk: false,
      headers: null,
      inferredType: null,
      rowsParsed: 0,
      parseErrors: 0,
      hasSnapshotRows: false,
      hasUpdateRows: false,
      errors: [],
      status: "ok",
      notes: [],
    };
    if (!found) {
      rec.status = isReq ? "missing_required" : "missing_optional";
      rec.notes.push(isReq ? "Required Tardis file missing for this date." : "Optional Tardis file not present.");
      dataTypes.push(rec);
      continue;
    }
    try {
      const stat = fs.statSync(found.path);
      rec.fileSizeBytes = stat.size;
      if (stat.size === 0) {
        rec.errors.push("file is empty");
        rec.status = "error";
        dataTypes.push(rec);
        continue;
      }
    } catch (e) {
      rec.errors.push(`stat failed: ${(e as Error).message}`);
      rec.status = "error";
      dataTypes.push(rec);
      continue;
    }

    // Read just the header to confirm gzip + columns.
    try {
      const hdrs = await readHeaderOnly(found.path);
      rec.gzipOk = true;
      rec.headers = hdrs;
      rec.inferredType = dataTypeFromHeaders(hdrs);
      const expectsTimestamp = hdrs.includes("timestamp");
      const expectsLocalTs = hdrs.includes("local_timestamp");
      if (!expectsTimestamp || !expectsLocalTs) {
        rec.errors.push("missing timestamp / local_timestamp columns");
      }
      // Light data-type-specific column expectations.
      if (t === "incremental_book_L2") {
        for (const required of ["is_snapshot", "side", "price", "amount"]) {
          if (!hdrs.includes(required)) rec.errors.push(`missing column: ${required}`);
        }
      }
      if (t === "trades") {
        for (const required of ["side", "price", "amount"]) {
          if (!hdrs.includes(required)) rec.errors.push(`missing column: ${required}`);
        }
      }
    } catch (e) {
      rec.errors.push(`gzip/header error: ${(e as Error).message}`);
      rec.gzipOk = false;
      rec.status = "error";
      dataTypes.push(rec);
      continue;
    }

    // Parse first N rows.
    try {
      let parsed = 0;
      let errs = 0;
      let snap = false;
      let upd = false;
      for await (const ev of streamTardisFile(found.path, { dataType: t, limit: sampleRows })) {
        parsed += 1;
        if (t === "incremental_book_L2" && "isSnapshot" in ev) {
          if ((ev as { isSnapshot: boolean }).isSnapshot) snap = true;
          else upd = true;
        }
      }
      rec.rowsParsed = parsed;
      rec.parseErrors = errs;
      rec.hasSnapshotRows = snap;
      rec.hasUpdateRows = upd;
      if (parsed === 0) {
        rec.errors.push("zero rows parsed in first sample");
        rec.status = "error";
      } else if (rec.errors.length > 0) {
        rec.status = "error";
      }
    } catch (e) {
      rec.errors.push(`parse error: ${(e as Error).message}`);
      rec.status = "error";
    }

    dataTypes.push(rec);
  }

  // Day verdict: every required type must end up with status=ok.
  const invalidReasons: string[] = [];
  let isValid = true;
  for (const rec of dataTypes) {
    if (!rec.required) continue;
    if (rec.status !== "ok") {
      isValid = false;
      invalidReasons.push(`${rec.dataType}: ${rec.status}${rec.errors.length ? " (" + rec.errors.join("; ") + ")" : ""}`);
    }
  }
  return {
    date: opts.date,
    symbol: opts.symbol,
    exchange: opts.exchange,
    inputPath: opts.inputPath,
    isValid,
    invalidReasons,
    dataTypes,
    warnings,
  };
}
