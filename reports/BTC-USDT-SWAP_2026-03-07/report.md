# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2026-03-07
- **Replay duration:** 12429.0s
- **Rows processed:** L2=78 610 691  trades=2 315 049  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 27 |
| LONG / SHORT | 14 / 13 |
| Triggered | 18 |
| Reached target | 0 |
| Failed by timeout | 18 |
| Invalidated before trigger | 5 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 4 |
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
| BTC-USDT-SWAP-LONG-1772872211000-17 | LONG | 2026-03-07T09:16:09.000Z | 68022.45 | 69382.90 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1772852776000-6 | LONG | 2026-03-07T03:14:20.000Z | 68438.05 | 69806.81 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1772842770000-2 | SHORT | 2026-03-07T04:02:52.000Z | 68045.25 | 66684.35 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1772906920000-21 | SHORT | 2026-03-07T19:19:04.000Z | 67350.55 | 66003.54 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-SHORT-1772910598000-22 | SHORT | 2026-03-07T19:27:48.000Z | 67169.05 | 65825.67 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **16068**
- Suppressions by reason:
  - `active_open`: 7549
  - `active_triggered`: 8519

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
