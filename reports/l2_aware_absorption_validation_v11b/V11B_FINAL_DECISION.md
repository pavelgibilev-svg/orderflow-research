# V11B FINAL DECISION (skeptical)

Build 2026-06-14T08:25:30+00:00 · L2-aware absorption validation v11b · skeptical, not production.

**STATUS: L2_ABSORPTION_EVIDENCE_REJECTED**

## v11 scope correction
- v11's REJECT applies to TRADES-ONLY features. v11 never used L2 (di/spread None for okx windows; book never reconstructed).

## Within-background L2 separation (the only test that counts)
- TREND_DOWN: trades 0.5 | **L2_FULL 0.489** (n 165/309, DOWN_0327 only) | **L2_LIGHT 0.503** (n 864/861, 3 down windows).
- RANGE: **L2_FULL 0.491** (n 408/1202).

## Reading
- L2 'matters' only if within-TREND_DOWN/RANGE |AUC-0.5| is materially above the trades-only ~0.50 floor. It is NOT:
  every within-context L2 cell sits at chance — TREND_DOWN L2_FULL 0.489 / L2_LIGHT 0.503; RANGE L2_FULL 0.491 / L2_LIGHT 0.518.
  Even allowing inverted orientation, |AUC-0.5| <= 0.02. Combined trades+L2 does not lift it either (TREND_DOWN 0.455-0.507).
- So **reconstructed order-book depth / refill / microprice does not separate markdown from absorption within a market
  context** at 1-minute causal resolution — the same chance floor as trades-only. The boundary remains unpredictable.

## Honest caveats (why this is REJECTED-for-this-featurization, not "L2 is useless forever")
1. **Single-window full-depth per context**: L2_FULL within-TREND_DOWN = DOWN_0327 only (n 474); within-RANGE = RANGE_0303
   only (n 1610). The remaining book caches (RANGE_0508, UP_0310, BOUNCE_0512) did not finish — the first build process
   died mid-RANGE_0508 and was relaunched. BUT the 3-window L2_LIGHT TREND_DOWN test (n 1725) agrees at 0.503, so the
   down-context negative is robust beyond one window.
2. **1-minute book snapshot**: features are sampled once per minute. Absorption/refill is plausibly a sub-minute
   (seconds) phenomenon; a per-second or per-event book featurization could capture dynamics this resolution smooths away.
   This is the one genuinely open door — NOT explored here.
3. **Liquidations + OI still unintegrated** — the other microstructure layer for seller exhaustion.
4. In-sample, OKX-only. No PnL, no tuning, no td_l. The absorption blocker is NOT alive on this evidence.
