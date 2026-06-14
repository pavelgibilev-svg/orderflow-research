# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-01-01
- **Replay duration:** 1304.0s
- **Rows processed:** L2=74 046 664  trades=1 804 360  other=625

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 28 |
| LONG / SHORT | 16 / 12 |
| Triggered | 16 |
| Reached target | 0 |
| Failed by timeout | 16 |
| Invalidated before trigger | 7 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 4 |
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
| BTCUSDT-LONG-1735689631000-1 | LONG | 2025-01-01T00:16:58.000Z | 93763.15 | 95638.41 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1735689868000-2 | LONG | 2025-01-01T00:16:58.000Z | 93763.15 | 95638.41 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1735724562000-15 | LONG | 2025-01-01T09:52:03.000Z | 93373.85 | 95241.33 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1735765597000-26 | LONG | 2025-01-01T21:21:13.000Z | 94947.85 | 96846.81 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1735690578000-3 | LONG | 2025-01-01T00:51:29.000Z | 94049.95 | 95930.95 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **9697**
- Suppressions by reason:
  - `active_open`: 6866
  - `active_triggered`: 2830
  - `cooldown`: 1

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
