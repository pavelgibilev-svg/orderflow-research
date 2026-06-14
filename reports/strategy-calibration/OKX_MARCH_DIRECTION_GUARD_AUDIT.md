# Direction/regime guard — OKX March

**Build:** 2026-06-02T16:57:16+00:00

Guard = regime_against(1d/180m) AND NOT reversal_proof  → reject.

| | base | after guard |
|---|--:|--:|
| trades | 1043 | 954 |
| winrate% | 36.63 | 37.11 |
| PF | 0.854 | 0.869 |
| expectancy% | -0.1255 | -0.1114 |
| wrong-dir | 538 | 489 |

rejected 89 (NOISE 52, GOOD 28); stops removed 51; fake-LONG removed 36.
