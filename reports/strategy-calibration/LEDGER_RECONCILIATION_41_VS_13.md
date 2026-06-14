# Ledger reconciliation - why 41 vs 13 OKX strict-ledger trades?

**Build:** 2026-05-23T10:09:35+00:00
**Scope:** Why 41 vs 13 OKX strict-ledger trade counts in two different reports

## A. Side-by-side comparison

| field | model_v1 (ACTUAL_EXIT_HOLD) | model_v2 (BLIND_24H_HOLD) |
|---|---|---|
| source report | okx_march_profitability_sanity.py / OKX_DIRECT_MARCH_PRE_COST_TRADE_LEDGER.json | hi_priority_filter_research.py Section F local strict_ledger helper |
| input alerts | filtered triggered zones | filtered triggered zones (same set) |
| ledger rule | one trade at a time | one trade at a time |
| position carry | until actual exit (target/stop/timeout) | blocks for full 24h regardless of actual exit |
| open_until formula | trig_sec + int(time_in_trade_h * 3600)  -- ACTUAL exit time | trig_sec + 24 * 3600  -- regardless of sim exit |
| entry source | trigger_price (or zone midpoint fallback) | trigger_price |
| stop/target tiebreak | stop_first (conservative) | stop_first |
| OKX trades | 41 | 13 |
| OKX W/L/T | 11/24/6 | 2/10/1 |
| OKX expectancy %/trade | -0.0497 | -0.5258 |
| OKX PF | 0.92 | 0.369 |
| OKX skipped (open) | 62 | not directly counted; effectively > 90 |
| Binance trades | 19 | 12 |
| Binance W/L/T | 5/3/11 | 5/2/5 |
| Binance expectancy | 0.6423 | 0.982 |
| Binance PF | 3.68 | 5.351 |
| Binance skipped (open) | 39 | not directly counted; effectively ~ 46 |

## B. Primary difference

model_v2 holds position for a hard 24h after entry, blocking subsequent signals for the full timeout window. model_v1 holds only until the actual exit (target/stop/timeout), freeing up signal slots as soon as a trade resolves. Same input signals, same simulation, ONLY the next-signal-allowed timestamp differs.

## C. Canonical decision

**Canonical = `model_v1 ACTUAL_EXIT_HOLD`**

The user's spec says: 'one trade at a time; position can carry across UTC day boundary until timeout/target/stop, but max holding time = 24h from entry.' model_v1 implements exactly this. model_v2 is a more conservative bound but artificially throttles trade count and is not what the spec requires.

## D. Flags

- `LEDGER_41_VS_13_EXPLAINED` = **YES**
- `PRIMARY_DIFFERENCE_BETWEEN_LEDGER_MODELS` = `position carry window: actual exit time (model_v1) vs blind 24h hold gate (model_v2)`