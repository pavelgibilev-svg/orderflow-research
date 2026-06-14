# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-10
- **Replay duration:** 1544.6s
- **Rows processed:** L2=58 814 586  trades=1 033 973  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 14 |
| LONG / SHORT | 7 / 7 |
| Triggered | 8 |
| Reached target | 0 |
| Failed by timeout | 8 |
| Invalidated before trigger | 6 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 0 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 0.00% | 1200 |
| 8h | 0.00% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1778419619000-9 | SHORT | 2026-05-10T14:47:22.000Z | 80770.05 | 79154.65 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1778420175000-10 | LONG | 2026-05-10T15:04:10.000Z | 81044.95 | 82665.85 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778371211000-1 | SHORT | 2026-05-10T01:24:38.000Z | 80537.75 | 78926.99 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1778373266000-2 | LONG | 2026-05-10T03:05:01.000Z | 80790.65 | 82406.46 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1778382222000-5 | LONG | 2026-05-10T08:25:47.000Z | 80856.05 | 82473.17 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **13980**
- Suppressions by reason:
  - `active_open`: 9806
  - `active_triggered`: 4174

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
