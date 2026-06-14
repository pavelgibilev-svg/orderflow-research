# OKX technical strategy replay — BTC-USDT-SWAP 2026-03-01

**Venue:** OKX (okex-swap)
**Window:** full UTC day
**Target:** 2% on horizons 4h, 8h, 24h
**Underlying backtest report:** `reports/BTC-USDT-SWAP_2026-03-01/`
**Run wall-clock:** 5624.2 s

## HARD DISCLAIMER

  • OKX is NOT Binance.
  • Strategy thresholds are calibrated for Binance USDS-M Futures BTCUSDT-perp.
  • This is a technical replay / cross-venue research run with Binance-tuned thresholds left UNCHANGED.
  • Zone counts below describe how the engine reacts to OKX L2 microstructure; they are NOT a backtest of profitability on OKX.
  • Do NOT quote any of these numbers as a strategy edge or winrate.

## A. Data quality

(Deep L2-quality numbers — snapshot anchor count, crossed-seconds,
sequence integrity — are in the companion audit
`reports/OKX_HISTORICAL_L2_AUDIT.md` Sections 4 and 5. The replay window
here was capped at full day
for compute-budget reasons; that's a knob, not a threshold change.)

## B. Zone output (engine reaction on OKX with Binance-tuned thresholds)

| metric                            | value |
|-----------------------------------|------:|
| Total zones created               | 43 |
| Still in CANDIDATE                | 0 |
| Confirmed (any later state)       | 43 |
| Triggered                         | 26 |
| RESOLVED_REACHED (raw)            | 7 |
| RESOLVED_FAILED                   | 19 |
| EXPIRED                           | 0 |
| INVALIDATED                       | 15 |
| NO_TRIGGER                        | 2 |
| LONG zones                        | 19 |
| SHORT zones                       | 24 |
| Unique-move clusters              | 1 |
| Duplicate-move credits absorbed   | 6 |
| Duplicate suppressions (dedup)    | 12402 |
| Cooldown after resolve            | 30 min |
| Raw triggered hit-rate            | 26.92 % |
| Unique-move-adjusted hit-rate     | 3.85 % |

> These hit-rates measure how often the Binance-tuned engine's triggers
> happen to land on a 2% move within the configured horizons on
> OKX data. They are NOT a profitability claim and should not be reported
> as a strategy edge.

See `OKX_TECHNICAL_REPLAY_2026-03-01_ZONES.csv` for the per-zone breakdown.

## C. Cross-venue interpretation guide

- **Too many zones vs Binance baseline** ⇒ OKX liquidity profile may make
  the imbalance / void thresholds easier to trip. Do NOT lower thresholds;
  flag for a dedicated cross-venue calibration task later.
- **Too few zones** ⇒ thresholds may be too tight for OKX. Same response —
  document, do not tune.
- **Crossed-seconds > ~0.5 %** in the L2 audit ⇒ reconstruction artefact
  or burst microstructure on OKX; cross-check with the independent
  `book_ticker` stream (Section 4.3 of `OKX_HISTORICAL_L2_AUDIT.md`).

## D. Future work (out of scope here)

- Calibrate dedup / cooldown / overlap thresholds independently for OKX
  under a venue-specific config.
- Cross-venue zone-density comparison Binance ↔ OKX on matched windows.
- Multi-day OKX sample (requires Tardis paid API key OR OKX VIP / premium).
