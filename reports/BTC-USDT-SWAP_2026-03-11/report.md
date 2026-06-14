# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-11
- **Replay duration:** 4688.3s
- **Rows processed:** L2=130 208 387  trades=4 992 047  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 30 |
| LONG / SHORT | 13 / 17 |
| Triggered | 21 |
| Reached target | 5 |
| Failed by timeout | 16 |
| Invalidated before trigger | 9 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 23.81% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 18.17% | 0.00% | 1200 |
| 8h | 38.75% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1773205204000-11 | SHORT | 2026-03-11T05:42:34.000Z | 69390.75 | 68002.93 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773200852000-10 | LONG | 2026-03-11T04:15:38.000Z | 69650.65 | 71043.66 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1773231661000-21 | LONG | 2026-03-11T13:14:04.000Z | 69803.15 | 71199.21 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1773231710000-22 | LONG | 2026-03-11T13:14:04.000Z | 69803.15 | 71199.21 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1773197989000-7 | SHORT | 2026-03-11T03:08:02.000Z | 69669.65 | 68276.26 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 5 |
| Unique reached moves | 1 |
| Duplicate move credits | 4 |
| Raw triggered hit rate | 23.81% |
| **Unique-move adjusted hit rate** | **4.76%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 5 | `BTC-USDT-SWAP-LONG-1773200852000-10` | BTC-USDT-SWAP-LONG-1773200852000-10, BTC-USDT-SWAP-LONG-1773223325000-15, BTC-USDT-SWAP-LONG-1773231035000-20, BTC-USDT-SWAP-LONG-1773231661000-21, BTC-USDT-SWAP-LONG-1773231710000-22 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **11467**
- Suppressions by reason:
  - `active_open`: 6408
  - `active_triggered`: 5059

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
