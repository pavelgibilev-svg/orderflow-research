# V11 FINAL DECISION (skeptical)

Build 2026-06-13 · forward-validated absorption labels v11 · skeptical, not production.

## ⚠️ MANUAL CORRECTION (overrides the auto-status)
The auto-script printed `ABSORPTION_LABELS_PROMISING` off the overall COMBINED AUC 0.624. That number is a
**Simpson's-paradox artifact** and the corrected verdict is:

**STATUS: `ABSORPTION_LABELS_REJECTED`** — for trades-only causal features. (The forward-label *framework* is sound and
should be reused; what is rejected is the claim that current causal evidence can predict absorption inside down-pressure.)

## Why REJECTED
- **Within-background separation is chance**: TREND_DOWN COMBINED AUC **0.500**, RANGE **0.508**. The headline 0.624 is
  entirely between-background (TREND_UP 0.659 / LOW_VOL 0.642) — i.e. it re-discovers "are we in a downtrend", which
  GATE_6A already encodes. Inside a down-pressure context it has **no** power to separate ACTIVE_MARKDOWN from
  SELL_PRESSURE_ABSORBED — the exact boundary v9/v10 needed.
- **Micro-absorption blocks are at/below chance**: ABSORPTION_REFILL 0.524, INITIATIVE_CONTROL 0.543,
  EXTENSION_NOT_LATE 0.427 (inverted — overextension *continued*, didn't revert). Only the two trend-proxy blocks
  (EFFORT_VS_RESULT 0.614, BACKGROUND_ALIGNMENT 0.623) cleared 0.55, and they collapse once conditioned on background.
- **Median-split classifier**: precision 28.3% vs base rate 21.7% = +6.6pp only, all from the trend component;
  false-markdown 71.7%.

## What DID work (keep these)
- **Forward labels are well-defined and not window-dominated** (markdown dominance 0.30, absorbed 0.20). They produce a
  clean, reusable markdown/absorbed/no-control split. This framework is the durable output of the pass.
- **Real base-rate finding**: of 21,282 sell-pressure candidates, ~63% are forward-ABSORBED and only ~17.5% forward-
  MARKDOWN; even in TREND_DOWN absorbed (1505) outnumber markdown (1094). When sell pressure appears, continuation is the
  minority outcome at 60m — itself a strong argument AGAINST treating td_s as a universal short signal.
- **Circularity CONFIRMED**: v9 ACTIVE_MARKDOWN label → only 31.8% forward-continued (50.1% absorbed); v9
  ABSORPTION_REVERSAL → 41.6% absorbed, LOWER than the markdown label. The old phase labels are anti-/non-informative
  about forward behaviour, so v10's blocker was bookkeeping against an uninformative label.

## Skeptical bottom line
- The honest test v10 never ran has now been run, and it fails: trades-only causal evidence cannot forecast absorption
  within a down context. The apparent "separation" is trend, not absorption.
- In-sample, single-venue OKX, one uptrend window. Do NOT freeze any blocker, do NOT start td_l. No production.
- Door is open: the absorption-specific blocks (REFILL, INITIATIVE) are exactly the ones that need L2 depth /
  liquidations / OI to have any chance — none of which are in the trades-only series for most windows.
