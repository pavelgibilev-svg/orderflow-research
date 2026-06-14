# V9 PHASE STATUS

Build 2026-06-13T07:52:13+00:00 · phase-separation audit v9 · skeptical, not production.

- STATUS (auto): PHASE_MODEL_PROMISING → **CORRECTED (manual): PHASE_MODEL_NEED_MORE_DATA** (see V9_PHASE_MODEL_DECISION.md addendum)
- March data: AVAILABLE (OKX-historical 2026-03, 30 days; 3 March windows already cached — DOWN_0327, UP_0310, RANGE_0303). NOT blocked.
- Auto "gate6A target 39.4% vs blocked 12.5%" is a weighting illusion (chop = 44% of minutes dominates the blocked average).
- Real leak: **GATE_6A = 40.6% in ABSORPTION, 28.9% in ACCUMULATION** = false short-permission in the phases that matter.
- **GATE_6E is the only phase-aware gate**: 29.1% markdown / 0% absorption / 0% accumulation / 0% uptrend / 5.2% chop — BUT only 2.3% in DISTRIBUTION (covers markdown only, not the range short).
- 8A ACTIVE_MARKDOWN-only by setup location: False (only 17 of ~1900 setups land in markdown; it is a VWAP-oscillation setup).
- RANGE splits accumulation/distribution: True (two opposite behaviors present).
- Classifier caveat: heuristic, in-sample, single-venue OKX, 1 uptrend window, 44% chop (over-greedy). No OOS phase validation.
- Next branch: **B (improve phase classifier first)**, not td_l calibration yet.
- PRODUCTION: NO.
