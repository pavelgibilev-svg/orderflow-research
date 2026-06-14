# V11 LABEL SEPARATION REPORT

Build 2026-06-13T10:39:27+00:00 · forward-validated absorption labels v11 · skeptical, not production.

Candidates n=21282 | ACTIVE_MARKDOWN n=3721 | SELL_PRESSURE_ABSORBED n=13414 | NO_CONTROL n=803 | base markdown rate 21.7%.

## AUC (markdown vs absorbed), causal evidence:
- EFFORT_VS_RESULT: AUC 0.614 (mean md 0.51 vs ab 0.364)
- ABSORPTION_REFILL: AUC 0.524 (mean md 0.194 vs ab 0.17)
- INITIATIVE_CONTROL: AUC 0.543 (mean md 0.815 vs ab 0.766)
- BACKGROUND_ALIGNMENT: AUC 0.623 (mean md 0.658 vs ab 0.57)
- EXTENSION_NOT_LATE: AUC 0.427 (mean md 0.917 vs ab 0.966)
- COMBINED: AUC 0.624 (mean md 0.619 vs ab 0.567)

Best single block: **BACKGROUND_ALIGNMENT** AUC 0.623. COMBINED AUC 0.624.

## Per-background AUC (COMBINED):
- TREND_DOWN: AUC 0.5 (md 1094/ab 1505)
- RANGE: AUC 0.508 (md 1669/ab 5283)
- TREND_UP: AUC 0.659 (md 145/ab 403)
- LOW_VOL: AUC 0.642 (md 813/ab 6223)

## Median-split classifier (thr=0.576, NO tuning):
- precision(markdown) 28.3% · recall 65.6% · base rate 21.7%
- false-markdown (called markdown, was absorbed) 71.7% · missed-markdown 34.4%
- per-window dominance: markdown 0.3, absorbed 0.2 (>=0.6 = one window dominates).

## Honest reading
- If COMBINED AUC barely beats 0.5 and BACKGROUND_ALIGNMENT carries it, the 'separation' is just 'are we already in a downtrend', not a micro-absorption signal. Micro blocks (EFFORT_VS_RESULT, ABSORPTION_REFILL, INITIATIVE_CONTROL) earning AUC near 0.5 means absorption is NOT causally predictable here.

## ⚠️ DECISIVE: the COMBINED 0.624 is a Simpson's-paradox artifact
- Conditioned on background, separation **vanishes in the two contexts that matter**: TREND_DOWN AUC **0.500**, RANGE AUC **0.508**. The whole 0.624 comes from BETWEEN-background differences (downtrends continue more than chop), i.e. it is re-discovering trend — which GATE_6A already encodes.
- So inside a down-pressure context, **causal trades-only evidence cannot tell ACTIVE_MARKDOWN from SELL_PRESSURE_ABSORBED**. That is exactly the boundary v9/v10 needed and it is not solved.
- Base-rate finding (real and useful): of 21,282 sell-pressure candidates, **63% are forward-ABSORBED and only 17.5% are forward-MARKDOWN** (the rest no-control/unknown). Even in TREND_DOWN, absorbed (1505) outnumber markdown (1094). When sell pressure appears, continuation is the minority outcome at 60m.
- Median-split precision 28.3% vs base 21.7% = +6.6pp — marginal, and it comes entirely from the trend component.
- EXTENSION_NOT_LATE AUC 0.427 (inverted): overextended down-moves CONTINUED more, not less — the mean-reversion/exhaustion intuition is NOT supported in this data.
