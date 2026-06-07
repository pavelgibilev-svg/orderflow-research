// In-memory L2 order book.
//
// Design choices:
//   - Map<price, amount> for O(1) lookup/update/delete.
//   - Sorted arrays of prices (bid descending, ask ascending) maintained
//     incrementally with binary search. Best-bid/best-ask is `arr[0]`.
//   - depthAroundMid walks the sorted array from the best price outward and
//     stops as soon as the bucket boundary is crossed — no per-call sort.
//   - Snapshot rows reset state for the corresponding side(s) on the
//     first row of a contiguous snapshot block, mirroring how Tardis emits
//     snapshots.
//
// The implementation is research-grade: optimised for clarity AND avoiding
// O(N log N) sort allocations on every feature tick, which dominated CPU
// when the book has 500-1500 levels per side.

export class OrderBook {
  private readonly bids = new Map<number, number>();
  private readonly asks = new Map<number, number>();
  /** Bid prices sorted descending. bidPrices[0] is best (highest) bid. */
  private readonly bidPrices: number[] = [];
  /** Ask prices sorted ascending. askPrices[0] is best (lowest) ask. */
  private readonly askPrices: number[] = [];
  private inSnapshot = false;
  private lastTs = 0;

  reset(): void {
    this.bids.clear();
    this.asks.clear();
    this.bidPrices.length = 0;
    this.askPrices.length = 0;
    this.inSnapshot = false;
  }

  /** Apply a raw row (snapshot or update). amount=0 deletes the level. */
  apply(opts: {
    ts: number;
    isSnapshot: boolean;
    side: "bid" | "ask";
    price: number;
    amount: number;
  }): void {
    if (!Number.isFinite(opts.price) || opts.price <= 0) return;
    if (!Number.isFinite(opts.amount) || opts.amount < 0) return;
    if (opts.isSnapshot && !this.inSnapshot) {
      // Fresh snapshot block: clear book.
      this.bids.clear();
      this.asks.clear();
      this.bidPrices.length = 0;
      this.askPrices.length = 0;
      this.inSnapshot = true;
    } else if (!opts.isSnapshot && this.inSnapshot) {
      this.inSnapshot = false;
    }

    const map = opts.side === "bid" ? this.bids : this.asks;
    const arr = opts.side === "bid" ? this.bidPrices : this.askPrices;
    const cur = map.get(opts.price);

    if (opts.amount === 0) {
      if (cur === undefined) return; // nothing to delete
      map.delete(opts.price);
      const i = opts.side === "bid" ? findDesc(arr, opts.price) : findAsc(arr, opts.price);
      if (i >= 0) arr.splice(i, 1);
      return;
    }

    if (cur !== undefined) {
      // Quantity update at an existing price — index doesn't move.
      map.set(opts.price, opts.amount);
      return;
    }

    // New price level — insert into sorted array.
    map.set(opts.price, opts.amount);
    if (opts.side === "bid") {
      const i = lowerBoundDesc(arr, opts.price);
      arr.splice(i, 0, opts.price);
    } else {
      const i = lowerBoundAsc(arr, opts.price);
      arr.splice(i, 0, opts.price);
    }
    this.lastTs = opts.ts;
  }

  bestBid(): number | null {
    return this.bidPrices.length > 0 ? this.bidPrices[0] : null;
  }
  bestAsk(): number | null {
    return this.askPrices.length > 0 ? this.askPrices[0] : null;
  }

  mid(): number | null {
    const bb = this.bestBid();
    const ba = this.bestAsk();
    if (bb === null || ba === null) return null;
    return (bb + ba) / 2;
  }

  spread(): number | null {
    const bb = this.bestBid();
    const ba = this.bestAsk();
    if (bb === null || ba === null) return null;
    return ba - bb;
  }

  spreadPct(): number | null {
    const m = this.mid();
    const s = this.spread();
    if (m === null || s === null || m <= 0) return null;
    return (s / m) * 100;
  }

