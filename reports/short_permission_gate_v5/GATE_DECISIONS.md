# GATE DECISIONS (status = blocks UP + retains DOWN + beats random)

Build 2026-06-12T16:24:24+00:00 · research/calibration.

| gate | allowed n | event+gate PF | random+gate PF | random_all PF | UP blocked% | RANGE blocked% | DOWN retained% | gate helps? | event adds? | **status** |
|---|--:|--:|--:|--:|--:|--:|--:|:--:|:--:|:--:|
| GATE_1_STRICT_DOWNTREND | 6084 | 1.309 | 1.573 | 1.416 | 60.5 | 57.8 | 50.4 | True | False | **NEED_MORE_DATA** |
| GATE_2_SELLER_CONTROL | 7921 | 1.274 | 1.458 | 1.416 | 45.0 | 42.6 | 64.6 | False | False | **REJECT** |
| GATE_3_NO_UPTREND | 7750 | 1.354 | 1.667 | 1.416 | 48.4 | 43.0 | 63.4 | True | False | **REJECT** |
| GATE_4_NO_CHOP | 12138 | 1.307 | 1.447 | 1.416 | 4.2 | 3.0 | 94.0 | False | False | **REJECT** |
| GATE_5_COMBINED | 5752 | 1.349 | 1.638 | 1.416 | 62.4 | 59.6 | 47.1 | True | False | **NEED_MORE_DATA** |

gate_helps = random+gate PF beats random_all (the gate removes losing regimes). event_adds = event beats random WITHIN the allowed set (the trigger itself has edge).
