# Binance live-recorder - pre-cost profitability sanity

**`PRE_COST_ONLY = YES`, `FEES_SLIPPAGE_INCLUDED = NO`, `PROFITABILITY_CLAIM = NO`.**

Sanity scenarios (NOT a profitability backtest):
  - Entry = `triggerPrice` (from zone's trigger reasons).
  - Target = +2 % in direction (engine's existing `target_pct 2`).
  - Stop scenarios: fixed 1 %, OR no-stop (diagnostic only).
  - Outcome from engine's per-horizon `reached/failed_by_timeout` + `mfePct/maePct/maxDrawdownBeforeTargetPct`.

## A. Fixed-stop 1 % scenario, 24h horizon

| set | trades | wins | losses | timeouts | winrate | avg win % | avg loss % | expectancy %/trade | profit factor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline (all triggered) | 41 | 0 | 22 | 19 | 0.0 | None | -1.0 | -0.5366 | 0.0 |
| filtered (kept) | 14 | 0 | 6 | 8 | 0.0 | None | -1.0 | -0.4286 | 0.0 |

## B. No-stop diagnostic, 24h horizon

| set | trades | expectancy %/trade | LONG n / exp | SHORT n / exp |
|---|---:|---:|---|---|
| baseline | 41 | -0.2783 | 13 / -0.4602 | 28 / -0.1939 |
| filtered | 14 | -0.1102 | 5 / -0.1469 | 9 / -0.0899 |

## C. Per-day expectancy (filtered, fixed-1 %)

| date | n trades | mean pnl %/trade |
|---|---:|---:|
| 2026-05-17 | 3 | -0.3333 |
| 2026-05-18 | 6 | -0.5 |
| 2026-05-19 | 4 | -0.25 |
| 2026-05-20 | 1 | -1.0 |

## D. Flags

- PRE_COST_ONLY = YES
- FEES_SLIPPAGE_INCLUDED = NO
- PROFITABILITY_CLAIM = NO
- PRE_COST_EXPECTANCY_POSITIVE = **NO**
- PRE_COST_PROFIT_FACTOR = **0.0**

## Caveat

- 4h/8h/24h horizon outcomes require future price data. On partial days where the recording
  ends at 24:00 UTC, late-trigger zones may have truncated horizons; the engine reports those as
  `failed_by_timeout` with whatever data was available.
- These are SANITY numbers under simplistic stop assumptions. NOT a profitability claim.