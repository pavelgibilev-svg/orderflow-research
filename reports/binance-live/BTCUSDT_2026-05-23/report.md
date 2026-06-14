# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-23
- **Replay duration:** 1070.7s
- **Rows processed:** L2=105 828 005  trades=3 000 881  other=899

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 19 |
| LONG / SHORT | 16 / 3 |
| Triggered | 12 |
| Reached target | 1 |
| Failed by timeout | 11 |
| Invalidated before trigger | 3 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 4 |
| Hit rate among triggered | 8.33% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 14.58% | 0.00% | 1200 |
| 8h | 22.60% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-LONG-1779567762000-13 | LONG | 2026-05-23T20:31:50.000Z | 76676.45 | 78209.98 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779547725000-10 | LONG | 2026-05-23T14:56:14.000Z | 76370.35 | 77897.76 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779531708000-8 | LONG | 2026-05-23T13:01:02.000Z | 76000.35 | 77520.36 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779525537000-7 | LONG | 2026-05-23T08:48:40.000Z | 75869.60 | 77386.99 | RESOLVED_REACHED | 24h |
| BTCUSDT-LONG-1779549307000-11 | LONG | 2026-05-23T18:12:56.000Z | 76427.70 | 77956.25 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 1 |
| Unique reached moves | 1 |
| Duplicate move credits | 0 |
| Raw triggered hit rate | 8.33% |
| **Unique-move adjusted hit rate** | **8.33%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 1 | `BTCUSDT-LONG-1779525537000-7` | BTCUSDT-LONG-1779525537000-7 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **28835**
- Suppressions by reason:
  - `active_open`: 25484
  - `active_triggered`: 3351

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 75418 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
