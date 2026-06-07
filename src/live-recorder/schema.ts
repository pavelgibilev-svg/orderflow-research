// ClickHouse DDL for the live-recorder. All tables are MergeTree-family with
// daily partitioning by event_time and an order key starting with
// (exchange, symbol). This is documented in section 5 of the spec.
//
// The migrations are idempotent — every CREATE TABLE uses IF NOT EXISTS.

export const DDL = {
  database(db: string): string {
    return `CREATE DATABASE IF NOT EXISTS ${db}`;
  },

  rawDepthEvents(db: string): string {
    return `
CREATE TABLE IF NOT EXISTS ${db}.raw_depth_events (
  exchange              LowCardinality(String),
  symbol                LowCardinality(String),
  event_time            DateTime64(3, 'UTC'),
  received_at           DateTime64(3, 'UTC'),
  first_update_id       UInt64,
  final_update_id       UInt64,
  prev_final_update_id  Int64 DEFAULT -1,
  bids_prices           Array(Float64),
  bids_qty              Array(Float64),
  asks_prices           Array(Float64),
  asks_qty              Array(Float64),
  raw_json              String CODEC(ZSTD(3)),
  inserted_at           DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (exchange, symbol, event_time, final_update_id)
`.trim();
  },

  orderbookSnapshots1s(db: string): string {
    return `
CREATE TABLE IF NOT EXISTS ${db}.orderbook_snapshots_1s (
  exchange                  LowCardinality(String),
  symbol                    LowCardinality(String),
  ts                        DateTime64(3, 'UTC'),
  best_bid                  Float64,
  best_ask                  Float64,
  mid                       Float64,
  spread                    Float64,
  bid_prices                Array(Float64),
  bid_qty                   Array(Float64),
  ask_prices                Array(Float64),
  ask_qty                   Array(Float64),
  depth                     UInt16,
  sequence_final_update_id  UInt64,
  is_resync                 UInt8 DEFAULT 0,
  quality_flags             Array(LowCardinality(String))
)
ENGINE = ReplacingMergeTree(ts)
PARTITION BY toYYYYMMDD(ts)
ORDER BY (exchange, symbol, ts)
`.trim();
  },

  trades(db: string): string {
    return `
CREATE TABLE IF NOT EXISTS ${db}.trades (
  exchange         LowCardinality(String),
  symbol           LowCardinality(String),
  event_time       DateTime64(3, 'UTC'),
  received_at      DateTime64(3, 'UTC'),
  trade_id         Int64 DEFAULT 0,
  agg_trade_id     Int64 DEFAULT 0,
  price            Float64,
  qty              Float64,
  side             LowCardinality(String),
  is_buyer_maker   UInt8,
  first_trade_id   Int64 DEFAULT 0,
  last_trade_id    Int64 DEFAULT 0,
  raw_json         String CODEC(ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (exchange, symbol, event_time, agg_trade_id)
`.trim();
  },

  bookTicker(db: string): string {
    return `
CREATE TABLE IF NOT EXISTS ${db}.book_ticker (
  exchange     LowCardinality(String),
  symbol       LowCardinality(String),
  event_time   DateTime64(3, 'UTC'),
  received_at  DateTime64(3, 'UTC'),
  update_id    UInt64,
  bid_price    Float64,
  bid_qty      Float64,
  ask_price    Float64,
  ask_qty      Float64,
  raw_json     String CODEC(ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (exchange, symbol, event_time, update_id)
`.trim();
  },

  markPrice(db: string): string {
    return `
CREATE TABLE IF NOT EXISTS ${db}.mark_price (
  exchange                  LowCardinality(String),
  symbol                    LowCardinality(String),
  event_time                DateTime64(3, 'UTC'),
  received_at               DateTime64(3, 'UTC'),
  mark_price                Float64,
  index_price               Float64,
  estimated_settle_price    Float64,
  funding_rate              Float64,
  next_funding_time         DateTime64(3, 'UTC'),
  raw_json                  String CODEC(ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (exchange, symbol, event_time)
`.trim();
  },

  liquidations(db: string): string {
    return `
CREATE TABLE IF NOT EXISTS ${db}.liquidations (
  exchange                LowCardinality(String),
  symbol                  LowCardinality(String),
  event_time              DateTime64(3, 'UTC'),
  received_at             DateTime64(3, 'UTC'),
  side                    LowCardinality(String),
  order_type              LowCardinality(String),
  time_in_force           LowCardinality(String),
  original_qty            Float64,
  price                   Float64,
  average_price           Float64,
  order_status            LowCardinality(String),
  last_filled_qty         Float64,
  filled_accumulated_qty  Float64,
  trade_time              DateTime64(3, 'UTC'),
  raw_json                String CODEC(ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (exchange, symbol, event_time)
`.trim();
  },

  recorderHealth(db: string): string {
    return `
CREATE TABLE IF NOT EXISTS ${db}.recorder_health (
  ts                       DateTime64(3, 'UTC'),
  exchange                 LowCardinality(String),
  symbol                   LowCardinality(String),
  status                   LowCardinality(String),
  ws_connected             UInt8,
  sequence_ok              UInt8,
  last_depth_event_time    DateTime64(3, 'UTC'),
  last_trade_event_time    DateTime64(3, 'UTC'),
  depth_events_per_sec     Float64,
  trades_per_sec           Float64,
  reconnect_count          UInt32,
  sequence_gap_count       UInt32,
  db_queue_size            UInt32,
  spool_queue_size         UInt32,
  notes                    String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (exchange, symbol, ts)
`.trim();
  },
};

/** Returns the full migration SQL list in dependency order. */
export function allMigrationSql(database: string): string[] {
  return [
    DDL.database(database),
    DDL.rawDepthEvents(database),
    DDL.orderbookSnapshots1s(database),
    DDL.trades(database),
    DDL.bookTicker(database),
    DDL.markPrice(database),
    DDL.liquidations(database),
    DDL.recorderHealth(database),
  ];
}

export const ALL_TABLES = [
  "raw_depth_events",
  "orderbook_snapshots_1s",
  "trades",
  "book_ticker",
  "mark_price",
  "liquidations",
  "recorder_health",
] as const;

export type RecorderTable = (typeof ALL_TABLES)[number];
