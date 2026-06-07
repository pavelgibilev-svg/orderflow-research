// REST snapshot client for Binance USDS-M Futures order book.
// PUBLIC endpoint — no API key, no signed request, no trading.
//
// Endpoint: GET https://fapi.binance.com/fapi/v1/depth?symbol=BTCUSDT&limit=1000
// Response shape (verified against the user-supplied depth.json):
//   {
//     "lastUpdateId": <int>,
//     "E": <event_time_ms>,
//     "T": <transaction_time_ms>,
//     "bids": [["price","qty"], ...],
//     "asks": [["price","qty"], ...]
//   }

import { URL } from "node:url";

export interface DepthSnapshot {
  exchange: "binance-futures";
  symbol: string;
  lastUpdateId: number;
  eventTimeMs: number;
  receivedAtMs: number;
  bids: Array<[number, number]>;
  asks: Array<[number, number]>;
  raw: string;
}

export interface BinanceRestClientOptions {
  baseUrl?: string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}

export class BinanceRestClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: BinanceRestClientOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? process.env.BINANCE_REST_BASE ?? "https://fapi.binance.com").replace(/\/$/, "");
    this.timeoutMs = opts.timeoutMs ?? 15_000;
    this.fetchImpl = opts.fetchImpl ?? fetch;
  }

  /** Fetch a depth snapshot. limit is one of 5,10,20,50,100,500,1000. */
  async fetchDepthSnapshot(symbol: string, limit = 1000): Promise<DepthSnapshot> {
    const u = new URL("/fapi/v1/depth", this.baseUrl);
    u.searchParams.set("symbol", symbol.toUpperCase());
    u.searchParams.set("limit", String(limit));
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), this.timeoutMs);
    let res: Response;
    try {
      res = await this.fetchImpl(u.toString(), { signal: ctrl.signal, method: "GET" });
    } finally {
      clearTimeout(t);
    }
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`Binance REST depth ${res.status}: ${body.slice(0, 300)}`);
    }
    const text = await res.text();
    const j = JSON.parse(text) as {
      lastUpdateId: number;
      E?: number;
      T?: number;
      bids: Array<[string, string]>;
      asks: Array<[string, string]>;
    };
    const now = Date.now();
    return {
      exchange: "binance-futures",
      symbol: symbol.toUpperCase(),
      lastUpdateId: j.lastUpdateId,
      eventTimeMs: j.E ?? j.T ?? now,
      receivedAtMs: now,
      bids: j.bids.map((p) => [Number(p[0]), Number(p[1])]),
      asks: j.asks.map((p) => [Number(p[0]), Number(p[1])]),
      raw: text,
    };
  }
}

/** Pure parser exposed for tests — converts a snapshot JSON string into the
 *  domain shape. Keeps the network call separate from the JSON shape logic. */
export function parseSnapshotPayload(symbol: string, body: string, receivedAtMs = Date.now()): DepthSnapshot {
  const j = JSON.parse(body) as {
    lastUpdateId: number;
    E?: number;
    T?: number;
    bids: Array<[string, string]>;
    asks: Array<[string, string]>;
  };
  return {
    exchange: "binance-futures",
    symbol: symbol.toUpperCase(),
    lastUpdateId: j.lastUpdateId,
    eventTimeMs: j.E ?? j.T ?? receivedAtMs,
    receivedAtMs,
    bids: j.bids.map((p) => [Number(p[0]), Number(p[1])]),
    asks: j.asks.map((p) => [Number(p[0]), Number(p[1])]),
    raw: body,
  };
}
