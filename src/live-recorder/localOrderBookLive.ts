// Live local order book for Binance USDS-M Futures, following the rules at
// https://developers.binance.com/docs/derivatives/usds-margined-futures/
// websocket-market-streams/How-to-manage-a-local-order-book-correctly
//
// State machine:
//   IDLE
//     -> open WebSocket (depth diff stream) and start buffering events
//     -> fetch REST depth snapshot (lastUpdateId = L)
//     -> drop buffered events with u < L
//     -> wait for an event with U <= L+1 AND u >= L+1; this is the first
//        event to apply on top of the snapshot
//     -> while applying subsequent events check pu == previous u; if not,
//        flag a sequence gap and request a re-snapshot.
//
// We reuse the existing src/replay/orderBook.ts OrderBook implementation for
// the price-level state — same code path that backtests use, so the live
// reconstruction is byte-identical to the backtest replay.

import { OrderBook } from "../replay/orderBook.js";
import type { DepthEvent } from "./binanceTypes.js";
import type { DepthSnapshot } from "./binanceRestClient.js";

export type ResyncCallback = () => Promise<DepthSnapshot>;

export interface LocalOrderBookLiveEvents {
  resync: (reason: "sequence_gap" | "initial" | "manual", at: number) => void;
  applied: (ev: DepthEvent) => void;
  bootstrapped: (lastUpdateId: number) => void;
}

export type ApplyOutcome =
  | { kind: "buffered" }
  | { kind: "dropped_stale" }
  | { kind: "applied"; isFirstAfterSnapshot: boolean }
  | { kind: "sequence_gap"; expected: number; got: number; eventFinalUpdateId: number };

interface BufferedEvent {
  ev: DepthEvent;
}

export interface LocalOrderBookLiveOpts {
  /** Async callback that fetches a fresh REST snapshot when we need one. */
  fetchSnapshot: ResyncCallback;
  /** Optional event hook called on resync events. */
  onResync?: (reason: "sequence_gap" | "initial" | "manual", at: number) => void;
}

export class LocalOrderBookLive {
  readonly book = new OrderBook();
  private bootstrapped = false;
  private lastSnapshotUpdateId = 0;
  private lastAppliedFinalUpdateId = 0;
  private buffered: BufferedEvent[] = [];
  private isResyncPending = false;
  private sequenceGapCount = 0;
  private resyncCount = 0;
  private readonly fetchSnapshot: ResyncCallback;
  private readonly onResync?: (reason: "sequence_gap" | "initial" | "manual", at: number) => void;

  constructor(opts: LocalOrderBookLiveOpts) {
    this.fetchSnapshot = opts.fetchSnapshot;
    this.onResync = opts.onResync;
  }

  getStats(): {
    bootstrapped: boolean;
    lastSnapshotUpdateId: number;
    lastAppliedFinalUpdateId: number;
    bufferedCount: number;
    sequenceGapCount: number;
    resyncCount: number;
  } {
    return {
      bootstrapped: this.bootstrapped,
      lastSnapshotUpdateId: this.lastSnapshotUpdateId,
      lastAppliedFinalUpdateId: this.lastAppliedFinalUpdateId,
      bufferedCount: this.buffered.length,
      sequenceGapCount: this.sequenceGapCount,
      resyncCount: this.resyncCount,
    };
  }

  /** Initial bootstrap. Caller must have already started buffering events. */
  async bootstrap(): Promise<void> {
    const snap = await this.fetchSnapshot();
    this.applySnapshot(snap);
    this.lastSnapshotUpdateId = snap.lastUpdateId;
    this.bootstrapped = true;
    this.isResyncPending = false;
    this.resyncCount++;
    this.onResync?.("initial", Date.now());
    // Drain buffered events that fall under or before lastUpdateId, then
    // apply the rest in order.
    const drained = this.buffered.slice();
    this.buffered = [];
    for (const item of drained) {
      this.applyDepthEvent(item.ev);
    }
  }

  /**
   * Apply a single depth diff event. Returns the outcome so the caller can
   * surface metrics. If we are not bootstrapped, the event is buffered and
   * "buffered" is returned.
   */
  applyDepthEvent(ev: DepthEvent): ApplyOutcome {
    if (!this.bootstrapped || this.isResyncPending) {
      this.buffered.push({ ev });
      // Bound the buffer to avoid unbounded memory if bootstrap is slow.
      if (this.buffered.length > 50_000) this.buffered.splice(0, this.buffered.length - 50_000);
      return { kind: "buffered" };
    }

    // 1. Drop events that ended before our snapshot.
    if (ev.finalUpdateId < this.lastSnapshotUpdateId) {
      return { kind: "dropped_stale" };
    }

    // 2. First event after snapshot must satisfy U <= L+1 AND u >= L+1.
    const isFirst = this.lastAppliedFinalUpdateId === 0;
    if (isFirst) {
      const L = this.lastSnapshotUpdateId;
      if (!(ev.firstUpdateId <= L + 1 && ev.finalUpdateId >= L + 1)) {
        // Stale — skip.
        return { kind: "dropped_stale" };
      }
    } else {
      // 3. Subsequent events must satisfy pu == previous u.
      if (ev.prevFinalUpdateId !== this.lastAppliedFinalUpdateId) {
        this.sequenceGapCount++;
        this.isResyncPending = true;
        return {
          kind: "sequence_gap",
          expected: this.lastAppliedFinalUpdateId,
          got: ev.prevFinalUpdateId,
          eventFinalUpdateId: ev.finalUpdateId,
        };
      }
    }
    // Apply the levels.
    for (const [price, qty] of ev.bids) {
      this.book.apply({ ts: ev.eventTimeMs, isSnapshot: false, side: "bid", price, amount: qty });
    }
    for (const [price, qty] of ev.asks) {
      this.book.apply({ ts: ev.eventTimeMs, isSnapshot: false, side: "ask", price, amount: qty });
    }
    this.lastAppliedFinalUpdateId = ev.finalUpdateId;
    return { kind: "applied", isFirstAfterSnapshot: isFirst };
  }

  /** Re-bootstrap because we hit a sequence gap or manual request. */
  async resync(reason: "sequence_gap" | "manual"): Promise<void> {
    this.isResyncPending = true;
    const snap = await this.fetchSnapshot();
    this.applySnapshot(snap);
    this.lastSnapshotUpdateId = snap.lastUpdateId;
    this.lastAppliedFinalUpdateId = 0;
    this.isResyncPending = false;
    this.resyncCount++;
    this.onResync?.(reason, Date.now());
    // Apply buffered events.
    const drained = this.buffered.slice();
    this.buffered = [];
    for (const item of drained) this.applyDepthEvent(item.ev);
  }

  // ---------- internals ----------
  private applySnapshot(snap: DepthSnapshot): void {
    this.book.reset();
    for (const [price, qty] of snap.bids) {
      this.book.apply({ ts: snap.eventTimeMs, isSnapshot: true, side: "bid", price, amount: qty });
    }
    for (const [price, qty] of snap.asks) {
      this.book.apply({ ts: snap.eventTimeMs, isSnapshot: true, side: "ask", price, amount: qty });
    }
  }
}
