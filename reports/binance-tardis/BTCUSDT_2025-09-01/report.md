# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-09-01
- **Replay duration:** 1872.4s
- **Rows processed:** L2=121 142 928  trades=3 269 295  other=1 650

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 22 |
| LONG / SHORT | 7 / 15 |
| Triggered | 17 |
| Reached target | 0 |
| Failed by timeout | 17 |
| Invalidated before trigger | 4 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 7.42% | 0.00% | 1200 |
| 8h | 20.94% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-LONG-1756693849000-8 | LONG | 2025-09-01T07:31:57.000Z | 108599.85 | 110771.85 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1756701053000-11 | LONG | 2025-09-01T07:31:42.000Z | 108559.10 | 110730.28 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1756685756000-3 | LONG | 2025-09-01T00:42:47.000Z | 108126.90 | 110289.44 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1756705921000-13 | LONG | 2025-09-01T06:24:43.000Z | 107979.95 | 110139.55 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1756684852000-1 | LONG | 2025-09-01T00:47:20.000Z | 108355.25 | 110522.35 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **13683**
- Suppressions by reason:
  - `active_open`: 6714
  - `active_triggered`: 6969

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
