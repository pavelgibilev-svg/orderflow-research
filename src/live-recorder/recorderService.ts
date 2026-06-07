// RecorderService — top-level orchestrator that wires together:
//   - BinanceWsClient (depth/aggTrade/bookTicker/markPrice/forceOrder)
//   - BinanceRestClient (initial + resync depth snapshots)
//   - LocalOrderBookLive (per symbol, applies snapshot+diff with sequence checks)
//   - BatchWriter (ClickHouse insert with spool fallback)
//   - HealthMonitor (periodic recorder_health rows)
//
// Per-symbol pipeline:
//   raw_depth_events <- every depth update (after parse)
//   trades           <- aggTrade
//   book_ticker      <- bookTicker
//   mark_price       <- markPriceUpdate
//   liquidations     <- forceOrder
//   orderbook_snapshots_1s <- LocalOrderBookLive every SNAPSHOT_INTERVAL_MS
//
// Public market-data only. No API key, no signed REST, no order endpoints.

import { BinanceWsClient } from "./binanceWsClient.js";
import { BinanceRestClient } from "./binanceRestClient.js";
import { LocalOrderBookLive } from "./localOrderBookLive.js";
import { BatchWriter } from "./batchWriter.js";
import { HealthMonitor } from "./healthMonitor.js";
import { ALL_TABLES } from "./schema.js";
import { formatDateTime64 } from "./healthMonitor.js";
import type { ClickHouseClient } from "./clickhouseClient.js";
import { SpoolWriter } from "./spoolWriter.js";
import type {
  DepthEvent,
  TradeEventLive,
  BookTickerEventLive,
  MarkPriceEventLive,
  LiquidationEventLive,
} from "./binanceTypes.js";

export interface RecorderServiceOpts {
  ch: ClickHouseClient;
  exchange: string;
  symbols: string[];
  depthSpeed?: "100ms" | "250ms" | "500ms" | "1000ms" | "default";
  snapshotIntervalMs?: number;
  /** ms — how often to attempt spool recovery. */
  spoolRecoveryIntervalMs?: number;
  spoolDir: string;
  log?: (level: "info" | "warn" | "error", msg: string, extra?: unknown) => void;
  /** Optional override of the websocket constructor (for tests). */
  wsCtor?: ConstructorParameters<typeof BinanceWsClient>[0]["wsCtor"];
  /** Optional REST base override (for tests / staging). */
  restBase?: string;
  /** Optional WS base override (for tests / staging). */
  wsBase?: string;
}

interface PerSymbolState {
  symbol: string;
  book: LocalOrderBookLive;
  // sliding 60s windows for events/sec calculation
  depthTimestamps: number[];
  tradeTimestamps: number[];
  lastDepthEventMs: number;
  lastTradeEventMs: number;
  snapshotTimer: NodeJS.Timeout | null;
  bootstrapPromise: Promise<void> | null;
  health: HealthMonitor;
}

export class RecorderService {
  private readonly opts: RecorderServiceOpts;
  private readonly ws: BinanceWsClient;
  private readonly rest: BinanceRestClient;
  private readonly writer: BatchWriter;
  private readonly spool: SpoolWriter;
  private readonly states = new Map<string, PerSymbolState>();
  private readonly log: (level: "info" | "warn" | "error", msg: string, extra?: unknown) => void;
  private readonly snapshotIntervalMs: number;
  private spoolRecoveryTimer: NodeJS.Timeout | null = null;
  private stopping = false;

