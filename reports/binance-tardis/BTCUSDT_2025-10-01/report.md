# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-10-01
- **Replay duration:** 1676.8s
- **Rows processed:** L2=108 669 861  trades=3 495 302  other=1 133

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 44 |
| LONG / SHORT | 19 / 25 |
| Triggered | 21 |
| Reached target | 6 |
| Failed by timeout | 15 |
| Invalidated before trigger | 18 |
| Expired (formation aged out) | 3 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 28.57% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 4.75% | 0.00% | 1200 |
| 8h | 37.50% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-LONG-1759321753000-21 | LONG | 2025-10-01T13:57:10.000Z | 116789.05 | 119124.83 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1759295918000-12 | LONG | 2025-10-01T08:20:47.000Z | 114749.05 | 117044.03 | RESOLVED_REACHED | 8h |
| BTCUSDT-LONG-1759313886000-18 | LONG | 2025-10-01T11:41:55.000Z | 116480.15 | 118809.75 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1759328147000-24 | LONG | 2025-10-01T15:29:08.000Z | 117610.65 | 119962.86 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1759322227000-22 | LONG | 2025-10-01T14:00:37.000Z | 116898.95 | 119236.93 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 6 |
| Unique reached moves | 1 |
| Duplicate move credits | 5 |
| Raw triggered hit rate | 28.57% |
| **Unique-move adjusted hit rate** | **4.76%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 6 | `BTCUSDT-LONG-1759278512000-3` | BTCUSDT-LONG-1759278512000-3, BTCUSDT-LONG-1759281304000-6, BTCUSDT-LONG-1759281383000-7, BTCUSDT-LONG-1759284308000-9, BTCUSDT-LONG-1759277281000-1, BTCUSDT-LONG-1759295918000-12 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **11082**
- Suppressions by reason:
  - `active_open`: 9747
  - `cooldown`: 181
  - `active_triggered`: 1154

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
