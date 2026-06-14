# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2025-08-01
- **Replay duration:** 7353.5s
- **Rows processed:** L2=150 683 894  trades=2 848 302  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 35 |
| LONG / SHORT | 15 / 20 |
| Triggered | 19 |
| Reached target | 3 |
| Failed by timeout | 16 |
| Invalidated before trigger | 12 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 4 |
| Hit rate among triggered | 15.79% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 2.17% | 1200 |
| 8h | 0.00% | 14.79% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1754030959000-12 | SHORT | 2025-08-01T07:13:55.000Z | 114848.75 | 112551.77 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1754007025000-2 | SHORT | 2025-08-01T00:49:57.000Z | 115190.15 | 112886.35 | RESOLVED_REACHED | 24h |
| BTC-USDT-SWAP-SHORT-1754079354000-33 | SHORT | 2025-08-01T22:34:07.000Z | 113045.15 | 110784.25 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1754051985000-19 | LONG | 2025-08-01T12:48:31.000Z | 115810.05 | 118126.25 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1754016775000-10 | SHORT | 2025-08-01T03:03:23.000Z | 115753.55 | 113438.48 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 3 |
| Unique reached moves | 1 |
| Duplicate move credits | 2 |
| Raw triggered hit rate | 15.79% |
| **Unique-move adjusted hit rate** | **5.26%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 3 | `BTC-USDT-SWAP-SHORT-1754006662000-1` | BTC-USDT-SWAP-SHORT-1754006662000-1, BTC-USDT-SWAP-SHORT-1754007025000-2, BTC-USDT-SWAP-SHORT-1754016775000-10 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10991**
- Suppressions by reason:
  - `active_open`: 7726
  - `active_triggered`: 3235
  - `cooldown`: 30

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
