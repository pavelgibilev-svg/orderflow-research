// Binance USDS-M Futures public combined-stream WebSocket client.
//
// Connects to wss://fstream.binance.com/stream?streams=<list> with N symbols
// and N streams per symbol (depth@100ms, aggTrade, bookTicker, markPrice@1s,
// forceOrder). On disconnect it reconnects with exponential backoff (1s, 2s,
// 4s, ... capped at 60s) and surfaces every reconnect to the subscriber.
//
// All inbound JSON is timestamped with `receivedAtMs = Date.now()` so the
// downstream pipeline can compute end-to-end latency.
//
// PUBLIC market-data only — no signed messages, no order ops.
// The class exposes only connect / close / event subscription. There are
// deliberately no methods for sending orders, cancelling orders, modifying
// positions, or any signed REST request.

import { EventEmitter } from "node:events";
import {
  parseDepthMessage,
  parseAggTrade,
  parseBookTicker,
  parseMarkPrice,
  parseForceOrder,
  type DepthEvent,
  type TradeEventLive,
  type BookTickerEventLive,
  type MarkPriceEventLive,
  type LiquidationEventLive,
} from "./binanceTypes.js";

export type BinanceStreamKind = "depth" | "aggTrade" | "bookTicker" | "markPrice" | "forceOrder";

export interface BinanceWsOptions {
  baseUrl?: string;
  symbols: string[];
  /** "100ms" or undefined (1000ms default by Binance). */
  depthSpeed?: "100ms" | "250ms" | "500ms" | "1000ms" | "default";
  /** Streams to subscribe to. Default: all five. */
  streams?: BinanceStreamKind[];
  /** Initial reconnect delay (ms). Doubles each failure up to maxBackoffMs. */
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  /** Optional override of the WebSocket constructor (for tests). */
  wsCtor?: { new (url: string): WebSocket } & typeof WebSocket;
}

export interface BinanceWsEvents {
  connect: () => void;
  disconnect: (info: { code: number; reason: string }) => void;
  reconnect: (attempt: number, delayMs: number) => void;
  raw: (msg: { stream: string; data: unknown; receivedAtMs: number; raw: string }) => void;
  depth: (ev: DepthEvent) => void;
  trade: (ev: TradeEventLive) => void;
  bookTicker: (ev: BookTickerEventLive) => void;
  markPrice: (ev: MarkPriceEventLive) => void;
  liquidation: (ev: LiquidationEventLive) => void;
  error: (err: Error) => void;
}

const DEFAULT_STREAMS: BinanceStreamKind[] = ["depth", "aggTrade", "bookTicker", "markPrice", "forceOrder"];

