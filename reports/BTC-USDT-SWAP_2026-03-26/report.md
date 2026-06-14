# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-26
- **Replay duration:** 3828.3s
- **Rows processed:** L2=114 527 432  trades=4 298 145  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 49 |
| LONG / SHORT | 23 / 26 |
| Triggered | 28 |
| Reached target | 11 |
| Failed by timeout | 17 |
| Invalidated before trigger | 16 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 5 |
| Hit rate among triggered | 39.29% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 1.92% | 1200 |
| 8h | 0.00% | 51.88% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1774548203000-37 | SHORT | 2026-03-26T18:21:20.000Z | 68246.15 | 66881.23 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774495702000-11 | SHORT | 2026-03-26T05:06:42.000Z | 70443.95 | 69035.07 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1774527206000-27 | SHORT | 2026-03-26T12:35:20.000Z | 69257.55 | 67872.40 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1774483234000-1 | LONG | 2026-03-26T00:49:02.000Z | 71409.05 | 72837.23 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774487843000-6 | SHORT | 2026-03-26T02:12:18.000Z | 71071.25 | 69649.82 | RESOLVED_REACHED | 8h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 11 |
| Unique reached moves | 1 |
| Duplicate move credits | 10 |
| Raw triggered hit rate | 39.29% |
| **Unique-move adjusted hit rate** | **3.57%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 11 | `BTC-USDT-SWAP-SHORT-1774485627000-4` | BTC-USDT-SWAP-SHORT-1774485627000-4, BTC-USDT-SWAP-SHORT-1774484401000-3, BTC-USDT-SWAP-SHORT-1774487843000-6, BTC-USDT-SWAP-SHORT-1774493504000-10, BTC-USDT-SWAP-SHORT-1774492655000-8, BTC-USDT-SWAP-SHORT-1774495702000-11, BTC-USDT-SWAP-SHORT-1774502716000-13, BTC-USDT-SWAP-SHORT-1774503105000-14, BTC-USDT-SWAP-SHORT-1774504288000-15, BTC-USDT-SWAP-SHORT-1774513471000-17, BTC-USDT-SWAP-SHORT-1774505134000-16 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **14511**
- Suppressions by reason:
  - `active_open`: 12111
  - `active_triggered`: 2400

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
