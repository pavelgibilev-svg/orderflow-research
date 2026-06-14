# Noise rules (normalized) — Binance 10d

**Build:** 2026-06-02T16:57:17+00:00
Base traded n=153 wr=20.26% PF=0.818 exp=-0.1137

| rule | reject | NOISE- | GOOD- | MID- | wrongdir- | stop- | kept n | kept wr% | kept PF |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| R1_LONG_bear_no_reclaim | 51 | 29 | 10 | 12 | 34 | 28 | 102 | 20.59 | 1.127 |
| R2_SHORT_bull_no_rejection | 7 | 5 | 0 | 2 | 4 | 1 | 146 | 21.23 | 0.841 |
| R3_ofi_conflict | 102 | 48 | 23 | 31 | 50 | 34 | 51 | 15.69 | 0.643 |
| R4_taker_conflict | 78 | 41 | 14 | 23 | 36 | 30 | 75 | 22.67 | 1.022 |
| R5_no_reclaim | 129 | 61 | 27 | 41 | 64 | 43 | 24 | 16.67 | 0.638 |
| R6_high_entropy_no_initiative | 0 | 0 | 0 | 0 | 0 | 0 | 153 | 20.26 | 0.818 |
| R7_low_uniqueness | 71 | 32 | 16 | 23 | 35 | 22 | 82 | 18.29 | 0.769 |
| R8_opposite_zone_conflict | 28 | 11 | 7 | 10 | 13 | 6 | 125 | 19.2 | 0.755 |
| R9_late_after_impulse | 6 | 3 | 0 | 3 | 4 | 1 | 147 | 21.09 | 0.838 |