# FALSE / MISSED SHORT-PERMISSION ANALYSIS

Build 2026-06-13T07:52:13+00:00 · phase-separation audit v9 · skeptical, not production.

- **gate6A activation in TARGET phases (markdown/distribution): 39.4%** vs **BLOCKED phases (absorption/accumulation/chop/uptrend): 12.5%**.
- gate6E activation: target 17.0% vs blocked 3.6%.
- td_s (old event) activation: target 47.5% vs blocked 21.6%.

- **FALSE short-permission** = gate/td_s firing in BLOCKED phases. If blocked-phase activation is HIGH, the current gate does NOT do phase separation (it only knows trend direction, not absorption vs markdown / accumulation vs distribution).
- **MISSED short-permission** = gate NOT firing in TARGET phases (low target activation).

## Per-phase activation (key rows)
- TREND_DOWN_ACTIVE_MARKDOWN: td_s 57.6% · gate6A 67.1% · gate6E 29.1% · 8A_setups 17 · n 3230
- RANGE_DISTRIBUTION_INTO_DEMAND: td_s 35.2% · gate6A 5.7% · gate6E 2.3% · 8A_setups 276 · n 2647
- TREND_DOWN_ABSORPTION_REVERSAL: td_s 29.2% · gate6A 40.6% · gate6E 0.0% · 8A_setups 16 · n 983
- RANGE_ACCUMULATION_UNDER_PRESSURE: td_s 26.3% · gate6A 28.9% · gate6E 0.0% · 8A_setups 192 · n 4338
- LOW_VOL_NO_CONTROL_CHOP: td_s 19.8% · gate6A 10.6% · gate6E 5.2% · 8A_setups 1172 · n 22241
- TREND_UP_NO_SHORT: td_s 24.5% · gate6A 0.0% · gate6E 0.0% · 8A_setups 49 · n 4573
- UNKNOWN: td_s 24.2% · gate6A 7.6% · gate6E 6.0% · 8A_setups 415 · n 12308

## ⚠️ Corrected reading — do not trust the aggregate "12.5% blocked" number
The blocked-phase aggregate (gate6A 12.5%) is misleading: LOW_VOL_CHOP carries 22241 of 32135 blocked minutes (69% of the weight) and its gate6A is only 10.6%, dragging the average down. Read the two structurally-dangerous blocked phases on their own:

| phase | role | gate6A | gate6E | verdict |
|---|---|---|---|---|
| TREND_DOWN_ABSORPTION_REVERSAL | short should be BLOCKED | **40.6%** | 0.0% | gate6A = **FALSE PERMISSION**; gate6E correct |
| RANGE_ACCUMULATION_UNDER_PRESSURE | short should be BLOCKED (long-watch) | **28.9%** | 0.0% | gate6A = **FALSE PERMISSION**; gate6E correct |
| TREND_DOWN_ACTIVE_MARKDOWN | short ALLOWED | 67.1% | 29.1% | both fire (correct) |
| RANGE_DISTRIBUTION_INTO_DEMAND | short ALLOWED | 5.7% | 2.3% | both **MISS** (missed permission — no gate covers the range short) |

**Conclusions:**
- GATE_6A is a trend-direction gate, not a phase gate — it false-permits shorts in absorption (40.6%) and accumulation (28.9%).
- GATE_6E is the only phase-aware gate (0% in both blocked structural phases) but only covers ACTIVE_MARKDOWN; it misses DISTRIBUTION (2.3%).
- Neither gate provides a usable short-permission inside RANGE_DISTRIBUTION_INTO_DEMAND → that phase has **no working detector** today.
- Ex-post per-phase PF (in V9_TD_S_BY_PHASE.csv) is small-n, in-sample noise — diagnostic only, not a green light.
