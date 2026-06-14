# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-01-01
- **Replay duration:** 1420.3s
- **Rows processed:** L2=62 609 291  trades=1 056 983  other=442

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 23 |
| LONG / SHORT | 12 / 11 |
| Triggered | 14 |
| Reached target | 0 |
| Failed by timeout | 14 |
| Invalidated before trigger | 3 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 6 |
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
| BTCUSDT-LONG-1767233765000-8 | LONG | 2026-01-01T17:20:47.000Z | 88113.35 | 89875.62 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1767230525000-6 | LONG | 2026-01-01T17:21:03.000Z | 88187.45 | 89951.20 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1767227473000-3 | LONG | 2026-01-01T01:07:04.000Z | 87843.95 | 89600.83 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1767231203000-7 | LONG | 2026-01-01T01:54:29.000Z | 87948.25 | 89707.21 | RESOLVED_FAILED | - |

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **12822**
- Suppressions by reason:
  - `active_open`: 8881
  - `active_triggered`: 3941

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
