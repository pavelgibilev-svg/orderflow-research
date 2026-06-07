// Typed shapes for the Binance USDS-M Futures public market-data streams.
// Field names are the wire-level lowercase one-letter codes documented at
// https://developers.binance.com/docs/derivatives/usds-margined-futures/
// We translate to camelCase domain events in the parser.

// ---------- raw wire shapes ----------

export interface BinanceCombinedStream<T> {
  stream: string;
  data: T;
}

export interface BinanceDiffDepthMessage {
  e: "depthUpdate";
  E: number; // event time (ms)
  T: number; // transaction time (ms)
  s: string; // symbol
  U: number; // first update id in event
  u: number; // final update id in event
  pu: number; // final update id in previous event
  b: Array<[string, string]>; // bids [price, qty]
  a: Array<[string, string]>; // asks
}

export interface BinanceAggTradeMessage {
  e: "aggTrade";
  E: number; // event time
  s: string;
  a: number; // aggregate trade id
  p: string; // price
  q: string; // qty
  f: number; // first trade id
  l: number; // last trade id
  T: number; // trade time
  m: boolean; // is buyer maker
}

export interface BinanceBookTickerMessage {
  e?: "bookTicker"; // futures emits without `e` historically
  u: number; // order book update id
  s: string;
  b: string; // best bid price
  B: string; // best bid qty
  a: string; // best ask price
  A: string; // best ask qty
  T?: number;
  E: number;
}

export interface BinanceMarkPriceMessage {
  e: "markPriceUpdate";
  E: number;
  s: string;
  p: string; // mark price
  i: string; // index price
  P: string; // estimated settle price
  r: string; // funding rate
  T: number; // next funding time
}

export interface BinanceForceOrderMessage {
  e: "forceOrder";
  E: number;
  o: {
    s: string;
    S: string; // side (BUY / SELL)
    o: string; // order type
    f: string; // time in force
    q: string; // original qty
    p: string; // price
    ap: string; // average price
    X: string; // order status
    l: string; // last filled qty
    z: string; // filled accumulated qty
    T: number; // trade time
  };
}

// ---------- normalised domain events ----------

export interface DepthEvent {
  exchange: string;
  symbol: string;
  eventTimeMs: number;
  receivedAtMs: number;
  firstUpdateId: number;
  finalUpdateId: number;
  prevFinalUpdateId: number;
  bids: Array<[number, number]>;
  asks: Array<[number, number]>;
  raw: string;
}

export interface TradeEventLive {
  exchange: string;
  symbol: string;
  eventTimeMs: number;
  receivedAtMs: number;
  aggTradeId: number;
  price: number;
  qty: number;
  side: "buy" | "sell";
  isBuyerMaker: boolean;
  firstTradeId: number;
  lastTradeId: number;
  raw: string;
}

export interface BookTickerEventLive {
  exchange: string;
  symbol: string;
  eventTimeMs: number;
  receivedAtMs: number;
  updateId: number;
  bidPrice: number;
  bidQty: number;
  askPrice: number;
  askQty: number;
  raw: string;
}

export interface MarkPriceEventLive {
  exchange: string;
  symbol: string;
  eventTimeMs: number;
  receivedAtMs: number;
  markPrice: number;
  indexPrice: number;
  estimatedSettlePrice: number;
  fundingRate: number;
  nextFundingTimeMs: number;
  raw: string;
}

export interface LiquidationEventLive {
  exchange: string;
  symbol: string;
  eventTimeMs: number;
  receivedAtMs: number;
  side: "buy" | "sell";
  orderType: string;
  timeInForce: string;
  originalQty: number;
  price: number;
  averagePrice: number;
  orderStatus: string;
  lastFilledQty: number;
  filledAccumulatedQty: number;
  tradeTimeMs: number;
  raw: string;
}

// ---------- parsers ----------

const EXCHANGE = "binance-futures";

export function parseDepthMessage(msg: BinanceDiffDepthMessage, receivedAtMs: number, raw: string): DepthEvent {
  return {
    exchange: EXCHANGE,
    symbol: msg.s,
    eventTimeMs: msg.E,
    receivedAtMs,
    firstUpdateId: msg.U,
    finalUpdateId: msg.u,
    prevFinalUpdateId: msg.pu,
    bids: msg.b.map((p) => [Number(p[0]), Number(p[1])]),
    asks: msg.a.map((p) => [Number(p[0]), Number(p[1])]),
    raw,
  };
}

export function parseAggTrade(msg: BinanceAggTradeMessage, receivedAtMs: number, raw: string): TradeEventLive {
  // Binance aggTrade `m` (isBuyerMaker) tells which side initiated the trade.
  // m=true  -> seller is taker, BUYER is maker -> taker was SELLING -> "sell"
  // m=false -> buyer is taker -> "buy"
  const side: "buy" | "sell" = msg.m ? "sell" : "buy";
  return {
    exchange: EXCHANGE,
    symbol: msg.s,
    eventTimeMs: msg.E,
    receivedAtMs,
    aggTradeId: msg.a,
    price: Number(msg.p),
    qty: Number(msg.q),
    side,
    isBuyerMaker: msg.m,
    firstTradeId: msg.f,
    lastTradeId: msg.l,
    raw,
  };
}

export function parseBookTicker(msg: BinanceBookTickerMessage, receivedAtMs: number, raw: string): BookTickerEventLive {
  return {
    exchange: EXCHANGE,
    symbol: msg.s,
    eventTimeMs: msg.E ?? msg.T ?? receivedAtMs,
    receivedAtMs,
    updateId: msg.u,
    bidPrice: Number(msg.b),
    bidQty: Number(msg.B),
    askPrice: Number(msg.a),
    askQty: Number(msg.A),
    raw,
  };
}

export function parseMarkPrice(msg: BinanceMarkPriceMessage, receivedAtMs: number, raw: string): MarkPriceEventLive {
  return {
    exchange: EXCHANGE,
    symbol: msg.s,
    eventTimeMs: msg.E,
    receivedAtMs,
    markPrice: Number(msg.p),
    indexPrice: Number(msg.i),
    estimatedSettlePrice: Number(msg.P),
    fundingRate: Number(msg.r),
    nextFundingTimeMs: msg.T,
    raw,
  };
}

export function parseForceOrder(msg: BinanceForceOrderMessage, receivedAtMs: number, raw: string): LiquidationEventLive {
  const side: "buy" | "sell" = (msg.o.S ?? "").toUpperCase() === "SELL" ? "sell" : "buy";
  return {
    exchange: EXCHANGE,
    symbol: msg.o.s,
    eventTimeMs: msg.E,
    receivedAtMs,
    side,
    orderType: msg.o.o,
    timeInForce: msg.o.f,
    originalQty: Number(msg.o.q),
    price: Number(msg.o.p),
    averagePrice: Number(msg.o.ap),
    orderStatus: msg.o.X,
    lastFilledQty: Number(msg.o.l),
    filledAccumulatedQty: Number(msg.o.z),
    tradeTimeMs: msg.o.T,
    raw,
  };
}
