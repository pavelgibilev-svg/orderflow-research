// ClickHouseDataSource — reads recorded depth + trade events from the
// orderflow database and yields them in the same shape the existing
// MarketReplayEngine consumes (`AnyEvent`).
//
// This adapter keeps the strategy engine source-agnostic: the same
// FeatureEngine / ZoneDetector / TargetChecker pipeline can run on Tardis
// CSV or on our own live-recorded ClickHouse data without code changes.
//
// Strategy thresholds are NOT touched here.

import type { ClickHouseClient } from "../live-recorder/clickhouseClient.js";
import type { AnyEvent, BookL2Event, TradeEvent, LiquidationEvent } from "./schema.js";
import type { MarketDataRange, MarketDataSource } from "./marketDataSource.js";

export interface ClickHouseDataSourceOptions {
  ch: ClickHouseClient;
  /** Page size for SELECT pagination. Default 50000. */
  pageSize?: number;
  /** Optional override of which tables to read. */
  tables?: {
    rawDepth: string;
    trades: string;
    liquidations: string;
  };
}

const DEFAULT_TABLES = {
  rawDepth: "raw_depth_events",
  trades: "trades",
  liquidations: "liquidations",
};

interface RawDepthRow {
  exchange: string;
  symbol: string;
  event_time: string;
  first_update_id: number | string;
  final_update_id: number | string;
  bids_prices: number[];
  bids_qty: number[];
  asks_prices: number[];
  asks_qty: number[];
}

interface TradeRow {
  exchange: string;
  symbol: string;
  event_time: string;
  agg_trade_id: number | string;
  price: number;
  qty: number;
  side: string;
}

interface LiquidationRow {
  exchange: string;
  symbol: string;
  event_time: string;
  side: string;
  price: number;
  original_qty: number;
}

export class ClickHouseDataSource implements MarketDataSource {
  readonly name = "clickhouse";
  private readonly ch: ClickHouseClient;
  private readonly pageSize: number;
  private readonly tables: typeof DEFAULT_TABLES;

  constructor(opts: ClickHouseDataSourceOptions) {
    this.ch = opts.ch;
    this.pageSize = opts.pageSize ?? 50_000;
    this.tables = opts.tables ?? DEFAULT_TABLES;
  }

  async *events(range: MarketDataRange): AsyncIterableIterator<AnyEvent> {
    // Load each table page-by-page, then n-way merge by event_time.
    const depthIter = this.streamRawDepth(range);
    const tradeIter = this.streamTrades(range);
    const liqIter = this.streamLiquidations(range);

    interface IterState {
      iter: AsyncIterator<AnyEvent>;
      head: AnyEvent | null;
      done: boolean;
    }
    const states: IterState[] = [];
    for (const it of [depthIter, tradeIter, liqIter]) {
      const a = it[Symbol.asyncIterator]();
      const f = await a.next();
      states.push({ iter: a, head: f.done ? null : f.value, done: !!f.done });
    }
    while (true) {
      let minIdx = -1;
      let minTs = Number.POSITIVE_INFINITY;
      for (let i = 0; i < states.length; i++) {
        const s = states[i];
        if (s.done || !s.head) continue;
        if (s.head.ts < minTs) {
          minTs = s.head.ts;
          minIdx = i;
        }
      }
      if (minIdx === -1) return;
      const s = states[minIdx];
      yield s.head!;
      const nx = await s.iter.next();
      if (nx.done) {
        s.done = true;
        s.head = null;
      } else s.head = nx.value;
    }
  }

  // ---------- per-table streamers ----------

  /**
   * Yields one BookL2Event per (price, side) inside each raw_depth_events row.
   * The first event of the day MAY be a snapshot row (Binance bootstraps via
   * REST then via diff stream) — we surface diffs as `isSnapshot=false`.
   * If the upstream depth includes amount=0 entries, the existing OrderBook
   * treats them as deletes.
   */
  private async *streamRawDepth(range: MarketDataRange): AsyncIterableIterator<BookL2Event> {
    const rows = await this.fetchPaged<RawDepthRow>(this.tables.rawDepth, range, [
      "exchange",
      "symbol",
      "event_time",
      "first_update_id",
      "final_update_id",
      "bids_prices",
      "bids_qty",
      "asks_prices",
      "asks_qty",
    ]);
    for (const r of rows) {
      const ts = parseDt64(r.event_time);
      // bids
      for (let i = 0; i < r.bids_prices.length; i++) {
        yield {
          source: "incremental_book_L2",
          ts,
          localTs: ts,
          isSnapshot: false,
          side: "bid",
          price: Number(r.bids_prices[i]),
          amount: Number(r.bids_qty[i] ?? 0),
        };
      }
      // asks
      for (let i = 0; i < r.asks_prices.length; i++) {
        yield {
          source: "incremental_book_L2",
          ts,
          localTs: ts,
          isSnapshot: false,
          side: "ask",
          price: Number(r.asks_prices[i]),
          amount: Number(r.asks_qty[i] ?? 0),
        };
      }
    }
  }

