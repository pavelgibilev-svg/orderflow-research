# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-24
- **Replay duration:** 4699.5s
- **Rows processed:** L2=133 515 386  trades=4 887 440  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 36 |
| LONG / SHORT | 16 / 20 |
| Triggered | 20 |
| Reached target | 4 |
| Failed by timeout | 16 |
| Invalidated before trigger | 14 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 20.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 2.58% | 17.00% | 1200 |
| 8h | 0.00% | 38.44% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1774315073000-8 | LONG | 2026-03-24T07:13:07.000Z | 70886.15 | 72303.87 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774311890000-5 | SHORT | 2026-03-24T00:32:28.000Z | 70566.95 | 69155.61 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1774385370000-34 | LONG | 2026-03-24T21:41:33.000Z | 70243.05 | 71647.91 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774362129000-23 | SHORT | 2026-03-24T14:45:45.000Z | 69581.15 | 68189.53 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774336685000-15 | SHORT | 2026-03-24T13:41:17.000Z | 70334.25 | 68927.57 | RESOLVED_REACHED | 8h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 4 |
| Unique reached moves | 1 |
| Duplicate move credits | 3 |
| Raw triggered hit rate | 20.00% |
| **Unique-move adjusted hit rate** | **5.00%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 4 | `BTC-USDT-SWAP-SHORT-1774311890000-5` | BTC-USDT-SWAP-SHORT-1774311890000-5, BTC-USDT-SWAP-SHORT-1774311662000-4, BTC-USDT-SWAP-SHORT-1774339003000-17, BTC-USDT-SWAP-SHORT-1774336685000-15 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **13397**
- Suppressions by reason:
  - `active_open`: 8636
  - `active_triggered`: 4761

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
