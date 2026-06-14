# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-05-18
- **Replay duration:** 1498.8s
- **Rows processed:** L2=124 657 427  trades=4 311 454  other=271

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 24 |
| LONG / SHORT | 12 / 12 |
| Triggered | 13 |
| Reached target | 0 |
| Failed by timeout | 13 |
| Invalidated before trigger | 9 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 0.00% | 1.67% | 1200 |
| 8h | 0.00% | 2.08% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1779067908000-6 | SHORT | 2026-05-18T06:10:21.000Z | 76569.65 | 75038.26 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1779067611000-5 | SHORT | 2026-05-18T01:37:18.000Z | 76783.75 | 75248.07 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779068145000-7 | LONG | 2026-05-18T11:41:13.000Z | 77283.45 | 78829.12 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779118453000-19 | LONG | 2026-05-18T19:02:03.000Z | 76717.55 | 78251.90 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1779064698000-4 | LONG | 2026-05-18T01:56:27.000Z | 77098.95 | 78640.93 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **11069**
- Suppressions by reason:
  - `active_open`: 5648
  - `active_triggered`: 5421

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 4355 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
