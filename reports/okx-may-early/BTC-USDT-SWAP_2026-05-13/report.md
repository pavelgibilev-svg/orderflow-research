# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-13
- **Replay duration:** 2194.4s
- **Rows processed:** L2=74 173 712  trades=2 430 682  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 29 |
| LONG / SHORT | 16 / 13 |
| Triggered | 17 |
| Reached target | 3 |
| Failed by timeout | 14 |
| Invalidated before trigger | 9 |
| Expired (formation aged out) | 3 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 17.65% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 3.42% | 1200 |
| 8h | 0.00% | 6.35% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1778680295000-21 | SHORT | 2026-05-13T15:58:21.000Z | 78791.95 | 77216.11 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778634622000-6 | SHORT | 2026-05-13T11:05:05.000Z | 80685.05 | 79071.35 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1778644566000-11 | LONG | 2026-05-13T09:04:55.000Z | 81278.65 | 82904.22 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778670952000-15 | SHORT | 2026-05-13T12:22:44.000Z | 80247.05 | 78642.11 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778670977000-16 | SHORT | 2026-05-13T12:22:47.000Z | 80215.05 | 78610.75 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 3 |
| Unique reached moves | 1 |
| Duplicate move credits | 2 |
| Raw triggered hit rate | 17.65% |
| **Unique-move adjusted hit rate** | **5.88%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 3 | `BTC-USDT-SWAP-SHORT-1778644071000-10` | BTC-USDT-SWAP-SHORT-1778644071000-10, BTC-USDT-SWAP-SHORT-1778636116000-8, BTC-USDT-SWAP-SHORT-1778634622000-6 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **8359**
- Suppressions by reason:
  - `active_open`: 6772
  - `active_triggered`: 1363
  - `cooldown`: 224

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
