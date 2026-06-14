# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-16
- **Replay duration:** 4764.2s
- **Rows processed:** L2=126 106 914  trades=5 349 595  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 45 |
| LONG / SHORT | 25 / 20 |
| Triggered | 24 |
| Reached target | 3 |
| Failed by timeout | 21 |
| Invalidated before trigger | 15 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 5 |
| Hit rate among triggered | 12.50% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 16.83% | 0.08% | 1200 |
| 8h | 26.25% | 0.10% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1773656977000-27 | LONG | 2026-03-16T10:50:18.000Z | 73478.65 | 74948.22 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773650790000-23 | LONG | 2026-03-16T13:35:27.000Z | 74376.95 | 75864.49 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773685469000-39 | LONG | 2026-03-16T19:10:12.000Z | 74377.25 | 75864.79 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773626785000-7 | SHORT | 2026-03-16T02:27:51.000Z | 72350.95 | 70903.93 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773695990000-40 | LONG | 2026-03-16T21:36:14.000Z | 74540.45 | 76031.26 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 3 |
| Unique reached moves | 1 |
| Duplicate move credits | 2 |
| Raw triggered hit rate | 12.50% |
| **Unique-move adjusted hit rate** | **4.17%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 3 | `BTC-USDT-SWAP-LONG-1773620182000-2` | BTC-USDT-SWAP-LONG-1773620182000-2, BTC-USDT-SWAP-LONG-1773620204000-3, BTC-USDT-SWAP-LONG-1773623888000-6 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **11140**
- Suppressions by reason:
  - `active_open`: 9130
  - `active_triggered`: 1822
  - `cooldown`: 188

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
