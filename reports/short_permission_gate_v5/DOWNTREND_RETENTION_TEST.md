# DOWNTREND RETENTION TEST (does the gate kill good shorts?)

Build 2026-06-12T16:24:23+00:00 · research/calibration.

| gate | dn before | dn after | retained% | winners retained% | PF after | randomDOWN PF |
|---|--:|--:|--:|--:|--:|--:|
| GATE_1_STRICT_DOWNTREND | 7021 | 3536 | 50.4 | 57.1 | 1.917 | 2.449 |
| GATE_2_SELLER_CONTROL | 7021 | 4538 | 64.6 | 67.3 | 1.92 | 2.449 |
| GATE_3_NO_UPTREND | 7021 | 4449 | 63.4 | 66.8 | 1.992 | 2.449 |
| GATE_4_NO_CHOP | 7021 | 6602 | 94.0 | 95.9 | 2.2 | 2.449 |
| GATE_5_COMBINED | 7021 | 3306 | 47.1 | 54.6 | 1.998 | 2.449 |

If retained% ~0 the gate is just 'no trade'. If PF after << randomDOWN PF, the entry still has no edge in down (regime exposure).
