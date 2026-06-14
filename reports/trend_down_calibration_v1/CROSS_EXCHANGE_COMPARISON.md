# CROSS-EXCHANGE COMPARISON

Build: research/calibration (updated after full L2 parse completed).

**STATUS: SINGLE_EXCHANGE_ONLY for clusters/capital-states; PRICE-LEVEL cross-check NOW available.**

## What can / cannot be compared
- Clusters & capital-states were built from **Bybit ob200 only**. OKX provides L2 for just the **last day of
  each window** (2025-11-22, 2026-01-31, 2026-02-14) and **no in-window OKX trades**, so cluster-level
  cross-venue *confirmation* and order-flow agreement are **N/A**.
- However, both venues now have reconstructed per-second mids on those 3 overlap days, so a real
  **price-agreement / data-quality cross-check** is possible and was run.

## Price agreement on the 3 overlap days (Bybit vs OKX reconstructed mid)
| date | common minutes | mean mid diff | median |mid diff| | minute-return corr |
|---|--:|--:|--:|--:|
| 2025-11-22 | 1440 | +0.4 bps | 0.7 bps | 0.995 |
| 2026-01-31 | 1440 | −0.0 bps | 0.6 bps | 0.998 |
| 2026-02-14 | 1440 | +0.1 bps | 0.5 bps | 0.992 |

**Verdict: Bybit and OKX mids agree to <1 bps with 0.99+ return correlation.** The two venues see identical
price action -> the Bybit-only mid-price outcome labels (MFE / hit2) are trustworthy and not a reconstruction
artifact. This also implies **price-derived capital-states would agree across venues**; only the
**order-flow-based** evidence (taker/CVD) remains untestable cross-venue here.

## Answers
1. **Does Bybit see the same as OKX?** — On PRICE: YES (mids agree <1 bps, corr 0.99+). On ORDER-FLOW: cannot test (no OKX trades).
2. **Vice versa** — same: price agreement strong; order-flow N/A.
3. **Where do signals coincide?** — Price-level structure coincides on all 3 overlap days; capital-state *labels* not independently built on OKX.
4. **Where is one venue noise?** — No price-level divergence observed (no venue is noisier on mid).
5. **Do cross-venue-confirmed clusters give better hit2/PF?** — **N/A** (only 1 OKX day/window; cannot form OKX clusters).
6. **Use cross-venue confirmation as filter/veto?** — **Not yet** — needs full-coverage OKX L2 + in-window trades on both venues. Price agreement alone is necessary-but-not-sufficient.
