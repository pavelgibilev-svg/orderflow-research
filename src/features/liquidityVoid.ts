// Liquidity void: how empty is the path between current price and the
// 2% target? A small ask-volume up to mid*1.02 means low resistance for an
// upward move. Symmetrically for shorts.

import type { BookState } from "../strategy/types.js";

export interface VoidResult {
  voidUp2PctScore: number;
  voidDown2PctScore: number;
  askVolUpTo2Pct: number;
  bidVolDownTo2Pct: number;
}

/**
 * Returns a 0..1 void score: 1 = empty (good for breakout), 0 = thick.
 * Calibration: compare 2% bucket volume against the 0.5% bucket (near book).
 * If 2% bucket / 0.5% bucket < 1.5 -> very thin compared to near book.
 */
export function computeVoid(state: BookState): VoidResult {
  const v2 = state.depthBuckets["2"] ?? { bid: 0, ask: 0 };
  const v05 = state.depthBuckets["0.5"] ?? { bid: 0, ask: 0 };
  // Per-side void:
  const askVolUpTo2Pct = v2.ask;
  const bidVolDownTo2Pct = v2.bid;

  // Higher void = lower asks beyond near book.
  // ratio = volume between 0.5% and 2% / volume up to 0.5%
  const askFar = Math.max(0, v2.ask - v05.ask);
  const bidFar = Math.max(0, v2.bid - v05.bid);
  const askNear = Math.max(1e-9, v05.ask);
  const bidNear = Math.max(1e-9, v05.bid);

  const voidUp = clamp01(1 - askFar / (askNear * 3));
  const voidDown = clamp01(1 - bidFar / (bidNear * 3));

  return {
    voidUp2PctScore: voidUp,
    voidDown2PctScore: voidDown,
    askVolUpTo2Pct,
    bidVolDownTo2Pct,
  };
}

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}
