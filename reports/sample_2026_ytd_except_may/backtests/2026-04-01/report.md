# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-04-01
- **Replay duration:** 576.4s
- **Rows processed:** L2=17 950 039  trades=4 104 211  other=1 090

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 9 |
| LONG / SHORT | 5 / 4 |
| Triggered | 5 |
| Reached target | 0 |
| Failed by timeout | 5 |
| Invalidated before trigger | 2 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 3.67% | 0.00% | 1200 |
| 8h | 12.08% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1775004555000-16 | SHORT | 2026-04-01T01:34:36.000Z | 67920.05 | 66561.65 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1775008141000-18 | SHORT | 2026-04-01T02:29:16.000Z | 67595.45 | 66243.54 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1775010708000-19 | LONG | 2026-04-01T03:10:28.000Z | 68009.45 | 69369.64 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1775002106000-15 | LONG | 2026-04-01T00:51:04.000Z | 68239.50 | 69604.29 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1775013375000-22 | LONG | 2026-04-01T03:45:52.000Z | 68101.60 | 69463.63 | RESOLVED_FAILED | - |

## Warnings

- L2 replay was capped at 4h (compute-budget knob, not a strategy threshold). 107013390 L2 events were dropped after the cutoff. Trades continued full day.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
