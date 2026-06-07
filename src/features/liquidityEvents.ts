// Tracks add/remove/cancel rates per side over the most recent rolling
// window. We feed it with raw L2 events from the replay engine.

export interface LiquidityEventSnapshot {
  windowSec: number;
  bidAddVol: number;
  bidRemoveVol: number;
  bidCancelVol: number;
  askAddVol: number;
  askRemoveVol: number;
  askCancelVol: number;
}

interface Item {
  ts: number;
  bidAdd: number;
  bidRemove: number;
  bidCancel: number;
  askAdd: number;
  askRemove: number;
  askCancel: number;
}

/**
 * Instead of distinguishing remove vs cancel deterministically (we cannot from
 * snapshots alone), we treat:
 *   amount > prev_amount  -> add (delta = new - prev)
 *   amount = 0            -> remove/cancel (full level)
 *   0 < amount < prev     -> partial reduction (often a hit by trade)
 * The caller (FeatureEngine) wires this with the previous level state.
 */
export class LiquidityEventTracker {
  private readonly windowMs: number;
  private items: Item[] = [];
  private prevBid = new Map<number, number>();
  private prevAsk = new Map<number, number>();

  constructor(windowSec = 60) {
    this.windowMs = windowSec * 1000;
  }

  recordL2(
    ts: number,
    side: "bid" | "ask",
    price: number,
    newAmount: number,
    isSnapshot: boolean
  ): void {
    if (isSnapshot) {
      // Snapshot rows reset our tracking — we treat them as a baseline.
      const map = side === "bid" ? this.prevBid : this.prevAsk;
      map.set(price, newAmount);
      return;
    }
    const map = side === "bid" ? this.prevBid : this.prevAsk;
    const prev = map.get(price) ?? 0;
    let bidAdd = 0,
      bidRemove = 0,
      bidCancel = 0;
    let askAdd = 0,
      askRemove = 0,
      askCancel = 0;
    if (side === "bid") {
      if (newAmount === 0 && prev > 0) bidCancel = prev;
      else if (newAmount > prev) bidAdd = newAmount - prev;
      else if (newAmount < prev && newAmount > 0) bidRemove = prev - newAmount;
    } else {
      if (newAmount === 0 && prev > 0) askCancel = prev;
      else if (newAmount > prev) askAdd = newAmount - prev;
      else if (newAmount < prev && newAmount > 0) askRemove = prev - newAmount;
    }
    if (bidAdd || bidRemove || bidCancel || askAdd || askRemove || askCancel) {
      this.items.push({ ts, bidAdd, bidRemove, bidCancel, askAdd, askRemove, askCancel });
    }
    if (newAmount === 0) map.delete(price);
    else map.set(price, newAmount);
    this.evict(ts);
  }

  private evict(ts: number): void {
    const cutoff = ts - this.windowMs;
    let i = 0;
    while (i < this.items.length && this.items[i].ts < cutoff) i++;
    if (i > 0) this.items = this.items.slice(i);
  }

  snapshot(ts: number): LiquidityEventSnapshot {
    this.evict(ts);
    let bA = 0,
      bR = 0,
      bC = 0,
      aA = 0,
      aR = 0,
      aC = 0;
    for (const it of this.items) {
      bA += it.bidAdd;
      bR += it.bidRemove;
      bC += it.bidCancel;
      aA += it.askAdd;
      aR += it.askRemove;
      aC += it.askCancel;
    }
    return {
      windowSec: this.windowMs / 1000,
      bidAddVol: bA,
      bidRemoveVol: bR,
      bidCancelVol: bC,
      askAddVol: aA,
      askRemoveVol: aR,
      askCancelVol: aC,
    };
  }

  /** 0..1: how much bid-side ADD activity dominates remove+cancel. */
  bidRefillScore(snap: LiquidityEventSnapshot): number {
    const out = snap.bidRemoveVol + snap.bidCancelVol;
    const inn = snap.bidAddVol;
    const total = inn + out;
    if (total <= 0) return 0;
    return clamp01(inn / total);
  }
  askRefillScore(snap: LiquidityEventSnapshot): number {
    const out = snap.askRemoveVol + snap.askCancelVol;
    const inn = snap.askAddVol;
    const total = inn + out;
    if (total <= 0) return 0;
    return clamp01(inn / total);
  }
  bidThinningScore(snap: LiquidityEventSnapshot): number {
    const out = snap.bidRemoveVol + snap.bidCancelVol;
    const inn = snap.bidAddVol;
    const total = inn + out;
    if (total <= 0) return 0;
    return clamp01(out / total);
  }
  askThinningScore(snap: LiquidityEventSnapshot): number {
    const out = snap.askRemoveVol + snap.askCancelVol;
    const inn = snap.askAddVol;
    const total = inn + out;
    if (total <= 0) return 0;
    return clamp01(out / total);
  }
}

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}
