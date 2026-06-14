# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-26
- **Replay duration:** 1208.1s
- **Rows processed:** L2=108 145 967  trades=3 665 614  other=947

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 23 |
| LONG / SHORT | 15 / 8 |
| Triggered | 15 |
| Reached target | 0 |
| Failed by timeout | 15 |
| Invalidated before trigger | 2 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 5 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 1.75% | 1201 |
| 8h | 0.00% | 7.28% | 961 |
| 24h | 0.00% | 100.00% | 1 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-LONG-1779766077000-8 | LONG | 2026-05-26T06:41:22.000Z | 77301.15 | 78847.17 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779834251000-23 | SHORT | 2026-05-26T22:48:21.000Z | 75674.85 | 74161.35 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779756719000-6 | LONG | 2026-05-26T10:27:23.000Z | 77407.45 | 78955.60 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779756783000-7 | LONG | 2026-05-26T10:29:00.000Z | 77428.45 | 78977.02 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779808598000-12 | SHORT | 2026-05-26T15:52:26.000Z | 76273.45 | 74747.98 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **23330**
- Suppressions by reason:
  - `active_open`: 19546
  - `active_triggered`: 3447
  - `cooldown`: 337

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 51508 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
