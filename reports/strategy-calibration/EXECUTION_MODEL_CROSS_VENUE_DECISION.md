# Execution model cross-venue decision

**Build:** 2026-05-23T10:13:09+00:00
**Diagnostic only. NOT a strategy change.**

## Criteria for 'promising'

- OKX improves: expectancy > baseline (-0.1782) AND PF > baseline (0.732) AND fewer losses than 27 AND n_trades >= 5.
- Binance does not break: expectancy > 0, PF > 1.0, wins ≥ 5 − 2.

## Promising variants

| variant | OKX exp % | OKX PF | OKX W/L | BIN exp % | BIN PF | BIN W/L |
|---|---:|---:|---|---:|---:|---|
| `delay_15m__stop_1.5pct` | 0.471 | 2.053 | 12/7 | 0.6648 | 3.694 | 5/1 |
| `trigger_entry__stop_1.5pct` | 0.3636 | 1.642 | 14/10 | 0.7416 | 4.293 | 5/1 |
| `retest__stop_1.25pct` | 0.3388 | 1.662 | 12/12 | 0.2524 | 1.576 | 3/5 |
| `delay_30m__stop_1.5pct` | 0.1777 | 1.299 | 10/10 | 0.7704 | 3.818 | 6/2 |
| `retest__stop_1.0pct` | 0.1065 | 1.196 | 10/19 | 0.3907 | 2.177 | 3/5 |
| `delay_30m__max(zb,1.0pct)` | 0.0093 | 1.015 | 10/19 | 0.6701 | 3.355 | 6/4 |
| `delay_30m__stop_1.0pct` | -0.0202 | 0.967 | 10/22 | 0.6836 | 3.522 | 6/5 |
| `delay_15m__stop_1.0pct` | -0.071 | 0.882 | 9/22 | 0.6294 | 3.464 | 5/4 |
| `trigger_entry__max(zb,1.25pct)` | -0.0886 | 0.875 | 11/20 | 0.7563 | 4.592 | 5/1 |
| `trigger_entry__stop_1.25pct` | -0.0913 | 0.869 | 11/20 | 0.756 | 4.586 | 5/2 |
| `trigger_entry__max(zb,1.0pct)` | -0.1701 | 0.75 | 10/26 | 0.6962 | 3.895 | 5/2 |

**`ROBUST_EXECUTION_VARIANT_FOUND` = YES**

**Best: `delay_15m__stop_1.5pct`**