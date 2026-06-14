# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-04
- **Replay duration:** 3622.9s
- **Rows processed:** L2=100 550 570  trades=4 331 594  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 22 |
| LONG / SHORT | 5 / 17 |
| Triggered | 18 |
| Reached target | 5 |
| Failed by timeout | 13 |
| Invalidated before trigger | 4 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 27.78% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 16.33% | 7.50% | 1200 |
| 8h | 38.33% | 30.21% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1777872147000-12 | SHORT | 2026-05-04T05:31:22.000Z | 79941.45 | 78342.62 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1777872403000-13 | SHORT | 2026-05-04T06:27:12.000Z | 79483.65 | 77893.98 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1777881059000-15 | SHORT | 2026-05-04T09:07:26.000Z | 79660.05 | 78066.85 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1777864927000-10 | SHORT | 2026-05-04T03:30:18.000Z | 80050.05 | 78449.05 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1777868198000-11 | SHORT | 2026-05-04T04:24:03.000Z | 80220.05 | 78615.65 | RESOLVED_REACHED | 8h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 5 |
| Unique reached moves | 2 |
| Duplicate move credits | 3 |
| Raw triggered hit rate | 27.78% |
| **Unique-move adjusted hit rate** | **11.11%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 1 | `BTC-USDT-SWAP-LONG-1777853128000-1` | BTC-USDT-SWAP-LONG-1777853128000-1 |
| 2 | SHORT | 4 | `BTC-USDT-SWAP-SHORT-1777864927000-10` | BTC-USDT-SWAP-SHORT-1777864927000-10, BTC-USDT-SWAP-SHORT-1777868198000-11, BTC-USDT-SWAP-SHORT-1777872147000-12, BTC-USDT-SWAP-SHORT-1777879456000-14 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **7608**
- Suppressions by reason:
  - `active_open`: 5844
  - `active_triggered`: 1764

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
