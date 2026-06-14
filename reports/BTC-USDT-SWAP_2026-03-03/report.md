# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-03
- **Replay duration:** 7933.4s
- **Rows processed:** L2=181 605 671  trades=6 897 977  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 46 |
| LONG / SHORT | 23 / 23 |
| Triggered | 26 |
| Reached target | 12 |
| Failed by timeout | 14 |
| Invalidated before trigger | 18 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 46.15% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 22.67% | 19.33% | 1200 |
| 8h | 44.69% | 52.92% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1772528433000-23 | SHORT | 2026-03-03T09:26:42.000Z | 66695.95 | 65362.03 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1772504097000-10 | SHORT | 2026-03-03T04:40:29.000Z | 68161.25 | 66798.02 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1772504005000-9 | SHORT | 2026-03-03T04:41:16.000Z | 68163.25 | 66799.99 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1772536899000-31 | LONG | 2026-03-03T11:39:28.000Z | 67032.55 | 68373.20 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1772513128000-13 | LONG | 2026-03-03T05:16:24.000Z | 68509.95 | 69880.15 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 12 |
| Unique reached moves | 2 |
| Duplicate move credits | 10 |
| Raw triggered hit rate | 46.15% |
| **Unique-move adjusted hit rate** | **7.69%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 3 | `BTC-USDT-SWAP-LONG-1772536899000-31` | BTC-USDT-SWAP-LONG-1772536899000-31, BTC-USDT-SWAP-LONG-1772535551000-30, BTC-USDT-SWAP-LONG-1772543243000-34 |
| 2 | SHORT | 9 | `BTC-USDT-SWAP-SHORT-1772496035000-1` | BTC-USDT-SWAP-SHORT-1772496035000-1, BTC-USDT-SWAP-SHORT-1772496525000-2, BTC-USDT-SWAP-SHORT-1772498676000-5, BTC-USDT-SWAP-SHORT-1772504097000-10, BTC-USDT-SWAP-SHORT-1772504005000-9, BTC-USDT-SWAP-SHORT-1772505226000-11, BTC-USDT-SWAP-SHORT-1772517425000-18, BTC-USDT-SWAP-SHORT-1772522407000-20, BTC-USDT-SWAP-SHORT-1772521223000-19 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10192**
- Suppressions by reason:
  - `active_open`: 6433
  - `active_triggered`: 3687
  - `cooldown`: 72

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
