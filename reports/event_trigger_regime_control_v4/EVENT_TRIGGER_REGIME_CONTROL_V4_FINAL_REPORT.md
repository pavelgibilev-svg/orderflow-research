# EVENT TRIGGER REGIME CONTROL v4 — FINAL REPORT

Build 2026-06-12T15:08:44+00:00 · RESEARCH/CALIBRATION, not production. TP=2%/SL=1.5%. di-free detector, OKX single-venue control.

## 1. Executive summary
- Tested the frozen v3 event-short trigger vs RANDOM short across regimes. DOWN lift_hit2 2.1 / lift_PF -0.679; UP lift_hit2 1.5 / lift_PF 0.021.
- RESEARCH_CANDIDATE templates: NONE.
## 2. Regimes/windows
- DOWN_NOV [TREND_DOWN] net -8.82% -> auto TREND_DOWN
- DOWN_JAN [TREND_DOWN] net -11.79% -> auto TREND_DOWN
- DOWN_APR [TREND_DOWN] net -12.46% -> auto TREND_DOWN
- DOWN_0327 [TREND_DOWN] net -2.86% -> auto TREND_DOWN
- UP_0310 [TREND_UP] net 9.43% -> auto TREND_UP
- RANGE_0508 [RANGE_CHOP] net 1.98% -> auto RANGE_CHOP
- RANGE_0303 [RANGE_CHOP] net -1.04% -> auto RANGE_CHOP
- BOUNCE_0512 [REVERSAL_BOUNCE] net -2.77% -> auto TREND_DOWN
## 3. Event vs random
- TREND_DOWN: event PF 1.812 vs random PF 2.491 (lift_hit2 2.1)
- TREND_UP: event PF 0.178 vs random PF 0.157 (lift_hit2 1.5)
- RANGE_CHOP: event PF 0.842 vs random PF 0.797 (lift_hit2 5.0)
- REVERSAL_BOUNCE: event PF 1.238 vs random PF 1.555 (lift_hit2 0.0)
## 4. Raw vs independent moments
- TREND_DOWN: raw 11867 -> 53 independent
- TREND_UP: raw 3558 -> 28 independent
- RANGE_CHOP: raw 3854 -> 37 independent
- REVERSAL_BOUNCE: raw 1621 -> 18 independent
## 5-6. Which families give real lift vs just regime
- See TEMPLATE_DECISIONS_V4; a family is regime-exposure if lift over random ~0 in DOWN and it still fires/loses in UP.
## 7. RANGE/CHOP behaviour: does the trigger stay quiet / not bleed? see EVENT_VS_RANDOM (RANGE row).
## 8. TREND_UP behaviour: does it stop shorting or keep catching the minus? (UP row).
## 9. REVERSAL/BOUNCE: late-short check (BOUNCE row).
## 10. cross-venue/lead-lag: NOT testable in OKX-only controls -> NEED_MORE_DATA (DOWNLOAD_REQUIREMENTS).
## 11. RESEARCH_CANDIDATE: NO
## 12. Download next: Bybit+OKX L2+trades for UP/RANGE/BOUNCE (see DOWNLOAD_REQUIREMENTS.md).

FINAL_ARTIFACTS_LOCATION:
- main_folder: reports/event_trigger_regime_control_v4/
- regime_windows_summary: REGIME_WINDOWS_SUMMARY.csv/.md
- event_candidates: EVENT_CANDIDATES_ALL_REGIMES.csv
- event_outcomes: EVENT_OUTCOMES_ALL_REGIMES.csv
- random_baseline: RANDOM_BASELINE_BY_REGIME.csv
- event_vs_random: EVENT_VS_RANDOM_BY_REGIME.md (+ _table.csv)
- independent_moments: INDEPENDENT_MOMENTS.csv (+ DEDUP_SUMMARY.md)
- template_scorecard: TEMPLATE_SCORECARD_V4.csv
- template_decisions: TEMPLATE_DECISIONS_V4.md
- final_report: EVENT_TRIGGER_REGIME_CONTROL_V4_FINAL_REPORT.md
- download_requirements: DOWNLOAD_REQUIREMENTS.md