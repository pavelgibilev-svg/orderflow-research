// `npm run backtest:okx-technical -- --date 2026-04-01 [--window 3h | --full-day]`
//
// Technical strategy replay on OKX BTC-USDT-SWAP. Thin wrapper around the
// existing per-day backtest pipeline (`tsx src/cli/backtestDay.ts ...`):
//
//   1. Locates files under  data/okx-historical/<SYMBOL>/<DATE>/  (the layout
//      produced by `scripts/okx/download_sample.py`).
//   2. Spawns the existing backtest CLI with OKX exchange slug, optional
//      L2-replay cap (--window 3h => --max-l2-hours 3), and pipes its
//      output to the user.
//   3. After the run completes, reads the backtest's JSON report and writes
//      OKX-labeled copies with a HARD DISCLAIMER at:
//          reports/OKX_TECHNICAL_REPLAY_<DATE>.md
//          reports/OKX_TECHNICAL_REPLAY_<DATE>.json
//          reports/OKX_TECHNICAL_REPLAY_<DATE>_ZONES.csv
//      The original backtest report folder is preserved untouched.
//
// NO strategy thresholds are changed. The strategy code is invoked
// exactly as it is invoked for Binance backtests; the only differences
// are the data folder, the venue label, and the report disclaimer.

import * as fs from "node:fs";
import * as path from "node:path";
import { spawn } from "node:child_process";
import { pathToFileURL } from "node:url";
import { parseArgs, getString, getOptString, getNumber } from "./args.js";

const SYMBOL_DEFAULT = "BTC-USDT-SWAP";
const EXCHANGE = "okex-swap";
const VENUE_DISPLAY = "OKX (okex-swap)";
const DATA_ROOT_DEFAULT = "data/okx-historical";

export interface OkxTechnicalArgs {
  date: string;
  symbol: string;
  windowHours: number | null;
  targetPct: number;
  horizons: string[];
  dataRoot: string;
  outDir: string;
  fromCache: boolean;
}

function parseWindow(s: string | null | undefined): number | null {
  if (!s || s === "full-day" || s === "full") return null;
  const m = /^(\d+(?:\.\d+)?)\s*h(ours?)?$/i.exec(s);
  if (!m) throw new Error(`Bad --window: ${s}. Expected "3h" or "full-day".`);
  return Number(m[1]);
}

function pickOkxArgs(argv: ReadonlyArray<string>): OkxTechnicalArgs {
  const a = parseArgs([...argv]);
  return {
    date: getString(a, "date"),
    symbol: getOptString(a, "symbol") ?? SYMBOL_DEFAULT,
    windowHours: parseWindow(getOptString(a, "window")),
    targetPct: getNumber(a, "target-pct", 2),
    horizons: (getOptString(a, "horizons") ?? "4h,8h,24h").split(",").map((s) => s.trim()),
    dataRoot: getOptString(a, "data-root") ?? DATA_ROOT_DEFAULT,
    outDir: getOptString(a, "out-dir") ?? "reports",
    fromCache: a.flags["from-cache"] === true || a.flags["from-cache"] === "true",
  };
}

const HARD_DISCLAIMER = [
  "OKX is NOT Binance.",
  "Strategy thresholds are calibrated for Binance USDS-M Futures BTCUSDT-perp.",
  "This is a technical replay / cross-venue research run with Binance-tuned thresholds left UNCHANGED.",
  "Zone counts below describe how the engine reacts to OKX L2 microstructure; they are NOT a backtest of profitability on OKX.",
  "Do NOT quote any of these numbers as a strategy edge or winrate.",
];

function disclaimerBlock(): string {
  return "  • " + HARD_DISCLAIMER.join("\n  • ");
}

