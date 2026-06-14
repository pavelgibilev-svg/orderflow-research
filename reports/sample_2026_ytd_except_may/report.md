# Sample 2026 (Jan-Apr) — Compatibility & Smoke-Test Backtest

> **This is a compatibility and smoke-test run, not a proof of strategy profitability.**
> Hit-rate numbers below come from a 4-day sample. They are useful only to verify
> the pipeline works end-to-end on real Tardis data. Do not use them to decide whether
> the strategy is "good".

- Generated: 2026-05-08T15:19:48.432Z
- Symbol: BTCUSDT
- Exchange: binance-futures
- Target: ±2.00%  Horizons: 4h, 8h, 24h
- Input: `./data/tardis/binance-futures/BTCUSDT`

## Per-day table

| Date | Valid | L2 rows | Trades rows | Optional present | Optional missing | Quality flag ticks | Snapshots | Zones | Candidates | Confirmed | Triggered | Reached 4h | Reached 8h | Reached 24h | Failed/no_trigger/inv | Baseline 24h up/down | Triggered hit rate | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-01-01 | yes | 9480504 | 1056983 | derivative_ticker,book_ticker,liquidations | - | 0 | - | 4 | 4 | 4 | 2 | 0 | 0 | 0 | 4 | 0.0%/0.0% | 0.0% | ok |
| 2026-02-01 | yes | 23129968 | 6759515 | derivative_ticker,book_ticker,liquidations | - | 0 | - | 3 | 3 | 3 | 1 | 0 | 0 | 1 | 2 | 0.0%/0.0% | 100.0% | ok |
| 2026-03-01 | yes | 28387554 | 5961363 | derivative_ticker,book_ticker,liquidations | - | 1 | - | 7 | 7 | 6 | 1 | 0 | 0 | 1 | 6 | 0.0%/0.0% | 100.0% | ok |
| 2026-04-01 | yes | 17950039 | 4104211 | derivative_ticker,book_ticker,liquidations | - | 0 | - | 9 | 9 | 8 | 5 | 0 | 0 | 0 | 9 | 0.0%/0.0% | 0.0% | ok |

## Anti-self-deception checks

- Failed / no_trigger / invalidated zones are kept in each day's `zones.csv` — not filtered out.
- This run does **not** modify `config/strategy.default.json`.
- This run does **not** sweep thresholds or pick the best.
- The hit rate above is reported only over zones that **actually triggered**.
- The per-day reports also include the unconditional 2% hit rate of the day's price walk; compare against it before drawing conclusions.

## What this sample can and cannot tell you

Can:
- Confirm the streaming Tardis CSV reader, order-book replay, feature engine, zone detector and target checker run end-to-end on real data.
- Confirm zone counts and statuses are non-degenerate (not all zero, not all reached).
- Surface real data-quality issues (gaps, crossed books, missing optional types).

Cannot:
- Prove the strategy is profitable: 4 days is too small, all four are first-of-month boundaries, and there is no out-of-sample split.
- Replace a proper monthly sweep over a paid Tardis subscription.
- Speak to slippage, fees, or any execution realism — this is a research module, not a trading bot.
