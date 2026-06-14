# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-05
- **Replay duration:** 7049.4s
- **Rows processed:** L2=159 648 597  trades=5 736 816  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 29 |
| LONG / SHORT | 18 / 11 |
| Triggered | 13 |
| Reached target | 5 |
| Failed by timeout | 8 |
| Invalidated before trigger | 13 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 38.46% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 4.33% | 19.83% | 1200 |
| 8h | 5.83% | 39.17% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1772675238000-7 | LONG | 2026-03-05T03:06:30.000Z | 72729.05 | 74183.63 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1772679264000-9 | SHORT | 2026-03-05T05:58:18.000Z | 72228.65 | 70784.08 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1772690822000-12 | SHORT | 2026-03-05T07:52:36.000Z | 71917.45 | 70479.10 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1772670314000-2 | SHORT | 2026-03-05T01:43:17.000Z | 72567.75 | 71116.40 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1772691247000-13 | LONG | 2026-03-05T10:26:48.000Z | 73291.70 | 74757.53 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 5 |
| Unique reached moves | 1 |
| Duplicate move credits | 4 |
| Raw triggered hit rate | 38.46% |
| **Unique-move adjusted hit rate** | **7.69%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 5 | `BTC-USDT-SWAP-SHORT-1772670314000-2` | BTC-USDT-SWAP-SHORT-1772670314000-2, BTC-USDT-SWAP-SHORT-1772669164000-1, BTC-USDT-SWAP-SHORT-1772679264000-9, BTC-USDT-SWAP-SHORT-1772689407000-11, BTC-USDT-SWAP-SHORT-1772673503000-4 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10367**
- Suppressions by reason:
  - `active_open`: 7576
  - `active_triggered`: 2791

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 1 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
