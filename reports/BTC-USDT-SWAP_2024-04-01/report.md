# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2024-04-01
- **Replay duration:** 6210.6s
- **Rows processed:** L2=132 587 802  trades=1 160 425  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 38 |
| LONG / SHORT | 14 / 24 |
| Triggered | 22 |
| Reached target | 14 |
| Failed by timeout | 8 |
| Invalidated before trigger | 15 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 63.64% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 4.75% | 33.33% | 1200 |
| 8h | 2.19% | 75.31% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1711929631000-1 | SHORT | 2024-04-01T00:27:58.000Z | 71118.65 | 69696.28 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1711936206000-8 | SHORT | 2024-04-01T03:29:10.000Z | 70599.25 | 69187.26 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-SHORT-1711929700000-2 | SHORT | 2024-04-01T01:41:54.000Z | 70877.65 | 69460.10 | RESOLVED_REACHED | 8h |
| BTC-USDT-SWAP-SHORT-1711929775000-3 | SHORT | 2024-04-01T05:36:00.000Z | 70302.45 | 68896.40 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-SHORT-1711982677000-32 | SHORT | 2024-04-01T14:52:46.000Z | 68803.65 | 67427.58 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 14 |
| Unique reached moves | 1 |
| Duplicate move credits | 13 |
| Raw triggered hit rate | 63.64% |
| **Unique-move adjusted hit rate** | **4.55%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 14 | `BTC-USDT-SWAP-SHORT-1711929631000-1` | BTC-USDT-SWAP-SHORT-1711929631000-1, BTC-USDT-SWAP-SHORT-1711931566000-4, BTC-USDT-SWAP-SHORT-1711932369000-5, BTC-USDT-SWAP-SHORT-1711929700000-2, BTC-USDT-SWAP-SHORT-1711936306000-9, BTC-USDT-SWAP-SHORT-1711936206000-8, BTC-USDT-SWAP-SHORT-1711941804000-11, BTC-USDT-SWAP-SHORT-1711942930000-13, BTC-USDT-SWAP-SHORT-1711946176000-14, BTC-USDT-SWAP-SHORT-1711948532000-16, BTC-USDT-SWAP-SHORT-1711929775000-3, BTC-USDT-SWAP-SHORT-1711956443000-25, BTC-USDT-SWAP-SHORT-1711975964000-27, BTC-USDT-SWAP-SHORT-1711979320000-30 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **13178**
- Suppressions by reason:
  - `active_open`: 11195
  - `active_triggered`: 1983

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 4 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
