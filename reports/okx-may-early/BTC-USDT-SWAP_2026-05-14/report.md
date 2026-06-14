# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-14
- **Replay duration:** 2910.1s
- **Rows processed:** L2=87 262 834  trades=2 795 483  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 29 |
| LONG / SHORT | 19 / 10 |
| Triggered | 15 |
| Reached target | 3 |
| Failed by timeout | 12 |
| Invalidated before trigger | 7 |
| Expired (formation aged out) | 2 |
| No trigger by end of day | 5 |
| Hit rate among triggered | 20.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 4.42% | 0.00% | 1200 |
| 8h | 0.00% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1778734797000-11 | LONG | 2026-05-14T05:25:21.000Z | 79549.25 | 81140.24 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1778744808000-15 | SHORT | 2026-05-14T10:07:44.000Z | 79545.55 | 77954.64 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778719099000-3 | SHORT | 2026-05-14T01:37:12.000Z | 79383.95 | 77796.27 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1778729820000-9 | LONG | 2026-05-14T05:32:15.000Z | 79589.25 | 81181.04 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1778769980000-23 | LONG | 2026-05-14T15:53:28.000Z | 81226.15 | 82850.67 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 3 |
| Unique reached moves | 1 |
| Duplicate move credits | 2 |
| Raw triggered hit rate | 20.00% |
| **Unique-move adjusted hit rate** | **6.67%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 3 | `BTC-USDT-SWAP-LONG-1778734797000-11` | BTC-USDT-SWAP-LONG-1778734797000-11, BTC-USDT-SWAP-LONG-1778729820000-9, BTC-USDT-SWAP-LONG-1778730834000-10 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **8494**
- Suppressions by reason:
  - `active_open`: 7015
  - `active_triggered`: 1479

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
