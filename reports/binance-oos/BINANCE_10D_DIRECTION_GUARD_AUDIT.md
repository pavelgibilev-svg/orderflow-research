# Direction/regime guard — Binance 10d

**Build:** 2026-06-02T16:57:17+00:00

Guard = regime_against(1d/180m) AND NOT reversal_proof  → reject.

| | base | after guard |
|---|--:|--:|
| trades | 153 | 102 |
| winrate% | 20.26 | 20.59 |
| PF | 0.818 | 0.983 |
| expectancy% | -0.1137 | -0.0092 |
| wrong-dir | 75 | 50 |

rejected 51 (NOISE 29, GOOD 10); stops removed 22; fake-LONG removed 40.
