# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2025-06-01
- **Replay duration:** 1337.8s
- **Rows processed:** L2=82 523 436  trades=1 959 946  other=635

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 36 |
| LONG / SHORT | 21 / 15 |
| Triggered | 19 |
| Reached target | 0 |
| Failed by timeout | 19 |
| Invalidated before trigger | 11 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 6 |
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
| BTCUSDT-LONG-1748813941000-29 | LONG | 2025-06-01T22:01:13.000Z | 105537.65 | 107648.40 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1748790610000-18 | LONG | 2025-06-01T16:05:47.000Z | 104859.05 | 106956.23 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1748771072000-15 | LONG | 2025-06-01T13:18:01.000Z | 104281.25 | 106366.88 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1748806865000-27 | LONG | 2025-06-01T20:40:21.000Z | 105217.45 | 107321.80 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1748796274000-23 | SHORT | 2025-06-01T18:03:34.000Z | 104848.25 | 102751.29 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **13369**
- Suppressions by reason:
  - `active_open`: 10718
  - `active_triggered`: 2651

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
