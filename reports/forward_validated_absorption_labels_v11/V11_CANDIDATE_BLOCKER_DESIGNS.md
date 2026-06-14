# V11 CANDIDATE ABSORPTION BLOCKER DESIGNS (proposal only — not optimized)

Build 2026-06-13T10:39:27+00:00 · forward-validated absorption labels v11 · skeptical, not production.

Only evidence blocks with AUC>=0.55 are eligible: **['EFFORT_VS_RESULT', 'BACKGROUND_ALIGNMENT']**.

- ABS_BLOCKER_CANDIDATE_A (conservative): block short only if COMBINED < low-quantile AND EFFORT_VS_RESULT low. Minimises markdown loss; small false-permission cut.
- ABS_BLOCKER_CANDIDATE_B (balanced): block short if COMBINED below median (causal). Expected: moderate false-permission cut, moderate markdown retention risk.
- ABS_BLOCKER_CANDIDATE_C (aggressive): block short if ANY of ['EFFORT_VS_RESULT', 'BACKGROUND_ALIGNMENT'] signals absorption strongly. Higher false-permission cut, higher markdown loss risk.

All are CAUSAL (evidence computed <=t). Expected effect is bounded by the AUC above — separation this weak means even the balanced candidate will trade markdown loss against false-permission cut roughly 1:1. Suitable for v12 router testing ONLY as a hypothesis, not as a frozen layer.

## ⚠️ CORRECTION — these candidates are NOT recommended for v12
The two "eligible" blocks (EFFORT_VS_RESULT, BACKGROUND_ALIGNMENT) only clear AUC>=0.55 **between** backgrounds. Conditioned on background they collapse to chance:
- **TREND_DOWN COMBINED AUC = 0.500**, **RANGE = 0.508** — no within-context separation at all.
- Both eligible blocks are essentially TREND proxies (recent downside / 3h return), which GATE_6A already encodes. They do not add absorption information inside a down-pressure context.
- The genuinely absorption-specific blocks (ABSORPTION_REFILL 0.524, INITIATIVE_CONTROL 0.543, EXTENSION_NOT_LATE 0.427) are at or below chance.

Therefore **no trustworthy absorption blocker can be proposed from trades-only causal features.** Building any of A/B/C would re-introduce a trend filter dressed up as an absorption blocker — the same mistake in a new form. Hold until L2 / liquidations / OI microstructure is available to give the REFILL/INITIATIVE blocks real signal.
