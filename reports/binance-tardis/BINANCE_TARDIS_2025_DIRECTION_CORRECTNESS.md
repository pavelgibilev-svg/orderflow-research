# Binance Tardis 2025 - direction correctness

**Build:** 2026-05-22T16:56:41+00:00
**Scope:** day-level 2 % feasibility (24h horizon) vs filtered Telegram alerts; live-valid filter.

| date | day Δ % | rng % | 24h up % | 24h dn % | verdict | LONG alerts | SHORT alerts | reached 2 % | direction correct | wrong-dir alerts |
|---|---:|---:|---:|---:|---|---:|---:|---:|---|---:|
| 2025-01-01 | 1.1033 | 2.4405 | 2.4405 | 1.6606 | UP_ONLY | 6 | 0 | 0 | YES | 0 |
| 2025-02-01 | -1.7303 | 2.502 | 0.9076 | 2.4409 | DOWN_ONLY | 2 | 1 | 1 | YES | 2 |
| 2025-03-01 | 2.0147 | 3.254 | 3.254 | 2.5708 | BOTH_FEASIBLE | 2 | 4 | 1 | YES | 0 |
| 2025-04-01 | 3.155 | 3.7807 | 3.7807 | 2.3247 | BOTH_FEASIBLE | 3 | 3 | 1 | YES | 0 |
| 2025-05-01 | 2.4415 | 3.4999 | 3.4999 | 1.291 | UP_ONLY | 4 | 3 | 2 | YES | 3 |
| 2025-06-01 | 0.9935 | 2.0287 | 2.0287 | 0.9507 | UP_ONLY | 3 | 1 | 0 | YES | 1 |
| 2025-07-01 | -1.3535 | 2.1915 | 0.8538 | 2.1445 | DOWN_ONLY | 0 | 3 | 0 | YES | 0 |
| 2025-08-01 | -2.1068 | 2.9592 | 1.6562 | 2.8741 | DOWN_ONLY | 1 | 6 | 2 | YES | 1 |
| 2025-09-01 | 0.9053 | 2.4739 | 2.4739 | 2.2417 | BOTH_FEASIBLE | 2 | 1 | 0 | YES | 0 |
| 2025-10-01 | 4.0036 | 4.1369 | 4.1369 | 1.2667 | UP_ONLY | 5 | 1 | 0 | YES | 1 |
| 2025-11-01 | 0.4473 | 1.0834 | 1.0834 | 0.7976 | NEITHER | 2 | 0 | 0 | None | 2 |
| 2025-12-01 | -4.5119 | 7.8685 | 3.6132 | 7.2946 | BOTH_FEASIBLE | 4 | 1 | 1 | YES | 0 |

## Summary

- days with up 2 % feasible: **8 / 12**
- days with down 2 % feasible: **7 / 12**
- days with both 2 % feasible: **4**
- days with NO 2 % feasible: **1**
- correct-direction days: **11**
- missed-opportunity days (feasible but no matching signal): **0**
- wrong-direction-alert days (no 2 % feasible AND filter still sent alerts): **1**
- filtered signals against only-feasible direction: **10**
- filtered signals matching feasible direction: **48**
- reached 2 % matching direction: **8**