export class BinanceWsClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private readonly url: string;
  private readonly initialBackoff: number;
  private readonly maxBackoff: number;
  private readonly wsCtor: typeof WebSocket;
  private wantOpen = false;
  private currentBackoff = 0;
  private reconnectCount = 0;
  private connectAttempt = 0;

  constructor(opts: BinanceWsOptions) {
    super();
    const baseUrl = (opts.baseUrl ?? process.env.BINANCE_WS_BASE ?? "wss://fstream.binance.com").replace(/\/$/, "");
    const streams = opts.streams ?? DEFAULT_STREAMS;
    const speed = opts.depthSpeed ?? "100ms";
    const lower = opts.symbols.map((s) => s.toLowerCase());
    const streamPaths: string[] = [];
    for (const s of lower) {
      for (const k of streams) {
        switch (k) {
          case "depth":
            streamPaths.push(speed === "default" ? `${s}@depth` : `${s}@depth@${speed}`);
            break;
          case "aggTrade":
            streamPaths.push(`${s}@aggTrade`);
            break;
          case "bookTicker":
            streamPaths.push(`${s}@bookTicker`);
            break;
          case "markPrice":
            streamPaths.push(`${s}@markPrice@1s`);
            break;
          case "forceOrder":
            streamPaths.push(`${s}@forceOrder`);
            break;
        }
      }
    }
    this.url = `${baseUrl}/stream?streams=${streamPaths.join("/")}`;
    this.initialBackoff = opts.initialBackoffMs ?? 1000;
    this.maxBackoff = opts.maxBackoffMs ?? 60_000;
    this.wsCtor =
      opts.wsCtor ??
      ((globalThis as unknown as { WebSocket?: typeof WebSocket }).WebSocket ??
        // Node 22+ exposes globalThis.WebSocket. If absent, fail early with a
        // clear message rather than crashing at .send().
        (() => {
          throw new Error("globalThis.WebSocket is not available — Node 22+ required, or pass wsCtor option.");
        })());
  }

  /** Returns the URL we will connect to (for diagnostics + tests). */
  getUrl(): string {
    return this.url;
  }
  /** Total reconnection events since startup. */
  getReconnectCount(): number {
    return this.reconnectCount;
  }

  connect(): void {
    this.wantOpen = true;
    this.openSocket();
  }

  close(): void {
    this.wantOpen = false;
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        /* ignore */
      }
      this.ws = null;
    }
  }

  // EventEmitter typing helper
  override on<K extends keyof BinanceWsEvents>(ev: K, cb: BinanceWsEvents[K]): this {
    return super.on(ev, cb as never);
  }
  override emit<K extends keyof BinanceWsEvents>(ev: K, ...args: Parameters<BinanceWsEvents[K]>): boolean {
    return super.emit(ev, ...(args as never[]));
  }

  // ---------- internals ----------

  private openSocket(): void {
    this.connectAttempt++;
    const ws = new this.wsCtor(this.url);
    this.ws = ws;
    ws.addEventListener("open", () => {
      this.currentBackoff = 0;
      this.emit("connect");
    });
    ws.addEventListener("close", (ev) => {
      const closeEv = ev as { code?: number; reason?: string };
      this.emit("disconnect", { code: closeEv.code ?? 0, reason: closeEv.reason ?? "" });
      this.scheduleReconnect();
    });
    ws.addEventListener("error", (e) => {
      const err = e instanceof Error ? e : new Error("ws error");
      this.emit("error", err);
    });
    ws.addEventListener("message", (msgEvt) => {
      const data = (msgEvt as MessageEvent).data;
      const text = typeof data === "string" ? data : data instanceof ArrayBuffer ? Buffer.from(new Uint8Array(data)).toString("utf8") : Buffer.isBuffer(data) ? data.toString("utf8") : String(data);
      const receivedAtMs = Date.now();
      this.handleRawMessage(text, receivedAtMs);
    });
  }

  private scheduleReconnect(): void {
    this.ws = null;
    if (!this.wantOpen) return;
    this.reconnectCount++;
    if (this.currentBackoff === 0) this.currentBackoff = this.initialBackoff;
    else this.currentBackoff = Math.min(this.currentBackoff * 2, this.maxBackoff);
    const delay = this.currentBackoff;
    this.emit("reconnect", this.reconnectCount, delay);
    setTimeout(() => {
      if (this.wantOpen) this.openSocket();
    }, delay);
  }

  /** Public for tests — feed a synthetic combined-stream message. */
  handleRawMessage(text: string, receivedAtMs: number): void {
    let outer: { stream?: string; data?: unknown };
    try {
      outer = JSON.parse(text);
    } catch {
      return;
    }
    if (!outer || typeof outer !== "object") return;
    const stream = outer.stream ?? "";
    const data = outer.data ?? outer; // some endpoints emit raw without {stream,data}
    this.emit("raw", { stream, data, receivedAtMs, raw: text });

    // Dispatch by event type.
    const d = data as Record<string, unknown>;
    const e = d["e"] as string | undefined;
    try {
      if (e === "depthUpdate") this.emit("depth", parseDepthMessage(d as never, receivedAtMs, text));
      else if (e === "aggTrade") this.emit("trade", parseAggTrade(d as never, receivedAtMs, text));
      else if (e === "markPriceUpdate") this.emit("markPrice", parseMarkPrice(d as never, receivedAtMs, text));
      else if (e === "forceOrder") this.emit("liquidation", parseForceOrder(d as never, receivedAtMs, text));
      else if (typeof d["u"] === "number" && typeof d["b"] === "string" && typeof d["a"] === "string") {
        // bookTicker — futures emits without `e` field.
        this.emit("bookTicker", parseBookTicker(d as never, receivedAtMs, text));
      } else if (stream.endsWith("@bookTicker")) {
        this.emit("bookTicker", parseBookTicker(d as never, receivedAtMs, text));
      }
    } catch (err) {
      this.emit("error", err instanceof Error ? err : new Error(String(err)));
    }
  }
}
