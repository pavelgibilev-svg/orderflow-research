# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-19
- **Replay duration:** 1146.4s
- **Rows processed:** L2=98 281 961  trades=2 658 588  other=716

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 18 |
| LONG / SHORT | 7 / 11 |
| Triggered | 10 |
| Reached target | 0 |
| Failed by timeout | 10 |
| Invalidated before trigger | 7 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1201 |
| 8h | 0.00% | 0.00% | 961 |
| 24h | 0.00% | 0.00% | 1 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1779150050000-3 | SHORT | 2026-05-19T01:26:06.000Z | 76604.65 | 75072.56 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779149821000-2 | SHORT | 2026-05-19T01:19:12.000Z | 76720.25 | 75185.85 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779148846000-1 | SHORT | 2026-05-19T01:25:19.000Z | 76670.45 | 75137.04 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779154395000-5 | SHORT | 2026-05-19T02:04:42.000Z | 76457.65 | 74928.50 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779174857000-9 | SHORT | 2026-05-19T08:26:19.000Z | 76972.75 | 75433.29 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **13086**
- Suppressions by reason:
  - `active_open`: 6277
  - `active_triggered`: 6809

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 7544 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
