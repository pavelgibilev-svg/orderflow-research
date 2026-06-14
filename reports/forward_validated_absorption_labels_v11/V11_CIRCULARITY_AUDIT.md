# V11 CIRCULARITY AUDIT (v9 labels vs forward behaviour)

Build 2026-06-13T10:39:27+00:00 · forward-validated absorption labels v11 · skeptical, not production.

- v9 ACTIVE_MARKDOWN candidates -> forward ACTIVE_MARKDOWN 31.8% / ABSORBED 50.1% / NO_CONTROL 4.2% (n 2548).
- v9 ABSORPTION_REVERSAL candidates -> forward ACTIVE_MARKDOWN 35.3% / ABSORBED 41.6% / NO_CONTROL 1.0% (n 575).

## Was v10 circular?
- v10 built its blocker from features in the SAME family used to define v9 ABSORPTION/ACCUMULATION, so blocked-phase activation fell mechanically.
- Circularity is CONFIRMED to the extent that v9 ABSORPTION_REVERSAL does NOT cleanly map to forward absorption: if its forward-ABSORBED share is not much higher than v9 ACTIVE_MARKDOWN's, the old label was not capturing true absorption, so v10's 'reduction' was bookkeeping.
- Verdict (auto text said "weak"): **CORRECTED — the separation is REVERSED, i.e. worse than none.**

## ⚠️ Corrected reading
- v9 **ACTIVE_MARKDOWN** label → only **31.8%** actually continued markdown forward; **50.1%** got ABSORBED. So the phase we trusted to allow shorts was forward-absorbed *more often than it continued*.
- v9 **ABSORPTION_REVERSAL** label → forward-absorbed **41.6%**, which is LOWER than the markdown label's 50.1%. The label named "absorption" was LESS absorbed than the label named "markdown" — the ordering is backwards.
- Conclusion: **v9 phase labels do not track forward markdown/absorption at all** (they encode current trend structure, not future capital behaviour). Therefore **v10's blocker was circular AND was not catching real absorption** — its "false-permission reduction" was bookkeeping against an uninformative label. Circularity: CONFIRMED. The whole v9→v10 absorption boundary needs to be rebuilt against forward labels (this pass), not patched.
