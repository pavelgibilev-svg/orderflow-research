# V8 FINAL DECISION (skeptical)

Build 2026-06-13T03:13:21+00:00 · research branch v8 · skeptical, not production.

## ⚠️ SKEPTICAL ADDENDUM (manual review — read this first)
The auto-scorecard flags several "candidates", but only **ONE survives scrutiny, and even it is not validated**:

1. **Robustness (barrier):** only **8A (FAILED_VWAP_RECLAIM)** beats random+gate under BOTH barriers — the intrabar hi/lo barrier used here (8A+6A PF 1.99, 8A+6E PF 2.66) AND the v7 mid-only barrier (8A+6A PF 1.97, 8A+6E PF 5.29). NOTE: v8 changed the triple-barrier to intrabar hi/lo (more realistic than v7 mid-only); this is a disclosed deviation and is WHY v8 numbers differ from v7.
2. **Regime concentration (killer caveat):** 8A's profit is entirely from the 4 TREND_DOWN windows (+~76R). It **LOSES in TREND_UP (−20R, 0% win, n25) and in RANGE_0508 (−20R, 0% win, n23)**. One window = **47%** of profit (dom_window_share 0.47). So 8A is *failed-recovery timing layered on top of downtrend exposure*, not a standalone entry.
3. **Sample / scope:** best 8A variants have n=68–162; OKX single-venue; in-sample; one TREND_UP window. The level-grid "best" cell is n=20 (overfit — ignore).
4. **The others:** 8B/8C/8D and old_event "beat" random+6E only because the v8 random+6E baseline is low; they fail the mid-barrier robustness check and/or are tiny-n (8D n=10). **Not candidates.**

**Honest status of 8A: `ENTRY_CANDIDATE_WEAK / NEED_MORE_DATA`** — promising, matches the hypothesis, robust to barrier choice, but profit is downtrend-concentrated and it loses outside downtrends. NOT validated, NOT production.

## Does the new entry add edge inside the frozen bearish gate?
- **PARTIAL / WEAK**: only **8A (FAILED_VWAP_RECLAIM)** robustly beats random+gate (both barriers, both gates) — but its profit is concentrated in TREND_DOWN windows and it loses in UP/RANGE. The auto-flagged 8B/8C/8D/old_event are not robust.
## Which entry variants beat random within gate
- ['8A+GATE_6A', '8A+GATE_6E', '8B+GATE_6E', '8C+GATE_6E', '8D+GATE_6E', 'old_event+GATE_6E'].
## Best level model
- STOP_1 / TARGET_6 / RR>=1.5 (PF5 1.201, n 20).
## Is fixed 2% still justified / structural better?
- See level grid; structural targets did not robustly beat fixed across stops (single-best cell = overfit risk).
## Does cooldown help?
- marginal: it mainly cuts sample (see diagnostic).
## Real entry candidate or only a regime filter?
- A weak entry candidate emerged; treat as NEED_MORE_DATA, not validated.
## Recommendation
- Do NOT productionize. Re-test the candidate on fresh windows before any claim.

FINAL_ARTIFACTS_LOCATION:
- main_folder: reports/failed_recovery_entry_v8/
- V8_STATUS.md · V8_ENTRY_DEFINITIONS.md · V8_LEVEL_DEFINITIONS.md
- V8_SCORECARD.csv · V8_SCORECARD_WITH_SLIPPAGE.csv · V8_PER_WINDOW_BREAKDOWN.csv
- V8_ENTRY_VS_RANDOM_GATE.csv/_REPORT.md · V8_LEVEL_CALIBRATION.csv/_REPORT.md · V8_COOLDOWN_DIAGNOSTIC.csv/.md
- V8_FINAL_DECISION.md
