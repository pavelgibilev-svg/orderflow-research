# GATE DECISIONS v6

Build 2026-06-12T16:45:47+00:00 · research/calibration.

| gate | status | UPblock% | DOWNret% | gate_helps | event_adds | allowed n |
|---|:--:|--:|--:|:--:|:--:|--:|
| OLD | **v5_reference** | 62.4 | 47.1 | True | False | 5752 |
| GATE_6A_STRICT_NO_UPTREND | **NEED_MORE_DATA** | 71.7 | 40.3 | True | False | 4766 |
| GATE_6B_DOWNTREND_ONLY | **NEED_MORE_DATA** | 80.0 | 25.9 | True | False | 3373 |
| GATE_6C_SELLER_CONTROL_STRICT | **REJECT** | 40.7 | 65.3 | False | False | 8179 |
| GATE_6D_NO_BOUNCE_NO_CHOP | **REJECT** | 4.2 | 93.1 | False | False | 12070 |
| GATE_6E_COMBINED_STRICT | **NEED_MORE_DATA** | 85.1 | 18.1 | True | False | 2405 |

RESEARCH_CANDIDATE requires multi-window UP evidence (we have ONE up window) -> ceiling is NEED_MORE_DATA even for strong blockers.
event_adds is FALSE everywhere -> the entry trigger still does not beat random within the allowed set (v5 conclusion holds).