  private async *streamTrades(range: MarketDataRange): AsyncIterableIterator<TradeEvent> {
    const rows = await this.fetchPaged<TradeRow>(this.tables.trades, range, [
      "exchange",
      "symbol",
      "event_time",
      "agg_trade_id",
      "price",
      "qty",
      "side",
    ]);
    for (const r of rows) {
      const ts = parseDt64(r.event_time);
      yield {
        source: "trades",
        ts,
        localTs: ts,
        id: String(r.agg_trade_id),
        side: r.side === "sell" ? "sell" : "buy",
        price: Number(r.price),
        amount: Number(r.qty),
      };
    }
  }

  private async *streamLiquidations(range: MarketDataRange): AsyncIterableIterator<LiquidationEvent> {
    const rows = await this.fetchPaged<LiquidationRow>(this.tables.liquidations, range, [
      "exchange",
      "symbol",
      "event_time",
      "side",
      "price",
      "original_qty",
    ]);
    for (const r of rows) {
      const ts = parseDt64(r.event_time);
      yield {
        source: "liquidations",
        ts,
        localTs: ts,
        id: "",
        side: r.side === "sell" ? "sell" : "buy",
        price: Number(r.price),
        amount: Number(r.original_qty),
      };
    }
  }

  /** Pull all rows from `table` for the range, paginated, sorted ascending by event_time. */
  private async fetchPaged<T>(
    table: string,
    range: MarketDataRange,
    cols: string[]
  ): Promise<T[]> {
    const colList = cols.join(", ");
    const fromIso = formatDt64(range.fromMs);
    const toIso = formatDt64(range.toMs);
    const sym = sqlEscape(range.symbol);
    const ex = sqlEscape(range.exchange);
    const out: T[] = [];
    let offset = 0;
    while (true) {
      const sql = `
        SELECT ${colList}
        FROM ${this.ch.qualifyTable(table)}
        WHERE exchange = '${ex}'
          AND symbol = '${sym}'
          AND event_time >= toDateTime64('${fromIso}', 3, 'UTC')
          AND event_time <  toDateTime64('${toIso}', 3, 'UTC')
        ORDER BY event_time ASC, exchange, symbol
        LIMIT ${this.pageSize}
        OFFSET ${offset}
      `;
      const rows = await this.ch.query<T>(sql);
      out.push(...rows);
      if (rows.length < this.pageSize) break;
      offset += this.pageSize;
    }
    return out;
  }
}

/** "2026-05-09 12:34:56.789" -> ms since epoch (UTC). */
export function parseDt64(s: string): number {
  if (typeof s !== "string") return 0;
  // ClickHouse JSONEachRow returns DateTime64 as "YYYY-MM-DD HH:MM:SS.fff".
  const t = s.replace(" ", "T") + "Z";
  const ms = Date.parse(t);
  return Number.isFinite(ms) ? ms : 0;
}

/** ms -> "YYYY-MM-DD HH:MM:SS.fff" expected by the SQL `toDateTime64` literal. */
export function formatDt64(ms: number): string {
  const d = new Date(ms);
  const yyyy = d.getUTCFullYear();
  const mm = pad2(d.getUTCMonth() + 1);
  const dd = pad2(d.getUTCDate());
  const HH = pad2(d.getUTCHours());
  const MM = pad2(d.getUTCMinutes());
  const SS = pad2(d.getUTCSeconds());
  const fff = String(d.getUTCMilliseconds()).padStart(3, "0");
  return `${yyyy}-${mm}-${dd} ${HH}:${MM}:${SS}.${fff}`;
}
function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}
function sqlEscape(s: string): string {
  return s.replace(/'/g, "''");
}