  constructor(opts: RecorderServiceOpts) {
    this.opts = opts;
    this.log = opts.log ?? defaultLogger;
    this.snapshotIntervalMs = opts.snapshotIntervalMs ?? 1000;
    this.spool = new SpoolWriter(opts.spoolDir);
    this.writer = new BatchWriter({
      ch: opts.ch,
      spool: this.spool,
      log: this.log,
    });
    this.ws = new BinanceWsClient({
      symbols: opts.symbols,
      depthSpeed: opts.depthSpeed ?? "100ms",
      baseUrl: opts.wsBase,
      wsCtor: opts.wsCtor,
    });
    this.rest = new BinanceRestClient({ baseUrl: opts.restBase });

    for (const sym of opts.symbols) {
      const upper = sym.toUpperCase();
      const book = new LocalOrderBookLive({
        fetchSnapshot: async () => this.rest.fetchDepthSnapshot(upper, 1000),
        onResync: (reason) => this.log("info", `[${upper}] order book resync (${reason})`),
      });
      const state: PerSymbolState = {
        symbol: upper,
        book,
        depthTimestamps: [],
        tradeTimestamps: [],
        lastDepthEventMs: 0,
        lastTradeEventMs: 0,
        snapshotTimer: null,
        bootstrapPromise: null,
        health: new HealthMonitor({
          exchange: opts.exchange,
          symbol: upper,
          collect: () => this.collectHealthSample(upper),
          emit: (row) => this.writer.enqueue("recorder_health", row),
        }),
      };
      this.states.set(upper, state);
    }
    this.wireWsHandlers();
  }

  async start(): Promise<void> {
    // 1. Make sure ClickHouse is reachable; warn but don't abort.
    const ok = await this.opts.ch.ping().catch(() => false);
    if (!ok) this.log("warn", "ClickHouse ping failed — events will spool to disk until DB recovers");

    // 2. Open the WebSocket and begin buffering.
    this.ws.connect();

    // 3. Bootstrap each symbol's order book from REST snapshot.
    for (const [sym, state] of this.states) {
      state.bootstrapPromise = state.book.bootstrap().catch((e) => {
        this.log("error", `[${sym}] initial bootstrap failed`, e);
      });
    }

    // 4. Periodic 1s snapshots and health emission.
    for (const [, state] of this.states) {
      state.snapshotTimer = setInterval(() => this.emitSnapshot(state), this.snapshotIntervalMs);
      if (state.snapshotTimer.unref) state.snapshotTimer.unref();
      state.health.start();
    }

    // 5. Periodic spool recovery (every 60s).
    const recoveryMs = this.opts.spoolRecoveryIntervalMs ?? 60_000;
    this.spoolRecoveryTimer = setInterval(
      () => this.writer.recoverSpool([...ALL_TABLES]).catch((e) => this.log("warn", "spool recovery failed", e)),
      recoveryMs
    );
    if (this.spoolRecoveryTimer.unref) this.spoolRecoveryTimer.unref();

    // 6. Start writer flush loop.
    this.writer.start();

    this.log("info", `RecorderService started symbols=${[...this.states.keys()].join(",")} ws=${this.ws.getUrl()}`);
  }

  async stop(): Promise<void> {
    this.stopping = true;
    for (const [, state] of this.states) {
      if (state.snapshotTimer) clearInterval(state.snapshotTimer);
      state.health.stop();
    }
    if (this.spoolRecoveryTimer) clearInterval(this.spoolRecoveryTimer);
    this.ws.close();
    await this.writer.stop();
  }

  private wireWsHandlers(): void {
    this.ws.on("connect", () => this.log("info", "WS connected"));
    this.ws.on("disconnect", (info) => this.log("warn", `WS disconnected code=${info.code} reason="${info.reason}"`));
    this.ws.on("reconnect", (n, delayMs) => this.log("warn", `WS reconnect attempt #${n} in ${delayMs}ms`));
    this.ws.on("error", (e) => this.log("error", "WS error", e));
    this.ws.on("depth", (ev) => this.onDepth(ev));
    this.ws.on("trade", (ev) => this.onTrade(ev));
    this.ws.on("bookTicker", (ev) => this.onBookTicker(ev));
    this.ws.on("markPrice", (ev) => this.onMarkPrice(ev));
    this.ws.on("liquidation", (ev) => this.onLiquidation(ev));
  }

