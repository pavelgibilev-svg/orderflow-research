// Absorption detection.
//
// The intuition: a side absorbs aggressive flow when there's heavy taker
// volume against it but the price barely moves (or returns). We compute a
// score in [0, 1]:
//
//   absorption_long = sellVolume / (1 + |priceProgressDownPct| * sellVolume)
//                     normalised against window total volume
//
// More concretely — large sell flow + small downward progress = high score.

export interface AbsorptionInputs {
  sellVolumeWindow: number;
  buyVolumeWindow: number;
  priceProgressUpPct: number; // positive number
  priceProgressDownPct: number; // positive number
  totalTradeVolumeWindow: number;
}

export interface AbsorptionResult {
  buyAbsorptionScore: number;
  sellAbsorptionScore: number;
}

/**
 * Score interpretation:
 *   - buyAbsorptionScore (long-zone signal): heavy SELL pressure, small downside progress.
 *   - sellAbsorptionScore (short-zone signal): heavy BUY pressure, small upside progress.
 */
export function computeAbsorption(in_: AbsorptionInputs): AbsorptionResult {
  const tot = Math.max(1e-9, in_.totalTradeVolumeWindow);
  // pressureRatio in [0,1] of sell vs total
  const sellRatio = in_.sellVolumeWindow / tot;
  const buyRatio = in_.buyVolumeWindow / tot;
  // progress dampener: stronger penalty for larger move
  const downDampener = 1 / (1 + in_.priceProgressDownPct * 50);
  const upDampener = 1 / (1 + in_.priceProgressUpPct * 50);

  // Long-side absorption needs (a) high sell ratio and (b) small downside progress.
  const buyAbs = clamp01(sellRatio * downDampener * 1.1);
  const sellAbs = clamp01(buyRatio * upDampener * 1.1);
  return { buyAbsorptionScore: buyAbs, sellAbsorptionScore: sellAbs };
}

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}
