# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2024-03-01
- **Replay duration:** 7345.0s
- **Rows processed:** L2=156 620 810  trades=1 059 398  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 32 |
| LONG / SHORT | 21 / 11 |
| Triggered | 23 |
| Reached target | 8 |
| Failed by timeout | 15 |
| Invalidated before trigger | 7 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 34.78% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 3.92% | 5.75% | 1200 |
| 8h | 21.56% | 7.19% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1709267649000-8 | LONG | 2024-03-01T05:00:03.000Z | 61565.95 | 62797.27 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1709251352000-1 | SHORT | 2024-03-01T02:12:05.000Z | 61114.15 | 59891.87 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1709274584000-12 | LONG | 2024-03-01T07:07:06.000Z | 61745.05 | 62979.95 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1709277138000-13 | LONG | 2024-03-01T08:19:21.000Z | 61832.95 | 63069.61 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1709269538000-9 | LONG | 2024-03-01T06:17:19.000Z | 61684.55 | 62918.24 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 8 |
| Unique reached moves | 1 |
| Duplicate move credits | 7 |
| Raw triggered hit rate | 34.78% |
| **Unique-move adjusted hit rate** | **4.35%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 8 | `BTC-USDT-SWAP-LONG-1709260315000-6` | BTC-USDT-SWAP-LONG-1709260315000-6, BTC-USDT-SWAP-LONG-1709265818000-7, BTC-USDT-SWAP-LONG-1709267649000-8, BTC-USDT-SWAP-LONG-1709269711000-10, BTC-USDT-SWAP-LONG-1709269538000-9, BTC-USDT-SWAP-LONG-1709274584000-12, BTC-USDT-SWAP-LONG-1709274535000-11, BTC-USDT-SWAP-LONG-1709277138000-13 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10751**
- Suppressions by reason:
  - `active_open`: 6256
  - `active_triggered`: 4495

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 1 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
