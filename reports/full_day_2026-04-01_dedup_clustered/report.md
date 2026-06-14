# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTCUSDT
- **Exchange:** binance-futures
- **Date (UTC):** 2026-04-01
- **Replay duration:** 2504.2s
- **Rows processed:** L2=124 963 429  trades=4 104 211  other=1 090

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 30 |
| LONG / SHORT | 16 / 14 |
| Triggered | 18 |
| Reached target | 0 |
| Failed by timeout | 18 |
| Invalidated before trigger | 10 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
| Hit rate among triggered | 0.00% |

> NOTE: hit rate is reported only over zones that actually triggered. Candidate / confirmed / expired zones are kept in zones.csv for honesty but are NOT counted in the hit rate.

## Unconditional baseline (price walk only, no zone signal)

| Horizon | Up rate | Down rate | Samples |
|---|---|---|---|
| 4h | 3.67% | 0.00% | 1200 |
| 8h | 12.08% | 0.00% | 960 |
| 24h | 0.00% | 0.00% | 0 |

> Compare zone hit rate against this baseline to see whether the signal adds anything.

## Top zones by absorption × void score

| ID | Dir | Trigger ts | Trigger px | Target px | Status | Reached horizon |
|---|---|---|---|---|---|---|
| BTCUSDT-SHORT-1775030073000-25 | SHORT | 2026-04-01T08:11:15.000Z | 68485.65 | 67115.94 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1775004964000-6 | SHORT | 2026-04-01T01:36:20.000Z | 67817.05 | 66460.71 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1775004555000-5 | SHORT | 2026-04-01T01:34:36.000Z | 67920.05 | 66561.65 | RESOLVED_FAILED | - |
| BTCUSDT-LONG-1775024990000-19 | LONG | 2026-04-01T06:34:16.000Z | 68934.05 | 70312.73 | RESOLVED_FAILED | - |
| BTCUSDT-SHORT-1775031459000-27 | SHORT | 2026-04-01T12:37:22.000Z | 68322.85 | 66956.39 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **11277**
- Suppressions by reason:
  - `active_open`: 5126
  - `active_triggered`: 6151

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