  // ---------- per-event handlers ----------

  private onDepth(ev: DepthEvent): void {
    const state = this.states.get(ev.symbol);
    if (!state) return;
    state.lastDepthEventMs = ev.eventTimeMs;
    state.depthTimestamps.push(ev.eventTimeMs);
    pruneWindow(state.depthTimestamps);

    // Persist the raw depth event.
    this.writer.enqueue("raw_depth_events", {
      exchange: ev.exchange,
      symbol: ev.symbol,
      event_time: formatDateTime64(ev.eventTimeMs),
      received_at: formatDateTime64(ev.receivedAtMs),
      first_update_id: ev.firstUpdateId,
      final_update_id: ev.finalUpdateId,
      prev_final_update_id: ev.prevFinalUpdateId,
      bids_prices: ev.bids.map((p) => p[0]),
      bids_qty: ev.bids.map((p) => p[1]),
      asks_prices: ev.asks.map((p) => p[0]),
      asks_qty: ev.asks.map((p) => p[1]),
      raw_json: ev.raw,
    });

    // Apply to local book; on sequence gap trigger a resync.
    const outcome = state.book.applyDepthEvent(ev);
    if (outcome.kind === "sequence_gap") {
      this.log(
        "warn",
        `[${ev.symbol}] sequence gap expected pu=${outcome.expected} got pu=${outcome.got}; resyncing`
      );
      state.book
        .resync("sequence_gap")
        .catch((e) => this.log("error", `[${ev.symbol}] resync failed`, e));
    }
  }

  private onTrade(ev: TradeEventLive): void {
    const state = this.states.get(ev.symbol);
    if (!state) return;
    state.lastTradeEventMs = ev.eventTimeMs;
    state.tradeTimestamps.push(ev.eventTimeMs);
    pruneWindow(state.tradeTimestamps);
    this.writer.enqueue("trades", {
      exchange: ev.exchange,
      symbol: ev.symbol,
      event_time: formatDateTime64(ev.eventTimeMs),
      received_at: formatDateTime64(ev.receivedAtMs),
      trade_id: ev.lastTradeId,
      agg_trade_id: ev.aggTradeId,
      price: ev.price,
      qty: ev.qty,
      side: ev.side,
      is_buyer_maker: ev.isBuyerMaker ? 1 : 0,
      first_trade_id: ev.firstTradeId,
      last_trade_id: ev.lastTradeId,
      raw_json: ev.raw,
    });
  }

  private onBookTicker(ev: BookTickerEventLive): void {
    this.writer.enqueue("book_ticker", {
      exchange: ev.exchange,
      symbol: ev.symbol,
      event_time: formatDateTime64(ev.eventTimeMs),
      received_at: formatDateTime64(ev.receivedAtMs),
      update_id: ev.updateId,
      bid_price: ev.bidPrice,
      bid_qty: ev.bidQty,
      ask_price: ev.askPrice,
      ask_qty: ev.askQty,
      raw_json: ev.raw,
    });
  }

  private onMarkPrice(ev: MarkPriceEventLive): void {
    this.writer.enqueue("mark_price", {
      exchange: ev.exchange,
      symbol: ev.symbol,
      event_time: formatDateTime64(ev.eventTimeMs),
      received_at: formatDateTime64(ev.receivedAtMs),
      mark_price: ev.markPrice,
      index_price: ev.indexPrice,
      estimated_settle_price: ev.estimatedSettlePrice,
      funding_rate: ev.fundingRate,
      next_funding_time: formatDateTime64(ev.nextFundingTimeMs),
      raw_json: ev.raw,
    });
  }

