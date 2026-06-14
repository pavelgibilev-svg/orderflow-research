# V9 NEXT BRANCH RECOMMENDATION

Build 2026-06-13T07:52:13+00:00 · phase-separation audit v9 · skeptical, not production.

**Recommended option: B (corrected). Auto-script said A; the manual skeptical review downgrades to B.**

- **Option A (phase separation works):** build td_l / long-permission gate ONLY for ACCUMULATION_UNDER_PRESSURE + ABSORPTION_REVERSAL phases.
- **Option B (phase separation fails / not yet trustworthy):** do NOT calibrate td_l yet; improve the phase classifier first (add the absorption/accumulation detection the gate lacks).
- **Option C (data insufficient):** collect fresh windows per phase (ACTIVE_MARKDOWN, ABSORPTION_REVERSAL, ACCUMULATION_UNDER_PRESSURE, DISTRIBUTION_INTO_DEMAND, LOW_VOL_CHOP).

**Why B, not A:** the only gate that actually separates phases (GATE_6E) goes silent in ACCUMULATION and ABSORPTION — which is correct for *short* permission, but means we have **no working detector for those phases yet** to anchor a td_l on. GATE_6A, which does fire there (40.6% absorption / 28.9% accumulation), fires for the *wrong* reason (down-pressure), so it cannot be inverted into a long gate. Building td_l now would be calibrating a long module on a phase boundary we have not validated.

**Concrete B plan (next pass):**
1. Add explicit causal absorption / accumulation features (sell-pressure-without-new-lows, defended-low count, buyer-recovery slope) and make them a *gating layer on top of* the frozen GATE_6A — i.e. GATE_6A AND NOT absorption AND NOT accumulation — to drive the false-permission in those two phases down from 40.6% / 28.9% toward ~0, WITHOUT touching the frozen gate internals.
2. Validate the phase classifier out-of-sample (the current run is in-sample; 44% of minutes fell into CHOP — tighten that bucket before trusting any rate).
3. Get more than one TREND_UP window and at least one clean dedicated ACCUMULATION and one DISTRIBUTION window (Option C feeds this) before any td_l.
4. Only after absorption/accumulation are reliably detected and OOS-checked → proceed to Option A (td_l for accumulation/absorption).
