# OKX direct partial March 2026 - direction correctness

**Build:** 2026-05-23T02:06:29+00:00
**Scope:** day-level 2 % feasibility (24h horizon) vs filtered Telegram alerts; live-valid filter.

| date | day Δ % | rng % | 24h up % | 24h dn % | verdict | LONG alerts | SHORT alerts | reached 2 % | direction correct | wrong-dir alerts |
|---|---:|---:|---:|---:|---|---:|---:|---:|---|---:|
| 2026-03-02 | 4.6445 | 7.465 | 7.3703 | 2.7232 | BOTH_FEASIBLE | 7 | 6 | 1 | YES | 0 |
| 2026-03-03 | -0.7254 | 4.7951 | 4.2448 | 4.5309 | BOTH_FEASIBLE | 5 | 1 | 1 | YES | 0 |
| 2026-03-04 | 6.3695 | 9.9051 | 9.8935 | 2.3307 | BOTH_FEASIBLE | 10 | 7 | 6 | YES | 0 |
| 2026-03-05 | -2.4856 | 4.1281 | 2.504 | 3.9566 | BOTH_FEASIBLE | 2 | 2 | 0 | YES | 0 |
| 2026-03-06 | -3.9241 | 5.4504 | 1.4991 | 5.1687 | DOWN_ONLY | 3 | 3 | 2 | YES | 3 |
| 2026-03-07 | -1.2434 | 2.4587 | 1.2365 | 2.3882 | DOWN_ONLY | 2 | 0 | 0 | NO | 2 |
| 2026-03-08 | -1.9167 | 3.9665 | 2.4912 | 3.8129 | BOTH_FEASIBLE | 5 | 4 | 1 | YES | 0 |
| 2026-03-09 | 3.6795 | 5.7248 | 5.7083 | 1.771 | UP_ONLY | 6 | 5 | 1 | YES | 5 |
| 2026-03-10 | 2.2552 | 4.9806 | 4.9806 | 3.261 | BOTH_FEASIBLE | 5 | 5 | 4 | YES | 0 |
| 2026-03-11 | 0.3411 | 3.4133 | 3.4132 | 2.0176 | BOTH_FEASIBLE | 5 | 2 | 2 | YES | 0 |
| 2026-03-12 | 0.4677 | 2.3472 | 2.3278 | 2.0511 | BOTH_FEASIBLE | 2 | 1 | 0 | YES | 0 |
| 2026-03-13 | 0.6345 | 5.006 | 5.0004 | 4.5257 | BOTH_FEASIBLE | 4 | 3 | 1 | YES | 0 |
| 2026-03-14 | 0.3989 | 1.4591 | 1.3414 | 1.4252 | NEITHER | 1 | 3 | 0 | None | 4 |
| 2026-03-15 | 2.2499 | 3.3457 | 3.3457 | 1.0741 | UP_ONLY | 3 | 1 | 2 | YES | 1 |

## Summary

- days with up 2 % feasible: **11 / 14**
- days with down 2 % feasible: **11 / 14**
- days with both 2 % feasible: **9**
- days with NO 2 % feasible: **1**
- correct-direction days: **12**
- missed-opportunity days: **1**
- wrong-direction-alert days: **1**
- filtered signals against only-feasible direction: **15**
- filtered signals matching feasible direction: **88**
- reached 2 % matching direction: **21**