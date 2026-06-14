# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-28
- **Replay duration:** 1703.1s
- **Rows processed:** L2=116 564 537  trades=3 962 260  other=1 132

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 15 |
| LONG / SHORT | 14 / 1 |
| Triggered | 7 |
| Reached target | 0 |
| Failed by timeout | 7 |
| Invalidated before trigger | 5 |
| Expired (formation aged out) | 1 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 15.90% | 1201 |
| 8h | 0.00% | 20.19% | 961 |
| 24h | 0.00% | 100.00% | 1 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-LONG-1779950053000-10 | LONG | 2026-05-28T06:45:23.000Z | 73824.60 | 75301.09 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779977136000-12 | LONG | 2026-05-28T14:13:06.000Z | 73797.40 | 75273.35 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779941042000-9 | LONG | 2026-05-28T14:16:03.000Z | 73964.35 | 75443.64 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779940611000-8 | LONG | 2026-05-28T14:16:24.000Z | 73999.20 | 75479.18 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779940393000-7 | LONG | 2026-05-28T14:16:54.000Z | 74013.75 | 75494.02 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **28540**
- Suppressions by reason:
  - `active_open`: 21831
  - `active_triggered`: 6709

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 86400 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
