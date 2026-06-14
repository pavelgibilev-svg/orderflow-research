# Orderflow L2 Strategy — Daily Report

- **Symbol:** BTC-USDT-SWAP
- **Exchange:** okex-swap
- **Date (UTC):** 2025-11-01
- **Replay duration:** 1730.0s
- **Rows processed:** L2=58 576 471  trades=1 022 504  other=0

## Zone summary

| Metric | Value |
|---|---|
| Total zones | 13 |
| LONG / SHORT | 7 / 6 |
| Triggered | 9 |
| Reached target | 0 |
| Failed by timeout | 9 |
| Invalidated before trigger | 2 |
| Expired (formation aged out) | 0 |
| No trigger by end of day | 2 |
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
| BTC-USDT-SWAP-SHORT-1761968377000-10 | SHORT | 2025-11-01T06:44:02.000Z | 109900.05 | 107702.05 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1761955801000-2 | LONG | 2025-11-01T00:51:04.000Z | 109688.85 | 111882.63 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1761971438000-11 | LONG | 2025-11-01T16:06:13.000Z | 110375.35 | 112582.86 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1761967572000-9 | LONG | 2025-11-01T03:42:14.000Z | 110163.95 | 112367.23 | RESOLVED_FAILED | - |
| BTC-USDT-SWAP-LONG-1761959626000-5 | LONG | 2025-11-01T01:29:18.000Z | 109839.95 | 112036.75 | RESOLVED_FAILED | - |

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
- Duplicate same-direction candidates suppressed during this run: **16077**
- Suppressions by reason:
  - `active_open`: 6343
  - `active_triggered`: 9734

> Deduplication is an **accounting fix** — it does not change any of the strategy thresholds in `config/strategy.default.json`. It only prevents the detector from emitting a second same-direction zone over the active price band of an existing one.

## Methodology recap

1. L2 events streamed from Tardis CSV gzip, never loaded fully into RAM.
2. Order book reconstructed level-by-level; snapshot rows reset state, amount=0 deletes the level.
3. Trades aggregated into rolling windows (5/15/60/300s by default) for buy/sell pressure.
4. Zones move through Candidate → Confirmed → Triggered. Failures kept in the report.
5. Target Checker scans forward from trigger time on 4h/8h/24h horizons looking for ±2% move.
