# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-29
- **Replay duration:** 1393.1s
- **Rows processed:** L2=104 031 549  trades=3 330 597  other=993

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 15 |
| LONG / SHORT | 15 / 0 |
| Triggered | 10 |
| Reached target | 0 |
| Failed by timeout | 10 |
| Invalidated before trigger | 2 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 2.67% | 0.00% | 1200 |
| 8h | 3.33% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-LONG-1780023188000-5 | LONG | 2026-05-29T04:58:13.000Z | 74053.45 | 75534.52 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1780021639000-4 | LONG | 2026-05-29T05:50:08.000Z | 74126.95 | 75609.49 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1780064716000-10 | LONG | 2026-05-29T14:52:33.000Z | 73839.80 | 75316.60 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1780064353000-9 | LONG | 2026-05-29T14:52:07.000Z | 73807.20 | 75283.34 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1780064772000-11 | LONG | 2026-05-29T15:08:29.000Z | 74090.45 | 75572.26 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **33609**
- Suppressions by reason:
  - `active_open`: 18849
  - `active_triggered`: 14760

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 86400 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
