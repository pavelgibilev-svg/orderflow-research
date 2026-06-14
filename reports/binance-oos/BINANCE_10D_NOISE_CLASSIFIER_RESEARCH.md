# D. Binance 10d — noise classifier research

**Build:** 2026-06-02T14:02:11+00:00
Base population = all triggered/sim zones (n=153; GOOD=31 NOISE=72 MID=50).
Rule = TRUE means REJECT. Applied post-hoc to the WHOLE triggered population (not just RS1 picks) to measure noise-removal power.

| rule | rejected | NOISE removed | GOOD lost | wrongdir removed | stop removed | kept n | kept wr% | kept PF |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| R1_LONG_bear_no_reclaim | 51 | 29 | 10 | 34 | 28 | 102 | 20.59 | 1.127 |
| R2_SHORT_bull_no_rejection | 7 | 5 | 0 | 4 | 1 | 146 | 21.23 | 0.841 |
| R3_ofi_direction_conflict | 102 | 48 | 23 | 50 | 34 | 51 | 15.69 | 0.643 |
| R4_no_reclaim_after_hit | 129 | 61 | 27 | 64 | 43 | 24 | 16.67 | 0.638 |
| R5_high_entropy | 0 | 0 | 0 | 0 | 0 | 153 | 20.26 | 0.818 |
| R6_taker_imbalance_conflict | 78 | 41 | 14 | 36 | 30 | 75 | 22.67 | 1.022 |
| R7_low_uniqueness_vs_prior | 71 | 32 | 16 | 35 | 22 | 82 | 18.29 | 0.769 |

Base (no filter): n=153 wr=20.26% PF=0.818 exp=-0.1137