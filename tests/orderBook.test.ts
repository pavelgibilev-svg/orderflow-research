import { describe, expect, it } from "vitest";
import { OrderBook } from "../src/replay/orderBook.js";

describe("OrderBook replay", () => {
  it("applies snapshot then updates with bid > 0 and amount=0 deletes level", () => {
    const ob = new OrderBook();
    ob.apply({ ts: 1, isSnapshot: true, side: "bid", price: 100, amount: 1 });
    ob.apply({ ts: 1, isSnapshot: true, side: "bid", price: 99, amount: 2 });
    ob.apply({ ts: 1, isSnapshot: true, side: "ask", price: 101, amount: 1.5 });
    ob.apply({ ts: 1, isSnapshot: true, side: "ask", price: 102, amount: 3 });

    expect(ob.bestBid()).toBe(100);
    expect(ob.bestAsk()).toBe(101);
    expect(ob.mid()).toBe(100.5);
    expect(ob.spread()).toBe(1);

    // amount=0 deletes the best bid level
    ob.apply({ ts: 2, isSnapshot: false, side: "bid", price: 100, amount: 0 });
    expect(ob.bestBid()).toBe(99);

    // Update keeps the level
    ob.apply({ ts: 3, isSnapshot: false, side: "bid", price: 99, amount: 5 });
    expect(ob.size().bids).toBe(1);
    expect(ob.bestBid()).toBe(99);
  });

  it("snapshot reset clears the previous book", () => {
    const ob = new OrderBook();
    ob.apply({ ts: 1, isSnapshot: false, side: "bid", price: 50, amount: 1 });
    ob.apply({ ts: 1, isSnapshot: false, side: "ask", price: 60, amount: 1 });
    expect(ob.size()).toEqual({ bids: 1, asks: 1 });

    // Snapshot resets, then new levels populate.
    ob.apply({ ts: 2, isSnapshot: true, side: "bid", price: 70, amount: 1 });
    ob.apply({ ts: 2, isSnapshot: true, side: "ask", price: 80, amount: 1 });
    expect(ob.size()).toEqual({ bids: 1, asks: 1 });
    expect(ob.bestBid()).toBe(70);
    expect(ob.bestAsk()).toBe(80);
  });

  it("crossed and empty book detection", () => {
    const ob = new OrderBook();
    expect(ob.isEmpty()).toBe(true);
    ob.apply({ ts: 1, isSnapshot: true, side: "bid", price: 100, amount: 1 });
    expect(ob.isEmpty()).toBe(true); // ask side still empty
    ob.apply({ ts: 1, isSnapshot: true, side: "ask", price: 99, amount: 1 });
    expect(ob.isEmpty()).toBe(false);
    expect(ob.isCrossed()).toBe(true);
  });

  it("depth around mid sums correct amounts inside pct windows", () => {
    const ob = new OrderBook();
    ob.apply({ ts: 1, isSnapshot: true, side: "bid", price: 100, amount: 1 });
    ob.apply({ ts: 1, isSnapshot: true, side: "bid", price: 99, amount: 1 });
    ob.apply({ ts: 1, isSnapshot: true, side: "ask", price: 101, amount: 1 });
    ob.apply({ ts: 1, isSnapshot: true, side: "ask", price: 102, amount: 1 });

    const buckets = ob.depthAroundMid([0.5, 5]);
    // mid = 100.5 -> 0.5% = +/- 0.5025 -> only inner levels
    expect(buckets["0.5"].bid).toBe(1);
    expect(buckets["0.5"].ask).toBe(1);
    // 5% covers everything
    expect(buckets["5"].bid).toBe(2);
    expect(buckets["5"].ask).toBe(2);
  });
});
