# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-18
- **Replay duration:** 3284.3s
- **Rows processed:** L2=98 973 305  trades=3 574 518  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 19 |
| LONG / SHORT | 7 / 12 |
| Triggered | 12 |
| Reached target | 0 |
| Failed by timeout | 12 |
| Invalidated before trigger | 6 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 12.08% | 1200 |
| 8h | 0.00% | 19.38% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-LONG-1779066243000-4 | LONG | 2026-05-18T11:41:15.000Z | 77299.75 | 78845.74 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779067925000-5 | SHORT | 2026-05-18T02:53:41.000Z | 76685.15 | 75151.45 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1779084718000-6 | LONG | 2026-05-18T11:43:27.000Z | 77284.95 | 78830.65 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779114363000-14 | SHORT | 2026-05-18T14:34:23.000Z | 76315.45 | 74789.14 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1779108309000-11 | SHORT | 2026-05-18T13:31:17.000Z | 77227.45 | 75682.90 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **7524**
- Suppressions by reason:
  - `active_open`: 5388
  - `active_triggered`: 2136

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
