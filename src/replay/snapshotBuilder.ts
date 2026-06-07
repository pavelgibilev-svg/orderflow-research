// Periodic snapshot builder. On every wall-clock tick (`featureIntervalSec`)
// we capture: best bid/ask, mid, spread, depth-around-mid buckets, total
// volumes per side and the top-N levels.

import type { BookState, DepthBuckets, StrategyConfig } from "../strategy/types.js";
import type { OrderBook } from "./orderBook.js";

export function captureBookState(
  book: OrderBook,
  ts: number,
  cfg: StrategyConfig,
  qualityFlags: string[]
): BookState {
  const bestBid = book.bestBid();
  const bestAsk = book.bestAsk();
  const mid = book.mid();
  const spread = book.spread();
  const spreadPct = book.spreadPct();
  let depthBuckets: DepthBuckets = {};
  if (mid !== null) depthBuckets = book.depthAroundMid(cfg.depthPctBuckets);
  return {
    ts,
    bestBid,
    bestAsk,
    mid,
    spread,
    spreadPct,
    totalBid: book.totalBid(),
    totalAsk: book.totalAsk(),
    depthBuckets,
    bidLevels: book.bidLevels(),
    askLevels: book.askLevels(),
    qualityFlags: qualityFlags.slice(),
  };
}

export interface ExportedSnapshot {
  ts: number;
  isoTs: string;
  bestBid: number | null;
  bestAsk: number | null;
  mid: number | null;
  bids: Array<[number, number]>;
  asks: Array<[number, number]>;
}

export function exportSnapshot(book: OrderBook, ts: number, depth: number): ExportedSnapshot {
  const top = book.topLevels(depth);
  return {
    ts,
    isoTs: new Date(ts).toISOString(),
    bestBid: book.bestBid(),
    bestAsk: book.bestAsk(),
    mid: book.mid(),
    bids: top.bids,
    asks: top.asks,
  };
}
