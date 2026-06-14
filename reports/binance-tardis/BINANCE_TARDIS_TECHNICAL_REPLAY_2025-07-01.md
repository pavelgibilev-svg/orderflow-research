# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-07-01
- **Replay duration:** 1497.3s
- **Rows processed:** L2=89 046 296  trades=2 043 731  other=962

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 24 |
| LONG / SHORT | 10 / 14 |
| Triggered | 14 |
| Reached target | 0 |
| Failed by timeout | 14 |
| Invalidated before trigger | 5 |
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
| BTCUSDT-SHORT-1751363678000-10 | SHORT | 2025-07-01T10:38:49.000Z | 106359.05 | 104231.87 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1751346262000-6 | SHORT | 2025-07-01T07:19:43.000Z | 106656.45 | 104523.32 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1751328366000-2 | SHORT | 2025-07-01T04:46:45.000Z | 106947.05 | 104808.11 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1751353807000-8 | SHORT | 2025-07-01T09:39:58.000Z | 106495.05 | 104365.15 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1751399641000-22 | SHORT | 2025-07-01T19:58:46.000Z | 105371.45 | 103264.02 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **9217**
- Suppressions by reason:
  - `active_open`: 8064
  - `cooldown`: 1
  - `active_triggered`: 1152

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
