# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2025-09-01
- **Replay duration:** 7448.3s
- **Rows processed:** L2=153 002 082  trades=1 978 524  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 31 |
| LONG / SHORT | 10 / 21 |
| Triggered | 23 |
| Reached target | 0 |
| Failed by timeout | 23 |
| Invalidated before trigger | 7 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 7.50% | 0.00% | 1200 |
| 8h | 21.25% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1756701019000-11 | LONG | 2025-09-01T07:31:41.000Z | 108585.65 | 110757.36 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1756714019000-19 | LONG | 2025-09-01T09:33:13.000Z | 109844.05 | 112040.93 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1756741596000-28 | SHORT | 2025-09-01T17:11:58.000Z | 108530.05 | 106359.45 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1756728889000-27 | SHORT | 2025-09-01T15:24:02.000Z | 108677.45 | 106503.90 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1756712574000-18 | LONG | 2025-09-01T09:32:31.000Z | 109843.95 | 112040.83 | RESOLVED_FAILED | - |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 0 |
| Unique reached moves | 0 |
| Duplicate move credits | 0 |
| Raw triggered hit rate | 0.00% |
| **Unique-move adjusted hit rate** | **0.00%** |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **15048**
- Suppressions by reason:
  - `active_open`: 6340
  - `active_triggered`: 8705
  - `cooldown`: 3

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
