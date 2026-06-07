// Pure SQL builders for the acceptance run. Building these as pure
// functions keeps them snapshot-testable without hitting ClickHouse.
//
// All queries are scoped to a (symbol, exchange, time-range) window. The
// query layer formats DateTime64 literals using the same `toDateTime64('...', 3, 'UTC')`
// pattern the rest of the project uses.

import { formatDt64 } from "../../data/clickhouseDataSource.js";

export interface AcceptanceWindow {
  exchange: string;
  symbol: string;
  fromMs: number;
  toMs: number;
}

function dt(ms: number): string {
  return `toDateTime64('${formatDt64(ms)}', 3, 'UTC')`;
}
function esc(s: string): string {
  return s.replace(/'/g, "''");
}

const TIME_COL_BY_TABLE: { [t: string]: string } = {
  raw_depth_events: "event_time",
  trades: "event_time",
  orderbook_snapshots_1s: "ts",
  book_ticker: "event_time",
  mark_price: "event_time",
  liquidations: "event_time",
  recorder_health: "ts",
};

/** Returns the SELECT count() per acceptance-table within the window. */
export function buildCountSql(table: string, w: AcceptanceWindow): string {
  const col = TIME_COL_BY_TABLE[table];
  if (!col) throw new Error(`Unknown table: ${table}`);
  return `
    SELECT count() AS c
    FROM ${esc(table)}
    WHERE exchange = '${esc(w.exchange)}'
      AND symbol = '${esc(w.symbol)}'
      AND ${col} >= ${dt(w.fromMs)}
      AND ${col} <  ${dt(w.toMs)}
  `.trim();
}

/** Min, max event_time per table within the window. */
export function buildMinMaxTimeSql(table: string, w: AcceptanceWindow): string {
  const col = TIME_COL_BY_TABLE[table];
  if (!col) throw new Error(`Unknown table: ${table}`);
  return `
    SELECT
      toString(min(${col})) AS first_ts,
      toString(max(${col})) AS last_ts
    FROM ${esc(table)}
    WHERE exchange = '${esc(w.exchange)}'
      AND symbol = '${esc(w.symbol)}'
      AND ${col} >= ${dt(w.fromMs)}
      AND ${col} <  ${dt(w.toMs)}
  `.trim();
}

/** Spread min/max/avg, count of crossed/empty snapshots. */
export function buildSnapshotQualitySql(w: AcceptanceWindow): string {
  return `
    SELECT
      count()                                                  AS snapshots,
      countIf(best_bid > 0 AND best_ask > 0 AND best_bid >= best_ask) AS crossed,
      countIf(best_bid = 0 OR best_ask = 0)                    AS empty,
      countIf(arrayExists(x -> x = 'CROSSED', quality_flags))  AS flagged_crossed,
      countIf(arrayExists(x -> x = 'EMPTY',   quality_flags))  AS flagged_empty,
      countIf(arrayExists(x -> x = 'WIDE_SPREAD', quality_flags)) AS flagged_wide_spread,
      min(spread)                                              AS spread_min,
      max(spread)                                              AS spread_max,
      avg(spread)                                              AS spread_avg
    FROM orderbook_snapshots_1s
    WHERE exchange = '${esc(w.exchange)}'
      AND symbol = '${esc(w.symbol)}'
      AND ts >= ${dt(w.fromMs)}
      AND ts <  ${dt(w.toMs)}
  `.trim();
}

/** Latest snapshot row at the end of the window. */
export function buildLatestSnapshotSql(w: AcceptanceWindow): string {
  return `
    SELECT
      toString(ts) AS ts,
      best_bid, best_ask, mid, spread,
      sequence_final_update_id,
      arrayStringConcat(quality_flags, ',') AS quality_flags_csv
    FROM orderbook_snapshots_1s
    WHERE exchange = '${esc(w.exchange)}'
      AND symbol = '${esc(w.symbol)}'
      AND ts >= ${dt(w.fromMs)}
      AND ts <  ${dt(w.toMs)}
    ORDER BY ts DESC
    LIMIT 1
  `.trim();
}

/** Aggregated recorder_health counters across the window. */
export function buildHealthAggregateSql(w: AcceptanceWindow): string {
  return `
    SELECT
      max(sequence_gap_count) AS sequence_gap_count,
      max(reconnect_count)    AS reconnect_count,
      max(db_queue_size)      AS max_db_queue_size,
      max(spool_queue_size)   AS max_spool_queue_size,
      countIf(status = 'OK')        AS ok_samples,
      countIf(status = 'DEGRADED')  AS degraded_samples,
      countIf(status = 'DOWN')      AS down_samples,
      count() AS samples
    FROM recorder_health
    WHERE exchange = '${esc(w.exchange)}'
      AND symbol = '${esc(w.symbol)}'
      AND ts >= ${dt(w.fromMs)}
      AND ts <  ${dt(w.toMs)}
  `.trim();
}

export const ACCEPTANCE_TABLES = [
  "raw_depth_events",
  "trades",
  "orderbook_snapshots_1s",
  "book_ticker",
  "mark_price",
  "liquidations",
  "recorder_health",
] as const;
