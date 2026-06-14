# V9 PHASE MODEL DECISION (skeptical)

Build 2026-06-13T07:52:13+00:00 · phase-separation audit v9 · skeptical, not production.

## ⚠️ SKEPTICAL ADDENDUM (manual review — read this first; overrides the auto-status below)
The auto-classifier printed `PHASE_MODEL_PROMISING`, but that is an artifact of how the "blocked average" is weighted. **Corrected status: `PHASE_MODEL_NEED_MORE_DATA`.** Reasons:

1. **The "separation" is a weighting illusion.** The auto blocked-average gate6A (12.5%) is low only because LOW_VOL_CHOP (n=22241, gate6A 10.6%) dominates the weighting. Looking at the phases that actually matter, the gate LEAKS:
   - **GATE_6A in TREND_DOWN_ABSORPTION_REVERSAL = 40.6%** (should be ~0 — this is exactly the false short-permission the pass was meant to catch).
   - **GATE_6A in RANGE_ACCUMULATION_UNDER_PRESSURE = 28.9%** (should be ~0 — short fired in a long/accumulation phase).
   So GATE_6A is **not** a phase separator; it is a trend-direction gate that fires on any down-pressure, including absorption and accumulation.
2. **Only GATE_6E behaves phase-aware** — 29.1% in ACTIVE_MARKDOWN, **0.0% in ABSORPTION, 0.0% in ACCUMULATION, 0.0% in UPTREND, 5.2% in CHOP**. That is the clean behavior we wanted. BUT it is also nearly silent in **DISTRIBUTION_INTO_DEMAND (2.3%)**, so GATE_6E covers only the ACTIVE_MARKDOWN short and cannot do the RANGE-distribution short at all.
3. **td_s (old event) leaks too**: 57.6% markdown / 35.2% distribution vs 29.2% absorption / 26.3% accumulation / 19.8% chop / 24.5% uptrend. A real gradient toward the correct phases, but it still fires 20–29% in every blocked phase — "gradient", not "mostly silent".
4. **8A is NOT markdown-only by setup location**: only 17 setups land in ACTIVE_MARKDOWN vs 276 in DISTRIBUTION, 1172 in CHOP, 192 in ACCUMULATION. 8A is a VWAP-oscillation setup that mechanically fires in ranges/chop. The v8 finding ("8A profit is downtrend-concentrated") was about *where the gated profit came from*, not where setups appear — a different question. The per-phase ex-post PF here (e.g. 8A PF 2.65 in absorption, 2.24 in chop) is small-n, in-sample noise and must not be read as "8A works in absorption/chop".
5. **Classifier is over-greedy and unvalidated**: LOW_VOL_NO_CONTROL_CHOP swallowed **22241 / 50320 = 44%** of all minutes. The chop bucket is too wide and is absorbing real structure. The whole classifier is a hand-tuned heuristic, in-sample, single-venue OKX, with only ONE uptrend window. No out-of-sample phase validation exists.

**Net:** the phase *idea* shows signal (phases are distinguishable; GATE_6E already acts as a partial phase-aware short-permission for ACTIVE_MARKDOWN; RANGE clearly contains two opposite behaviors). But the working gate (GATE_6A) does the opposite of phase separation in the two phases that matter most (absorption, accumulation), and no gate covers DISTRIBUTION. That is not "promising" yet — it is "needs a real phase classifier + more data".

**STATUS (auto): PHASE_MODEL_PROMISING  →  CORRECTED: PHASE_MODEL_NEED_MORE_DATA**
- March data: AVAILABLE (OKX-historical 2026-03, 30 days; 3 March windows already cached)

## A) Does td_s/gate mainly activate in correct phases?
- gate6A: target 39.4% vs blocked 12.5% -> SEPARATES.
- td_s(old event): target 47.5% vs blocked 21.6%.
## B) Does it wrongly activate in blocked phases?
- gate6A in TREND_DOWN_ABSORPTION_REVERSAL: **40.6%** (false permission if high).
- gate6A blocked-phase average: 12.5% -> mostly silent in blocked phases.
## C) Does 8A only work in ACTIVE_MARKDOWN?
- 8A setups: ACTIVE_MARKDOWN n=17 (hit2 11.8%); other phases with >=5 setups: ['RANGE_DISTRIBUTION_INTO_DEMAND', 'TREND_DOWN_ABSORPTION_REVERSAL', 'RANGE_ACCUMULATION_UNDER_PRESSURE', 'LOW_VOL_NO_CONTROL_CHOP', 'TREND_UP_NO_SHORT', 'UNKNOWN'] -> 8A also fires elsewhere.
## D) Does RANGE split into accumulation vs distribution?
- RANGE_ACCUMULATION n=4338, RANGE_DISTRIBUTION n=2647 -> YES, both behaviors present -> separate RANGE modules warranted.
## E) Is LOW_VOL/CHOP a no-trade filter?
- LOW_VOL_NO_CONTROL_CHOP gate6A 10.6% -> gate already mostly silent there (good no-trade).

## Skeptical reading
- The frozen GATE_6A/6E only encode TREND DIRECTION (no-uptrend / downtrend-only). They have NO absorption-vs-markdown or accumulation-vs-distribution logic.
- So if gate activation is similar in ACTIVE_MARKDOWN and ABSORPTION_REVERSAL, the gate is NOT a phase separator; a dedicated phase classifier is needed before any td_l calibration.
