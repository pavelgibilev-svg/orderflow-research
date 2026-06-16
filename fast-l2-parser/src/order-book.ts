// L2 order book reconstruction (NOT a matching engine).
//
// Tardis ships absolute-volume L2 increments: each update means "the resting
// size at price X is now Y". size === 0 removes the level. Snapshot rows reset
// the relevant side once. Best bid/ask are cached and only recomputed when the
// current best level is deleted — never by scanning the whole Map per update.
//
// Spread validation is intentionally NOT done here (see validateSpread): it is
// driven externally per timestamp batch by OrderBookTimestampDispatcher.

import type { Side } from "./types.js";
import { CrossedBookError, SequenceGapError, InvalidBookUpdateError } from "./order-book-errors.js";

export interface OrderBookBuilderOptions {
  /** Enforce monotonic incremental sequence (sequence === lastSequence + 1). Default true. */
  validateSequence?: boolean;
}

export class OrderBookBuilder {
  private bids: Map<number, number>;
  private asks: Map<number, number>;

  private bestBidPrice: number | undefined;
  private bestAskPrice: number | undefined;

  private lastSequence: number;

  private inSnapshotMode: boolean;
  private snapshotBidStarted: boolean;
  private snapshotAskStarted: boolean;

  private readonly validateSequence: boolean;

  constructor(options?: OrderBookBuilderOptions) {
    this.bids = new Map<number, number>();
    this.asks = new Map<number, number>();
    this.bestBidPrice = undefined;
    this.bestAskPrice = undefined;
    this.lastSequence = 0;
    this.inSnapshotMode = false;
    this.snapshotBidStarted = false;
    this.snapshotAskStarted = false;
    this.validateSequence = options?.validateSequence ?? true;
  }

  /**
   * Apply one absolute-volume L2 update. Does NOT validate the spread
   * (the dispatcher calls validateSpread once per timestamp batch).
   */
  applyUpdate(
    timestampNs: number,
    sequence: number,
    side: Side,
    price: number,
    size: number,
    isSnapshot: boolean
  ): void {
    // 1-3. Structural validation (throws before touching any state).
    if (side !== 0 && side !== 1) {
      throw new InvalidBookUpdateError("side must be 0 (bid) or 1 (ask)", "side", side);
    }
    if (!Number.isFinite(price) || price <= 0) {
      throw new InvalidBookUpdateError("price must be a finite number > 0", "price", price);
    }
    if (!Number.isFinite(size) || size < 0) {
      throw new InvalidBookUpdateError("size must be a finite number >= 0", "size", size);
    }

    // 4. Snapshot-mode handling — clear each side at most once per snapshot block.
    if (isSnapshot) {
      if (!this.inSnapshotMode) this.enterSnapshotMode();
      if (side === 0 && !this.snapshotBidStarted) {
        this.clearBids();
        this.snapshotBidStarted = true;
      } else if (side === 1 && !this.snapshotAskStarted) {
        this.clearAsks();
        this.snapshotAskStarted = true;
      }
    } else if (this.inSnapshotMode) {
      this.exitSnapshotMode(); // first incremental after a snapshot block
    }

    // 5. Sequence validation — incremental rows only.
    if (!isSnapshot && this.validateSequence) {
      if (this.lastSequence !== 0 && sequence !== this.lastSequence + 1) {
        throw new SequenceGapError(timestampNs, this.lastSequence + 1, sequence, this.lastSequence);
      }
      this.lastSequence = sequence;
    }

    // 6-7. Apply absolute level + maintain cached best price.
    if (side === 0) {
      if (size === 0) {
        if (this.bids.delete(price) && price === this.bestBidPrice) this.recomputeBestBid();
      } else {
        this.bids.set(price, size);
        if (this.bestBidPrice === undefined || price > this.bestBidPrice) this.bestBidPrice = price;
      }
    } else {
      if (size === 0) {
        if (this.asks.delete(price) && price === this.bestAskPrice) this.recomputeBestAsk();
      } else {
        this.asks.set(price, size);
        if (this.bestAskPrice === undefined || price < this.bestAskPrice) this.bestAskPrice = price;
      }
    }
    // 8. Deliberately NO validateSpread() here.
  }

  /**
   * Validate the crossed-book invariant. Called by the dispatcher AFTER all
   * updates for one timestamp have been applied. No-op if either side is empty.
   */
  validateSpread(timestampNs: number, sequence: number): void {
    if (this.bids.size === 0 || this.asks.size === 0) return;
    const bb = this.bestBidPrice;
    const ba = this.bestAskPrice;
    if (bb === undefined || ba === undefined) return;
    if (bb >= ba) {
      throw new CrossedBookError(timestampNs, sequence, bb, ba, this.bids.size, this.asks.size);
    }
  }

  getBestBid(): number | undefined {
    return this.bestBidPrice;
  }
  getBestAsk(): number | undefined {
    return this.bestAskPrice;
  }
  getBestBidSize(): number | undefined {
    return this.bestBidPrice === undefined ? undefined : this.bids.get(this.bestBidPrice);
  }
  getBestAskSize(): number | undefined {
    return this.bestAskPrice === undefined ? undefined : this.asks.get(this.bestAskPrice);
  }

  /** Raw float64 spread. No rounding in core — round only in reporting. */
  getSpread(): number | undefined {
    if (this.bestBidPrice === undefined || this.bestAskPrice === undefined) return undefined;
    return this.bestAskPrice - this.bestBidPrice;
  }

  /** Full reset to an empty, fresh book (used between files / on demand). */
  reset(): void {
    this.bids.clear();
    this.asks.clear();
    this.bestBidPrice = undefined;
    this.bestAskPrice = undefined;
    this.lastSequence = 0;
    this.inSnapshotMode = false;
    this.snapshotBidStarted = false;
    this.snapshotAskStarted = false;
  }

  getBidDepth(): number {
    return this.bids.size;
  }
  getAskDepth(): number {
    return this.asks.size;
  }

  // ---- internals ----

  private enterSnapshotMode(): void {
    this.inSnapshotMode = true;
    this.snapshotBidStarted = false;
    this.snapshotAskStarted = false;
    this.lastSequence = 0; // snapshot resets sequence tracking
  }

  /** Reset snapshot flags only — does NOT clear the book. */
  private exitSnapshotMode(): void {
    this.inSnapshotMode = false;
    this.snapshotBidStarted = false;
    this.snapshotAskStarted = false;
    // lastSequence stays 0 so the first incremental sets it without a gap check.
  }

  private clearBids(): void {
    this.bids.clear();
    this.bestBidPrice = undefined;
  }
  private clearAsks(): void {
    this.asks.clear();
    this.bestAskPrice = undefined;
  }

  /** Linear rescan of one side — only called when the current best level is deleted. */
  private recomputeBestBid(): void {
    let best: number | undefined = undefined;
    for (const p of this.bids.keys()) {
      if (best === undefined || p > best) best = p;
    }
    this.bestBidPrice = best;
  }
  private recomputeBestAsk(): void {
    let best: number | undefined = undefined;
    for (const p of this.asks.keys()) {
      if (best === undefined || p < best) best = p;
    }
    this.bestAskPrice = best;
  }
}
