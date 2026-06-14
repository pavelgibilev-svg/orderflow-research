# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-05-01
- **Replay duration:** 1607.8s
- **Rows processed:** L2=100 939 742  trades=2 825 344  other=923

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 41 |
| LONG / SHORT | 23 / 18 |
| Triggered | 22 |
| Reached target | 9 |
| Failed by timeout | 13 |
| Invalidated before trigger | 14 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 4 |
| Hit rate among triggered | 40.91% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 18.65% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-LONG-1746092546000-18 | LONG | 2025-05-01T09:50:29.000Z | 95558.75 | 97469.93 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1746088147000-14 | LONG | 2025-05-01T09:20:36.000Z | 95249.95 | 97154.95 | RESOLVED_REACHED | 8h |
| BTCUSDT-LONG-1746079811000-13 | LONG | 2025-05-01T08:56:15.000Z | 95172.25 | 97075.70 | RESOLVED_REACHED | 8h |
| BTCUSDT-LONG-1746065848000-9 | LONG | 2025-05-01T02:26:44.000Z | 94825.65 | 96722.16 | RESOLVED_REACHED | 24h |
| BTCUSDT-LONG-1746094051000-20 | LONG | 2025-05-01T10:16:39.000Z | 95831.55 | 97748.18 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 9 |
| Unique reached moves | 1 |
| Duplicate move credits | 8 |
| Raw triggered hit rate | 40.91% |
| **Unique-move adjusted hit rate** | **4.55%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 9 | `BTCUSDT-LONG-1746060724000-4` | BTCUSDT-LONG-1746057935000-2, BTCUSDT-LONG-1746060724000-4, BTCUSDT-LONG-1746058194000-3, BTCUSDT-LONG-1746062166000-6, BTCUSDT-LONG-1746062484000-7, BTCUSDT-LONG-1746065848000-9, BTCUSDT-LONG-1746067543000-11, BTCUSDT-LONG-1746079811000-13, BTCUSDT-LONG-1746088147000-14 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **11679**
- Suppressions by reason:
  - `active_open`: 9852
  - `active_triggered`: 1827

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
