// Tardis CSV row schemas, normalised to plain numeric fields.
// Reference: https://docs.tardis.dev/downloadable-csv-files/data-types
//
// All timestamps in returned objects are in **milliseconds** (UTC).

import { microsToMs } from "./time.js";

export type DataType =
  | "incremental_book_L2"
  | "trades"
  | "book_ticker"
  | "derivative_ticker"
  | "liquidations"
  | "book_snapshot_25"
  | "book_snapshot_5"
  | "quotes";

// ----- Generic event union -----

export interface BaseEvent {
  ts: number; // ms
  localTs: number;
  source: DataType;
}

export interface BookL2Event extends BaseEvent {
  source: "incremental_book_L2";
  isSnapshot: boolean;
  side: "bid" | "ask";
  price: number;
  amount: number; // 0 means delete
}

export interface TradeEvent extends BaseEvent {
  source: "trades";
  id: string;
  side: "buy" | "sell"; // taker side
  price: number;
  amount: number;
}

export interface BookTickerEvent extends BaseEvent {
  source: "book_ticker";
  bidPrice: number;
  bidAmount: number;
  askPrice: number;
  askAmount: number;
}

export interface DerivativeTickerEvent extends BaseEvent {
  source: "derivative_ticker";
  fundingRate: number | null;
  predictedFundingRate: number | null;
  openInterest: number | null;
  lastPrice: number | null;
  indexPrice: number | null;
  markPrice: number | null;
}

export interface LiquidationEvent extends BaseEvent {
  source: "liquidations";
  id: string;
  side: "buy" | "sell";
  price: number;
  amount: number;
}

export type AnyEvent =
  | BookL2Event
  | TradeEvent
  | BookTickerEvent
  | DerivativeTickerEvent
  | LiquidationEvent;

// ----- Header -> column index helpers -----

function idx(headers: string[], name: string): number {
  const i = headers.indexOf(name);
  if (i < 0) throw new Error(`Column "${name}" not found in CSV header`);
  return i;
}

function maybeIdx(headers: string[], name: string): number {
  return headers.indexOf(name);
}

// ----- Row parsers -----

export function makeIncrementalBookL2Parser(headers: string[]): (row: string[]) => BookL2Event {
  const tsI = idx(headers, "timestamp");
  const ltsI = idx(headers, "local_timestamp");
  const isSnapI = idx(headers, "is_snapshot");
  const sideI = idx(headers, "side");
  const priceI = idx(headers, "price");
  const amtI = idx(headers, "amount");
  return (row: string[]) => {
    const side = row[sideI];
    return {
      source: "incremental_book_L2",
      ts: microsToMs(row[tsI]),
      localTs: microsToMs(row[ltsI]),
      isSnapshot: row[isSnapI] === "true",
      side: side === "ask" ? "ask" : "bid",
      price: +row[priceI],
      amount: +row[amtI],
    };
  };
}

export function makeTradesParser(headers: string[]): (row: string[]) => TradeEvent {
  const tsI = idx(headers, "timestamp");
  const ltsI = idx(headers, "local_timestamp");
  const idI = idx(headers, "id");
  const sideI = idx(headers, "side");
  const priceI = idx(headers, "price");
  const amtI = idx(headers, "amount");
  return (row: string[]) => ({
    source: "trades",
    ts: microsToMs(row[tsI]),
    localTs: microsToMs(row[ltsI]),
    id: row[idI] ?? "",
    side: row[sideI] === "buy" ? "buy" : "sell",
    price: +row[priceI],
    amount: +row[amtI],
  });
}

export function makeBookTickerParser(headers: string[]): (row: string[]) => BookTickerEvent {
  const tsI = idx(headers, "timestamp");
  const ltsI = idx(headers, "local_timestamp");
  const bpI = idx(headers, "bid_price");
  const baI = idx(headers, "bid_amount");
  const apI = idx(headers, "ask_price");
  const aaI = idx(headers, "ask_amount");
  return (row: string[]) => ({
    source: "book_ticker",
    ts: microsToMs(row[tsI]),
    localTs: microsToMs(row[ltsI]),
    bidPrice: +row[bpI],
    bidAmount: +row[baI],
    askPrice: +row[apI],
    askAmount: +row[aaI],
  });
}

function numOrNull(s: string | undefined): number | null {
  if (s === undefined || s === "" || s === "NaN") return null;
  const n = +s;
  return Number.isFinite(n) ? n : null;
}

export function makeDerivativeTickerParser(headers: string[]): (row: string[]) => DerivativeTickerEvent {
  const tsI = idx(headers, "timestamp");
  const ltsI = idx(headers, "local_timestamp");
  const frI = maybeIdx(headers, "funding_rate");
  const pfrI = maybeIdx(headers, "predicted_funding_rate");
  const oiI = maybeIdx(headers, "open_interest");
  const lpI = maybeIdx(headers, "last_price");
  const ipI = maybeIdx(headers, "index_price");
  const mpI = maybeIdx(headers, "mark_price");
  return (row: string[]) => ({
    source: "derivative_ticker",
    ts: microsToMs(row[tsI]),
    localTs: microsToMs(row[ltsI]),
    fundingRate: frI >= 0 ? numOrNull(row[frI]) : null,
    predictedFundingRate: pfrI >= 0 ? numOrNull(row[pfrI]) : null,
    openInterest: oiI >= 0 ? numOrNull(row[oiI]) : null,
    lastPrice: lpI >= 0 ? numOrNull(row[lpI]) : null,
    indexPrice: ipI >= 0 ? numOrNull(row[ipI]) : null,
    markPrice: mpI >= 0 ? numOrNull(row[mpI]) : null,
  });
}

export function makeLiquidationsParser(headers: string[]): (row: string[]) => LiquidationEvent {
  const tsI = idx(headers, "timestamp");
  const ltsI = idx(headers, "local_timestamp");
  const idI = maybeIdx(headers, "id");
  const sideI = idx(headers, "side");
  const priceI = idx(headers, "price");
  const amtI = idx(headers, "amount");
  return (row: string[]) => ({
    source: "liquidations",
    ts: microsToMs(row[tsI]),
    localTs: microsToMs(row[ltsI]),
    id: idI >= 0 ? row[idI] ?? "" : "",
    side: row[sideI] === "buy" ? "buy" : "sell",
    price: +row[priceI],
    amount: +row[amtI],
  });
}

// ----- Header-based dispatcher -----

export function dataTypeFromHeaders(headers: string[]): DataType | null {
  const set = new Set(headers);
  if (set.has("is_snapshot") && set.has("side") && set.has("price") && set.has("amount")) {
    return "incremental_book_L2";
  }
  if (set.has("bid_price") && set.has("ask_price") && set.has("bid_amount") && set.has("ask_amount")) {
    return "book_ticker";
  }
  if ((set.has("funding_rate") || set.has("predicted_funding_rate") || set.has("mark_price")) && set.has("open_interest")) {
    return "derivative_ticker";
  }
  if (set.has("id") && set.has("side") && set.has("price") && set.has("amount") && !set.has("is_snapshot")) {
    // both trades and liquidations look similar; rely on filename mostly.
    return "trades";
  }
  return null;
}