  private onLiquidation(ev: LiquidationEventLive): void {
    this.writer.enqueue("liquidations", {
      exchange: ev.exchange,
      symbol: ev.symbol,
      event_time: formatDateTime64(ev.eventTimeMs),
      received_at: formatDateTime64(ev.receivedAtMs),
      side: ev.side,
      order_type: ev.orderType,
      time_in_force: ev.timeInForce,
      original_qty: ev.originalQty,
      price: ev.price,
      average_price: ev.averagePrice,
      order_status: ev.orderStatus,
      last_filled_qty: ev.lastFilledQty,
      filled_accumulated_qty: ev.filledAccumulatedQty,
      trade_time: formatDateTime64(ev.tradeTimeMs),
      raw_json: ev.raw,
    });
  }

  // ---------- periodic snapshot ----------

  private emitSnapshot(state: PerSymbolState): void {
    const stats = state.book.getStats();
    if (!stats.bootstrapped) return; // not yet ready
    const top = state.book.book.topLevels(50);
    const ts = Date.now();
    const bestBid = state.book.book.bestBid();
    const bestAsk = state.book.book.bestAsk();
    const mid = state.book.book.mid();
    const spread = state.book.book.spread();
    const flags: string[] = [];
    if (state.book.book.isCrossed()) flags.push("CROSSED");
    if (state.book.book.isEmpty()) flags.push("EMPTY");
    const sp = state.book.book.spreadPct();
    if (sp !== null && sp > 0.5) flags.push("WIDE_SPREAD");
    this.writer.enqueue("orderbook_snapshots_1s", {
      exchange: this.opts.exchange,
      symbol: state.symbol,
      ts: formatDateTime64(ts),
      best_bid: bestBid ?? 0,
      best_ask: bestAsk ?? 0,
      mid: mid ?? 0,
      spread: spread ?? 0,
      bid_prices: top.bids.map((p) => p[0]),
      bid_qty: top.bids.map((p) => p[1]),
      ask_prices: top.asks.map((p) => p[0]),
      ask_qty: top.asks.map((p) => p[1]),
      depth: 50,
      sequence_final_update_id: stats.lastAppliedFinalUpdateId,
      is_resync: 0,
      quality_flags: flags,
    });
  }

  // ---------- health collection ----------

  private collectHealthSample(symbol: string) {
    const state = this.states.get(symbol);
    const spoolStats = this.spool.stats();
    const wstats = this.writer.stats();
    const dbQueueSize = Object.values(wstats.pending).reduce((a, b) => a + b, 0);
    return {
      wsConnected: !!state, // overestimates — a more precise flag would track WS open/close
      sequenceOk: state ? state.book.getStats().bootstrapped && state.book.getStats().sequenceGapCount === 0 : false,
      lastDepthEventTimeMs: state?.lastDepthEventMs ?? 0,
      lastTradeEventTimeMs: state?.lastTradeEventMs ?? 0,
      depthEventCountInWindow: state?.depthTimestamps.length ?? 0,
      tradeEventCountInWindow: state?.tradeTimestamps.length ?? 0,
      reconnectCount: this.ws.getReconnectCount(),
      sequenceGapCount: state?.book.getStats().sequenceGapCount ?? 0,
      dbQueueSize,
      spoolQueueSize: spoolStats.totalLines,
      notes: spoolStats.files > 0 ? `spool_files=${spoolStats.files}` : "",
    };
  }
}

function pruneWindow(arr: number[], windowMs = 60_000): void {
  const cutoff = Date.now() - windowMs;
  while (arr.length > 0 && arr[0] < cutoff) arr.shift();
}

function defaultLogger(level: "info" | "warn" | "error", msg: string, extra?: unknown): void {
  const prefix = level.toUpperCase();
  if (extra instanceof Error) console.log(`[${new Date().toISOString()}] ${prefix} ${msg} :: ${extra.message}`);
  else if (extra !== undefined) console.log(`[${new Date().toISOString()}] ${prefix} ${msg} :: ${JSON.stringify(extra)}`);
  else console.log(`[${new Date().toISOString()}] ${prefix} ${msg}`);
}
