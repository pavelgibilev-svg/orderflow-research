# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-04
- **Replay duration:** 7981.6s
- **Rows processed:** L2=179 632 147  trades=7 498 948  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 54 |
| LONG / SHORT | 30 / 24 |
| Triggered | 32 |
| Reached target | 15 |
| Failed by timeout | 17 |
| Invalidated before trigger | 18 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 46.88% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 45.33% | 0.42% | 1200 |
| 8h | 96.15% | 0.21% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1772584188000-4 | LONG | 2026-03-04T01:32:09.000Z | 68406.45 | 69774.58 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1772616258000-27 | LONG | 2026-03-04T09:34:30.000Z | 71377.85 | 72805.41 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1772589606000-9 | SHORT | 2026-03-04T02:16:50.000Z | 68114.45 | 66752.16 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1772616423000-28 | LONG | 2026-03-04T09:34:33.000Z | 71404.45 | 72832.54 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1772637425000-40 | LONG | 2026-03-04T15:26:26.000Z | 72730.05 | 74184.65 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 15 |
| Unique reached moves | 1 |
| Duplicate move credits | 14 |
| Raw triggered hit rate | 46.88% |
| **Unique-move adjusted hit rate** | **3.13%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 15 | `BTC-USDT-SWAP-LONG-1772584188000-4` | BTC-USDT-SWAP-LONG-1772584188000-4, BTC-USDT-SWAP-LONG-1772584858000-5, BTC-USDT-SWAP-LONG-1772596380000-13, BTC-USDT-SWAP-LONG-1772602176000-17, BTC-USDT-SWAP-LONG-1772595707000-11, BTC-USDT-SWAP-LONG-1772606412000-18, BTC-USDT-SWAP-LONG-1772608667000-20, BTC-USDT-SWAP-LONG-1772606902000-19, BTC-USDT-SWAP-LONG-1772611621000-23, BTC-USDT-SWAP-LONG-1772611599000-22, BTC-USDT-SWAP-LONG-1772613179000-25, BTC-USDT-SWAP-LONG-1772616258000-27, BTC-USDT-SWAP-LONG-1772616423000-28, BTC-USDT-SWAP-LONG-1772631907000-37, BTC-USDT-SWAP-LONG-1772632793000-38 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **8931**
- Suppressions by reason:
  - `active_open`: 5614
  - `active_triggered`: 3302
  - `cooldown`: 15

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
