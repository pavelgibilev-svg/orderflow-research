# Binance Tardis 2025 - audit of 7 primary unique moves

**Build:** 2026-05-22T16:56:43+00:00
**Each row = one engine-flagged primary_unique_reached_move zone. Filter decision audit + sim-trade outcome at target 2 % / stop 1 % / timeout 24 h.**

| date | regime | direction | conf->trig min | filter kept | lost reason | sim exit | sim pnl % | sim time (h) | telegram alert | strict ledger took |
|---|---|---|---:|:---:|---|---|---:|---:|:---:|:---:|
| 2025-02-01 | bearish | SHORT | 18.65 | YES | kept_by_filter | target_2pct | 2.0 | 21.2278 | YES | YES |
| 2025-03-01 | bullish | LONG | 9.766666666666667 | YES | kept_by_filter | target_2pct | 2.0 | 2.5164 | YES | NO |
| 2025-04-01 | bullish | LONG | 105.56666666666666 | NO | slow_trigger_gt_60min | target_2pct | 2.0 | 12.92 | NO | NO |
| 2025-05-01 | bullish | LONG | 11.616666666666667 | YES | kept_by_filter | target_2pct | 2.0 | 11.5842 | YES | NO |
| 2025-08-01 | bearish | SHORT | 7.466666666666667 | YES | kept_by_filter | target_2pct | 2.0 | 19.9311 | YES | YES |
| 2025-10-01 | bullish | LONG | 140.08333333333334 | NO | slow_trigger_gt_60min | target_2pct | 2.0 | 5.7047 | NO | NO |
| 2025-12-01 | bearish | SHORT | 8.733333333333333 | YES | kept_by_filter | target_2pct | 2.0 | 12.0367 | YES | YES |

## Counts

- total primary unique reached zones: **7**
- kept by filter: **5**
- lost by filter: **2**
- target reached in sim (any of the 7): **7**
- strict-ledger took (out of kept): **3**