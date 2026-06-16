// Shared types.
//
// There are TWO event shapes in this project, kept distinct on purpose:
//
//   * `L2ParserCallback` (task 1, CSV parser) — carries `symbol`, no isSnapshot.
//   * `L2EventCallback` + `L2UpdateEvent` (task 2, order book) — carry
//     `isSnapshot`, no symbol. This is the canonical order-book event.
//
// Both are flat primitive callbacks: NO object is allocated per row/update, so
// there is nothing for the GC to churn through on the hot path.

/** Side encoded as a number to avoid string comparisons downstream. 0 = bid, 1 = ask. */
export type Side = 0 | 1;

// ============================================================================
// Order-book event (task 2)
// ============================================================================

/**
 * One L2 increment. `size` is the ABSOLUTE volume now resting at `price`
 * (Tardis semantics), NOT a delta. `size === 0` means "remove this level".
 * `isSnapshot === true` marks a row that belongs to the initial snapshot phase.
 */
export interface L2UpdateEvent {
  timestampNs: number;
  sequence: number;
  side: Side;
  price: number;
  size: number;
  isSnapshot: boolean;
}

/** Flat primitive callback for order-book updates (preferred — zero per-update alloc). */
export type L2EventCallback = (
  timestampNs: number,
  sequence: number,
  side: Side,
  price: number,
  size: number,
  isSnapshot: boolean
) => void;

// ============================================================================
// CSV parser event (task 1) — has `symbol`, no `isSnapshot`
// ============================================================================

/** Variant A — a single mutable struct reused across all rows (no per-row alloc). */
export interface MutableL2UpdateEvent {
  timestampNs: number;
  sequence: number;
  symbol: string;
  side: Side;
  price: number;
  size: number;
}

/**
 * Flat primitive callback emitted by the CSV parser. `symbol` is the empty
 * string when the parser runs with `parseSymbol: false` (benchmark mode), which
 * skips the only per-row string allocation.
 */
export type L2ParserCallback = (
  timestampNs: number,
  sequence: number,
  symbol: string,
  side: Side,
  price: number,
  size: number
) => void;
