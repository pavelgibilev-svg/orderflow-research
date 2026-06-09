// Markdown / JSON renderers for the validate:tardis output.

import type { DayValidation } from "../strategy/validateTardisCore.js";

export interface ValidateRunSummary {
  generatedAt: string;
  inputPath: string;
  symbol: string;
  exchange: string;
  days: DayValidation[];
}

export function buildValidateMarkdown(s: ValidateRunSummary): string {
  const lines: string[] = [];
  lines.push(`# Tardis Compatibility Validation — 2026 YTD (excluding May)`);
  lines.push("");
  lines.push(`> This is a **compatibility and smoke-test report**, not a proof of strategy profitability.`);
  lines.push("");
  lines.push(`- Generated: ${s.generatedAt}`);
  lines.push(`- Input path: \`${s.inputPath}\``);
  lines.push(`- Symbol: ${s.symbol}`);
  lines.push(`- Exchange: ${s.exchange}`);
  lines.push(`- Dates checked: ${s.days.map((d) => d.date).join(", ")}`);
  lines.push("");

  lines.push(`## Per-day verdict`);
  lines.push("");
  lines.push(`| Date | Verdict | Required types | Optional types | Reasons |`);
  lines.push(`|---|---|---|---|---|`);
  for (const d of s.days) {
    const req = d.dataTypes.filter((dt) => dt.required);
    const opt = d.dataTypes.filter((dt) => !dt.required);
    const reqStr = req.map((r) => `${r.dataType}:${r.status}`).join("<br/>");
    const optStr = opt.map((r) => `${r.dataType}:${r.status}`).join("<br/>");
    lines.push(
      `| ${d.date} | ${d.isValid ? "VALID" : "INVALID"} | ${reqStr} | ${optStr} | ${d.invalidReasons.join("; ") || "-"} |`
    );
  }
  lines.push("");

  for (const d of s.days) {
    lines.push(`## ${d.date}`);
    lines.push("");
    lines.push(`**Verdict:** ${d.isValid ? "VALID" : "INVALID"}`);
    if (d.invalidReasons.length > 0) {
      lines.push("");
      lines.push(`Invalid reasons:`);
      for (const r of d.invalidReasons) lines.push(`- ${r}`);
    }
    lines.push("");
    lines.push(`| Data type | Required | Status | File | Size | Headers OK | Rows parsed | Notes |`);
    lines.push(`|---|---|---|---|---|---|---|---|`);
    for (const dt of d.dataTypes) {
      const file = dt.filePath ?? "-";
      const size = dt.fileSizeBytes !== null ? formatBytes(dt.fileSizeBytes) : "-";
      const headersOk = dt.gzipOk && dt.headers !== null;
      const notes = dt.errors.length > 0 ? dt.errors.join("; ") : dt.notes.join("; ");
      lines.push(
        `| ${dt.dataType} | ${dt.required ? "yes" : "no"} | ${dt.status} | \`${file}\` | ${size} | ${headersOk ? "yes" : "no"} | ${dt.rowsParsed} | ${notes} |`
      );
    }
    if (d.warnings.length > 0) {
      lines.push("");
      lines.push(`Warnings:`);
      for (const w of d.warnings) lines.push(`- ${w}`);
    }
    lines.push("");
  }

  lines.push(`## What you can / cannot conclude`);
  lines.push("");
  lines.push(`- A **VALID** verdict means the file layout, gzip, headers and the first 1000 rows all parse.`);
  lines.push(`- It does **not** mean the strategy makes money on that day.`);
  lines.push(`- Optional missing types (\`derivative_ticker\`, \`book_ticker\`, \`liquidations\`) are not strategy-critical for the smoke test.`);
  lines.push(`- A day is INVALID only if \`incremental_book_L2\` or \`trades\` is missing or fails to parse.`);
  lines.push("");
  return lines.join("\n");
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
