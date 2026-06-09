// MarketDataSource — abstraction over the existing Tardis CSV pipeline and
// the new ClickHouse-backed live-recorded data. The strategy engine
// (FeatureEngine + ZoneDetector + TargetChecker) only needs to consume a
// time-ordered async stream of typed events; this interface formalises that.
//
// Existing CLIs (`backtest:day`, `backtest:sample-2026`, `validate:tardis`)
// remain unchanged — they call resolveInputFiles + replayFiles directly,
// which is one specific implementation. The `backtest:db` CLI wires up the
// ClickHouseDataSource implementation.

import type { AnyEvent } from "./schema.js";

export interface MarketDataRange {
  symbol: string;
  exchange: string;
  /** Inclusive start timestamp (ms). */
  fromMs: number;
  /** Exclusive end timestamp (ms). */
  toMs: number;
}

export interface MarketDataSource {
  /** Human label used in logs. */
  readonly name: string;
  /** Async iterator over events in chronological order. */
  events(range: MarketDataRange): AsyncIterableIterator<AnyEvent>;
}
