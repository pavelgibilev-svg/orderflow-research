# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-02-01
- **Replay duration:** 1385.3s
- **Rows processed:** L2=76 540 994  trades=2 078 447  other=1 525

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 33 |
| LONG / SHORT | 19 / 14 |
| Triggered | 16 |
| Reached target | 1 |
| Failed by timeout | 15 |
| Invalidated before trigger | 11 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 5 |
| Hit rate among triggered | 6.25% |

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
| BTCUSDT-LONG-1738368376000-2 | LONG | 2025-02-01T01:18:06.000Z | 102603.95 | 104656.03 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1738451924000-33 | LONG | 2025-02-01T23:39:17.000Z | 100699.15 | 102713.13 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1738412483000-20 | LONG | 2025-02-01T17:20:59.000Z | 102228.15 | 104272.71 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1738400947000-16 | SHORT | 2025-02-01T09:34:31.000Z | 101675.40 | 99641.89 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1738419618000-21 | LONG | 2025-02-01T15:49:41.000Z | 102134.20 | 104176.88 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 1 |
| Unique reached moves | 1 |
| Duplicate move credits | 0 |
| Raw triggered hit rate | 6.25% |
| **Unique-move adjusted hit rate** | **6.25%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 1 | `BTCUSDT-SHORT-1738373960000-7` | BTCUSDT-SHORT-1738373960000-7 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **12853**
- Suppressions by reason:
  - `active_open`: 9085
  - `active_triggered`: 3768

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