async function spawnBacktestDay(opts: OkxTechnicalArgs): Promise<{ exitCode: number; durationMs: number }> {
  const dayDir = path.join(opts.dataRoot, opts.symbol, opts.date);
  if (!fs.existsSync(dayDir)) {
    throw new Error(
      `OKX day folder not found: ${dayDir}. Run scripts/okx/download_sample.py for ${opts.date} first.`,
    );
  }
  const args: string[] = [
    "tsx",
    "src/cli/backtestDay.ts",
    "--input",
    dayDir,
    "--exchange",
    EXCHANGE,
    "--symbol",
    opts.symbol,
    "--date",
    opts.date,
    "--target-pct",
    String(opts.targetPct),
    "--horizons",
    opts.horizons.join(","),
  ];
  if (opts.windowHours !== null) {
    args.push("--max-l2-hours", String(opts.windowHours));
  }
  console.log("[okx-technical] HARD DISCLAIMER:");
  console.log(disclaimerBlock());
  console.log("");
  console.log(`[okx-technical] spawning: npx ${args.join(" ")}`);
  const startedAt = Date.now();
  return await new Promise((resolve, reject) => {
    const child = spawn("npx", args, { stdio: "inherit", shell: true });
    child.on("error", (err) => reject(err));
    child.on("exit", (code) => {
      resolve({ exitCode: code ?? 0, durationMs: Date.now() - startedAt });
    });
  });
}

interface BacktestDayJsonShape {
  symbol?: string;
  date?: string;
  exchange?: string;
  zones: Array<Record<string, unknown>>;
  daily_summary: Record<string, number>;
}

function findBacktestReportDir(symbol: string, date: string): string | null {
  // backtestDay writes to reports/<SYMBOL>_<DATE> by default
  const candidate = path.join("reports", `${symbol}_${date}`);
  if (fs.existsSync(candidate)) return candidate;
  return null;
}

function readBacktestJson(dir: string): BacktestDayJsonShape | null {
  // The existing backtest:day writes:
  //   <dir>/zones.json         => flat array of zone objects
  //   <dir>/daily_summary.csv  => key,value summary metrics
  // We compose a synthetic JsonShape from both.
  const zonesPath = path.join(dir, "zones.json");
  const summaryPath = path.join(dir, "daily_summary.csv");
  if (!fs.existsSync(zonesPath)) return null;
  let zones: Array<Record<string, unknown>> = [];
  try {
    const parsed = JSON.parse(fs.readFileSync(zonesPath, "utf-8"));
    if (Array.isArray(parsed)) zones = parsed as Array<Record<string, unknown>>;
    else if (parsed && Array.isArray((parsed as { zones?: unknown[] }).zones))
      zones = (parsed as { zones: Array<Record<string, unknown>> }).zones;
  } catch {
    /* fall through with empty array */
  }
  const daily_summary: Record<string, number> = {};
  if (fs.existsSync(summaryPath)) {
    const lines = fs.readFileSync(summaryPath, "utf-8").split(/\r?\n/);
    for (const line of lines.slice(1)) {
      const m = /^([^,]+),(.*)$/.exec(line.trim());
      if (!m) continue;
      const v = Number(m[2]);
      if (Number.isFinite(v)) daily_summary[m[1]] = v;
    }
  }
  return { zones, daily_summary };
}

function countZonesByField(zones: Array<Record<string, unknown>>, field: string, value: string): number {
  return zones.filter((z) => z[field] === value).length;
}

function ds(bt: BacktestDayJsonShape | null, key: string): number | null {
  const v = bt?.daily_summary?.[key];
  return v === undefined || !Number.isFinite(v) ? null : v;
}

function fmtPct(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "n/a";
  return `${(x * 100).toFixed(2)} %`;
}

