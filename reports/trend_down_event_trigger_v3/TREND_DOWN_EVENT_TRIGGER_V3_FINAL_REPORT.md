# TREND_DOWN EVENT-TRIGGER v3 — FINAL REPORT

Build 2026-06-12T14:32:51+00:00 · RESEARCH/CALIBRATION, not production. TP=2%/SL=1.5%.

## 1. Executive summary
- **METHOD WIN, EDGE FAIL.** The event trigger DID fix the v2 gap — it now samples ACTIVE_MARKDOWN_EVENT=589, FORCED_UNWIND_EVENT=93, CVD_BREAKDOWN=454 short samples (v2 pivots gave 0 markdown/unwind).
- BUT the high numbers are **REGIME EXPOSURE, not an edge**: naive 'short a random minute' in these 3 strong-down windows scores hit2 39.5% / PF 2.268 — i.e. event-shorts (hit2 41.0% / PF 1.991) beat random by only **1.5 pp** (≈0; PF actually lower than random).
- 1944 'events' are heavily overlapping -> only **255 independent moments**. Even the supposed-veto TRUE_DISAGREEMENT 'wins' here -> categories don't separate in a downtrend.
- RESEARCH_CANDIDATE templates: NONE (all event-short families -> NEED_MORE_DATA: no lift over the naive baseline).
## 2. Why lower-high pivot replaced
- It only caught bounces (DISTRIBUTION). Events sample the actual markdown/unwind/CVD-breakdown moments.
## 3. Event families tested
- A ACTIVE_MARKDOWN, B FORCED_UNWIND, C CVD_BREAKDOWN, D SELL_PRESSURE_NO_ABSORPTION, E ABSORPTION(no-short).
## 4. Cross-venue disagreement types
- SYNC_CONFIRMATION: n=1058 PF=2.919 role=signal
- VENUE_NOISE: n=733 PF=1.235 role=veto/ignore
- TRUE_DISAGREEMENT: n=123 PF=2.471 role=VETO
- LEAD_LAG_CONFIRMATION: n=30 PF=1.323 role=signal(early)
## 5. Lead-lag
- See LEAD_LAG_CONFIRMATION row; treated as early signal not veto.
## 6. Best event family: SELL_PRESSURE_NO_ABSORPTION_EVENT (PF 2.189, n 808) · best entry policy: NO_ENTRY_ABSORPTION (PF 2.189)
## 7. ACTIVE_MARKDOWN/FORCED_UNWIND samples: YES
## 8-9. Templates kept / rejected
- TD_ACTIVE_MARKDOWN_EVENT_SHORT_TEMPLATE: NEED_MORE_DATA (n 589, PF 1.848)
- TD_FORCED_UNWIND_EVENT_SHORT_TEMPLATE: NEED_MORE_DATA (n 93, PF 1.355)
- TD_CVD_BREAKDOWN_EVENT_SHORT_TEMPLATE: NEED_MORE_DATA (n 454, PF 2.081)
- TD_LEAD_LAG_MARKDOWN_SHORT_TEMPLATE: NEED_MORE_DATA (n 30, PF 1.323)
- TD_TRUE_DISAGREEMENT_VETO: VETO_CANDIDATE (n 123, PF 2.471)
- TD_ABSORPTION_DIVERGENCE_NO_SHORT: NEED_MORE_DATA (n 0, PF None)
- TD_VENUE_NOISE_IGNORE: VETO_CANDIDATE (n 733, PF 1.235)
## 10. RESEARCH_CANDIDATE: NO
## 11. Next: more true TREND_DOWN windows (full OKX+trades), test event triggers OOS; refine lead-lag confirm window; do not tune thresholds.

FINAL_ARTIFACTS_LOCATION:
- main_folder: reports/trend_down_event_trigger_v3/
- event_candidates: EVENT_CANDIDATES_RAW.csv / EVENT_CANDIDATES_UNIQUE.csv / EVENT_CASEBOOK (see GOOD_EVENT_ZONE_CASEBOOK.md)
- event_outcomes: EVENT_OUTCOMES.csv
- entry_policy_comparison: ENTRY_POLICY_COMPARISON.csv/.md
- disagreement_types: CROSS_VENUE_DISAGREEMENT_TYPES.csv/.md
- filter_templates: EVENT_FILTER_TEMPLATES.json/.md
- filter_scorecard: EVENT_FILTER_SCORECARD.csv
- good_event_casebook: GOOD_EVENT_ZONE_CASEBOOK.md/.csv
- comparison_with_v2: COMPARISON_WITH_V2_LOWER_HIGH.md
- final_report: TREND_DOWN_EVENT_TRIGGER_V3_FINAL_REPORT.md