# TREND_UP STRICT BLOCK TEST (2026-03-10..16, +9.4%)

Build 2026-06-12T16:45:47+00:00 · research/calibration.

| gate | before | after | blocked% | PF after | rand+gate PF |
|---|--:|--:|--:|--:|--:|
| OLD | 2200 | 828 | 62.4 | 0.0 | 0.0 |
| GATE_6A_STRICT_NO_UPTREND | 2200 | 623 | 71.7 | 0.0 | 0.0 |
| GATE_6B_DOWNTREND_ONLY | 2200 | 440 | 80.0 | 0.0 | 0.0 |
| GATE_6C_SELLER_CONTROL_STRICT | 2200 | 1304 | 40.7 | 0.134 | 0.176 |
| GATE_6D_NO_BOUNCE_NO_CHOP | 2200 | 2108 | 4.2 | 0.151 | 0.207 |
| GATE_6E_COMBINED_STRICT | 2200 | 328 | 85.1 | 0.0 | 0.0 |

- v5 OLD gate blocked 62.4%; best v6 **GATE_6E_COMBINED_STRICT** blocks 85.1%.
- shorts survive when a deep intraday pullback briefly makes ret60/ret180 negative inside the uptrend; ret_360m + VWAP catch most of them.
