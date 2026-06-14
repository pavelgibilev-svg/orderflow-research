# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-03-01
- **Replay duration:** 2825.0s
- **Rows processed:** L2=139 795 935  trades=5 961 363  other=1 483

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 46 |
| LONG / SHORT | 25 / 21 |
| Triggered | 24 |
| Reached target | 8 |
| Failed by timeout | 16 |
| Invalidated before trigger | 21 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 1 |
| Hit rate among triggered | 33.33% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 7.50% | 10.83% | 1200 |
| 8h | 9.38% | 27.08% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1772330906000-10 | SHORT | 2026-03-01T16:49:24.000Z | 65919.75 | 64601.35 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1772384928000-36 | LONG | 2026-03-01T18:04:02.000Z | 66337.05 | 67663.79 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1772396271000-41 | LONG | 2026-03-01T22:13:09.000Z | 66556.75 | 67887.88 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1772396164000-40 | LONG | 2026-03-01T22:13:10.000Z | 66216.50 | 67540.83 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1772323262000-1 | SHORT | 2026-03-01T01:08:04.000Z | 66550.15 | 65219.15 | RESOLVED_REACHED | 24h |

## Move clustering accounting

Pure post-processing. Two RESOLVED_REACHED zones share a `uniqueMoveId` when they are the same direction and their `[triggerTs, reachedAt]` windows overlap or sit within `120` minutes of each other.

| Metric | Value |
|---|---|
| Move clustering enabled | yes |
| Reached zones (raw) | 8 |
| Unique reached moves | 1 |
| Duplicate move credits | 7 |
| Raw triggered hit rate | 33.33% |
| **Unique-move adjusted hit rate** | **4.17%** |

| Move | Dir | Size | Primary zone | Members |
|---|---|---|---|---|
| 1 | SHORT | 8 | `BTCUSDT-SHORT-1772323262000-1` | BTCUSDT-SHORT-1772323262000-1, BTCUSDT-SHORT-1772334048000-12, BTCUSDT-SHORT-1772336293000-14, BTCUSDT-SHORT-1772339107000-16, BTCUSDT-SHORT-1772340270000-18, BTCUSDT-SHORT-1772350918000-24, BTCUSDT-SHORT-1772356375000-28, BTCUSDT-SHORT-1772360989000-32 |

> The **unique-move-adjusted hit rate** is the honest headline number. The raw rate is kept only as a diagnostic — it counts every triggered zone that reached the target separately, even when several of them rode the same multi-hour directional move at progressively different price bands.

## Deduplication accounting

- Deduplication enabled: **yes**
- Cooldown after resolve: **30 min**
- Duplicate same-direction candidates suppressed during this run: **10825**
- Suppressions by reason:
  - `active_open`: 7262
  - `active_triggered`: 3464
  - `cooldown`: 99

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Warnings

- Encountered 1 feature ticks with quality flags.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
