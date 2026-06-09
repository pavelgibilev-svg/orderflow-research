// Markdown / CSV / JSON renderers for the backtest:sample-2026 overall report.

import type { SampleRunDayResult } from "../strategy/sampleRunnerCore.js";

export interface SampleRunSummary {
  generatedAt: string;
  symbol: string;
  exchange: string;
  targetPct: number;
  horizons: string[];
  inputPath: string;
  days: SampleRunDayResult[];
}

export function buildSampleRunMarkdown(s: SampleRunSummary): string {
  const lines: string[] = [];
  lines.push(`# Sample 2026 (Jan-Apr) — Compatibility & Smoke-Test Backtest`);
  lines.push("");
  lines.push(`> **This is a compatibility and smoke-test run, not a proof of strategy profitability.**`);
  lines.push(`> Hit-rate numbers below come from a 4-day sample. They are useful only to verify`);
  lines.push(`> the pipeline works end-to-end on real Tardis data. Do not use them to decide whether`);
  lines.push(`> the strategy is "good".`);
  lines.push("");
  lines.push(`- Generated: ${s.generatedAt}`);
  lines.push(`- Symbol: ${s.symbol}`);
  lines.push(`- Exchange: ${s.exchange}`);
  lines.push(`- Target: ±${s.targetPct.toFixed(2)}%  Horizons: ${s.horizons.join(", ")}`);
  lines.push(`- Input: \`${s.inputPath}\``);
  lines.push("");

  lines.push(`## Per-day table`);
  lines.push("");
  const header = [
    "Date",
    "Valid",
    "L2 rows",
    "Trades rows",
    "Optional present",
    "Optional missing",
    "Quality flag ticks",
    "Snapshots",
    "Zones",
    "Candidates",
    "Confirmed",
    "Triggered",
    "Reached 4h",
    "Reached 8h",
    "Reached 24h",
    "Failed/no_trigger/inv",
    "Baseline 24h up/down",
    "Triggered hit rate",
    "Notes",
  ];
  lines.push("| " + header.join(" | ") + " |");
  lines.push("|" + header.map(() => "---").join("|") + "|");
  for (const d of s.days) {
    const v = d.validation;
    const opt = v.dataTypes.filter((dt) => !dt.required);
    const optPresent = opt.filter((o) => o.status === "ok").map((o) => o.dataType).join(",") || "-";
    const optMissing = opt.filter((o) => o.status !== "ok").map((o) => o.dataType).join(",") || "-";
    const b = d.backtest;
    const baseline24h = b?.baselines.find((x) => x.horizon === "24h") ?? null;
    const baseline = baseline24h
      ? `${(baseline24h.upRate * 100).toFixed(1)}%/${(baseline24h.downRate * 100).toFixed(1)}%`
      : "-";
    const fields: Array<string | number> = [
      d.date,
      d.isValid ? "yes" : "no",
      b ? b.rowsProcessed.l2 : "-",
      b ? b.rowsProcessed.trades : "-",
      optPresent,
      optMissing,
      b ? b.qualityFlagsTickCount : "-",
      d.snapshotsExported || "-",
      b ? b.zonesTotal : "-",
      b ? b.zonesCandidates : "-",
      b ? b.zonesConfirmed : "-",
      b ? b.zonesTriggered : "-",
      b ? b.zonesReachedByHorizon["4h"] ?? 0 : "-",
      b ? b.zonesReachedByHorizon["8h"] ?? 0 : "-",
      b ? b.zonesReachedByHorizon["24h"] ?? 0 : "-",
      b ? b.zonesFailedOrNoTriggerOrInvalidated : "-",
      baseline,
      b ? `${(b.triggeredHitRate * 100).toFixed(1)}%` : "-",
      d.notes || (d.errored ? `ERROR: ${d.errored}` : "-"),
    ];
    lines.push("| " + fields.join(" | ") + " |");
  }
  lines.push("");

  lines.push(`## Anti-self-deception checks`);
  lines.push("");
  lines.push(`- Failed / no_trigger / invalidated zones are kept in each day's \`zones.csv\` — not filtered out.`);
  lines.push(`- This run does **not** modify \`config/strategy.default.json\`.`);
  lines.push(`- This run does **not** sweep thresholds or pick the best.`);
  lines.push(`- The hit rate above is reported only over zones that **actually triggered**.`);
  lines.push(`- The per-day reports also include the unconditional 2% hit rate of the day's price walk; compare against it before drawing conclusions.`);
  lines.push("");
  lines.push(`## What this sample can and cannot tell you`);
  lines.push("");
  lines.push(`Can:`);
  lines.push(`- Confirm the streaming Tardis CSV reader, order-book replay, feature engine, zone detector and target checker run end-to-end on real data.`);
  lines.push(`- Confirm zone counts and statuses are non-degenerate (not all zero, not all reached).`);
  lines.push(`- Surface real data-quality issues (gaps, crossed books, missing optional types).`);
  lines.push("");
  lines.push(`Cannot:`);
  lines.push(`- Prove the strategy is profitable: 4 days is too small, all four are first-of-month boundaries, and there is no out-of-sample split.`);
  lines.push(`- Replace a proper monthly sweep over a paid Tardis subscription.`);
  lines.push(`- Speak to slippage, fees, or any execution realism — this is a research module, not a trading bot.`);
  lines.push("");

  return lines.join("\n");
}
