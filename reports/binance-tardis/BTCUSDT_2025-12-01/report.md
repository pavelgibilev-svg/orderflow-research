# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-12-01
- **Replay duration:** 2647.5s
- **Rows processed:** L2=170 098 911  trades=6 767 867  other=2 922

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 38 |
| LONG / SHORT | 19 / 19 |
| Triggered | 18 |
| Reached target | 6 |
| Failed by timeout | 12 |
| Invalidated before trigger | 20 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 33.33% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 7.75% | 37.58% | 1200 |
| 8h | 3.65% | 56.67% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-LONG-1764575940000-21 | LONG | 2025-12-01T09:03:25.000Z | 86857.35 | 88594.50 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1764570353000-18 | LONG | 2025-12-01T06:42:17.000Z | 86200.15 | 87924.15 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1764578168000-22 | LONG | 2025-12-01T09:03:25.000Z | 86857.35 | 88594.50 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1764559394000-8 | SHORT | 2025-12-01T03:36:15.000Z | 86200.25 | 84476.24 | RESOLVED_REACHED | 24h |
| BTCUSDT-LONG-1764563455000-13 | LONG | 2025-12-01T06:03:55.000Z | 86070.65 | 87792.06 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 6 |
| Unique reached moves | 1 |
| Duplicate move credits | 5 |
| Raw triggered hit rate | 33.33% |
| **Unique-move adjusted hit rate** | **5.56%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 6 | `BTCUSDT-SHORT-1764557985000-6` | BTCUSDT-SHORT-1764557985000-6, BTCUSDT-SHORT-1764559394000-8, BTCUSDT-SHORT-1764561745000-10, BTCUSDT-SHORT-1764561893000-11, BTCUSDT-SHORT-1764564451000-15, BTCUSDT-SHORT-1764563848000-14 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **8210**
- Suppressions by reason:
  - `active_open`: 5688
  - `active_triggered`: 2515
  - `cooldown`: 7

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 2 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
