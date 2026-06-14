# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-05-11
- **Replay duration:** 2611.6s
- **Rows processed:** L2=83 908 626  trades=3 287 356  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 23 |
| LONG / SHORT | 11 / 12 |
| Triggered | 12 |
| Reached target | 0 |
| Failed by timeout | 12 |
| Invalidated before trigger | 8 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 6.00% | 3.75% | 1200 |
| 8h | 7.50% | 6.15% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTC-USDT-SWAP-SHORT-1778504003000-19 | SHORT | 2026-05-11T13:34:22.000Z | 80921.55 | 79303.12 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778459773000-4 | SHORT | 2026-05-11T00:52:57.000Z | 81315.05 | 79688.75 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1778500804000-18 | LONG | 2026-05-11T12:24:38.000Z | 81290.25 | 82916.06 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778458305000-2 | SHORT | 2026-05-11T00:52:58.000Z | 81331.65 | 79705.02 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1778466188000-9 | SHORT | 2026-05-11T03:07:20.000Z | 81020.85 | 79400.43 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **8348**
- Suppressions by reason:
  - `active_open`: 7589
  - `active_triggered`: 759

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 28800 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
