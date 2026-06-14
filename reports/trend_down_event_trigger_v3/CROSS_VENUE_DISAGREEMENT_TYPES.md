# CROSS-VENUE TYPES (not all disagreement is veto)

Build 2026-06-12T14:32:29+00:00 · research/calibration.

| type | n | hit2% | W/L/TO | PF | role |
|---|--:|--:|:--:|--:|---|
| SYNC_CONFIRMATION | 1058 | 44.5 | 471/183/404 | 2.919 | signal |
| VENUE_NOISE | 733 | 35.2 | 258/237/238 | 1.235 | veto/ignore |
| TRUE_DISAGREEMENT | 123 | 49.6 | 61/28/34 | 2.471 | VETO |
| LEAD_LAG_CONFIRMATION | 30 | 23.3 | 7/6/17 | 1.323 | signal(early) |

LEAD_LAG_CONFIRMATION is treated as a potential EARLY signal (one venue leads), not a veto. TRUE_DISAGREEMENT / VENUE_NOISE are vetoes.
