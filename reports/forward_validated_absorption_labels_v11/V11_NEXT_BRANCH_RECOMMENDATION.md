# V11 NEXT BRANCH RECOMMENDATION

Build 2026-06-13 · forward-validated absorption labels v11 · skeptical, not production.

**Recommended next: DATA COLLECTION (microstructure + per-state OOS windows) — NOT a v12 router, NOT td_l.**

Rationale: v11 shows trades-only causal evidence cannot separate markdown from absorption inside a down context
(within-TREND_DOWN AUC 0.500). A router or td_l built now would just be a trend filter relabelled as absorption. The
blocks that *should* carry absorption signal (ABSORPTION_REFILL, INITIATIVE_CONTROL) are at chance precisely because the
trades-only series lacks the depth/flow that would make them work.

Priority (see V11_DATA_REQUEST_FOR_OOS_WINDOWS.csv):
1. **Microstructure data on existing + new windows**: L2 depth (bid refill / wall persistence near lows), liquidations
   (forced-seller exhaustion), and OI (position unwind vs new shorts). These are the physical mechanism of absorption;
   without them, "absorption" is unobservable in this dataset. Only 3 windows currently have any L2.
2. **Dedicated per-capital-state windows for OOS**: SELL_PRESSURE_ABSORBED / failed-breakdown days, a DISTRIBUTION window,
   and a 2nd+ TREND_UP / ACTIVE_MARKUP window (the single uptrend window is the binding limitation across v4–v11).
3. **Re-run v11 forward-label + evidence pipeline** on that richer data. The label framework and AUC/within-background
   diagnostic are reusable as-is — only the evidence blocks need the new inputs.

What to KEEP from v11:
- The forward-label definitions (markdown / absorbed / no-control over 15/30/60/120m) — validated, not window-dominated.
- The within-background AUC test as the standard guard against Simpson's-paradox "separation".
- The base-rate finding (~63% of sell-pressure candidates absorb at 60m) — reinforces: td_s must stay phase-gated, never universal.

What NOT to do:
- No ABS_BLOCKER_CANDIDATE_A/B/C build (they are trend proxies — see V11_CANDIDATE_BLOCKER_DESIGNS.md correction).
- No td_l: the absorption/accumulation boundary it would anchor on is not yet observable, let alone OOS-validated.
- No threshold tuning to lift the in-sample AUC — that would manufacture a pretty number with no forward meaning.
- GATE_6A/6E/8A stay frozen; 8A stays a markdown-only timing overlay (v8).
