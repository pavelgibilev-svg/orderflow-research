# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-15
- **Replay duration:** 2650.5s
- **Rows processed:** L2=86 494 146  trades=3 885 236  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 21 |
| LONG / SHORT | 9 / 12 |
| Triggered | 13 |
| Reached target | 9 |
| Failed by timeout | 4 |
| Invalidated before trigger | 5 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 3 |
| Hit rate among triggered | 69.23% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 10.67% | 1200 |
| 8h | 0.00% | 13.33% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1778838340000-15 | SHORT | 2026-05-15T13:01:07.000Z | 80229.65 | 78625.06 | RESOLVED_REACHED | 4h |
| BTC-USDT-SWAP-LONG-1778804104000-2 | LONG | 2026-05-15T00:34:28.000Z | 81606.35 | 83238.48 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778812213000-10 | SHORT | 2026-05-15T05:00:18.000Z | 80619.05 | 79006.67 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-LONG-1778810204000-7 | LONG | 2026-05-15T02:52:01.000Z | 81261.35 | 82886.58 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778804554000-4 | SHORT | 2026-05-15T00:43:40.000Z | 81230.65 | 79606.04 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 9 |
| Unique reached moves | 1 |
| Duplicate move credits | 8 |
| Raw triggered hit rate | 69.23% |
| **Unique-move adjusted hit rate** | **7.69%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 9 | `BTC-USDT-SWAP-SHORT-1778804554000-4` | BTC-USDT-SWAP-SHORT-1778804554000-4, BTC-USDT-SWAP-SHORT-1778803317000-1, BTC-USDT-SWAP-SHORT-1778805492000-5, BTC-USDT-SWAP-SHORT-1778811800000-9, BTC-USDT-SWAP-SHORT-1778812213000-10, BTC-USDT-SWAP-SHORT-1778828865000-13, BTC-USDT-SWAP-SHORT-1778836619000-14, BTC-USDT-SWAP-SHORT-1778838340000-15, BTC-USDT-SWAP-SHORT-1778838611000-16 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **8392**
- Suppressions by reason:
  - `active_open`: 5980
  - `active_triggered`: 2412

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
