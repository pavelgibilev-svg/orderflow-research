# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-08-01
- **Replay duration:** 2536.3s
- **Rows processed:** L2=154 535 131  trades=4 671 690  other=1 946

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 32 |
| LONG / SHORT | 16 / 16 |
| Triggered | 19 |
| Reached target | 4 |
| Failed by timeout | 15 |
| Invalidated before trigger | 9 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 4 |
| Hit rate among triggered | 21.05% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 2.17% | 1200 |
| 8h | 0.00% | 14.90% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1754031047000-11 | SHORT | 2025-08-01T07:11:28.000Z | 114950.45 | 112651.44 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1754052815000-20 | LONG | 2025-08-01T13:12:04.000Z | 115948.35 | 118267.32 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1754052071000-19 | LONG | 2025-08-01T12:46:43.000Z | 115838.15 | 118154.91 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1754074626000-26 | SHORT | 2025-08-01T20:08:00.000Z | 113150.90 | 110887.88 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1754006470000-1 | SHORT | 2025-08-01T00:12:09.000Z | 115430.90 | 113122.28 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 4 |
| Unique reached moves | 1 |
| Duplicate move credits | 3 |
| Raw triggered hit rate | 21.05% |
| **Unique-move adjusted hit rate** | **5.26%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 4 | `BTCUSDT-SHORT-1754006470000-1` | BTCUSDT-SHORT-1754006470000-1, BTCUSDT-SHORT-1754007034000-2, BTCUSDT-SHORT-1754007113000-3, BTCUSDT-SHORT-1754017211000-10 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **8730**
- Suppressions by reason:
  - `active_open`: 6151
  - `active_triggered`: 2579

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
