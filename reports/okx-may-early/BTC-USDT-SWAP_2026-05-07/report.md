# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-07
- **Replay duration:** 2542.7s
- **Rows processed:** L2=85 422 242  trades=2 775 616  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 27 |
| LONG / SHORT | 13 / 14 |
| Triggered | 16 |
| Reached target | 1 |
| Failed by timeout | 15 |
| Invalidated before trigger | 10 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 6.25% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 0.00% | 4.48% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1778126481000-10 | LONG | 2026-05-07T06:33:49.000Z | 81175.45 | 82798.96 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778138721000-13 | SHORT | 2026-05-07T08:21:20.000Z | 81304.35 | 79678.26 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1778112289000-2 | SHORT | 2026-05-07T00:34:14.000Z | 81101.75 | 79479.71 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778150798000-16 | SHORT | 2026-05-07T13:36:23.000Z | 80697.05 | 79083.11 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1778113698000-5 | LONG | 2026-05-07T06:43:57.000Z | 81337.95 | 82964.71 | RESOLVED_FAILED | - |

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
| 1 | SHORT | 1 | `BTC-USDT-SWAP-SHORT-1778138721000-13` | BTC-USDT-SWAP-SHORT-1778138721000-13 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **9400**
- Suppressions by reason:
  - `active_open`: 5623
  - `active_triggered`: 3777

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
