# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-16
- **Replay duration:** 1334.0s
- **Rows processed:** L2=52 753 479  trades=1 911 637  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 23 |
| LONG / SHORT | 13 / 10 |
| Triggered | 13 |
| Reached target | 0 |
| Failed by timeout | 13 |
| Invalidated before trigger | 5 |
| Expired (formation aged out) | 2 |
| No trigger by end of day | 3 |
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
| BTC-USDT-SWAP-SHORT-1778913373000-9 | SHORT | 2026-05-16T06:41:05.000Z | 78750.05 | 77175.05 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778890285000-2 | SHORT | 2026-05-16T04:10:22.000Z | 79020.05 | 77439.65 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778895819000-6 | SHORT | 2026-05-16T04:33:09.000Z | 78922.25 | 77343.80 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778926759000-16 | SHORT | 2026-05-16T10:28:16.000Z | 77737.45 | 76182.70 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778923475000-14 | SHORT | 2026-05-16T10:10:53.000Z | 77856.45 | 76299.32 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **11758**
- Suppressions by reason:
  - `active_open`: 9238
  - `active_triggered`: 2520

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
