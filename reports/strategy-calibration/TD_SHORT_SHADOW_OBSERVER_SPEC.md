# C. TD-short shadow observer logic

**Build:** 2026-06-04T17:35:03+00:00

Mode: SHADOW / RESEARCH ONLY. Telegram DISABLED. No production.

On each confirmed zone (causal, decision uses only <= confirmedTs):
1. classify regime; 2. ignore if not TREND_DOWN; 3. ignore if not SHORT;
4. mandatory gates -> REJECT+reasons on fail; 5. confluence>=2 -> REJECT(weak) on fail;
6. else TD_SHORT_CANDIDATE; log hypothetical entry, TP 2%, SL 1.5%;
7. selection first-eligible max2/day + cluster cooldown; 8. outcome only in offline eval.
