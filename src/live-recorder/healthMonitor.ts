// Periodic health emitter. Computes per-second event rates from a rolling
// window and writes one row per (exchange, symbol) into recorder_health.

import type { BatchWriter } from "./batchWriter.js";

export interface HealthMonitorOpts {
  exchange: string;
  symbol: string;
  intervalMs?: number;
  windowMs?: number;
  /** Function returning current recorder snapshot. */
  collect: () => HealthSample;
  emit: (row: Record<string, unknown>) => void;
}

export interface HealthSample {
  wsConnected: boolean;
  sequenceOk: boolean;
  lastDepthEventTimeMs: number;
  lastTradeEventTimeMs: number;
  depthEventCountInWindow: number;
  tradeEventCountInWindow: number;
  reconnectCount: number;
  sequenceGapCount: number;
  dbQueueSize: number;
  spoolQueueSize: number;
  notes?: string;
}

export class HealthMonitor {
  private readonly opts: HealthMonitorOpts;
  private readonly intervalMs: number;
  private readonly windowMs: number;
  private timer: NodeJS.Timeout | null = null;

  constructor(opts: HealthMonitorOpts) {
    this.opts = opts;
    this.intervalMs = opts.intervalMs ?? 10_000;
    this.windowMs = opts.windowMs ?? 60_000;
  }

  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => this.tick(), this.intervalMs);
    if (this.timer.unref) this.timer.unref();
  }
  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  /** Public for tests. */
  tick(): void {
    const s = this.opts.collect();
    const seconds = this.windowMs / 1000;
    const dPerSec = s.depthEventCountInWindow / seconds;
    const tPerSec = s.tradeEventCountInWindow / seconds;
    const status = this.classify(s);
    const ts = Date.now();
    this.opts.emit({
      ts: dt(ts),
      exchange: this.opts.exchange,
      symbol: this.opts.symbol,
      status,
      ws_connected: s.wsConnected ? 1 : 0,
      sequence_ok: s.sequenceOk ? 1 : 0,
      last_depth_event_time: dt(s.lastDepthEventTimeMs),
      last_trade_event_time: dt(s.lastTradeEventTimeMs),
      depth_events_per_sec: round3(dPerSec),
      trades_per_sec: round3(tPerSec),
      reconnect_count: s.reconnectCount,
      sequence_gap_count: s.sequenceGapCount,
      db_queue_size: s.dbQueueSize,
      spool_queue_size: s.spoolQueueSize,
      notes: s.notes ?? "",
    });
  }

  private classify(s: HealthSample): "OK" | "DEGRADED" | "DOWN" {
    if (!s.wsConnected) return "DOWN";
    const now = Date.now();
    if (s.lastDepthEventTimeMs > 0 && now - s.lastDepthEventTimeMs > 30_000) return "DEGRADED";
    if (!s.sequenceOk) return "DEGRADED";
    if (s.spoolQueueSize > 0) return "DEGRADED";
    return "OK";
  }
}

/** ClickHouse DateTime64 wants ISO-like format. */
function dt(ts: number): string {
  if (!ts || !Number.isFinite(ts)) return "1970-01-01 00:00:00.000";
  return new Date(ts).toISOString().replace("T", " ").replace("Z", "");
}
function round3(n: number): number {
  return Math.round(n * 1000) / 1000;
}

export function formatDateTime64(ts: number): string {
  return dt(ts);
}