function renderOkxMd(opts: OkxTechnicalArgs, durationMs: number, bt: BacktestDayJsonShape | null): string {
  const wlabel = opts.windowHours === null ? "full UTC day" : `${opts.windowHours}h window`;
  const zones = bt?.zones ?? [];
  const long = countZonesByField(zones, "direction", "LONG");
  const short = countZonesByField(zones, "direction", "SHORT");
  const candidates = countZonesByField(zones, "status", "CANDIDATE");
  const confirmed = zones.length - candidates;
  const triggered = ds(bt, "zones_triggered") ?? 0;
  const reached = ds(bt, "zones_reached") ?? 0;
  const failed = ds(bt, "status_RESOLVED_FAILED") ?? 0;
  const invalidated = ds(bt, "status_INVALIDATED") ?? 0;
  const noTrigger = ds(bt, "status_NO_TRIGGER") ?? 0;
  const expired = ds(bt, "status_EXPIRED") ?? 0;
  const rawHit = ds(bt, "raw_triggered_hit_rate");
  const uniqueHit = ds(bt, "unique_move_adjusted_hit_rate");
  const uniqueMoves = ds(bt, "unique_reached_moves") ?? 0;
  const dupCredits = ds(bt, "duplicate_move_credits") ?? 0;
  const dupSuppressions = ds(bt, "duplicate_suppression_count") ?? 0;
  const cooldownMin = ds(bt, "cooldown_minutes_after_resolve") ?? 0;
  return `# OKX technical strategy replay — ${opts.symbol} ${opts.date}

**Venue:** ${VENUE_DISPLAY}
**Window:** ${wlabel}
**Target:** ${opts.targetPct}% on horizons ${opts.horizons.join(", ")}
**Underlying backtest report:** \`reports/${opts.symbol}_${opts.date}/\`
**Run wall-clock:** ${(durationMs / 1000).toFixed(1)} s

## HARD DISCLAIMER

${disclaimerBlock()}

## A. Data quality

(Deep L2-quality numbers — snapshot anchor count, crossed-seconds,
sequence integrity — are in the companion audit
\`reports/OKX_HISTORICAL_L2_AUDIT.md\` Sections 4 and 5. The replay window
here was capped at ${opts.windowHours === null ? "full day" : `${opts.windowHours}h`}
for compute-budget reasons; that's a knob, not a threshold change.)

## B. Zone output (engine reaction on OKX with Binance-tuned thresholds)

| metric                            | value |
|-----------------------------------|------:|
| Total zones created               | ${zones.length} |
| Still in CANDIDATE                | ${candidates} |
| Confirmed (any later state)       | ${confirmed} |
| Triggered                         | ${triggered} |
| RESOLVED_REACHED (raw)            | ${reached} |
| RESOLVED_FAILED                   | ${failed} |
| EXPIRED                           | ${expired} |
| INVALIDATED                       | ${invalidated} |
| NO_TRIGGER                        | ${noTrigger} |
| LONG zones                        | ${long} |
| SHORT zones                       | ${short} |
| Unique-move clusters              | ${uniqueMoves} |
| Duplicate-move credits absorbed   | ${dupCredits} |
| Duplicate suppressions (dedup)    | ${dupSuppressions} |
| Cooldown after resolve            | ${cooldownMin} min |
| Raw triggered hit-rate            | ${fmtPct(rawHit)} |
| Unique-move-adjusted hit-rate     | ${fmtPct(uniqueHit)} |

> These hit-rates measure how often the Binance-tuned engine's triggers
> happen to land on a ${opts.targetPct}% move within the configured horizons on
> OKX data. They are NOT a profitability claim and should not be reported
> as a strategy edge.

See \`OKX_TECHNICAL_REPLAY_${opts.date}_ZONES.csv\` for the per-zone breakdown.

## C. Cross-venue interpretation guide

- **Too many zones vs Binance baseline** ⇒ OKX liquidity profile may make
  the imbalance / void thresholds easier to trip. Do NOT lower thresholds;
  flag for a dedicated cross-venue calibration task later.
- **Too few zones** ⇒ thresholds may be too tight for OKX. Same response —
  document, do not tune.
- **Crossed-seconds > ~0.5 %** in the L2 audit ⇒ reconstruction artefact
  or burst microstructure on OKX; cross-check with the independent
  \`book_ticker\` stream (Section 4.3 of \`OKX_HISTORICAL_L2_AUDIT.md\`).

## D. Future work (out of scope here)

- Calibrate dedup / cooldown / overlap thresholds independently for OKX
  under a venue-specific config.
- Cross-venue zone-density comparison Binance ↔ OKX on matched windows.
- Multi-day OKX sample (requires Tardis paid API key OR OKX VIP / premium).
`;
}

