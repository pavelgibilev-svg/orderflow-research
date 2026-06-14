# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2024-02-01
- **Replay duration:** 6027.8s
- **Rows processed:** L2=134 701 097  trades=851 462  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 36 |
| LONG / SHORT | 19 / 17 |
| Triggered | 25 |
| Reached target | 6 |
| Failed by timeout | 19 |
| Invalidated before trigger | 9 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 24.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 7.92% | 0.00% | 1200 |
| 8h | 32.81% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1706811091000-31 | LONG | 2024-02-01T19:48:17.000Z | 43210.50 | 44074.71 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1706802501000-23 | SHORT | 2024-02-01T15:55:21.000Z | 42612.05 | 41759.81 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1706813444000-32 | LONG | 2024-02-01T19:05:15.000Z | 42929.35 | 43787.94 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1706746134000-2 | SHORT | 2024-02-01T00:22:38.000Z | 42477.05 | 41627.51 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1706803483000-25 | LONG | 2024-02-01T17:07:54.000Z | 42911.25 | 43769.47 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 6 |
| Unique reached moves | 1 |
| Duplicate move credits | 5 |
| Raw triggered hit rate | 24.00% |
| **Unique-move adjusted hit rate** | **4.00%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 6 | `BTC-USDT-SWAP-LONG-1706752955000-12` | BTC-USDT-SWAP-LONG-1706752955000-12, BTC-USDT-SWAP-LONG-1706752748000-10, BTC-USDT-SWAP-LONG-1706752880000-11, BTC-USDT-SWAP-LONG-1706769712000-16, BTC-USDT-SWAP-LONG-1706773107000-17, BTC-USDT-SWAP-LONG-1706753414000-13 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **11763**
- Suppressions by reason:
  - `active_open`: 8091
  - `active_triggered`: 3671
  - `cooldown`: 1

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
