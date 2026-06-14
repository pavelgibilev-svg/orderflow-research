# V8 ENTRY vs RANDOM+GATE (the core test)

Build 2026-06-13T03:13:21+00:00 · research branch v8 · skeptical, not production.

| entry | gate | n | entry PF | random+gate PF | beats 0/5/10bps | dom-window share | decision |
|---|---|--:|--:|--:|:--:|--:|:--:|
| 8A | GATE_6A | 162 | 1.99 | 1.525 | True/True/True | 0.47 | **ENTRY_CANDIDATE** |
| 8A | GATE_6E | 68 | 2.663 | 1.37 | True/True/True | 0.46 | **ENTRY_CANDIDATE** |
| 8B | GATE_6A | 256 | 1.464 | 1.525 | False/False/False | 0.66 | **REJECT** |
| 8B | GATE_6E | 110 | 1.523 | 1.37 | True/True/True | 0.86 | **ENTRY_CANDIDATE** |
| 8C | GATE_6A | 828 | 1.552 | 1.525 | False/True/True | 0.56 | **REJECT** |
| 8C | GATE_6E | 350 | 1.803 | 1.37 | True/True/True | 0.52 | **ENTRY_CANDIDATE** |
| 8D | GATE_6A | 35 | 1.443 | 1.525 | False/False/False | 1.46 | **REJECT** |
| 8D | GATE_6E | 10 | 2.619 | 1.37 | True/True/True | 0.68 | **ENTRY_CANDIDATE** |
| old_event | GATE_6A | 4766 | 1.418 | 1.525 | False/False/False | 0.58 | **REJECT** |
| old_event | GATE_6E | 2405 | 1.716 | 1.37 | True/True/True | 0.54 | **ENTRY_CANDIDATE** |

An entry is useful ONLY if entry+gate PF beats random+gate PF (same gate). Otherwise the gate, not the entry, is the edge.
