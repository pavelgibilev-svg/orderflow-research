# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-22
- **Replay duration:** 1116.1s
- **Rows processed:** L2=115 700 601  trades=2 569 251  other=720

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 27 |
| LONG / SHORT | 13 / 14 |
| Triggered | 14 |
| Reached target | 7 |
| Failed by timeout | 7 |
| Invalidated before trigger | 7 |
| Expired (formation aged out) | 2 |
| No trigger by end of day | 4 |
| Hit rate among triggered | 50.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 0.00% | 15.21% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1779461413000-13 | SHORT | 2026-05-22T18:45:58.000Z | 76140.10 | 74617.30 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779460506000-12 | SHORT | 2026-05-22T15:25:13.000Z | 76545.75 | 75014.83 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779478080000-20 | SHORT | 2026-05-22T22:44:16.000Z | 75527.75 | 74017.19 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779478203000-21 | SHORT | 2026-05-22T22:44:16.000Z | 75527.75 | 74017.19 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779422839000-5 | SHORT | 2026-05-22T04:51:37.000Z | 77382.20 | 75834.56 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 7 |
| Unique reached moves | 1 |
| Duplicate move credits | 6 |
| Raw triggered hit rate | 50.00% |
| **Unique-move adjusted hit rate** | **7.14%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 7 | `BTCUSDT-SHORT-1779422839000-5` | BTCUSDT-SHORT-1779422839000-5, BTCUSDT-SHORT-1779416443000-4, BTCUSDT-SHORT-1779414465000-3, BTCUSDT-SHORT-1779409025000-1, BTCUSDT-SHORT-1779411938000-2, BTCUSDT-SHORT-1779440811000-6, BTCUSDT-SHORT-1779459206000-11 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **23680**
- Suppressions by reason:
  - `active_open`: 19817
  - `active_triggered`: 3863

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 48831 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
