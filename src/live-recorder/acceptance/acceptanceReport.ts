// Pure report writer for the live-recorder acceptance run. Takes a typed
// stats object and emits an .md and a .json. No I/O for ClickHouse or
// Binance happens here — it's all input. This makes the writer fully
// snapshot-testable and lets the orchestrator build the data structure
// step-by-step as the run progresses.

export interface AcceptanceTableCount {
  table: string;
  rowCount: number;
  firstTs: string | null;
  lastTs: string | null;
}

export interface AcceptanceSnapshotQuality {
  snapshots: number;
  crossed: number;
  empty: number;
  flaggedCrossed: number;
  flaggedEmpty: number;
  flaggedWideSpread: number;
  spreadMin: number;
  spreadMax: number;
  spreadAvg: number;
}

export interface AcceptanceLatestSnapshot {
  ts: string;
  bestBid: number;
  bestAsk: number;
  mid: number;
  spread: number;
  sequenceFinalUpdateId: number;
  qualityFlagsCsv: string;
}

export interface AcceptanceHealth {
  sequenceGapCount: number;
  reconnectCount: number;
  maxDbQueueSize: number;
  maxSpoolQueueSize: number;
  okSamples: number;
  degradedSamples: number;
  downSamples: number;
  samples: number;
}

export interface AcceptanceBacktestSummary {
  ran: boolean;
  zonesFound: number;
  zonesTriggered: number;
  zonesReachedRaw: number;
  uniqueReachedMoves: number;
  reportPath: string | null;
  /** Filled when ran=false to explain why. */
  skippedReason?: string;
}

export interface AcceptanceReportInput {
  startTimeIso: string;
  endTimeIso: string;
  durationMs: number;
  exchange: string;
  symbols: string[];
  primarySymbol: string;
  ch: { url: string; database: string };
  /** Per-table counts in window order (raw_depth_events, trades, ...). */
  tableCounts: AcceptanceTableCount[];
  snapshotQuality: AcceptanceSnapshotQuality | null;
  latestSnapshot: AcceptanceLatestSnapshot | null;
  health: AcceptanceHealth | null;
  spoolFilesCreated: boolean;
  insertErrorsObserved: boolean;
  /** Notes that came from the orchestrator (warnings, etc). */
  notes: string[];
  backtest: AcceptanceBacktestSummary;
}

interface VerdictPart {
  ok: boolean;
  label: string;
  detail?: string;
}

export interface AcceptanceVerdict {
  parts: VerdictPart[];
  overall: "PASS" | "DEGRADED" | "FAIL";
}

/** Pure verdict computation — also exposed for tests. */
export function computeVerdict(input: AcceptanceReportInput): AcceptanceVerdict {
  const parts: VerdictPart[] = [];
  const depth = input.tableCounts.find((t) => t.table === "raw_depth_events");
  const trades = input.tableCounts.find((t) => t.table === "trades");
  const snaps = input.tableCounts.find((t) => t.table === "orderbook_snapshots_1s");
  const bt = input.tableCounts.find((t) => t.table === "book_ticker");
  const health = input.health;

  parts.push({
    ok: !!depth && depth.rowCount > 0,
    label: "raw_depth_events written",
    detail: depth ? `${depth.rowCount} rows` : "no rows",
  });
  parts.push({
    ok: !!trades && trades.rowCount > 0,
    label: "trades written",
    detail: trades ? `${trades.rowCount} rows` : "no rows",
  });
  parts.push({
    ok: !!snaps && snaps.rowCount > 0,
    label: "orderbook_snapshots_1s written",
    detail: snaps ? `${snaps.rowCount} rows` : "no rows",
  });
  parts.push({
    ok: !!bt && bt.rowCount > 0,
    label: "book_ticker written",
    detail: bt ? `${bt.rowCount} rows` : "no rows",
  });
  parts.push({
    ok: input.snapshotQuality === null || input.snapshotQuality.crossed === 0,
    label: "no crossed snapshots",
    detail: input.snapshotQuality ? `crossed=${input.snapshotQuality.crossed}/${input.snapshotQuality.snapshots}` : "no snapshots",
  });
  parts.push({
    ok: input.snapshotQuality === null || input.snapshotQuality.empty === 0,
    label: "no empty snapshots",
    detail: input.snapshotQuality ? `empty=${input.snapshotQuality.empty}` : "-",
  });
  parts.push({
    ok: !input.spoolFilesCreated,
    label: "no spool files (CH was reachable throughout)",
    detail: input.spoolFilesCreated ? "spool files present" : "none",
  });
  parts.push({
    ok: !input.insertErrorsObserved,
    label: "no ClickHouse insert errors",
    detail: input.insertErrorsObserved ? "errors observed" : "none",
  });
  parts.push({
    ok: !!health && health.sequenceGapCount === 0,
    label: "no sequence gaps",
    detail: health ? `gaps=${health.sequenceGapCount}` : "no health samples",
  });
  parts.push({
    ok: input.backtest.ran,
    label: "backtest:db ran end-to-end",
    detail: input.backtest.ran
      ? `zones=${input.backtest.zonesFound} triggered=${input.backtest.zonesTriggered} reached_raw=${input.backtest.zonesReachedRaw} unique_moves=${input.backtest.uniqueReachedMoves}`
      : input.backtest.skippedReason ?? "skipped",
  });

  const failed = parts.filter((p) => !p.ok);
  const dataMissing = failed.some(
    (p) => p.label === "raw_depth_events written" || p.label === "trades written" || p.label === "orderbook_snapshots_1s written"
  );
  const overall: AcceptanceVerdict["overall"] = dataMissing
    ? "FAIL"
    : failed.length > 0
    ? "DEGRADED"
    : "PASS";
  return { parts, overall };
}

