# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-27
- **Replay duration:** 3972.0s
- **Rows processed:** L2=115 017 887  trades=4 506 746  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 33 |
| LONG / SHORT | 20 / 13 |
| Triggered | 20 |
| Reached target | 9 |
| Failed by timeout | 11 |
| Invalidated before trigger | 10 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 45.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 20.08% | 1200 |
| 8h | 0.00% | 56.77% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1774594419000-13 | LONG | 2026-03-27T07:11:59.000Z | 68764.55 | 70139.84 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1774585514000-10 | LONG | 2026-03-27T05:12:19.000Z | 68694.35 | 70068.24 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1774571281000-3 | LONG | 2026-03-27T01:25:44.000Z | 68921.95 | 70300.39 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1774598331000-14 | SHORT | 2026-03-27T08:35:48.000Z | 67869.55 | 66512.16 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-LONG-1774570334000-1 | LONG | 2026-03-27T01:58:30.000Z | 68995.15 | 70375.05 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 9 |
| Unique reached moves | 1 |
| Duplicate move credits | 8 |
| Raw triggered hit rate | 45.00% |
| **Unique-move adjusted hit rate** | **5.00%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 9 | `BTC-USDT-SWAP-SHORT-1774570637000-2` | BTC-USDT-SWAP-SHORT-1774570637000-2, BTC-USDT-SWAP-SHORT-1774578177000-9, BTC-USDT-SWAP-SHORT-1774577539000-8, BTC-USDT-SWAP-SHORT-1774573301000-5, BTC-USDT-SWAP-SHORT-1774572338000-4, BTC-USDT-SWAP-SHORT-1774585870000-11, BTC-USDT-SWAP-SHORT-1774598331000-14, BTC-USDT-SWAP-SHORT-1774600484000-17, BTC-USDT-SWAP-SHORT-1774600392000-16 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **13062**
- Suppressions by reason:
  - `active_open`: 8162
  - `active_triggered`: 4900

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 1 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
