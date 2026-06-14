# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-01-01
- **Replay duration:** 986.0s
- **Rows processed:** L2=62 609 291  trades=1 056 983  other=442

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 10 |
| LONG / SHORT | 5 / 5 |
| Triggered | 6 |
| Reached target | 0 |
| Failed by timeout | 6 |
| Invalidated before trigger | 2 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 0.00% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-LONG-1767225631000-1 | LONG | 2026-01-01T00:05:15.000Z | 87719.45 | 89473.84 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1767230525000-4 | LONG | 2026-01-01T17:21:03.000Z | 88187.45 | 89951.20 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1767227473000-3 | LONG | 2026-01-01T01:07:04.000Z | 87843.95 | 89600.83 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1767226228000-2 | SHORT | 2026-01-01T04:12:52.000Z | 87645.85 | 85892.93 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1767289418000-8 | SHORT | 2026-01-01T18:05:22.000Z | 88229.75 | 86465.15 | RESOLVED_FAILED | - |

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
