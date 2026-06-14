# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-02-01
- **Replay duration:** 2528.3s
- **Rows processed:** L2=165 962 192  trades=6 759 515  other=2 125

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 20 |
| LONG / SHORT | 7 / 13 |
| Triggered | 11 |
| Reached target | 6 |
| Failed by timeout | 5 |
| Invalidated before trigger | 7 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 54.55% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.08% | 20.00% | 1200 |
| 8h | 0.10% | 46.25% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-LONG-1769985661000-17 | LONG | 2026-02-01T23:36:10.000Z | 77560.50 | 79111.71 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1769929070000-4 | SHORT | 2026-02-01T07:04:52.000Z | 78082.25 | 76520.60 | RESOLVED_REACHED | 24h |
| BTCUSDT-LONG-1769980916000-16 | LONG | 2026-02-01T22:11:01.000Z | 77276.75 | 78822.29 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1769904037000-1 | SHORT | 2026-02-01T01:07:10.000Z | 78566.05 | 76994.73 | RESOLVED_REACHED | 24h |
| BTCUSDT-SHORT-1769940184000-7 | SHORT | 2026-02-01T10:36:21.000Z | 78500.35 | 76930.34 | RESOLVED_REACHED | 8h |

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