function renderOkxZonesCsv(bt: BacktestDayJsonShape | null): string {
  const zones = bt?.zones ?? [];
  const cols = [
    "zone_id",
    "direction",
    "state",
    "createdTs",
    "confirmedTs",
    "triggerTs",
    "resolvedTs",
    "priceLow",
    "priceHigh",
    "triggerPrice",
    "reachedTs",
    "mfePct",
    "maePct",
    "timeToTargetMs",
    "reachedHorizon",
    "suppressionReason",
    "uniqueMoveId",
    "isPrimaryMoveZone",
    "duplicateMoveCredit",
  ];
  const lines: string[] = [cols.join(",")];
  for (const z of zones) {
    lines.push(
      cols
        .map((k) => {
          const v = (z as Record<string, unknown>)[k];
          if (v === undefined || v === null) return "";
          if (typeof v === "string") return v.replace(/,/g, ";");
          return String(v);
        })
        .join(","),
    );
  }
  return lines.join("\n") + "\n";
}

async function main(): Promise<void> {
  const opts = pickOkxArgs(process.argv.slice(2));

  let durationMs = 0;
  if (opts.fromCache) {
    console.log("[okx-technical] --from-cache: reusing existing backtest reports, no re-run.");
    console.log("[okx-technical] HARD DISCLAIMER:");
    console.log(disclaimerBlock());
    console.log("");
  } else {
    const { exitCode, durationMs: d } = await spawnBacktestDay(opts);
    durationMs = d;
    if (exitCode !== 0) {
      console.error(`[okx-technical] backtest:day exited with code ${exitCode}`);
      process.exit(exitCode);
    }
  }

  const btDir = findBacktestReportDir(opts.symbol, opts.date);
  const btJson = btDir ? readBacktestJson(btDir) : null;
  if (!btJson) {
    console.warn(`[okx-technical] WARN: could not parse the underlying backtest JSON from ${btDir ?? "(no dir found)"}`);
  }

  fs.mkdirSync(opts.outDir, { recursive: true });
  const mdPath = path.join(opts.outDir, `OKX_TECHNICAL_REPLAY_${opts.date}.md`);
  const jsonPath = path.join(opts.outDir, `OKX_TECHNICAL_REPLAY_${opts.date}.json`);
  const csvPath = path.join(opts.outDir, `OKX_TECHNICAL_REPLAY_${opts.date}_ZONES.csv`);

  const summary = {
    venue: VENUE_DISPLAY,
    symbol: opts.symbol,
    date: opts.date,
    window_hours: opts.windowHours,
    target_pct: opts.targetPct,
    horizons: opts.horizons,
    okx_is_binance: false,
    okx_is_directly_equivalent_to_binance_usdsm_futures: false,
    hard_disclaimer: HARD_DISCLAIMER,
    underlying_backtest_dir: btDir,
    underlying_backtest_duration_ms: durationMs,
    underlying_backtest_summary: btJson,
  };

  fs.writeFileSync(jsonPath, JSON.stringify(summary, null, 2), "utf-8");
  fs.writeFileSync(mdPath, renderOkxMd(opts, durationMs, btJson));
  fs.writeFileSync(csvPath, renderOkxZonesCsv(btJson));

  console.log(`[okx-technical] wrote: ${mdPath}`);
  console.log(`[okx-technical] wrote: ${jsonPath}`);
  console.log(`[okx-technical] wrote: ${csvPath}`);
}

const isMain =
  typeof process !== "undefined" &&
  !!process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href;

if (isMain) {
  main().catch((err) => {
    console.error("[okx-technical] FAILED:", err);
    process.exit(1);
  });
}
