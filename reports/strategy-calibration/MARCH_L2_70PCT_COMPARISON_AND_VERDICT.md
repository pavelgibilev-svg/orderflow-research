# L2 vs no-L2 verdict

**Build:** 2026-05-26T14:32:37+00:00

## Comparison

| metric | no-L2 (confirm-stage leak-free) | L2-enhanced |
|---|---|---|
| best selector | `CONF::P::taker_total_vol_15m_le_69071.8+utc_hour_le_4.0::top1` | `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` |
| precision % | 42.86 | 40.0 |
| selected n | 28 | 25 |
| H1 / H2 | 38.46/46.67 | 41.67/38.46 |

## Verdict
- L2 features did NOT meaningfully lift precision past current ceiling
- 70 % goal reached with L2: **False**.

- Best L2 paper-trade model: `L2::P::taker_total_vol_15m_le_69071.8+dist_to_recent_swing_high_pct_le_0.321::top1` | confirmed | stop_1.5 — winrate 56.0 %, expectancy after cost 0.4417 %, PF after cost 1.725.