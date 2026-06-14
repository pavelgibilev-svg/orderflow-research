# V10 BLOCKER DECISION (skeptical)

Build 2026-06-13 · absorption/accumulation blocker v10 · skeptical, not production.

## ⚠️ MANUAL CORRECTION (read first — overrides the auto-status)
The auto-script printed `BLOCKER_PROMISING` with headline **b10F**, but that selection is the exact failure mode this
pass was told to avoid: **b10F only reaches the absorption<20% goal by blocking ~59% of ACTIVE_MARKDOWN and ~53% of
DISTRIBUTION** ("works by blocking almost everything"). And the non-circular ex-post test FAILED. Corrected verdict:

**STATUS: `BLOCKER_NEED_MORE_DATA`** — headline **b10E** (the interpretable, markdown-preserving variant). The
accumulation half is genuinely promising; the absorption half is not solved.

## Per-blocker behaviour on GATE_6A (orig: absorption 40.6%, accumulation 28.9%)
| blocker | absorption after | accumulation after | markdown retention | distribution retention | read |
|---|---|---|---|---|---|
| b10A (F1 price-response) | 40.8% | 27.1% | 98.3% | 90.8% | barely fires — useless |
| b10B (F2 failed-breakdown) | 27.2% | 12.2% | **51.2%** | 71.7% | real, but halves markdown |
| b10C (F3 vwap-reclaim) | 40.8% | 28.7% | 100% | 94.7% | barely fires — useless |
| b10D (F5 cvd-divergence) | 38.1% | 27.9% | 97.2% | 96.7% | barely fires — useless |
| **b10E (>=2 signs)** | **33.8%** | **13.7%** | **71.0%** | 80.9% | **best phase behaviour** |
| b10F (any sign or chop) | 18.1% | 4.5% | **40.9%** | 47.4% | hits goal only by gutting markdown |

## Verdict by sub-problem
- **ACCUMULATION_UNDER_PRESSURE: partial success.** b10E cuts false-permission 28.9% -> 13.7% while keeping 71% of
  markdown and 81% of distribution. That is real separation (not just blocking everything). Promising.
- **ABSORPTION_REVERSAL: NOT solved.** b10E only gets to 33.8% (goal was <15-20%). The only variant that reaches the
  goal (b10F, 18.1%) destroys the markdown phase (retention 40.9%). No clean absorption blocker exists yet.
- **CHOP suppression** works (it is mostly the F6 term inside b10F), but b10F's collateral damage to markdown makes it
  unusable as the global router.

## Why this is NOT "promising" overall — the honest (non-circular) evidence
1. **Circularity:** v9's ABSORPTION/ACCUMULATION labels were themselves defined with "selling-but-no-new-low" logic, so
   a blocker built from the same family mechanically lowers activation in those phases. That reduction is largely
   bookkeeping, not prediction.
2. **Ex-post forward-downside test FAILS** (this is the part the gate has no knowledge of, so it is the real test):
   - ACTIVE_MARKDOWN: b10E-fire fwd-min −0.48% vs not-fire −0.46% (n 626/1530) — no discrimination.
   - ABSORPTION_REVERSAL: fire −0.94% vs not-fire −0.84% (n 71/325) — **wrong direction**: blocked minutes fell MORE.
   - ACCUMULATION_UNDER_PRESSURE: fire −0.27% vs not-fire −0.28% (n 670/585) — identical.
   So the blocker is **not** demonstrably catching "price stops falling". It reduces activation without forward evidence
   of real absorption. `expost_ordering_ok = False`.
3. **Feature quality:** the three interpretable absorption features (F1 price-response, F3 vwap-reclaim, F5 cvd-divergence)
   barely fire on gate-active minutes. The reduction is carried by F2 (failed-breakdown, which costs half of markdown)
   and F6 (chop). The absorption thesis is not yet captured by a feature that works.

## Skeptical reading
- One-window dominance of b10E blocks is low (0.21) — good, not a single-window artifact.
- All in-sample, single-venue OKX, ONE uptrend window, heuristic + partly-circular phase labels. PFs in the
  absorption/distribution cells are small-n noise — diagnostic only.
- Net: the router idea is alive for ACCUMULATION (and CHOP), but ABSORPTION needs a better, forward-validated feature
  before anything is locked. This is a safer router direction, NOT a validated layer. No production.
