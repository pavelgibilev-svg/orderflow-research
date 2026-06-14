# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-17
- **Replay duration:** 500.6s
- **Rows processed:** L2=45 252 024  trades=1 168 596  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 20 |
| LONG / SHORT | 9 / 11 |
| Triggered | 12 |
| Reached target | 0 |
| Failed by timeout | 12 |
| Invalidated before trigger | 5 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 1.42% | 565 |
| 8h | 0.00% | 0.00% | 325 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1779060364000-18 | SHORT | 2026-05-17T23:40:25.000Z | 77627.05 | 76074.51 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779035421000-12 | SHORT | 2026-05-17T17:01:32.000Z | 77894.50 | 76336.61 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779015183000-2 | SHORT | 2026-05-17T11:01:21.000Z | 78340.15 | 76773.35 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779016874000-4 | LONG | 2026-05-17T12:36:20.000Z | 78501.15 | 80071.17 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779015977000-3 | LONG | 2026-05-17T12:36:25.000Z | 78512.25 | 80082.49 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **10844**
- Suppressions by reason:
  - `active_open`: 8835
  - `active_triggered`: 2009

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 11738 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
