# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-03-01
- **Replay duration:** 1829.3s
- **Rows processed:** L2=117 922 346  trades=3 014 683  other=1 082

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 28 |
| LONG / SHORT | 12 / 16 |
| Triggered | 16 |
| Reached target | 2 |
| Failed by timeout | 14 |
| Invalidated before trigger | 10 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 12.50% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 9.92% | 0.42% | 1200 |
| 8h | 16.56% | 2.71% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1740810423000-18 | SHORT | 2025-03-01T07:38:34.000Z | 84720.05 | 83025.65 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1740802593000-11 | SHORT | 2025-03-01T06:35:12.000Z | 84887.45 | 83189.70 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1740791653000-4 | LONG | 2025-03-01T01:41:18.000Z | 84129.95 | 85812.55 | RESOLVED_REACHED | 4h |
| BTCUSDT-LONG-1740802801000-12 | LONG | 2025-03-01T04:32:07.000Z | 86007.50 | 87727.65 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1740789547000-2 | SHORT | 2025-03-01T00:54:45.000Z | 83842.45 | 82165.60 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 2 |
| Unique reached moves | 1 |
| Duplicate move credits | 1 |
| Raw triggered hit rate | 12.50% |
| **Unique-move adjusted hit rate** | **6.25%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 2 | `BTCUSDT-LONG-1740791653000-4` | BTCUSDT-LONG-1740791653000-4, BTCUSDT-LONG-1740794813000-5 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10874**
- Suppressions by reason:
  - `active_open`: 4884
  - `active_triggered`: 5990

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
