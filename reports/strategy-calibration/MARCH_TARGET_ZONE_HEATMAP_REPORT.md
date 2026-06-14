# Target-zone heatmap report

**Build:** 2026-05-29T17:37:26+00:00

- zones with target-zone computed: **1043**
- zones with a >=2% target (room to run): **216**
- zones blocked (<2% to first obstacle): **827** (79.29%)

## Target type distribution

| type | n |
|---|---:|
| blocked | 827 |
| hvn | 56 |
| session_high | 55 |
| session_low | 38 |
| swing_low | 36 |
| swing_high | 23 |
| open_void_2pct | 8 |

## Method
leak-free: swing pivots (5m half-window, 8h trailing) + session H/L + volume-profile HVN (50$ bins, 80th pct) + reused L2 void/wall features; all computed from buckets/trades with timestamp <= confirmedTs.