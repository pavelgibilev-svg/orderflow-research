# V10 NEXT BRANCH RECOMMENDATION

Build 2026-06-13 · absorption/accumulation blocker v10 · skeptical, not production.

**Recommended next: more phase-classifier work — specifically a forward-validated ABSORPTION feature — NOT td_l calibration, NOT lock-in.**

Split verdict drives this:
- **ACCUMULATION blocker (b10E) is the keeper-direction**: 28.9% -> 13.7% false-permission while retaining 71% of markdown. Worth carrying forward, but still in-sample only.
- **ABSORPTION blocker does not exist yet**: no variant gets absorption under ~20% without destroying markdown, and the ex-post forward-downside test does NOT confirm it catches real absorption. So the absorption half is effectively REJECTED pending a better feature.

Concrete next pass (v11 candidate):
1. **Design an absorption feature that is validated against forward behaviour, not against the (circular) phase label.** Target property: minutes flagged absorbed should have measurably *less* forward downside than non-flagged gate-active minutes in the same window. The current F1/F3/F5 fail this; F2/F6 only cut sample. Candidate ideas: delta-vs-displacement efficiency (CVD spent per unit of downside), repeated-low-rejection with shrinking wick depth, post-sweep reclaim speed.
2. **Break the circularity**: re-derive the ABSORPTION/ACCUMULATION phase labels and the blocker features from *independent* signal families so "reduction" is not bookkeeping.
3. **OOS + window diversity**: get a real dedicated ACCUMULATION window, a DISTRIBUTION window, and a 2nd TREND_UP window (Option C from v9) before trusting any rate. Everything here is in-sample, single-venue OKX, 1 uptrend window.
4. **Only after absorption is forward-validated** → proceed to td_l (long module) on ACCUMULATION/ABSORPTION. Building td_l now would anchor a long strategy on an in-sample, partly-circular, ex-post-unvalidated boundary.

Unchanged constraints carried forward:
- GATE_6A / GATE_6E / ENTRY_8A frozen; blocker is a layer only.
- 8A stays a TIMING overlay inside ACTIVE_MARKDOWN; not a standalone short entry (v8).
- No threshold tuning to PF; no production; TP 2% / SL 1.5% unchanged.
