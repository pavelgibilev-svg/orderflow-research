# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-27
- **Replay duration:** 1295.6s
- **Rows processed:** L2=107 449 742  trades=3 435 361  other=943

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 15 |
| LONG / SHORT | 15 / 0 |
| Triggered | 6 |
| Reached target | 0 |
| Failed by timeout | 6 |
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
| BTCUSDT-LONG-1779855465000-5 | LONG | 2026-05-27T07:38:27.000Z | 76772.00 | 78307.44 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779856226000-6 | LONG | 2026-05-27T12:19:15.000Z | 76723.30 | 78257.77 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779848353000-4 | LONG | 2026-05-27T07:35:54.000Z | 76784.25 | 78319.93 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779847386000-3 | LONG | 2026-05-27T03:05:50.000Z | 76787.75 | 78323.51 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779892057000-11 | LONG | 2026-05-27T15:21:50.000Z | 76451.10 | 77980.12 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 0 |
| Unique reached moves | 0 |
| Duplicate move credits | 0 |
| Raw triggered hit rate | 0.00% |
| **Unique-move adjusted hit rate** | **0.00%** |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **35246**
- Suppressions by reason:
  - `active_open`: 25711
  - `active_triggered`: 9535

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 86400 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
