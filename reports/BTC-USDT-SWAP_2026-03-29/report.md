# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-29
- **Replay duration:** 2094.7s
- **Rows processed:** L2=74 086 832  trades=2 605 372  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 24 |
| LONG / SHORT | 11 / 13 |
| Triggered | 16 |
| Reached target | 6 |
| Failed by timeout | 10 |
| Invalidated before trigger | 8 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 37.50% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 6.17% | 1200 |
| 8h | 0.00% | 7.71% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1774760584000-13 | LONG | 2026-03-29T05:53:13.000Z | 66794.75 | 68130.65 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1774743999000-4 | LONG | 2026-03-29T01:12:10.000Z | 66524.65 | 67855.14 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774768706000-17 | SHORT | 2026-03-29T10:07:42.000Z | 66480.45 | 65150.84 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1774779062000-19 | SHORT | 2026-03-29T10:21:37.000Z | 66410.05 | 65081.85 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1774752923000-8 | SHORT | 2026-03-29T13:08:35.000Z | 66544.65 | 65213.76 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 6 |
| Unique reached moves | 1 |
| Duplicate move credits | 5 |
| Raw triggered hit rate | 37.50% |
| **Unique-move adjusted hit rate** | **6.25%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 6 | `BTC-USDT-SWAP-SHORT-1774757504000-12` | BTC-USDT-SWAP-SHORT-1774757504000-12, BTC-USDT-SWAP-SHORT-1774760707000-14, BTC-USDT-SWAP-SHORT-1774763331000-16, BTC-USDT-SWAP-SHORT-1774768706000-17, BTC-USDT-SWAP-SHORT-1774779062000-19, BTC-USDT-SWAP-SHORT-1774752923000-8 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **15533**
- Suppressions by reason:
  - `active_open`: 6695
  - `active_triggered`: 8838

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 1 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
