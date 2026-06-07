// OKX-swap data schema as distributed by the Tardis CDN.
//
// All five files use the Tardis canonical layout for OKX swap perpetuals.
// Columns and example rows verified against
//   data/okx-historical/BTC-USDT-SWAP/2026-04-01/
// see reports/OKX_HISTORICAL_L2_AUDIT.md sections D.1–D.5 for the audit.

/** Tardis exchange slug for OKX swap (perpetual) instruments. */
export const OKX_SWAP_EXCHANGE_SLUG = "okex-swap";

/** Default Tardis CDN base for OKX-swap CSV.gz files. */
export const OKX_TARDIS_BASE = "https://datasets.tardis.dev/v1";

/**
 * Build the OKX-swap Tardis dataset URL for one data type / date / symbol.
 *
 * Per Tardis' published policy the **first day of every calendar month**
 * is free without an API key; other days require paid credentials.
 */
export function buildOkxTardisUrl(opts: {
  dataType: OkxDataType;
  date: string; // YYYY-MM-DD
  symbol: string; // e.g. "BTC-USDT-SWAP"
  base?: string;
}): string {
  const [yyyy, mm, dd] = opts.date.split("-");
  const base = (opts.base ?? OKX_TARDIS_BASE).replace(/\/$/, "");
  return `${base}/${OKX_SWAP_EXCHANGE_SLUG}/${opts.dataType}/${yyyy}/${mm}/${dd}/${opts.symbol}.csv.gz`;
}

/** OKX-swap data types we read from Tardis. */
export type OkxDataType =
  | "incremental_book_L2"
  | "trades"
  | "book_ticker"
  | "derivative_ticker"
  | "liquidations";

export const OKX_REQUIRED_DATA_TYPES: ReadonlyArray<OkxDataType> = ["incremental_book_L2", "trades"];

export const OKX_RECOMMENDED_DATA_TYPES: ReadonlyArray<OkxDataType> = [
  "book_ticker",
  "derivative_ticker",
  "liquidations",
];

/* ----------------------------------------------------------------------- */
/* Row-level CSV schemas. Numeric fields are kept as strings to preserve  */
/* the original decimal precision until the consumer parses them.         */
/* ----------------------------------------------------------------------- */

export interface OkxL2Row {
  exchange: "okex-swap";
  symbol: string;
  /** Microseconds since epoch (OKX matching-engine time). */
  timestamp: string;
  /** Microseconds since epoch (Tardis ingestion time). */
  local_timestamp: string;
  /** "true" => initial-state row; "false" => incremental delta. */
  is_snapshot: "true" | "false";
  side: "bid" | "ask";
  /** USDT price level. */
  price: string;
  /** Contracts at this level. `0` means delete level. */
  amount: string;
}

export interface OkxTradeRow {
  exchange: "okex-swap";
  symbol: string;
  timestamp: string;
  local_timestamp: string;
  /** Monotonic OKX trade id. */
  id: string;
  /** Taker side: `"buy"` = taker buy, `"sell"` = taker sell. */
  side: "buy" | "sell";
  price: string;
  amount: string;
}

export interface OkxBookTickerRow {
  exchange: "okex-swap";
  symbol: string;
  timestamp: string;
  local_timestamp: string;
  ask_amount: string;
  ask_price: string;
  bid_price: string;
  bid_amount: string;
}

export interface OkxDerivativeTickerRow {
  exchange: "okex-swap";
  symbol: string;
  timestamp: string;
  local_timestamp: string;
  funding_timestamp: string;
  funding_rate: string;
  predicted_funding_rate: string;
  open_interest: string;
  last_price: string;
  index_price: string;
  mark_price: string;
}

export interface OkxLiquidationRow {
  exchange: "okex-swap";
  symbol: string;
  timestamp: string;
  local_timestamp: string;
  id: string;
  /** Liquidation direction. */
  side: "buy" | "sell";
  price: string;
  amount: string;
}

/**
 * Contract spec metadata for OKX BTC-USDT perpetual swap. Useful when
 * comparing raw "amount" (contracts) to USDT notional.
 *
 * 1 BTC-USDT-SWAP contract = 0.01 BTC underlying. So an `amount=10` row in
 * a trade means 0.10 BTC traded.
 */
export const OKX_BTCUSDT_SWAP_CONTRACT_SIZE_BTC = 0.01;

/** Hard rule: this venue is **OKX**, not Binance. */
export const OKX_VENUE_DISPLAY = "OKX";
export const OKX_IS_BINANCE = false;
