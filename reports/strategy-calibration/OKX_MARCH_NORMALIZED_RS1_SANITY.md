# OKX March — normalized RS1 sanity

**Build:** 2026-06-02T16:56:47+00:00

Replace absolute `supp_opp_15m<=4497.76` with OKX-derived normalized equivalents (pctile≤75 / z≤0.468). top1/day unchanged.

| ruleset | trades | wr% | exp% | PF | maxCL | overlap w/ frozen |
|---|--:|--:|--:|--:|--:|--:|
| frozen RS1 | 29 | 62.07 | 0.6475 | 2.258 | 3 | 29 |
| NRS1_A pctile≤75 | 29 | 55.17 | 0.4061 | 1.647 | 3 | 26 |
| NRS1_B z≤0.468 | 29 | 55.17 | 0.4061 | 1.647 | 3 | 25 |
| NRS1_C pctile+scorefloor | 24 | 50.0 | 0.249 | 1.361 | 3 | 21 |

**PRESERVES_EDGE=PARTIAL** · best=NRS1_A_pctile
