// Data quality checks. Producing these flags is a hard requirement of the
// spec — sections 6 ("Quality flags") and 13 ("Data Quality").

import type { BookState, StrategyConfig } from "../strategy/types.js";
import type { OrderBook } from "./orderBook.js";

export interface QualityState {
  lastEventTs: number;
  totalGapsMs: number;
  invalidIntervals: number;
}

export function newQualityState(): QualityState {
  return { lastEventTs: 0, totalGapsMs: 0, invalidIntervals: 0 };
}

export function evaluateBookQuality(
  book: OrderBook,
  ts: number,
  cfg: StrategyConfig,
  q: QualityState
): string[] {
  const flags: string[] = [];
  if (book.isEmpty()) flags.push("EMPTY_BOOK");
  if (book.isCrossed()) flags.push("CROSSED");
  const sp = book.spreadPct();
  if (sp !== null && sp > cfg.quality.maxSpreadPct) flags.push("WIDE_SPREAD");
  if (cfg.quality.requireBestBidAsk) {
    if (book.bestBid() === null || book.bestAsk() === null) flags.push("NO_BBO");
  }
  if (q.lastEventTs > 0 && ts - q.lastEventTs > cfg.quality.maxGapMs) flags.push("GAP");
  if (flags.length > 0) q.invalidIntervals += 1;
  return flags;
}
