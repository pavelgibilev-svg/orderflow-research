# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-02
- **Replay duration:** 7615.1s
- **Rows processed:** L2=173 447 649  trades=7 068 119  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 37 |
| LONG / SHORT | 16 / 21 |
| Triggered | 21 |
| Reached target | 7 |
| Failed by timeout | 14 |
| Invalidated before trigger | 14 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 33.33% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 22.25% | 2.67% | 1200 |
| 8h | 53.33% | 6.67% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1772409634000-1 | LONG | 2026-03-02T00:44:10.000Z | 66284.95 | 67610.65 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1772418726000-11 | SHORT | 2026-03-02T03:04:01.000Z | 66099.95 | 64777.95 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1772468544000-32 | LONG | 2026-03-02T16:44:29.000Z | 69775.85 | 71171.37 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1772420096000-14 | LONG | 2026-03-02T03:11:21.000Z | 66409.15 | 67737.33 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1772459159000-23 | LONG | 2026-03-02T14:33:30.000Z | 66050.45 | 67371.46 | RESOLVED_REACHED | 4h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 7 |
| Unique reached moves | 1 |
| Duplicate move credits | 6 |
| Raw triggered hit rate | 33.33% |
| **Unique-move adjusted hit rate** | **4.76%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 7 | `BTC-USDT-SWAP-LONG-1772409634000-1` | BTC-USDT-SWAP-LONG-1772409634000-1, BTC-USDT-SWAP-LONG-1772410803000-4, BTC-USDT-SWAP-LONG-1772419889000-13, BTC-USDT-SWAP-LONG-1772420096000-14, BTC-USDT-SWAP-LONG-1772420976000-15, BTC-USDT-SWAP-LONG-1772461492000-27, BTC-USDT-SWAP-LONG-1772459159000-23 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10031**
- Suppressions by reason:
  - `active_open`: 3397
  - `cooldown`: 37
  - `active_triggered`: 6597

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
