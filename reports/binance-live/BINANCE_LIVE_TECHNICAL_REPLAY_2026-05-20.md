# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-20
- **Replay duration:** 1213.5s
- **Rows processed:** L2=114 333 976  trades=2 615 874  other=667

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 9 |
| LONG / SHORT | 0 / 9 |
| Triggered | 6 |
| Reached target | 0 |
| Failed by timeout | 6 |
| Invalidated before trigger | 2 |
| Expired (formation aged out) | 0 |
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
| BTCUSDT-SHORT-1779281813000-9 | SHORT | 2026-05-20T13:29:14.000Z | 76848.95 | 75311.97 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779235367000-1 | SHORT | 2026-05-20T00:08:27.000Z | 76562.65 | 75031.40 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779266372000-8 | SHORT | 2026-05-20T13:36:06.000Z | 76736.65 | 75201.92 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779261829000-7 | SHORT | 2026-05-20T13:28:12.000Z | 76848.15 | 75311.19 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779255181000-6 | SHORT | 2026-05-20T13:36:01.000Z | 76748.65 | 75213.68 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **30893**
- Suppressions by reason:
  - `active_open`: 19149
  - `active_triggered`: 11744

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 86400 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
