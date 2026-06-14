# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2025-10-01
- **Replay duration:** 3023.8s
- **Rows processed:** L2=92 168 407  trades=2 097 545  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 41 |
| LONG / SHORT | 21 / 20 |
| Triggered | 24 |
| Reached target | 4 |
| Failed by timeout | 20 |
| Invalidated before trigger | 15 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 16.67% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 3.75% | 0.00% | 1200 |
| 8h | 36.67% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1759281845000-5 | LONG | 2025-10-01T03:25:41.000Z | 114484.95 | 116774.65 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1759293679000-8 | LONG | 2025-10-01T05:12:16.000Z | 114666.75 | 116960.09 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1759341955000-36 | LONG | 2025-10-01T22:08:09.000Z | 118042.20 | 120403.04 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1759333326000-26 | LONG | 2025-10-01T16:07:53.000Z | 117534.65 | 119885.34 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1759320125000-20 | LONG | 2025-10-01T14:02:30.000Z | 116915.05 | 119253.35 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 4 |
| Unique reached moves | 1 |
| Duplicate move credits | 3 |
| Raw triggered hit rate | 16.67% |
| **Unique-move adjusted hit rate** | **4.17%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 4 | `BTC-USDT-SWAP-LONG-1759279863000-4` | BTC-USDT-SWAP-LONG-1759279863000-4, BTC-USDT-SWAP-LONG-1759281845000-5, BTC-USDT-SWAP-LONG-1759283655000-7, BTC-USDT-SWAP-LONG-1759293679000-8 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **15287**
- Suppressions by reason:
  - `active_open`: 11277
  - `active_triggered`: 4010

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
