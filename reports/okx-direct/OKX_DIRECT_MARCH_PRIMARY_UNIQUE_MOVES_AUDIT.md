# OKX direct partial March 2026 - audit of primary unique moves

**Build:** 2026-05-23T02:06:31+00:00
**Each row = engine-flagged primary_unique_reached_move zone; filter decision audit + sim-trade outcome at target 2 % / stop 1 % / timeout 24 h.**

| date | day Δ % | 24h up % | 24h dn % | direction | conf->trig min | filter kept | lost reason | sim exit | sim pnl % | sim time (h) | telegram | strict ledger took |
|---|---:|---:|---:|---|---:|:---:|---|---|---:|---:|:---:|:---:|
| 2026-03-02 | 4.6445 | 7.3703 | 2.7232 | LONG | 24.116666666666667 | YES | kept_by_filter | stop_1pct | -1.0 | 6.43 | YES | YES |
| 2026-03-03 | -0.7254 | 4.2448 | 4.5309 | SHORT | 10.516666666666667 | YES | kept_by_filter | target_2pct | 2.0 | 8.3806 | YES | YES |
| 2026-03-03 | -0.7254 | 4.2448 | 4.5309 | LONG | 8.333333333333334 | YES | kept_by_filter | stop_1pct | -1.0 | 3.0839 | YES | YES |
| 2026-03-04 | 6.3695 | 9.8935 | 2.3307 | LONG | 51.18333333333333 | YES | kept_by_filter | stop_1pct | -1.0 | 2.0033 | YES | NO |
| 2026-03-05 | -2.4856 | 2.504 | 3.9566 | SHORT | 57.18333333333333 | YES | kept_by_filter | stop_1pct | -1.0 | 8.7244 | YES | NO |
| 2026-03-06 | -3.9241 | 1.4991 | 5.1687 | SHORT | 47.8 | YES | kept_by_filter | target_2pct | 2.0 | 13.0844 | YES | YES |
| 2026-03-08 | -1.9167 | 2.4912 | 3.8129 | SHORT | 2.0833333333333335 | YES | kept_by_filter | stop_1pct | -1.0 | 8.4808 | YES | YES |
| 2026-03-09 | 3.6795 | 5.7083 | 1.771 | LONG | 35.483333333333334 | YES | kept_by_filter | target_2pct | 2.0 | 4.13 | YES | YES |
| 2026-03-10 | 2.2552 | 4.9806 | 3.261 | LONG | 7.683333333333334 | YES | kept_by_filter | target_2pct | 2.0 | 2.2597 | YES | YES |
| 2026-03-10 | 2.2552 | 4.9806 | 3.261 | SHORT | 0.55 | YES | kept_by_filter | target_2pct | 2.0 | 5.4008 | YES | YES |
| 2026-03-10 | 2.2552 | 4.9806 | 3.261 | SHORT | 39.516666666666666 | YES | kept_by_filter | target_2pct | 2.0 | 4.17 | YES | YES |
| 2026-03-11 | 0.3411 | 3.4132 | 2.0176 | LONG | 15.583333333333334 | YES | kept_by_filter | stop_1pct | -1.0 | 7.8883 | YES | YES |
| 2026-03-13 | 0.6345 | 5.0004 | 4.5257 | LONG | 9.066666666666666 | YES | kept_by_filter | stop_1pct | -1.0 | 3.005 | YES | YES |
| 2026-03-13 | 0.6345 | 5.0004 | 4.5257 | SHORT | 1.2666666666666666 | YES | kept_by_filter | stop_1pct | -1.0 | 0.3194 | YES | NO |
| 2026-03-15 | 2.2499 | 3.3457 | 1.0741 | LONG | 11.25 | YES | kept_by_filter | target_2pct | 2.0 | 22.3286 | YES | YES |

## Counts

- total primary unique reached zones: **15**
- kept by filter: **15**
- lost by filter: **0**
- target reached in sim: **7**
- strict-ledger took: **12**
- strict-ledger skipped due to open position: **3**