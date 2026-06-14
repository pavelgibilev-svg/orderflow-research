# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-08
- **Replay duration:** 3706.6s
- **Rows processed:** L2=106 062 362  trades=3 745 266  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 34 |
| LONG / SHORT | 13 / 21 |
| Triggered | 21 |
| Reached target | 8 |
| Failed by timeout | 13 |
| Invalidated before trigger | 8 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 5 |
| Hit rate among triggered | 38.10% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 5.08% | 1200 |
| 8h | 1.67% | 12.29% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1772937050000-7 | SHORT | 2026-03-08T02:49:49.000Z | 67032.45 | 65691.80 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1772937086000-8 | SHORT | 2026-03-08T02:50:58.000Z | 66821.65 | 65485.22 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1772938557000-9 | LONG | 2026-03-08T10:26:17.000Z | 68125.35 | 69487.86 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1772956387000-16 | LONG | 2026-03-08T08:40:38.000Z | 67361.45 | 68708.68 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1772930593000-4 | SHORT | 2026-03-08T00:48:18.000Z | 67168.45 | 65825.08 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 8 |
| Unique reached moves | 1 |
| Duplicate move credits | 7 |
| Raw triggered hit rate | 38.10% |
| **Unique-move adjusted hit rate** | **4.76%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 8 | `BTC-USDT-SWAP-SHORT-1772930593000-4` | BTC-USDT-SWAP-SHORT-1772930593000-4, BTC-USDT-SWAP-SHORT-1772928898000-2, BTC-USDT-SWAP-SHORT-1772932298000-6, BTC-USDT-SWAP-SHORT-1772937050000-7, BTC-USDT-SWAP-SHORT-1772955851000-15, BTC-USDT-SWAP-SHORT-1772966351000-24, BTC-USDT-SWAP-SHORT-1772965735000-23, BTC-USDT-SWAP-SHORT-1772960413000-19 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **13680**
- Suppressions by reason:
  - `active_open`: 6337
  - `active_triggered`: 7343

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
