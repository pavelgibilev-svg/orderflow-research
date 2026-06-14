# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-03-01
- **Replay duration:** 859.5s
- **Rows processed:** L2=28 387 554  trades=5 961 363  other=1 483

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 7 |
| LONG / SHORT | 3 / 4 |
| Triggered | 1 |
| Reached target | 1 |
| Failed by timeout | 0 |
| Invalidated before trigger | 3 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 100.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 7.50% | 10.83% | 1200 |
| 8h | 9.38% | 27.08% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1772323262000-8 | SHORT | 2026-03-01T01:08:04.000Z | 66550.15 | 65219.15 | RESOLVED_REACHED | 24h |

## Warnings

- Encountered 1 feature ticks with quality flags.
- L2 replay was capped at 4h (compute-budget knob, not a strategy threshold). 111408381 L2 events were dropped after the cutoff. Trades continued full day.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
