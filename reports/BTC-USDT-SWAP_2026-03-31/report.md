# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-31
- **Replay duration:** 4774.6s
- **Rows processed:** L2=132 062 724  trades=5 451 335  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 29 |
| LONG / SHORT | 12 / 17 |
| Triggered | 22 |
| Reached target | 7 |
| Failed by timeout | 15 |
| Invalidated before trigger | 6 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 31.82% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 23.33% | 12.17% | 1200 |
| 8h | 43.23% | 41.46% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1774915354000-1 | LONG | 2026-03-31T00:38:04.000Z | 66844.15 | 68181.03 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-SHORT-1774933202000-11 | SHORT | 2026-03-31T05:14:36.000Z | 67387.35 | 66039.60 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1774933245000-12 | SHORT | 2026-03-31T05:16:07.000Z | 67390.05 | 66042.25 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-LONG-1774988188000-27 | LONG | 2026-03-31T20:52:01.000Z | 68147.15 | 69510.09 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774946279000-16 | SHORT | 2026-03-31T09:15:09.000Z | 66625.05 | 65292.55 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 7 |
| Unique reached moves | 3 |
| Duplicate move credits | 4 |
| Raw triggered hit rate | 31.82% |
| **Unique-move adjusted hit rate** | **13.64%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | LONG | 2 | `BTC-USDT-SWAP-LONG-1774915354000-1` | BTC-USDT-SWAP-LONG-1774915354000-1, BTC-USDT-SWAP-LONG-1774916501000-3 |
| 2 | LONG | 1 | `BTC-USDT-SWAP-LONG-1774950763000-22` | BTC-USDT-SWAP-LONG-1774950763000-22 |
| 3 | SHORT | 4 | `BTC-USDT-SWAP-SHORT-1774922015000-9` | BTC-USDT-SWAP-SHORT-1774922015000-9, BTC-USDT-SWAP-SHORT-1774928879000-10, BTC-USDT-SWAP-SHORT-1774933202000-11, BTC-USDT-SWAP-SHORT-1774933245000-12 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **9852**
- Suppressions by reason:
  - `active_open`: 4673
  - `active_triggered`: 5179

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
