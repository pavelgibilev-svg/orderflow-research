# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-30
- **Replay duration:** 4017.8s
- **Rows processed:** L2=118 811 686  trades=4 605 023  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 38 |
| LONG / SHORT | 22 / 16 |
| Triggered | 23 |
| Reached target | 5 |
| Failed by timeout | 18 |
| Invalidated before trigger | 12 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 21.74% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 4.42% | 2.50% | 1200 |
| 8h | 9.79% | 21.15% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1774874303000-25 | SHORT | 2026-03-30T13:30:15.000Z | 67755.15 | 66400.05 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1774834280000-7 | LONG | 2026-03-30T02:45:21.000Z | 66971.95 | 68311.39 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1774829318000-3 | LONG | 2026-03-30T00:19:15.000Z | 66427.85 | 67756.41 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1774829392000-4 | LONG | 2026-03-30T00:19:15.000Z | 66427.85 | 67756.41 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1774897033000-31 | SHORT | 2026-03-30T19:06:34.000Z | 66480.05 | 65150.45 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 5 |
| Unique reached moves | 2 |
| Duplicate move credits | 3 |
| Raw triggered hit rate | 21.74% |
| **Unique-move adjusted hit rate** | **8.70%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 3 | `BTC-USDT-SWAP-LONG-1774829318000-3` | BTC-USDT-SWAP-LONG-1774829268000-2, BTC-USDT-SWAP-LONG-1774829318000-3, BTC-USDT-SWAP-LONG-1774829392000-4 |
| 2 | SHORT | 2 | `BTC-USDT-SWAP-SHORT-1774874303000-25` | BTC-USDT-SWAP-SHORT-1774874303000-25, BTC-USDT-SWAP-SHORT-1774858134000-21 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **14990**
- Suppressions by reason:
  - `active_open`: 7285
  - `cooldown`: 4
  - `active_triggered`: 7701

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
