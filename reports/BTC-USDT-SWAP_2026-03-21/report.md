# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-21
- **Replay duration:** 1759.3s
- **Rows processed:** L2=57 862 599  trades=1 749 022  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 21 |
| LONG / SHORT | 9 / 12 |
| Triggered | 15 |
| Reached target | 10 |
| Failed by timeout | 5 |
| Invalidated before trigger | 6 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 66.67% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.58% | 1200 |
| 8h | 0.00% | 0.83% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1774135368000-21 | SHORT | 2026-03-21T23:45:24.000Z | 70065.05 | 68663.75 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-LONG-1774051508000-1 | LONG | 2026-03-21T00:16:21.000Z | 70623.35 | 72035.82 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774078231000-9 | SHORT | 2026-03-21T08:21:16.000Z | 70551.85 | 69140.81 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1774110303000-13 | SHORT | 2026-03-21T16:28:51.000Z | 70325.05 | 68918.55 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1774053604000-4 | SHORT | 2026-03-21T01:44:59.000Z | 70493.45 | 69083.58 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 10 |
| Unique reached moves | 1 |
| Duplicate move credits | 9 |
| Raw triggered hit rate | 66.67% |
| **Unique-move adjusted hit rate** | **6.67%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 10 | `BTC-USDT-SWAP-SHORT-1774053604000-4` | BTC-USDT-SWAP-SHORT-1774053604000-4, BTC-USDT-SWAP-SHORT-1774071458000-8, BTC-USDT-SWAP-SHORT-1774078231000-9, BTC-USDT-SWAP-SHORT-1774052542000-2, BTC-USDT-SWAP-SHORT-1774110303000-13, BTC-USDT-SWAP-SHORT-1774110996000-14, BTC-USDT-SWAP-SHORT-1774111884000-15, BTC-USDT-SWAP-SHORT-1774112836000-17, BTC-USDT-SWAP-SHORT-1774112945000-18, BTC-USDT-SWAP-SHORT-1774135368000-21 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **19368**
- Suppressions by reason:
  - `active_open`: 8378
  - `active_triggered`: 10990

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 1 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
