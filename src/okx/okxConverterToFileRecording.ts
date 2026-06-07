// Pure utilities that describe + plan the OKX-swap CSV.gz -> file-recording
// JSONL conversion. The heavy streaming converter is implemented in
//   scripts/okx/convert_and_replay.py
// (chosen because the source files are 600+ MB and Python's pyarrow / gzip
// streaming is the most efficient). This TS module exposes the *plan*,
// *output paths*, and *expected schema* so the converter has a single
// source of truth and tests can assert against it.

import * as path from "node:path";
import type { OkxDayLocator } from "./okxHistoricalDataSource.js";
import { OKX_VENUE_DISPLAY, OKX_SWAP_EXCHANGE_SLUG, OKX_IS_BINANCE } from "./okxTardisSchema.js";

/** The seven output files the converter produces, in deterministic order. */
export const OKX_FILE_RECORDING_OUTPUTS = [
  "raw_depth_events.jsonl",
  "trades.jsonl",
  "book_ticker.jsonl",
  "mark_price.jsonl",
  "liquidations.jsonl",
  "orderbook_snapshots_1s.jsonl",
  "health.jsonl",
  "metadata.json",
] as const;

export type OkxFileRecordingFile = (typeof OKX_FILE_RECORDING_OUTPUTS)[number];

/** Default destination root: `data/file-recordings-from-okx/okx-swap`. */
export const DEFAULT_FILE_RECORDING_ROOT = path.join(
  "data",
  "file-recordings-from-okx",
  OKX_SWAP_EXCHANGE_SLUG,
);

export interface OkxConversionPlan {
  src: OkxDayLocator;
  destDir: string;
  outputs: ReadonlyArray<{ file: OkxFileRecordingFile; absPath: string }>;
  /** Replay window applied during conversion (mirrors what
   *  scripts/okx/convert_and_replay.py uses). `null` = full UTC day. */
  windowUtcHours: { start: number; end: number } | null;
}

export function planOkxConversion(opts: {
  src: OkxDayLocator;
  destRoot?: string;
  windowUtcHours?: { start: number; end: number } | null;
}): OkxConversionPlan {
  const destRoot = opts.destRoot ?? DEFAULT_FILE_RECORDING_ROOT;
  const destDir = path.join(destRoot, opts.src.symbol, opts.src.date);
  const outputs = OKX_FILE_RECORDING_OUTPUTS.map((file) => ({
    file,
    absPath: path.join(destDir, file),
  }));
  return {
    src: opts.src,
    destDir,
    outputs,
    windowUtcHours: opts.windowUtcHours ?? null,
  };
}

/**
 * Shape of one raw_depth_events.jsonl line. The converter (Python) emits
 * this exact JSON; downstream backtest:okx-technical reads it back via
 * the same shape.
 */
export interface RawDepthEventLine {
  ts_us: number;
  ingest_ts_us: number;
  exchange: "okex-swap";
  symbol: string;
  is_snapshot: boolean;
  side: "BID" | "ASK";
  price: number;
  amount: number;
  segment_id?: number;
}

export interface TradeEventLine {
  ts_us: number;
  ingest_ts_us: number;
  exchange: "okex-swap";
  symbol: string;
  trade_id: number | null;
  side: "BUY" | "SELL";
  price: number;
  amount: number;
}

export interface BookTickerLine {
  ts_us: number;
  ingest_ts_us: number;
  exchange: "okex-swap";
  symbol: string;
  best_bid: number;
  best_ask: number;
  best_bid_amount: number;
  best_ask_amount: number;
}

export interface MarkPriceLine {
  ts_us: number;
  ingest_ts_us: number;
  exchange: "okex-swap";
  symbol: string;
  mark_price: number | null;
  index_price: number | null;
  last_price: number | null;
  funding_rate: number | null;
  predicted_funding_rate: number | null;
  open_interest: number | null;
}

export interface LiquidationLine {
  ts_us: number;
  ingest_ts_us: number;
  exchange: "okex-swap";
  symbol: string;
  side: "BUY" | "SELL";
  price: number;
  amount: number;
}

export interface Snapshot1sLine {
  ts_us: number;
  best_bid: number | null;
  best_ask: number | null;
  mid: number | null;
  spread: number | null;
  bid_levels: number;
  ask_levels: number;
  quality_flags: ReadonlyArray<"CROSSED" | "EMPTY" | "WIDE_SPREAD">;
  segment_id?: number;
}

export interface HealthLine {
  ts_us: number;
  status: string;
  source: string;
  sequence_gap_count: number;
  reconnect_count: number;
  db_queue_size: number;
  spool_queue_size: number;
  note?: string;
}

export interface FileRecordingMetadata {
  schema_version: 1;
  exchange: "okex-swap";
  venue_display: typeof OKX_VENUE_DISPLAY;
  instrument: string;
  instrument_kind: "perpetual_swap";
  is_binance_futures: typeof OKX_IS_BINANCE;
  is_directly_equivalent_to_binance_usdsm_futures: false;
  source: {
    provider: "Tardis";
    channel: "datasets.tardis.dev/v1/okex-swap";
    data_types_present: ReadonlyArray<string>;
    original_files_dir: string;
  };
  window: { start_utc: string; end_utc: string; duration_hours: number };
  l2_stream: Record<string, unknown>;
  snapshots_1s: Record<string, unknown>;
  trades: Record<string, unknown>;
  strategy_engine_invoked: boolean;
  strategy_skip_reason?: string;
}
