# Noise rules (normalized) — OKX March

**Build:** 2026-06-02T16:57:16+00:00
Base traded n=1043 wr=36.63% PF=0.854 exp=-0.1255

| rule | reject | NOISE- | GOOD- | MID- | wrongdir- | stop- | kept n | kept wr% | kept PF |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| R1_LONG_bear_no_reclaim | 97 | 53 | 30 | 14 | 53 | 51 | 946 | 37.21 | 0.867 |
| R2_SHORT_bull_no_rejection | 96 | 59 | 32 | 5 | 53 | 55 | 947 | 36.96 | 0.875 |
| R3_ofi_conflict | 77 | 50 | 21 | 6 | 49 | 48 | 966 | 37.37 | 0.885 |
| R4_taker_conflict | 371 | 205 | 130 | 36 | 189 | 184 | 672 | 37.5 | 0.866 |
| R5_no_reclaim | 541 | 284 | 199 | 58 | 271 | 264 | 502 | 36.45 | 0.799 |
| R6_high_entropy_no_initiative | 0 | 0 | 0 | 0 | 0 | 0 | 1043 | 36.63 | 0.854 |
| R7_low_uniqueness | 378 | 214 | 131 | 33 | 212 | 203 | 665 | 37.74 | 0.904 |
| R8_opposite_zone_conflict | 610 | 322 | 242 | 46 | 305 | 307 | 433 | 32.33 | 0.746 |
| R9_late_after_impulse | 90 | 36 | 40 | 14 | 38 | 35 | 953 | 35.89 | 0.817 |