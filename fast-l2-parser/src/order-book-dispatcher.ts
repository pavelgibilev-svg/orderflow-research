// Timestamp-batch dispatcher.
//
// The exchange may emit several updates sharing one timestampNs; the book may be
// transiently crossed *within* that batch. So the crossed-book check must run
// only once the batch is complete. This dispatcher tracks timestamp changes and
// calls book.validateSpread() exactly at batch boundaries (and once at finish).
//
// Hot-path discipline: no per-update object, no arrays, no map/filter/reduce,
// no logging, no JSON. Just a few primitive fields.

import type { Side } from "./types.js";
import { OrderBookBuilder } from "./order-book.js";

export class OrderBookTimestampDispatcher {
  private currentTimestampNs = 0;
  private lastSequenceInBatch = 0;
  private started = false;

  constructor(private readonly book: OrderBookBuilder) {}

  onUpdate(
    timestampNs: number,
    sequence: number,
    side: Side,
    price: number,
    size: number,
    isSnapshot: boolean
  ): void {
    if (!this.started) {
      // First update ever — open the first batch, don't validate anything yet.
      this.started = true;
      this.currentTimestampNs = timestampNs;
    } else if (timestampNs !== this.currentTimestampNs) {
      // New timestamp → the previous batch is complete. Validate it, then roll.
      this.book.validateSpread(this.currentTimestampNs, this.lastSequenceInBatch);
      this.currentTimestampNs = timestampNs;
    }

    this.book.applyUpdate(timestampNs, sequence, side, price, size, isSnapshot);
    this.lastSequenceInBatch = sequence;
  }

  /** Flush the final batch. No-op if no updates were ever seen. */
  finish(): void {
    if (!this.started) return;
    this.book.validateSpread(this.currentTimestampNs, this.lastSequenceInBatch);
  }
}
