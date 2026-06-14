# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-13
- **Replay duration:** 5094.0s
- **Rows processed:** L2=136 579 375  trades=5 970 637  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 32 |
| LONG / SHORT | 12 / 20 |
| Triggered | 18 |
| Reached target | 7 |
| Failed by timeout | 11 |
| Invalidated before trigger | 10 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 4 |
| Hit rate among triggered | 38.89% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 14.67% | 14.58% | 1200 |
| 8h | 50.83% | 34.38% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1773406851000-17 | LONG | 2026-03-13T13:17:52.000Z | 73030.85 | 74491.47 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773418383000-26 | SHORT | 2026-03-13T16:19:38.000Z | 71360.55 | 69933.34 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1773396407000-11 | LONG | 2026-03-13T10:15:17.000Z | 72313.65 | 73759.92 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1773426956000-31 | SHORT | 2026-03-13T22:02:10.000Z | 70791.15 | 69375.33 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1773364676000-6 | SHORT | 2026-03-13T01:38:17.000Z | 71243.25 | 69818.38 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 7 |
| Unique reached moves | 2 |
| Duplicate move credits | 5 |
| Raw triggered hit rate | 38.89% |
| **Unique-move adjusted hit rate** | **11.11%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 6 | `BTC-USDT-SWAP-LONG-1773360301000-1` | BTC-USDT-SWAP-LONG-1773360301000-1, BTC-USDT-SWAP-LONG-1773360324000-2, BTC-USDT-SWAP-LONG-1773362170000-4, BTC-USDT-SWAP-LONG-1773362182000-5, BTC-USDT-SWAP-LONG-1773395617000-9, BTC-USDT-SWAP-LONG-1773396407000-11 |
| 2 | SHORT | 1 | `BTC-USDT-SWAP-SHORT-1773408336000-22` | BTC-USDT-SWAP-SHORT-1773408336000-22 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10886**
- Suppressions by reason:
  - `active_open`: 7793
  - `active_triggered`: 3093

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
