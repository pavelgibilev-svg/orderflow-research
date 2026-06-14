# COMPARISON WITH v2 LOWER-HIGH PIVOT

Build 2026-06-12T14:32:51+00:00 · v2 = reports/trend_down_crossvenue_v2 (lower-high pivot + capital_state).

- v2 trigger: lower-high pivots -> mostly DISTRIBUTION_INTO_BOUNCE (21) + UNKNOWN 169/219 (77%); ACTIVE_MARKDOWN=0, FORCED_UNWIND=0.
- v3 trigger: EVENTS. ACTIVE_MARKDOWN_EVENT samples = **589**; FORCED_UNWIND_EVENT samples = **93**; CVD_BREAKDOWN = 454.
- less DISTRIBUTION-only? YES — events sample markdown/unwind directly
- ACTIVE_MARKDOWN samples appeared? YES (589); FORCED_UNWIND appeared? YES (93)
- UNKNOWN reduced? events are typed by construction (no UNKNOWN bucket).
- baseline PF: v2 short ~0.72 vs v3 event short 1.991 (better).
- best entry policy PF: 2.189.
- lead-lag edge or noise? see CROSS_VENUE_DISAGREEMENT_TYPES (LEAD_LAG row).
- disagreement still a single veto? NO — split into TRUE_DISAGREEMENT/VENUE_NOISE (veto) vs LEAD_LAG/SYNC (signal).