  isCrossed(): boolean {
    const bb = this.bestBid();
    const ba = this.bestAsk();
    return bb !== null && ba !== null && bb >= ba;
  }

  bidLevels(): number {
    return this.bids.size;
  }
  askLevels(): number {
    return this.asks.size;
  }

  /** Return depth (sum of amount) within +/- pct around mid for several pcts. */
  depthAroundMid(pcts: number[]): { [pctKey: string]: { bid: number; ask: number } } {
    const out: { [pctKey: string]: { bid: number; ask: number } } = {};
    const mid = this.mid();
    if (mid === null) {
      for (const p of pcts) out[p.toString()] = { bid: 0, ask: 0 };
      return out;
    }
    // Walk sorted prices outward from the best, accumulating volume per bucket.
    // pcts are sorted ascending so we accumulate into progressively larger buckets.
    const sorted = [...pcts].sort((a, b) => a - b);

    // Pre-walk bid side (sorted descending). For each pct compute total bid volume
    // for prices >= mid*(1 - pct/100). Because the array is sorted desc we
    // accumulate while price >= lower bound.
    let bidIdx = 0;
    let bidSum = 0;
    let askIdx = 0;
    let askSum = 0;
    for (const pct of sorted) {
      const lower = mid * (1 - pct / 100);
      const upper = mid * (1 + pct / 100);
      while (bidIdx < this.bidPrices.length && this.bidPrices[bidIdx] >= lower) {
        bidSum += this.bids.get(this.bidPrices[bidIdx]) ?? 0;
        bidIdx++;
      }
      while (askIdx < this.askPrices.length && this.askPrices[askIdx] <= upper) {
        askSum += this.asks.get(this.askPrices[askIdx]) ?? 0;
        askIdx++;
      }
      out[pct.toString()] = { bid: bidSum, ask: askSum };
    }
    return out;
  }

  /** Return total volume on bid side (across all levels). */
  totalBid(): number {
    let s = 0;
    for (const v of this.bids.values()) s += v;
    return s;
  }
  totalAsk(): number {
    let s = 0;
    for (const v of this.asks.values()) s += v;
    return s;
  }

  /** Top N levels of each side, sorted by price closest to mid. */
  topLevels(depth: number): { bids: Array<[number, number]>; asks: Array<[number, number]> } {
    const bids: Array<[number, number]> = [];
    for (let i = 0; i < this.bidPrices.length && bids.length < depth; i++) {
      const p = this.bidPrices[i];
      const a = this.bids.get(p);
      if (a !== undefined) bids.push([p, a]);
    }
    const asks: Array<[number, number]> = [];
    for (let i = 0; i < this.askPrices.length && asks.length < depth; i++) {
      const p = this.askPrices[i];
      const a = this.asks.get(p);
      if (a !== undefined) asks.push([p, a]);
    }
    return { bids, asks };
  }

  isEmpty(): boolean {
    return this.bids.size === 0 || this.asks.size === 0;
  }

  /** Snapshot of internal state for tests. */
  size(): { bids: number; asks: number } {
    return { bids: this.bids.size, asks: this.asks.size };
  }
}

// ---------- Sorted-array helpers ----------

/** Linear search of price in array sorted descending; returns -1 if not present. */
function findDesc(arr: number[], price: number): number {
  // Binary search for descending array.
  let lo = 0,
    hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (arr[mid] === price) return mid;
    if (arr[mid] > price) lo = mid + 1;
    else hi = mid;
  }
  return -1;
}

function findAsc(arr: number[], price: number): number {
  let lo = 0,
    hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (arr[mid] === price) return mid;
    if (arr[mid] < price) lo = mid + 1;
    else hi = mid;
  }
  return -1;
}

/** Insertion index for a descending-sorted array (so larger prices come first). */
function lowerBoundDesc(arr: number[], price: number): number {
  let lo = 0,
    hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (arr[mid] > price) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** Insertion index for an ascending-sorted array. */
function lowerBoundAsc(arr: number[], price: number): number {
  let lo = 0,
    hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (arr[mid] < price) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}
