// Order book imbalance helpers.

import type { BookState } from "../strategy/types.js";

/** Imbalance per pct bucket: (bid - ask) / (bid + ask). Range -1..+1. */
export function computeImbalance(state: BookState): { [pctKey: string]: number } {
  const out: { [pctKey: string]: number } = {};
  for (const [k, v] of Object.entries(state.depthBuckets)) {
    const sum = v.bid + v.ask;
    out[k] = sum > 0 ? (v.bid - v.ask) / sum : 0;
  }
  return out;
}
