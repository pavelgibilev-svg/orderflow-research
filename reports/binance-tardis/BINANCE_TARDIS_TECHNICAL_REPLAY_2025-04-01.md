# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-04-01
- **Replay duration:** 2133.6s
- **Rows processed:** L2=138 924 099  trades=3 204 984  other=1 123

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 40 |
| LONG / SHORT | 23 / 17 |
| Triggered | 23 |
| Reached target | 9 |
| Failed by timeout | 14 |
| Invalidated before trigger | 13 |
| Expired (formation aged out) | 2 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 39.13% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 10.83% | 3.00% | 1200 |
| 8h | 27.08% | 9.58% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1743524434000-36 | SHORT | 2025-04-01T16:26:23.000Z | 84881.65 | 83184.02 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1743500724000-22 | LONG | 2025-04-01T10:16:37.000Z | 84404.25 | 86092.34 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1743498506000-20 | LONG | 2025-04-01T09:31:25.000Z | 84295.95 | 85981.87 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1743465767000-1 | LONG | 2025-04-01T02:16:45.000Z | 82901.55 | 84559.58 | RESOLVED_REACHED | 24h |
| BTCUSDT-LONG-1743465875000-2 | LONG | 2025-04-01T02:17:31.000Z | 82968.05 | 84627.41 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 9 |
| Unique reached moves | 1 |
| Duplicate move credits | 8 |
| Raw triggered hit rate | 39.13% |
| **Unique-move adjusted hit rate** | **4.35%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 9 | `BTCUSDT-LONG-1743467274000-3` | BTCUSDT-LONG-1743467274000-3, BTCUSDT-LONG-1743465767000-1, BTCUSDT-LONG-1743465875000-2, BTCUSDT-LONG-1743474947000-7, BTCUSDT-LONG-1743480611000-9, BTCUSDT-LONG-1743476243000-8, BTCUSDT-LONG-1743484982000-11, BTCUSDT-LONG-1743490074000-13, BTCUSDT-LONG-1743492978000-16 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **9621**
- Suppressions by reason:
  - `active_open`: 8213
  - `active_triggered`: 1408

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 1 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
