# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-21
- **Replay duration:** 1349.7s
- **Rows processed:** L2=123 811 195  trades=2 851 345  other=689

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 25 |
| LONG / SHORT | 13 / 12 |
| Triggered | 16 |
| Reached target | 0 |
| Failed by timeout | 16 |
| Invalidated before trigger | 7 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 1 |
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
| BTCUSDT-LONG-1779325402000-5 | LONG | 2026-05-21T01:14:48.000Z | 78097.05 | 79658.99 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779342844000-10 | SHORT | 2026-05-21T06:45:58.000Z | 77610.05 | 76057.85 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779331245000-9 | LONG | 2026-05-21T04:03:09.000Z | 78085.55 | 79647.26 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779357069000-14 | SHORT | 2026-05-21T10:25:17.000Z | 77523.95 | 75973.47 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779326244000-6 | SHORT | 2026-05-21T10:26:45.000Z | 77322.35 | 75775.90 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **12452**
- Suppressions by reason:
  - `active_open`: 8601
  - `active_triggered`: 3841
  - `cooldown`: 10

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 3600 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
