# Execution variants under canonical strict-ledger (DIAGNOSTIC only, NOT strategy changes)

**Build:** 2026-05-23T10:13:09+00:00
**Target strict 2 %. Timeout 24h. Diagnostic only — engine is NOT modified.**

| variant | OKX n W/L/T | OKX winrate | OKX exp % | OKX PF | BIN n W/L/T | BIN winrate | BIN exp % | BIN PF | OKX stops avoided | BIN stops avoided |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| `trigger_entry__stop_1.0pct` | 44 10/27/7 | 22.73 | -0.1782 | 0.732 | 18 5/3/10 | 27.78 | 0.7098 | 4.129 | 0 | 0 |
| `trigger_entry__stop_1.25pct` | 40 11/20/9 | 27.5 | -0.0913 | 0.869 | 17 5/2/10 | 29.41 | 0.756 | 4.586 | 7 | 1 |
| `trigger_entry__stop_1.5pct` | 31 14/10/7 | 45.16 | 0.3636 | 1.642 | 17 5/1/11 | 29.41 | 0.7416 | 4.293 | 17 | 2 |
| `trigger_entry__zone_boundary_stop` | 68 8/56/4 | 11.76 | -0.1575 | 0.617 | 29 2/18/9 | 6.9 | 0.0596 | 1.195 | -29 | -15 |
| `trigger_entry__max(zb,1.0pct)` | 42 10/26/6 | 23.81 | -0.1701 | 0.75 | 18 5/2/11 | 27.78 | 0.6962 | 3.895 | 1 | 1 |
| `trigger_entry__max(zb,1.25pct)` | 39 11/20/8 | 28.21 | -0.0886 | 0.875 | 17 5/1/11 | 29.41 | 0.7563 | 4.592 | 7 | 2 |
| `delay_5m__stop_1.0pct` | 45 10/29/6 | 22.22 | -0.1863 | 0.725 | 19 5/3/11 | 26.32 | 0.6336 | 3.572 | -2 | 0 |
| `delay_10m__stop_1.0pct` | 45 9/29/7 | 20.0 | -0.2237 | 0.666 | 18 5/2/11 | 27.78 | 0.7453 | 5.118 | -2 | 1 |
| `delay_15m__stop_1.0pct` | 39 9/22/8 | 23.08 | -0.071 | 0.882 | 19 5/4/10 | 26.32 | 0.6294 | 3.464 | 5 | -1 |
| `delay_30m__stop_1.0pct` | 39 10/22/7 | 25.64 | -0.0202 | 0.967 | 19 6/5/8 | 31.58 | 0.6836 | 3.522 | 5 | -2 |
| `delay_15m__stop_1.5pct` | 30 12/7/11 | 40.0 | 0.471 | 2.053 | 18 5/1/12 | 27.78 | 0.6648 | 3.694 | 20 | 2 |
| `delay_30m__stop_1.5pct` | 31 10/10/11 | 32.26 | 0.1777 | 1.299 | 17 6/2/9 | 35.29 | 0.7704 | 3.818 | 17 | 1 |
| `delay_30m__max(zb,1.0pct)` | 37 10/19/8 | 27.03 | 0.0093 | 1.015 | 19 6/4/9 | 31.58 | 0.6701 | 3.355 | 8 | -1 |
| `retest__stop_1.0pct` | 37 10/19/8 | 27.03 | 0.1065 | 1.196 | 18 3/5/10 | 16.67 | 0.3907 | 2.177 | 8 | -2 |
| `retest__stop_1.25pct` | 33 12/12/9 | 36.36 | 0.3388 | 1.662 | 17 3/5/9 | 17.65 | 0.2524 | 1.576 | 15 | -2 |
| `retest__zone_boundary_stop` | 66 6/57/3 | 9.09 | -0.1169 | 0.634 | 31 0/26/5 | 0.0 | -0.0835 | 0.624 | -30 | -23 |

## Notes
- All variants share the SAME filtered signal pool and SAME canonical ledger rule.
- Variants differ only in (a) entry timing (trigger / delay_Nm / retest) and (b) stop placement (fixed % / zone-boundary).
- Target is strict 2 % across all variants.
- This is a DIAGNOSTIC. NO strategy change is proposed.