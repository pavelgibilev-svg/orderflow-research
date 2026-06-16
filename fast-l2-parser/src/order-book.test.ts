import { describe, it, expect } from "vitest";
import { OrderBookBuilder } from "./order-book.js";
import { OrderBookTimestampDispatcher } from "./order-book-dispatcher.js";
import { CrossedBookError, SequenceGapError, InvalidBookUpdateError } from "./order-book-errors.js";

describe("OrderBookBuilder — basic level ops", () => {
  it("1. inserts a bid", () => {
    const book = new OrderBookBuilder();
    book.applyUpdate(1, 1, 0, 100, 5, false);
    expect(book.getBestBid()).toBe(100);
    expect(book.getBestBidSize()).toBe(5);
  });

  it("2. inserts an ask", () => {
    const book = new OrderBookBuilder();
    book.applyUpdate(1, 1, 1, 101, 3, false);
    expect(book.getBestAsk()).toBe(101);
    expect(book.getBestAskSize()).toBe(3);
  });

  it("3. updates an existing level (absolute size)", () => {
    const book = new OrderBookBuilder();
    book.applyUpdate(1, 1, 0, 100, 5, false);
    book.applyUpdate(1, 2, 0, 100, 8, false);
    expect(book.getBestBidSize()).toBe(8);
  });

  it("4. deletes a level with size 0", () => {
    const book = new OrderBookBuilder();
    book.applyUpdate(1, 1, 0, 100, 5, false);
    book.applyUpdate(1, 2, 0, 100, 0, false);
    expect(book.getBestBid()).toBeUndefined();
  });
});

describe("OrderBookBuilder — best level caching", () => {
  it("5. raises best bid on a higher insert", () => {
    const book = new OrderBookBuilder();
    book.applyUpdate(1, 1, 0, 100, 5, false);
    book.applyUpdate(1, 2, 0, 101, 2, false);
    expect(book.getBestBid()).toBe(101);
  });

  it("6. lowers best ask on a lower insert", () => {
    const book = new OrderBookBuilder();
    book.applyUpdate(1, 1, 1, 105, 1, false);
    book.applyUpdate(1, 2, 1, 104, 1, false);
    expect(book.getBestAsk()).toBe(104);
  });

  it("7. recomputes best bid after deleting the top", () => {
    const book = new OrderBookBuilder();
    book.applyUpdate(1, 1, 0, 100, 5, false);
    book.applyUpdate(1, 2, 0, 101, 2, false);
    book.applyUpdate(1, 3, 0, 101, 0, false);
    expect(book.getBestBid()).toBe(100);
  });

  it("8. recomputes best ask after deleting the top", () => {
    const book = new OrderBookBuilder();
    book.applyUpdate(1, 1, 1, 105, 5, false);
    book.applyUpdate(1, 2, 1, 104, 2, false);
    book.applyUpdate(1, 3, 1, 104, 0, false);
    expect(book.getBestAsk()).toBe(105);
  });
});

describe("crossed-book validation (batch-scoped)", () => {
  it("9. throws CrossedBookError after a completed timestamp batch", () => {
    const book = new OrderBookBuilder({ validateSequence: false });
    const dispatcher = new OrderBookTimestampDispatcher(book);
    dispatcher.onUpdate(1000, 1, 0, 100, 5, false);
    dispatcher.onUpdate(1000, 2, 1, 99, 5, false);
    expect(() => dispatcher.finish()).toThrow(CrossedBookError);
  });

  it("10. does NOT throw for a transient cross resolved within one batch", () => {
    const book = new OrderBookBuilder({ validateSequence: false });
    const dispatcher = new OrderBookTimestampDispatcher(book);
    dispatcher.onUpdate(1000, 1, 0, 100, 5, false);
    dispatcher.onUpdate(1001, 2, 1, 101, 5, false);
    // Inside timestamp=1002 the book is briefly crossed (ask 99 vs bid 100),
    // but the same batch removes bid 100 before the batch closes.
    dispatcher.onUpdate(1002, 3, 1, 99, 5, false);
    dispatcher.onUpdate(1002, 4, 0, 100, 0, false);
    expect(() => dispatcher.finish()).not.toThrow();
    expect(book.getBestBid()).toBeUndefined();
    expect(book.getBestAsk()).toBe(99);
  });
});

describe("sequence validation", () => {
  it("11. detects a sequence gap", () => {
    const book = new OrderBookBuilder({ validateSequence: true });
    book.applyUpdate(1, 10, 0, 100, 1, false);
    expect(() => book.applyUpdate(2, 12, 0, 101, 1, false)).toThrow(SequenceGapError);
  });

  it("12. snapshot resets sequence so the next incremental does not require +1", () => {
    const book = new OrderBookBuilder({ validateSequence: true });
    book.applyUpdate(1, 10, 0, 100, 1, false);
    book.applyUpdate(2, 1, 0, 99, 1, true); // snapshot
    expect(() => book.applyUpdate(3, 5, 0, 98, 1, false)).not.toThrow();
  });
});

describe("snapshot mode", () => {
  it("13. clears a side only once per snapshot block", () => {
    const book = new OrderBookBuilder({ validateSequence: false });
    book.applyUpdate(1, 1, 0, 100, 1, false); // pre-existing incremental level
    book.applyUpdate(2, 2, 0, 99, 1, true); // snapshot row #1 → clears bids once, sets 99
    book.applyUpdate(2, 3, 0, 98, 1, true); // snapshot row #2 → must NOT clear again
    expect(book.getBidDepth()).toBe(2);
    expect(book.getBestBid()).toBe(99);
  });
});

describe("invalid updates", () => {
  it("14. rejects invalid side / price / size", () => {
    const book = new OrderBookBuilder();
    // invalid side
    expect(() => book.applyUpdate(1, 1, 2 as unknown as 0 | 1, 100, 1, false)).toThrow(InvalidBookUpdateError);
    // price <= 0
    expect(() => book.applyUpdate(1, 1, 0, 0, 1, false)).toThrow(InvalidBookUpdateError);
    expect(() => book.applyUpdate(1, 1, 0, -5, 1, false)).toThrow(InvalidBookUpdateError);
    // NaN price
    expect(() => book.applyUpdate(1, 1, 0, NaN, 1, false)).toThrow(InvalidBookUpdateError);
    // negative size
    expect(() => book.applyUpdate(1, 1, 0, 100, -1, false)).toThrow(InvalidBookUpdateError);
    // Infinity size
    expect(() => book.applyUpdate(1, 1, 0, 100, Infinity, false)).toThrow(InvalidBookUpdateError);
  });
});