export function buildAcceptanceMarkdown(input: AcceptanceReportInput, verdict?: AcceptanceVerdict): string {
  const v = verdict ?? computeVerdict(input);
  const lines: string[] = [];
  lines.push(`# Live Recorder Acceptance Run — ${input.primarySymbol} ${input.startTimeIso}`);
  lines.push("");
  lines.push(`> Acceptance check that the live recorder writes Binance Futures public market data to ClickHouse and that the strategy module can read it back via \`backtest:db\`. Public market-data only. No API key. No trading endpoints.`);
  lines.push("");
  lines.push(`- Verdict: **${v.overall}**`);
  lines.push(`- Start (UTC): ${input.startTimeIso}`);
  lines.push(`- End   (UTC): ${input.endTimeIso}`);
  lines.push(`- Duration: ${formatDuration(input.durationMs)}`);
  lines.push(`- Exchange: ${input.exchange}`);
  lines.push(`- Symbols: ${input.symbols.join(", ")}`);
  lines.push(`- ClickHouse: ${input.ch.url} (db=${input.ch.database})`);
  lines.push("");
  lines.push(`## 1. Table row counts (within acceptance window)`);
  lines.push("");
  lines.push(`| Table | Rows | First ts | Last ts |`);
  lines.push(`|---|---|---|---|`);
  for (const t of input.tableCounts) {
    lines.push(`| ${t.table} | ${t.rowCount.toLocaleString()} | ${t.firstTs ?? "-"} | ${t.lastTs ?? "-"} |`);
  }
  lines.push("");

  lines.push(`## 2. Snapshot quality`);
  lines.push("");
  if (input.snapshotQuality) {
    const q = input.snapshotQuality;
    lines.push(`| Metric | Value |`);
    lines.push(`|---|---|`);
    lines.push(`| Snapshots | ${q.snapshots} |`);
    lines.push(`| Crossed (best_bid >= best_ask) | ${q.crossed} |`);
    lines.push(`| Empty (best_bid==0 OR best_ask==0) | ${q.empty} |`);
    lines.push(`| flag CROSSED | ${q.flaggedCrossed} |`);
    lines.push(`| flag EMPTY | ${q.flaggedEmpty} |`);
    lines.push(`| flag WIDE_SPREAD | ${q.flaggedWideSpread} |`);
    lines.push(`| Spread min / max / avg | ${q.spreadMin} / ${q.spreadMax} / ${q.spreadAvg.toFixed(4)} |`);
  } else {
    lines.push(`(no snapshots in window)`);
  }
  lines.push("");

  lines.push(`## 3. Latest snapshot`);
  lines.push("");
  if (input.latestSnapshot) {
    const s = input.latestSnapshot;
    lines.push(`| Field | Value |`);
    lines.push(`|---|---|`);
    lines.push(`| ts | ${s.ts} |`);
    lines.push(`| best_bid | ${s.bestBid} |`);
    lines.push(`| best_ask | ${s.bestAsk} |`);
    lines.push(`| mid | ${s.mid} |`);
    lines.push(`| spread | ${s.spread} |`);
    lines.push(`| sequence_final_update_id | ${s.sequenceFinalUpdateId} |`);
    lines.push(`| quality_flags | ${s.qualityFlagsCsv || "(none)"} |`);
  } else {
    lines.push(`(no snapshot)`);
  }
  lines.push("");

  lines.push(`## 4. Recorder health summary`);
  lines.push("");
  if (input.health) {
    const h = input.health;
    lines.push(`| Metric | Value |`);
    lines.push(`|---|---|`);
    lines.push(`| Sequence gap count (max during window) | ${h.sequenceGapCount} |`);
    lines.push(`| Reconnect count (max during window) | ${h.reconnectCount} |`);
    lines.push(`| Max DB queue size | ${h.maxDbQueueSize} |`);
    lines.push(`| Max spool queue size | ${h.maxSpoolQueueSize} |`);
    lines.push(`| OK / DEGRADED / DOWN samples | ${h.okSamples} / ${h.degradedSamples} / ${h.downSamples} (total=${h.samples}) |`);
  } else {
    lines.push(`(no recorder_health rows yet — recorder may not have completed a sample window)`);
  }
  lines.push("");

  lines.push(`## 5. Spool / insert-error checks`);
  lines.push("");
  lines.push(`- Spool files created during this run: **${input.spoolFilesCreated ? "yes" : "no"}**`);
  lines.push(`- ClickHouse insert errors observed: **${input.insertErrorsObserved ? "yes" : "no"}**`);
  lines.push("");

  lines.push(`## 6. backtest:db sanity replay`);
  lines.push("");
  if (input.backtest.ran) {
    lines.push(`| Field | Value |`);
    lines.push(`|---|---|`);
    lines.push(`| Ran | yes |`);
    lines.push(`| Zones found | ${input.backtest.zonesFound} |`);
    lines.push(`| Triggered | ${input.backtest.zonesTriggered} |`);
    lines.push(`| Reached zones (raw) | ${input.backtest.zonesReachedRaw} |`);
    lines.push(`| Unique reached moves | ${input.backtest.uniqueReachedMoves} |`);
    lines.push(`| Report path | \`${input.backtest.reportPath ?? "-"}\` |`);
    lines.push("");
    lines.push(`> A 10-minute window is far too short for the strategy to find 2% zones — the goal here is only to verify that \`ClickHouseDataSource\` can read the recorded data and the pipeline doesn't crash. Zero zones is normal.`);
  } else {
    lines.push(`Skipped: ${input.backtest.skippedReason ?? "(no reason)"}`);
  }
  lines.push("");

  lines.push(`## 7. Verdict`);
  lines.push("");
  lines.push(`Overall: **${v.overall}**`);
  lines.push("");
  lines.push(`| Check | Pass? | Detail |`);
  lines.push(`|---|---|---|`);
  for (const p of v.parts) lines.push(`| ${p.label} | ${p.ok ? "yes" : "no"} | ${p.detail ?? ""} |`);
  lines.push("");

  if (input.notes.length > 0) {
    lines.push(`## 8. Run notes`);
    lines.push("");
    for (const n of input.notes) lines.push(`- ${n}`);
    lines.push("");
  }

  lines.push(`## How to read this`);
  lines.push("");
  lines.push(`**Normal values for a 10-minute BTCUSDT acceptance run on a healthy network:**`);
  lines.push(`- raw_depth_events: ~30 000 – 200 000 rows (depth@100ms with active markets)`);
  lines.push(`- trades: ~5 000 – 100 000 rows depending on activity`);
  lines.push(`- orderbook_snapshots_1s: ~600 (one per second over 600s, ±a few)`);
  lines.push(`- book_ticker: any positive number — Binance emits on every BBO change`);
  lines.push(`- mark_price: ~10 rows (1Hz)`);
  lines.push(`- liquidations: 0–dozens (sporadic — zero is normal on quiet markets)`);
  lines.push(`- crossed/empty snapshots: 0`);
  lines.push(`- sequence gaps: 0 ideally; 1–2 acceptable on a fresh start while the order book bootstraps`);
  lines.push(`- DB queue size: stays small (< maxBatchSize 5000) — large numbers indicate ClickHouse is slow`);
  lines.push(`- spool files: 0 ideally — any non-zero means the recorder went into fallback`);
  lines.push("");
  lines.push(`**Treat as a problem:**`);
  lines.push(`- raw_depth_events == 0 or trades == 0 — recorder isn't writing the strategy-critical streams`);
  lines.push(`- orderbook_snapshots_1s much fewer than ~60 per minute — the snapshot loop isn't firing`);
  lines.push(`- crossed > 0 — the local order book reconstruction is buggy`);
  lines.push(`- spool files > 0 OR insert errors yes — ClickHouse is unhealthy or the writer can't keep up`);
  lines.push(`- sequence_gap_count growing without bound — Binance is reordering events or the recorder lost packets`);
  lines.push(`- backtest:db FAILED — the ClickHouseDataSource adapter can't read what the recorder wrote (schema drift)`);
  lines.push("");

  return lines.join("\n");
}

function formatDuration(ms: number): string {
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3_600_000) return `${(ms / 60_000).toFixed(1)}min`;
  return `${(ms / 3_600_000).toFixed(2)}h`;
}
