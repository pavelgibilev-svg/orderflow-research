# V11 STATUS

Build 2026-06-13 · forward-validated absorption labels v11 · skeptical, not production.

- STATUS (auto): ABSORPTION_LABELS_PROMISING → **CORRECTED (manual): ABSORPTION_LABELS_REJECTED** (trades-only causal features) — see V11_FINAL_DECISION.md.
- March: AVAILABLE (OKX-historical 2026-03, 30 days; 3 March windows cached); all IN_SAMPLE_ONLY (no true OOS).
- candidates 21282 | forward-markdown 3721 (~17.5%) | forward-absorbed 13414 (~63%) | no_control 803 — most sell-pressure ABSORBS.
- COMBINED causal AUC 0.624 OVERALL **but a Simpson's-paradox artifact**: within TREND_DOWN AUC **0.500**, within RANGE **0.508** (chance). The 0.624 is just trend re-discovered.
- micro-absorption blocks at/below chance: ABSORPTION_REFILL 0.524, INITIATIVE_CONTROL 0.543, EXTENSION_NOT_LATE 0.427 (inverted).
- per-window dominance markdown 0.30 / absorbed 0.20 (labels NOT window-dominated — the framework is fine).
- circularity CONFIRMED: v9 ACTIVE_MARKDOWN→fwd-continued only 31.8%; v9 ABSORPTION→fwd-absorbed 41.6% (< markdown label's 50.1%, reversed). v10 blocker was bookkeeping.
- Keep: the forward-label framework + the base-rate finding. Reject: trades-only causal absorption prediction.
- PRODUCTION: NO. No td_l. Needs L2/liquidations/OI + OOS windows.
