// Tiny state-machine that documents the OKX `books-l2-tbt` resync protocol
// our converter and audit code apply. The actual book mutation reuses
// OrderBook from src/replay/orderBook.ts; this file is the protocol layer
// that decides WHICH rows go to the book and WHEN to emit `segment_id`
// boundaries.
//
// The protocol, distilled from the OKX docs and the Tardis CSV layout:
//
//   1. The stream begins with a (possibly empty) prefix of `is_snapshot=false`
//      rows that Tardis recorded BEFORE the OKX subscription completed.
//      Per OKX, these must NOT be applied to the post-snapshot book.
//      We tag them as "pre_snapshot" and drop them (with a counter).
//
//   2. The first contiguous run of `is_snapshot=true` rows is the initial
//      anchor: a top-N (~400 per side) snapshot of the book at the time
//      OKX accepted the subscription. We reset the book and apply each row.
//
//   3. Subsequent `is_snapshot=false` rows are deltas. amount=0 deletes,
//      amount>0 sets the level.
//
//   4. Mid-stream re-anchor: if a new contiguous block of `is_snapshot=true`
//      rows appears (Tardis reconnected to OKX), reset the book again and
//      bump `segment_id`. Subsequent deltas belong to the new segment.
//
//   5. `qty=0` on a level that doesn't currently exist in the book is a no-op
//      (NOT a gap). Tardis sometimes records redundant deletes.
//
//   6. There is NO explicit sequence-id column for OKX in the Tardis L2
//      export. We measure continuity by per-microsecond ordering only; gap
//      counting is performed on the `trades.id` field (which IS monotonic
//      on OKX), not on L2.

export type OkxL2Phase = "pre_snapshot" | "in_snapshot" | "deltas";

export interface OkxReplayCounters {
  pre_snapshot_deltas_dropped: number;
  snapshot_anchors: number;
  snapshot_rows_applied: number;
  delta_rows_applied: number;
  level_deletes: number;
  level_sets: number;
  zero_qty_noop_on_missing_level: number;
  segment_id: number;
}

export function newCounters(): OkxReplayCounters {
  return {
    pre_snapshot_deltas_dropped: 0,
    snapshot_anchors: 0,
    snapshot_rows_applied: 0,
    delta_rows_applied: 0,
    level_deletes: 0,
    level_sets: 0,
    zero_qty_noop_on_missing_level: 0,
    segment_id: 0,
  };
}

export interface OkxReplayState {
  phase: OkxL2Phase;
  /** Microsecond timestamp of the current snapshot anchor (start of
   *  the contiguous `is_snapshot=true` block). */
  currentAnchorTsUs: number | null;
  counters: OkxReplayCounters;
}

export function newState(): OkxReplayState {
  return { phase: "pre_snapshot", currentAnchorTsUs: null, counters: newCounters() };
}

export type OkxReplayDecision =
  | { kind: "drop_pre_snapshot" }
  | { kind: "reset_and_apply_snapshot"; segmentId: number }
  | { kind: "apply_snapshot_row" }
  | { kind: "apply_delta" };

/** Stateful decision function called per L2 row, in stream order. Caller
 *  feeds the returned decision to its book + emitter.
 */
export function decide(
  state: OkxReplayState,
  row: { isSnapshot: boolean; tsUs: number },
): OkxReplayDecision {
  const c = state.counters;
  if (row.isSnapshot) {
    if (state.phase !== "in_snapshot" || state.currentAnchorTsUs !== row.tsUs) {
      // Start of a new snapshot chunk: reset and bump segment_id
      state.phase = "in_snapshot";
      state.currentAnchorTsUs = row.tsUs;
      c.snapshot_anchors += 1;
      c.segment_id = c.snapshot_anchors; // 1-based id of the active segment
      c.snapshot_rows_applied += 1;
      return { kind: "reset_and_apply_snapshot", segmentId: c.segment_id };
    }
    c.snapshot_rows_applied += 1;
    return { kind: "apply_snapshot_row" };
  }
  // delta row
  if (state.phase === "pre_snapshot") {
    c.pre_snapshot_deltas_dropped += 1;
    return { kind: "drop_pre_snapshot" };
  }
  // Either in_snapshot or deltas: transition into deltas
  state.phase = "deltas";
  c.delta_rows_applied += 1;
  return { kind: "apply_delta" };
}

/** Convenience helper for the qty-0 / qty>0 mutation that callers apply
 *  to their own SortedMap-based book. The OrderBook from
 *  src/replay/orderBook.ts already does this; this helper exists for the
 *  converter pass which doesn't import OrderBook. */
export function applyLevelMutation(
  bids: Map<number, number>,
  asks: Map<number, number>,
  row: { side: "bid" | "ask"; price: number; amount: number },
  counters: OkxReplayCounters,
): void {
  const map = row.side === "bid" ? bids : asks;
  if (row.amount === 0) {
    if (map.has(row.price)) {
      map.delete(row.price);
      counters.level_deletes += 1;
    } else {
      counters.zero_qty_noop_on_missing_level += 1;
    }
  } else {
    map.set(row.price, row.amount);
    counters.level_sets += 1;
  }
}
